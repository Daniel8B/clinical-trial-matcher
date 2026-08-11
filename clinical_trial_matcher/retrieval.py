"""Retrieval arms and fusion. Pure functions — main.py composes them.

Kept out of main.py so the Week 3 Day 3 eval harness can call each arm
in-process without going over HTTP.
"""

import re

DENSE_LIMIT = 100
LEXICAL_LIMIT = 100
RERANK_TOP = 20
EF_SEARCH = 200
RRF_K = 60

DENSE_SQL = """
SELECT id, nct_id, section, chunk_text, -(embedding <#> %s::vector) AS score
FROM chunks
ORDER BY embedding <#> %s::vector ASC
LIMIT %s
"""

# No GIN index: measured 87ms indexed vs 32ms sequential at 33k chunks.
# ts_rank_cd must score every matching row regardless, and at ~12% corpus
# match rate random heap access loses to a sequential read.
#
# Normalisation flag 2 divides the rank by document length. Without it,
# ts_rank_cd has no length normalisation at all (this is the concrete gap
# between it and BM25) and long brief_summary chunks dominate every query
# simply by containing more term occurrences.
LEXICAL_SQL = """
SELECT id, nct_id, section, chunk_text,
       ts_rank_cd(tsv, to_tsquery('english', %s), 2) AS score
FROM chunks
WHERE tsv @@ to_tsquery('english', %s)
ORDER BY score DESC
LIMIT %s
"""

TITLE_SQL = "SELECT nct_id, brief_title FROM trials WHERE nct_id = ANY(%s)"


def build_tsquery(query: str) -> str:
    """Query text -> OR-joined tsquery string.

    plainto_tsquery joins terms with AND: 'type 2 diabetes elderly' matched
    1 chunk of 32,949. OR matched 3,966. Ranking, not filtering, is what
    selects the good ones.

    Non-alphanumerics are stripped rather than escaped — to_tsquery treats
    &, |, !, ( ) as operators and raises a syntax error on stray ones.
    """
    terms = re.findall(r"[A-Za-z0-9]+", query)
    return " | ".join(terms)


def _rows_to_dicts(rows):
    return [
        {
            "id": r[0],
            "nct_id": r[1],
            "section": r[2],
            "chunk_text": r[3],
            "score": float(r[4]),
        }
        for r in rows
    ]


def dense_search(cur, query_vector: list[float], limit: int = DENSE_LIMIT):
    cur.execute("SELECT set_config('hnsw.ef_search', %s, true)", (str(EF_SEARCH),))
    cur.execute(DENSE_SQL, (query_vector, query_vector, limit))
    return _rows_to_dicts(cur.fetchall())


def lexical_search(cur, query: str, limit: int = LEXICAL_LIMIT):
    tsquery = build_tsquery(query)
    if not tsquery:
        return []
    cur.execute(LEXICAL_SQL, (tsquery, tsquery, limit))
    return _rows_to_dicts(cur.fetchall())


def rrf_fuse(rankings: list[list[int]], k: int = RRF_K) -> list[tuple[int, float]]:
    """Reciprocal rank fusion over ranked lists of chunk ids.

    Scores are discarded, positions kept: cosine (0-1) and ts_rank_cd
    (unbounded, different scale) cannot be added meaningfully. Rank 1 is the
    best position; k flattens the curve so appearing in both lists beats
    topping one.
    """
    scores: dict[int, float] = {}
    for ranking in rankings:
        for position, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + position)
    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)


def rerank(cross_encoder, query: str, chunks: list[dict]) -> list[dict]:
    """Cross-encoder rescoring. Overwrites 'score' with the CE score.

    Measured 10.7ms/pair on CPU, linear in candidate count. Bi-encoders embed
    query and chunk independently; a cross-encoder reads them jointly, which
    is the only mechanism here that could represent polarity.
    """
    if not chunks:
        return []
    pairs = [(query, c["chunk_text"]) for c in chunks]
    scores = cross_encoder.predict(pairs)
    for chunk, score in zip(chunks, scores):
        chunk["score"] = float(score)
    return sorted(chunks, key=lambda c: c["score"], reverse=True)


def dedupe_to_trials(chunks: list[dict], top_k: int) -> list[dict]:
    """Max-over-chunks: a trial's rank is its best chunk's rank.

    Input must already be sorted best-first — the first chunk seen for a trial
    is therefore its best. One strongly matching criterion is enough to surface
    a trial, which is correct for a proposer.
    """
    seen = set()
    out = []
    for chunk in chunks:
        if chunk["nct_id"] in seen:
            continue
        seen.add(chunk["nct_id"])
        out.append(chunk)
        if len(out) == top_k:
            break
    return out


def attach_titles(cur, results: list[dict]) -> list[dict]:
    if not results:
        return []
    nct_ids = [r["nct_id"] for r in results]
    cur.execute(TITLE_SQL, (nct_ids,))
    titles = dict(cur.fetchall())
    for r in results:
        r["brief_title"] = titles.get(r["nct_id"], "")
    return results


def search(
    cur,
    embedder,
    cross_encoder,
    query: str,
    top_k: int = 5,
    use_lexical: bool = True,
    use_rerank: bool = True,
) -> list[dict]:
    """Full pipeline. Flags are for the Day 3 ablation, not the public API."""
    query_vector = embedder.encode(query).tolist()
    dense = dense_search(cur, query_vector)

    if use_lexical:
        lexical = lexical_search(cur, query)
        by_id = {c["id"]: c for c in dense + lexical}
        fused = rrf_fuse([[c["id"] for c in dense], [c["id"] for c in lexical]])
        candidates = [by_id[cid] for cid, _ in fused]
        for chunk, (_, rrf_score) in zip(candidates, fused):
            chunk["score"] = rrf_score
    else:
        candidates = dense

    if use_rerank:
        candidates = rerank(cross_encoder, query, candidates[:RERANK_TOP])

    return attach_titles(cur, dedupe_to_trials(candidates, top_k))