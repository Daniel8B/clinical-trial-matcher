"""
Parse raw ClinicalTrials.gov records into trial rows and chunk rows.

Pure transformation: no network, no embedding, no database. Import
parse_study() from ingest.py, or run this file directly to print the
distribution of what would be inserted.

Usage:
    python chunker.py
"""

import json
import re
from pathlib import Path

RAW_PATH = Path("data") / "raw_trials.json"

# Minimum characters for a criterion to be worth embedding. Below this it is
# a fragment ("Age >= 18") that carries almost no retrievable meaning.
MIN_CHUNK_CHARS = 30

# MiniLM truncates silently at 256 tokens (~1000 chars). Long free-text
# summaries get split rather than silently losing their tail.
MAX_CHUNK_CHARS = 900

INCLUSION_RE = re.compile(r"^\s*#*\s*inclusion\s+criteria\s*:?\s*$", re.I)
EXCLUSION_RE = re.compile(r"^\s*#*\s*exclusion\s+criteria\s*:?\s*$", re.I)
BULLET_RE = re.compile(r"^\s*[\*\-\u2022]\s+")
NUMBERED_RE = re.compile(r"^\s*\d+[\.\)]\s+")


def clean(text: str) -> str:
    """Undo markdown escaping and normalise whitespace."""
    if not text:
        return ""
    # ClinicalTrials.gov escapes markdown specials: \> \< \[ \* \_ etc.
    text = re.sub(r"\\([><\[\]\*_#`])", r"\1", text)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def parse_age_years(raw: str | None) -> int | None:
    """'18 Years' -> 18. '6 Months' -> 0. '90 Days' -> 0. None/junk -> None."""
    if not raw:
        return None
    match = re.match(r"\s*(\d+)\s*(\w+)", raw)
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2).lower()
    if unit.startswith("year"):
        return value
    if unit.startswith("month"):
        return value // 12
    if unit.startswith("week"):
        return value // 52
    if unit.startswith("day"):
        return value // 365
    if unit.startswith("hour") or unit.startswith("minute"):
        return 0
    return None


def split_long(text: str) -> list[str]:
    """Split text exceeding MAX_CHUNK_CHARS on sentence boundaries."""
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    parts, current = [], ""
    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > MAX_CHUNK_CHARS:
            parts.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current.strip():
        parts.append(current.strip())
    # A single sentence can exceed the cap with no boundary to split on.
    # MiniLM truncates at 256 tokens silently, so hard-cut rather than
    # let the tail vanish with no error.
    capped: list[str] = []
    for part in parts:
        while len(part) > MAX_CHUNK_CHARS:
            capped.append(part[:MAX_CHUNK_CHARS])
            part = part[MAX_CHUNK_CHARS:]
        if part.strip():
            capped.append(part.strip())
    return capped


def split_criteria(raw: str) -> tuple[list[str], list[str]]:
    """
    Split eligibilityCriteria into (inclusion, exclusion) criterion lists.

    Walks line by line tracking which section header was seen last. Bullets
    and numbered items become individual criteria; unmarked prose lines are
    accumulated as a single criterion each.
    """
    inclusion: list[str] = []
    exclusion: list[str] = []
    section = "inclusion"  # criteria before any header are inclusion by convention

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if INCLUSION_RE.match(stripped):
            section = "inclusion"
            continue
        if EXCLUSION_RE.match(stripped):
            section = "exclusion"
            continue

        item = BULLET_RE.sub("", stripped)
        item = NUMBERED_RE.sub("", item)
        item = clean(item)
        if not item:
            continue

        target = inclusion if section == "inclusion" else exclusion
        target.append(item)

    return inclusion, exclusion


def parse_study(study: dict) -> tuple[dict, list[dict]] | None:
    """
    Turn one raw API record into (trial_row, chunk_rows).

    Returns None if the record has no NCT id — nothing downstream can key on it.
    """
    protocol = study.get("protocolSection", {})
    ident = protocol.get("identificationModule", {})
    status = protocol.get("statusModule", {})
    design = protocol.get("designModule", {})
    conds = protocol.get("conditionsModule", {})
    elig = protocol.get("eligibilityModule", {})
    desc = protocol.get("descriptionModule", {})

    nct_id = ident.get("nctId")
    if not nct_id:
        return None

    trial = {
        "nct_id": nct_id,
        "brief_title": clean(ident.get("briefTitle") or ident.get("officialTitle") or ""),
        "overall_status": status.get("overallStatus"),
        "phases": design.get("phases") or [],
        "study_type": design.get("studyType"),
        "conditions": conds.get("conditions") or [],
        "sex": elig.get("sex"),
        "min_age_years": parse_age_years(elig.get("minimumAge")),
        "max_age_years": parse_age_years(elig.get("maximumAge")),
        "enrollment": (design.get("enrollmentInfo") or {}).get("count"),
    }

    chunks: list[dict] = []

    def add(section: str, text: str) -> None:
        for part in split_long(text):
            if len(part) < MIN_CHUNK_CHARS:
                continue
            chunks.append(
                {
                    "nct_id": nct_id,
                    "section": section,
                    "chunk_index": len(chunks),
                    "chunk_text": part,
                }
            )

    summary = clean(desc.get("briefSummary") or "")
    if summary:
        add("brief_summary", summary)

    inclusion, exclusion = split_criteria(elig.get("eligibilityCriteria") or "")
    for criterion in inclusion:
        add("inclusion", criterion)
    for criterion in exclusion:
        add("exclusion", criterion)

    return trial, chunks


def main() -> None:
    with open(RAW_PATH, encoding="utf-8") as f:
        studies = json.load(f)

    trials, all_chunks, skipped = [], [], 0
    for study in studies:
        parsed = parse_study(study)
        if parsed is None:
            skipped += 1
            continue
        trial, chunks = parsed
        trials.append(trial)
        all_chunks.extend(chunks)

    per_trial = {}
    for chunk in all_chunks:
        per_trial[chunk["nct_id"]] = per_trial.get(chunk["nct_id"], 0) + 1
    counts = sorted(per_trial.values())
    lengths = sorted(len(c["chunk_text"]) for c in all_chunks)

    sections = {}
    for chunk in all_chunks:
        sections[chunk["section"]] = sections.get(chunk["section"], 0) + 1

    def pct(values, p):
        return values[int(len(values) * p)] if values else 0

    print(f"studies read        : {len(studies)}")
    print(f"trials parsed       : {len(trials)}")
    print(f"skipped (no nct_id) : {skipped}")
    print(f"trials with 0 chunks: {len(trials) - len(per_trial)}")
    print(f"total chunks        : {len(all_chunks)}")
    print()
    print("chunks per trial    : min %d  median %d  p95 %d  max %d"
          % (counts[0], pct(counts, 0.5), pct(counts, 0.95), counts[-1]) if counts else "no chunks")
    print("chunk chars         : min %d  median %d  p95 %d  max %d"
          % (lengths[0], pct(lengths, 0.5), pct(lengths, 0.95), lengths[-1]) if lengths else "")
    print()
    print("by section          :", sections)
    print()
    print("--- sample trial row ---")
    print(json.dumps(trials[0], indent=2, ensure_ascii=False))
    print()
    print("--- 3 sample chunks from that trial ---")
    for chunk in [c for c in all_chunks if c["nct_id"] == trials[0]["nct_id"]][:3]:
        print(f"[{chunk['section']} #{chunk['chunk_index']}] {chunk['chunk_text'][:200]}")


if __name__ == "__main__":
    main()