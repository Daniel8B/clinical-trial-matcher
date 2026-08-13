"""Grounded answer generation over retrieved chunks."""

from __future__ import annotations

import re

from clinical_trial_matcher.llm import LLMClient

MAX_EVIDENCE = 5
MAX_CHUNK_CHARS = 400

# UNCALIBRATED. Cross-encoder logits are unbounded; observed 1.57-5.74 on a
# single query (Week 3 Day 1). Calibrate against the Day 3 golden set.
MIN_SCORE = 2.0

SYSTEM_PROMPT = (
    "You answer questions about clinical trials using only the numbered evidence "
    "given to you.\n"
    "Rules:\n"
    "1. Use only the evidence. Do not add facts from your own knowledge.\n"
    "2. Cite every claim with the bracket number of its evidence item, like [2].\n"
    "3. Evidence marked 'exclusion' lists who CANNOT join the trial. Never present "
    "an exclusion criterion as a reason a patient qualifies.\n"
    "4. If the evidence does not answer the question, say so.\n"
    "5. Be brief. Do not recommend treatment or decide eligibility."
)

CITATION_PATTERN = re.compile(r"\[(\d+)\]")


def build_evidence(results: list[dict]) -> list[dict]:
    """Take the top results, truncate them, and give each a citation number."""
    evidence = []
    for number, result in enumerate(results[:MAX_EVIDENCE], start=1):
        evidence.append(
            {
                "number": number,
                "nct_id": result["nct_id"],
                "brief_title": result["brief_title"],
                "section": result["section"],
                "text": result["chunk_text"][:MAX_CHUNK_CHARS],
            }
        )
    return evidence


def format_prompt(query: str, evidence: list[dict]) -> str:
    """The user message: the evidence block, then the question."""
    blocks = [
        f"[{item['number']}] Trial {item['nct_id']} ({item['section']}): {item['text']}"
        for item in evidence
    ]
    return "Evidence:\n" + "\n\n".join(blocks) + f"\n\nQuestion: {query}"


def extract_citations(answer: str, evidence: list[dict]) -> list[int]:
    """Citation numbers the model emitted that actually exist in the evidence."""
    valid = {item["number"] for item in evidence}
    cited = {int(n) for n in CITATION_PATTERN.findall(answer)}
    return sorted(cited & valid)


def generate_answer(client: LLMClient, query: str, results: list[dict], max_tokens: int) -> dict:
    """Answer the query from the results. Never invents prose when it cannot."""
    if not results or results[0]["score"] < MIN_SCORE:
        return {
            "answer": None,
            "citations": [],
            "evidence": build_evidence(results),
            "generation_available": True,
            "reason": "no_good_match",
        }

    if not client.is_available():
        return {
            "answer": None,
            "citations": [],
            "evidence": build_evidence(results),
            "generation_available": False,
            "reason": "llm_unavailable",
        }

    evidence = build_evidence(results)
    answer = client.complete(
        system=SYSTEM_PROMPT,
        user=format_prompt(query, evidence),
        max_tokens=max_tokens,
    )
    return {
        "answer": answer,
        "citations": extract_citations(answer, evidence),
        "evidence": evidence,
        "generation_available": True,
        "reason": None,
    }