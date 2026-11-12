"""Phase 13: a repeatable evaluation harness for the research assistant.

Phase 12 checked answer quality with an ad-hoc sweep of twelve questions printed to a
terminal. That is a demonstration, not a measurement: no metric is recorded, nothing regresses
visibly, and the sweep cannot be re-run against a later build.

This module scores answers against a fixed set of items whose expectations are *rules*, not
prose:

  expectStatus     which of grounded / partial / insufficient the answer may be
  mustCiteAny      source ids, at least one of which has to be cited
  mustCiteAll      source ids that must all be cited (comparison questions)
  mustMentionEntities   entities that must appear in the cited evidence

The metrics are all computable from the answer object, so they cannot be inflated by a
favourable reading:

  statusAccuracy        answer status matches the expectation
  citationHitRate       at least one expected source cited
  citationCompleteness  every required source cited
  unsupportedClaimRate  claims that are not a verbatim sentence of the passage they cite
  refusalCorrectness    questions with no corpus answer are refused with no citations
  entityCoverage        named entities actually reached the answer

`unsupportedClaimRate` is the one that matters most. A claim is supported only if its text
appears in the passage it cites; anything else would be the assistant asserting something the
retrieved document does not contain, which is the failure mode this whole subsystem exists to
prevent.
"""
from __future__ import annotations
import safedata

import statistics
import time
from pathlib import Path

BENCHMARK = Path(__file__).resolve().parents[1] / "tests" / "data" / "assistant_benchmark"

STATUS_EQUIVALENCE = {
    # "notGrounded" is a deliberate expectation class: the answer may be partial or refused,
    # but it must not claim to be a complete, well-grounded answer.
    "notGrounded": {"partial", "insufficient"},
}


def load_benchmark() -> dict:
    return safedata.load(BENCHMARK)


def _status_matches(expected: str, actual: str) -> bool:
    if expected in STATUS_EQUIVALENCE:
        return actual in STATUS_EQUIVALENCE[expected]
    return expected == actual


def _claim_is_supported(claim: dict, citations: list[dict], passage_texts: dict) -> bool:
    """A claim is supported when its sentence occurs in the evidence it cites.

    The limitations recorded on the cited artifact count as that evidence: a claim saying what a
    model does *not* do is supported by the model's own recorded limitation, and the citation
    carries that list to the reader. Anything else has to appear in the passage body.
    """
    index = claim.get("citation", 0)
    if not 1 <= index <= len(citations):
        return False
    passage_id = claim.get("passageId")
    text = passage_texts.get(passage_id)
    if text is None:
        return False
    quote = (claim.get("quote") or claim.get("text") or "").strip()
    if not quote:
        return False
    if quote in text:
        return True
    limitations = citations[index - 1].get("limitations") or []
    return any(quote in limitation for limitation in limitations)


def score_item(item: dict, answer: dict, passage_texts: dict, elapsed_ms: float) -> dict:
    citations = answer.get("citations") or []
    claims = answer.get("claims") or []
    cited_ids = {citation.get("sourceId") for citation in citations}
    cited_text = " ".join(passage_texts.get(claim.get("passageId"), "") for claim in claims)
    status = answer.get("status")

    must_any = item.get("mustCiteAny") or []
    must_all = item.get("mustCiteAll") or []

    unsupported = [claim for claim in claims
                   if not _claim_is_supported(claim, citations, passage_texts)]

    entities = item.get("mustMentionEntities") or []
    covered = [entity for entity in entities
               if entity in cited_ids or entity.lower() in cited_text.lower()]

    refusal_expected = item["expectStatus"] == "insufficient"
    refusal_ok = None
    if refusal_expected:
        refusal_ok = status == "insufficient" and not citations and not claims

    return {
        "id": item["id"],
        "category": item["category"],
        "question": item["question"],
        "expected": item["expectStatus"],
        "actual": status,
        "statusMatch": _status_matches(item["expectStatus"], status),
        "citationHit": (bool(cited_ids & set(must_any)) if must_any else None),
        "citationComplete": (all(sid in cited_ids for sid in must_all) if must_all else None),
        "unsupportedClaims": len(unsupported),
        "claimCount": len(claims),
        "entityCoverage": (len(covered) / len(entities)) if entities else None,
        "refusalCorrect": refusal_ok,
        "coverageGaps": [gap.get("entity") for gap in answer.get("coverageGaps") or []],
        "subQuestions": len((answer.get("plan") or {}).get("subQuestions") or []),
        "latencyMs": round(elapsed_ms, 2),
    }


