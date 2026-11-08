"""Phase 13: query decomposition and multi-hop evidence planning.

The Phase 12 assistant issued exactly one retrieval query per question. That is enough for
"what does the OSD-46 classifier predict" and wrong for everything comparative. Ask it to
compare OSD-314 with OSD-346 and BM25 returns whichever accession better matches the shared
vocabulary, because the second accession is never queried on its own terms. The answer then
looks complete while covering one side of the question.

This module turns a question into an explicit plan before any retrieval happens:

    "Compare the findings of OSD-314 and OSD-346"
      -> primary    : compare the findings of OSD-314 and OSD-346
      -> entity     : OSD-314      (retrieved on its own)
      -> entity     : OSD-346      (retrieved on its own)

    "Why did the gravity model fail and what evidence would validate it"
      -> primary    : why did the gravity model fail
      -> follow-up  : what evidence would validate the gravity model

The plan is data, and it is returned to the caller, so a reader can see which sub-questions
the answer claims to address. Two properties matter for integrity:

* coverage is checkable. If a sub-question retrieves nothing, that is a recorded gap and the
  answer cannot be labelled `grounded`, however good the other retrieval was.
* decomposition cannot invent evidence. Every sub-question is just a retrieval string; the
  answer still comes from retrieved passages with citations.

Everything here is deterministic and dependency-free: same question, same plan.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Accessions look like OSD-46, OSD-782, GLDS-46. Model identifiers are slugs ending in a
# version, e.g. radiation-quality-osd46-v1. Both are real, checkable names in the registry, so
# naming one in a question is a strong signal about what must be retrieved.
ACCESSION = re.compile(r"\b(?:OSD|GLDS)[-\s]?(\d{1,4})\b", re.I)
MODEL_SLUG = re.compile(r"\b([a-z][a-z0-9]*(?:-[a-z0-9]+)*-v\d+)\b")

COMPARISON_MARKERS = ("compare", "comparison", "difference between", "differ between",
                      "versus", " vs ", "how do these differ")

# A conjunction only splits the question when both halves can stand alone. "the difference
# between OSD-314 and OSD-346" contains "and" but is one question about two entities, so the
# split rule requires a second interrogative or a minimum length on each side.
SECOND_INTERROGATIVE = ("what", "why", "how", "which", "when", "who", "would", "could",
                        "does", "do ", "is ", "are ", "can ")

PRONOUN_START = ("it ", "its ", "that ", "those ", "these ", "they ", "them ", "this ",
                 "the same ", "and ", "what about")

MAX_SUBQUESTIONS = 4


@dataclass
class SubQuestion:
    """One retrieval target inside a plan."""
    id: str
    text: str
    kind: str                      # primary | entity | followup | comparison
    entity: str | None = None
    derived_from: str | None = None

    def to_dict(self) -> dict:
        return {"id": self.id, "text": self.text, "kind": self.kind,
                "entity": self.entity, "derivedFrom": self.derived_from}


@dataclass
class Plan:
    question: str
    sub_questions: list[SubQuestion] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    is_comparison: bool = False
    resolved_followup: str | None = None
    multi_hop: bool = False

    def to_dict(self) -> dict:
        return {
            "original": self.question,
            "resolvedQuestion": self.resolved_followup,
            "isComparison": self.is_comparison,
            "multiHop": self.multi_hop,
            "entities": self.entities,
            "subQuestions": [sub.to_dict() for sub in self.sub_questions],
            "strategy": ("single-pass" if len(self.sub_questions) <= 1
                         else f"multi-pass ({len(self.sub_questions)} retrievals)"),
        }


def normalise_accession(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    return f"OSD-{int(digits)}"


def entities(question: str) -> list[str]:
    """Accessions and model identifiers named in the question, in first-mention order."""
    found: list[tuple[int, str]] = []
    slug_spans: list[tuple[int, int]] = []
    for match in MODEL_SLUG.finditer(question):
        slug = match.group(1)
        # A slug must look like a model id, not an ordinary hyphenated phrase.
        if re.search(r"-v\d+$", slug) and len(slug) > 8:
            found.append((match.start(), slug))
            slug_spans.append(match.span())
    for match in ACCESSION.finditer(question):
        # `radiation-quality-osd46-v1` contains "osd46"; that accession is a property of the
        # model id, not a separate entity the question asked about, so it is not extracted
        # twice. Double-counting it invented a coverage gap for every model question.
        if any(start <= match.start() < end for start, end in slug_spans):
            continue
        found.append((match.start(), normalise_accession(match.group(0))))
    ordered: list[str] = []
    for _, value in sorted(found):
        if value not in ordered:
            ordered.append(value)
    return ordered


def is_comparison(question: str) -> bool:
    lowered = f" {question.lower()} "
    return any(marker in lowered for marker in COMPARISON_MARKERS)


def _split_conjunction(question: str) -> list[str]:
    """Split a two-part question, but only when each part can stand alone."""
    for separator in ("; and ", "; ", ", and "):
        if separator in question:
            left, right = question.split(separator, 1)
            if len(left) > 20 and len(right) > 20:
                return [left.strip(" ,;"), right.strip(" ,;")]
    # " and " is the common case and the dangerous one: do not split "A and B are different".
    if " and " in question:
        left, right = question.split(" and ", 1)
        right_lower = right.lower().lstrip()
        if len(left) > 20 and len(right) > 20 and right_lower.startswith(SECOND_INTERROGATIVE):
            return [left.strip(" ,;"), right.strip(" ,;")]
    return [question]


def resolve_followup(question: str, context: list[str] | None) -> str | None:
    """Attach the entities of a previous question to a pronoun-led follow-up.

    Only the entity names are borrowed, never the whole previous question: the follow-up keeps
    its own wording, so its retrieval still reflects what was actually asked.
    """
    if not context:
        return None
    lowered = question.lower().lstrip()
    if not lowered.startswith(PRONOUN_START):
        return None
    for previous in reversed(context[:2]):
        previous_entities = entities(previous)
        if previous_entities:
            stripped = re.sub(r"^(?:it|its|that|those|these|they|them|this|the same)\s+",
                              "", lowered).strip(" ?")
            return f"{' '.join(previous_entities)} {stripped}".strip()
    return None


def decompose(question: str, context: list[str] | None = None) -> Plan:
    """Build the retrieval plan for one question."""
    cleaned = " ".join((question or "").split())
    plan = Plan(question=cleaned)

    resolved = resolve_followup(cleaned, context)
    working = resolved or cleaned
    plan.resolved_followup = resolved

    plan.entities = entities(working)
    plan.is_comparison = is_comparison(working) and len(plan.entities) >= 2

    parts = _split_conjunction(working)
    plan.multi_hop = len(parts) > 1

    plan.sub_questions.append(SubQuestion(id="q1", text=parts[0], kind="primary"))
    for index, part in enumerate(parts[1:], start=2):
        plan.sub_questions.append(
            SubQuestion(id=f"q{index}", text=part, kind="followup",
                        derived_from=parts[0]))

    # Comparative questions get one retrieval per named entity, because a shared query cannot
    # be relied on to surface the side that matches the vocabulary less well. The entity
    # question repeats the comparison verb so the ranking still sees the question's intent.
    if plan.is_comparison:
        verb = "compare" if "compare" in working.lower() else "evidence for"
        for entity in plan.entities:
            if len(plan.sub_questions) >= MAX_SUBQUESTIONS:
                break
            plan.sub_questions.append(
                SubQuestion(id=f"e{len(plan.sub_questions) + 1}", text=f"{entity} {verb}",
                            kind="entity", entity=entity, derived_from=parts[0]))

    plan.sub_questions = plan.sub_questions[:MAX_SUBQUESTIONS]
    return plan
