"""
Pull raw study records from ClinicalTrials.gov API v2.

Writes data/raw_trials.json. Does no parsing, chunking, or embedding:
network I/O is separated from transformation so the chunker can be
re-run without re-fetching.

Usage:
    python fetch_trials.py
    python fetch_trials.py --per-condition 500
"""

import argparse
import json
import time
from pathlib import Path

import requests

API_URL = "https://clinicaltrials.gov/api/v2/studies"

CONDITIONS = ["cancer", "diabetes", "cardiovascular disease"]

# Whole modules, not leaf fields. More forgiving against spec drift, and
# these five carry everything the schema needs.
FIELDS = ",".join(
    [
        "protocolSection.identificationModule",
        "protocolSection.statusModule",
        "protocolSection.designModule",
        "protocolSection.conditionsModule",
        "protocolSection.eligibilityModule",
        "protocolSection.descriptionModule",
    ]
)

PAGE_SIZE = 100
OUTPUT_PATH = Path("data") / "raw_trials.json"


def fetch_condition(condition: str, target: int) -> list[dict]:
    """Page through the API for one condition until `target` studies collected."""
    collected: list[dict] = []
    page_token: str | None = None
    page_num = 0

    while len(collected) < target:
        params = {
            "query.cond": condition,
            "filter.overallStatus": "RECRUITING",
            "fields": FIELDS,
            "pageSize": min(PAGE_SIZE, target - len(collected)),
            "countTotal": "true",
        }
        if page_token:
            params["pageToken"] = page_token

        response = requests.get(API_URL, params=params, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(
                f"API returned {response.status_code} for '{condition}'.\n"
                f"URL: {response.url}\n"
                f"Body: {response.text[:500]}"
            )

        payload = response.json()
        studies = payload.get("studies", [])
        if not studies:
            print(f"  '{condition}': no more studies at page {page_num}")
            break

        collected.extend(studies)
        page_num += 1
        print(f"  '{condition}': page {page_num}, {len(collected)} collected")

        page_token = payload.get("nextPageToken")
        if not page_token:
            break

        time.sleep(0.3)  # deliberate politeness; public unauthenticated API

    return collected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--per-condition",
        type=int,
        default=700,
        help="studies to fetch per condition (default 700 -> ~2100 total)",
    )
    args = parser.parse_args()

    all_studies: list[dict] = []
    for condition in CONDITIONS:
        print(f"Fetching '{condition}'...")
        all_studies.extend(fetch_condition(condition, args.per_condition))

    # A study can match more than one condition query. Dedupe on NCT id,
    # keeping first occurrence.
    seen: set[str] = set()
    deduped: list[dict] = []
    for study in all_studies:
        try:
            nct_id = study["protocolSection"]["identificationModule"]["nctId"]
        except KeyError:
            continue
        if nct_id in seen:
            continue
        seen.add(nct_id)
        deduped.append(study)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(deduped, f, ensure_ascii=False)

    print()
    print(f"Fetched      : {len(all_studies)}")
    print(f"After dedupe : {len(deduped)}")
    print(f"Written to   : {OUTPUT_PATH}")

    if deduped:
        first = deduped[0]
        print()
        print("Top-level keys of record 0 :", list(first.keys()))
        print("protocolSection modules    :", list(first["protocolSection"].keys()))
        elig = first["protocolSection"].get("eligibilityModule", {})
        print("eligibilityModule keys     :", list(elig.keys()))
        criteria = elig.get("eligibilityCriteria", "")
        print(f"eligibilityCriteria length : {len(criteria)} chars")
        print("--- first 400 chars of eligibilityCriteria ---")
        print(criteria[:400])


if __name__ == "__main__":
    main()