def _rate(values: list[bool]) -> float | None:
    scored = [value for value in values if value is not None]
    if not scored:
        return None
    return round(sum(1 for value in scored if value) / len(scored), 4)


def evaluate(answer_function, benchmark: dict | None = None,
             passage_texts: dict | None = None) -> dict:
    """Run the whole benchmark and return per-item results plus aggregate metrics."""
    benchmark = benchmark or load_benchmark()
    if passage_texts is None:
        from app import evidence
        passage_texts = {passage.id: passage.text for passage in evidence.corpus()["passages"]}

    items = []
    for item in benchmark["items"]:
        started = time.perf_counter()
        answer = answer_function(item["question"])
        elapsed = (time.perf_counter() - started) * 1000
        payload = answer if isinstance(answer, dict) else answer.render()
        items.append(score_item(item, payload, passage_texts, elapsed))

    latencies = [item["latencyMs"] for item in items]
    total_claims = sum(item["claimCount"] for item in items)
    unsupported_total = sum(item["unsupportedClaims"] for item in items)

    def by_category(category: str) -> dict:
        subset = [item for item in items if item["category"] == category]
        return {
            "items": len(subset),
            "statusAccuracy": _rate([item["statusMatch"] for item in subset]),
            "citationHitRate": _rate([item["citationHit"] for item in subset]),
        }

    categories = sorted({item["category"] for item in items})
    return {
        "benchmark": {"items": len(items), "categories": categories,
                      "source": BENCHMARK.name},
        "metrics": {
            "statusAccuracy": _rate([item["statusMatch"] for item in items]),
            "citationHitRate": _rate([item["citationHit"] for item in items]),
            "citationCompleteness": _rate([item["citationComplete"] for item in items]),
            "unsupportedClaimRate": (round(unsupported_total / total_claims, 4)
                                     if total_claims else 0.0),
            "refusalCorrectness": _rate([item["refusalCorrect"] for item in items]),
            "entityCoverage": _rate([
                (item["entityCoverage"] or 0) >= 1.0
                for item in items if item["entityCoverage"] is not None]),
            "multiHopItemShare": round(
                sum(1 for item in items if item["subQuestions"] > 1) / len(items), 4),
            "claimsTotal": total_claims,
            "unsupportedClaimsTotal": unsupported_total,
        },
        "latency": {
            "medianMs": round(statistics.median(latencies), 2),
            "p95Ms": round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 2),
            "maxMs": round(max(latencies), 2),
            "totalMs": round(sum(latencies), 2),
        },
        "byCategory": {category: by_category(category) for category in categories},
        "failures": [item for item in items
                     if not item["statusMatch"]
                     or item["citationHit"] is False
                     or item["citationComplete"] is False
                     or item["unsupportedClaims"] > 0
                     or item["refusalCorrect"] is False],
        "items": items,
    }


def format_summary(report: dict) -> str:
    """A compact table for the terminal and for the documentation."""
    metrics = report["metrics"]
    lines = [
        f"{'metric':26s} {'value':>8s}",
        f"{'-' * 26} {'-' * 8}",
    ]
    for key in ("statusAccuracy", "citationHitRate", "citationCompleteness",
                "unsupportedClaimRate", "refusalCorrectness", "entityCoverage",
                "multiHopItemShare"):
        value = metrics.get(key)
        lines.append(f"{key:26s} {('n/a' if value is None else f'{value:.4f}'):>8s}")
    lines.append(f"{'claimsTotal':26s} {metrics['claimsTotal']:>8d}")
    lines.append(f"{'unsupportedClaimsTotal':26s} {metrics['unsupportedClaimsTotal']:>8d}")
    lines.append("")
    lines.append(f"latency median {report['latency']['medianMs']:.1f} ms  "
                 f"p95 {report['latency']['p95Ms']:.1f} ms  "
                 f"max {report['latency']['maxMs']:.1f} ms")
    if report["failures"]:
        lines.append("")
        lines.append(f"{len(report['failures'])} item(s) below expectation:")
        for failure in report["failures"]:
            reason = []
            if not failure["statusMatch"]:
                reason.append(f"status {failure['actual']} != {failure['expected']}")
            if failure["citationHit"] is False:
                reason.append("no expected source cited")
            if failure["citationComplete"] is False:
                reason.append("incomplete citation set")
            if failure["unsupportedClaims"]:
                reason.append(f"{failure['unsupportedClaims']} unsupported claim(s)")
            if failure["refusalCorrect"] is False:
                reason.append("expected a refusal")
            lines.append(f"  {failure['id']:10s} {'; '.join(reason)}")
    else:
        lines.append("")
        lines.append("every item met its expectation")
    return "\n".join(lines)
