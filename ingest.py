"""
Load ClinicalTrials.gov records into Postgres with embeddings.

Reads data/raw_trials.json, parses via chunker.parse_study, embeds every
chunk, and reloads both tables. Destructive by design: DROP + CREATE, so
the schema lives in git rather than only in a Docker volume.

Usage:
    python ingest.py
    python ingest.py --no-index      # skip HNSW, for latency comparison
"""

import argparse
import json
import time
from pathlib import Path

import psycopg
from sentence_transformers import SentenceTransformer

from chunker import parse_study
from clinical_trial_matcher.config import settings

RAW_PATH = Path("data") / "raw_trials.json"
BATCH_SIZE = 256

SCHEMA_SQL = """
DROP TABLE IF EXISTS chunks;
DROP TABLE IF EXISTS trials;

CREATE TABLE trials (
    nct_id         TEXT PRIMARY KEY,
    brief_title    TEXT NOT NULL,
    overall_status TEXT,
    phases         TEXT[],
    study_type     TEXT,
    conditions     TEXT[],
    sex            TEXT,
    min_age_years  INTEGER,
    max_age_years  INTEGER,
    enrollment     INTEGER,
    ingested_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chunks (
    id          BIGSERIAL PRIMARY KEY,
    nct_id      TEXT NOT NULL REFERENCES trials(nct_id) ON DELETE CASCADE,
    section     TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_text  TEXT NOT NULL,
    embedding   vector(384) NOT NULL
);

CREATE INDEX chunks_nct_id_idx ON chunks (nct_id);
CREATE INDEX trials_conditions_idx ON trials USING GIN (conditions);
"""

# vector_ip_ops matches the <#> operator used in /search. An index built for
# a different operator class is silently ignored by the planner.
INDEX_SQL = """
CREATE INDEX chunks_embedding_idx ON chunks
USING hnsw (embedding vector_ip_ops)
WITH (m = 16, ef_construction = 64);
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-index", action="store_true", help="skip HNSW build")
    args = parser.parse_args()

    with open(RAW_PATH, encoding="utf-8") as f:
        studies = json.load(f)

    trials, chunks = [], []
    for study in studies:
        parsed = parse_study(study)
        if parsed is None:
            continue
        trial, trial_chunks = parsed
        trials.append(trial)
        chunks.extend(trial_chunks)

    print(f"parsed: {len(trials)} trials, {len(chunks)} chunks")

    embedder = SentenceTransformer(settings.embedding_model_name)
    device = embedder.device
    print(f"embedding on: {device}")

    t0 = time.perf_counter()
    vectors = embedder.encode(
        [c["chunk_text"] for c in chunks],
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        convert_to_numpy=True,
    )
    embed_seconds = time.perf_counter() - t0
    print(f"embedded {len(vectors)} chunks in {embed_seconds:.1f}s "
          f"({len(vectors) / embed_seconds:.0f}/s)")

    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)

            t0 = time.perf_counter()
            cur.executemany(
                "INSERT INTO trials (nct_id, brief_title, overall_status, phases, "
                "study_type, conditions, sex, min_age_years, max_age_years, enrollment) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    (
                        t["nct_id"], t["brief_title"], t["overall_status"],
                        t["phases"], t["study_type"], t["conditions"], t["sex"],
                        t["min_age_years"], t["max_age_years"], t["enrollment"],
                    )
                    for t in trials
                ],
            )
            print(f"inserted trials in {time.perf_counter() - t0:.1f}s")

            t0 = time.perf_counter()
            cur.executemany(
                "INSERT INTO chunks (nct_id, section, chunk_index, chunk_text, embedding) "
                "VALUES (%s, %s, %s, %s, %s::vector)",
                [
                    (c["nct_id"], c["section"], c["chunk_index"],
                     c["chunk_text"], vectors[i].tolist())
                    for i, c in enumerate(chunks)
                ],
            )
            print(f"inserted chunks in {time.perf_counter() - t0:.1f}s")

            if args.no_index:
                print("HNSW index: SKIPPED (--no-index)")
            else:
                t0 = time.perf_counter()
                cur.execute(INDEX_SQL)
                print(f"HNSW index built in {time.perf_counter() - t0:.1f}s")

    print("done")


if __name__ == "__main__":
    main()