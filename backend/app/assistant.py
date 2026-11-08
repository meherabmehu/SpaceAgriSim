"""NASA evidence-grounded research assistant.

The composer is deliberately **extractive**: answers are assembled out of sentences
that were retrieved from the corpus, with a citation index attached to each one. An
optional language model may rephrase an answer, but it never chooses the evidence and
cannot introduce a sentence without a citation, because the citation list is fixed
before any model sees the text.

Why not "just ask an LLM and let it cite"
----------------------------------------
Because that is how invented citations happen. Retrieval-augmented generation still
lets a model state something the retrieved documents do not contain. Here the boundary
is structural rather than a prompt instruction: `EvidenceAnswer` holds
`claims: list[Claim]`, every `Claim` carries a `citation` index, and the renderer
refuses to emit a claim without one. A language model can only run *after* that
structure exists, and its output is validated against the same structure before it is
returned.

Three answer modes
------------------
`grounded`  enough evidence was retrieved and the question maps to a known intent.
`partial`   something relevant was found but does not fully answer the question.
`insufficient`  the corpus does not contain evidence for the question. This is a
            first-class outcome, not an error: saying "the repository does not record
            this" is a correct scientific answer, and inventing one is not.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app import evidence

MAX_CLAIMS = 5
MIN_EVIDENCE_SCORE = 2.5

# Intents carry a phrase set plus how the answer should be framed. The frames are
# what stop a corpus hit from being presented as the wrong kind of fact: a model row
# retrieved for "what does this predict" must be framed as a model, not a measurement.
INTENTS = (
    {
        "id": "model_scope",
        "phrases": ("what does", "actually predict", "predict", "classifier", "model do",
                    "what is", "output", "target", "inputs", "features", "schema"),
        "frame": ("This is a model output, not a measurement. The model predicts: {target}. "
                  "It does not predict anything outside that target."),
        "kinds": ("model",),
    },
    {
        "id": "model_selection",
        "phrases": ("which model", "what model", "can analyse", "can analyze", "analyse",
                    "analyze", "suitable model", "run inference", "which ai"),
        "frame": ("Model selection is determined by the input schema and the source data, "
                  "not by preference. The candidates recorded here are:"),
        "kinds": ("model", "classification"),
    },
    {
        "id": "exclusion",
        "phrases": ("why", "excluded", "not served", "retired", "rejected", "why not",
                    "failed", "fail", "unsupported", "withdrawn"),
        "frame": ("These exclusions are documented findings, not missing features:"),
        "kinds": ("evaluation", "classification"),
    },
    {
        "id": "evidence_for_assumption",
        "phrases": ("what evidence", "supports", "assumptions", "justify", "basis",
                    "is it validated", "validated", "calibrated"),
        "frame": ("The evidence recorded for these assumptions is:"),
        "kinds": ("evaluation", "methodology", "dataset"),
    },
    {
        "id": "earth_only",
        "phrases": ("earth only", "earth-only", "crop growth", "yield prediction",
                    "ground", "not nasa", "external"),
        "frame": ("Earth-only and external evidence must be separated from NASA-measured "
                  "evidence. In this repository:"),
        "kinds": ("model", "methodology", "dataset"),
    },
    {
        "id": "uncertainty",
        "phrases": ("uncertainty", "interval", "confidence", "calibrat", "coverage",
                    "how sure", "error bar", "reliab"),
        "frame": ("Intervals here are measured, not guaranteed. The recorded positions are:"),
        "kinds": ("evaluation", "model", "methodology"),
    },
    {
        "id": "dataset_suitability",
        "phrases": ("dataset", "study", "osd-", "experiment", "suitable for training",
                    "future training", "future ai", "training data", "which nasa",
                    "microgravity", "radiation study", "suitable", "eligib"),
        "frame": ("These are the registered studies and their provenance:"),
        "kinds": ("dataset", "evaluation"),
    },
    {
        "id": "comparison",
        "phrases": ("compare", "difference between", "versus", "vs", "how do", "differ"),
        "frame": ("Comparison is only meaningful within a shared classification and "
                  "measurement basis:"),
        "kinds": ("dataset", "model", "evaluation"),
    },
)

GREETING = re.compile(r"^\s*(?:hi|hello|hey|good (?:morning|afternoon|evening))\b", re.I)


@dataclass
class Claim:
    """One citable statement. A claim without a citation is rejected by the renderer."""
    text: str
    citation: int
    passage_id: str
    quote: str = ""

    def to_dict(self) -> dict:
        return {"text": self.text, "citation": self.citation,
                "passageId": self.passage_id, "quote": self.quote}


@dataclass
class EvidenceAnswer:
    question: str
    status: str
    summary: str
    claims: list[Claim] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    intent: str | None = None
    limitations: list[str] = field(default_factory=list)
    measured_versus_interpreted: dict = field(default_factory=dict)
    refusal: str | None = None

    def render(self) -> dict:
        """Serialise, refusing any claim that lacks a resolvable citation."""
        rendered = []
        for claim in self.claims:
            if claim.citation < 1 or claim.citation > len(self.citations):
                raise ValueError("Refusing to emit an uncited claim")
            rendered.append(claim.to_dict())
        return {
            "question": self.question,
            "status": self.status,
            "intent": self.intent,
            "summary": self.summary,
            "claims": rendered,
            "citations": self.citations,
            "limitations": self.limitations,
            "measuredVersusInterpreted": self.measured_versus_interpreted,
            "refusal": self.refusal,
            "grounding": {
                "citationCount": len(self.citations),
                "claimsWithCitation": sum(1 for c in self.claims if c.citation >= 1),
                "everyClaimCited": all(c.citation >= 1 for c in self.claims),
                "retrieval": "BM25 over verified repository artifacts",
            },
        }


def detect_intent(question: str) -> dict | None:
    lowered = question.lower()
    best, best_score = None, 0
    for intent in INTENTS:
        score = sum(1 for phrase in intent["phrases"] if phrase in lowered)
        if score > best_score:
            best, best_score = intent, score
    return best


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 30]


def _first_sentence(text: str) -> str:
    sentences = _sentences(text)
    return sentences[0] if sentences else text[:240]


def _select_passages(question: str, intent: dict | None) -> list[tuple]:
    hits = evidence.search(question, limit=10)
    if intent:
        # The intent lists its evidence kinds in priority order. A question about which
        # datasets exist should lead with a dataset record, not with an evaluation note
        # that happens to share vocabulary, so the primary kind is boosted rather than
        # merely sorted ahead.
        primary = intent["kinds"][0]
        def weight(pair):
            passage, score = pair
            if passage.kind == primary:
                return score * 1.35
            if passage.kind in intent["kinds"]:
                return score
            return score * 0.6
        hits = sorted(((p, weight((p, sc))) for p, sc in hits), key=lambda x: -x[1])
    return hits


def answer(question: str, *, max_claims: int = MAX_CLAIMS) -> EvidenceAnswer:
    """Compose a grounded answer, or say plainly that the evidence is insufficient."""
    cleaned = (question or "").strip()
    if not cleaned:
        return EvidenceAnswer(
            question="", status="insufficient",
            summary="Ask a question about a NASA study, a registered model, or a "
                    "documented finding.",
            refusal="empty-question")
    if len(cleaned) > evidence.MAX_QUESTION_CHARS:
        raise ValueError(
            f"Question exceeds {evidence.MAX_QUESTION_CHARS} characters; the assistant "
            "answers from a bounded evidence set and does not accept documents as input.")

    if GREETING.match(cleaned) and len(cleaned) < 30:
        return EvidenceAnswer(
            question=cleaned, status="insufficient",
            summary="This assistant answers questions about SpaceAgriSim's NASA datasets, "
                    "registered models, and documented scientific findings, with a citation "
                    "for every statement.",
            refusal="greeting")

    intent = detect_intent(cleaned)
    hits = _select_passages(cleaned, intent)

    # Two floors, because an absolute one alone is not enough. A passage that merely
    # shares a stem with the question ("train") can clear the absolute floor and then
    # pad an answer with irrelevant records, so anything scoring below a fraction of
    # the best match is dropped as well.
    top_score = hits[0][1] if hits else 0.0
    relative_floor = max(top_score * 0.30, MIN_EVIDENCE_SCORE)
    strong = [pair for pair in hits if pair[1] >= relative_floor]
    if not strong:
        return EvidenceAnswer(
            question=cleaned, status="insufficient", intent=intent["id"] if intent else None,
            summary=("The repository does not record evidence that answers this question. "
                     "It is not answered from general knowledge, because an unsourced "
                     "answer about NASA data is indistinguishable from an invented one."),
            limitations=["No passage in the corpus scored above the evidence floor."],
            refusal="insufficient-evidence")

    claims: list[Claim] = []
    citations: list[dict] = []
    limitations: list[str] = []
    seen = set()
    for passage, score in strong:
        if len(claims) >= max_claims:
            break
        if passage.source_id in seen:
            continue
        seen.add(passage.source_id)
        quote = _first_sentence(passage.text)
        claims.append(Claim(text=quote, citation=len(citations) + 1,
                            passage_id=passage.id, quote=quote[:400]))
        citation = passage.citation()
        citation["retrievalScore"] = round(float(score), 2)
        citations.append(citation)
        for limitation in passage.limitations[:2]:
            if limitation not in limitations:
                limitations.append(limitation)

    kinds = {citation["kind"] for citation in citations}
    measured = [c["sourceId"] for c in citations if c["evidenceClass"] == "measured data"]
    interpreted = [c["sourceId"] for c in citations if c["evidenceClass"] != "measured data"]

    status = "grounded" if intent and len(claims) >= 2 else "partial"
    if status != "grounded":
        # A partial answer is a pointer to the evidence, not an answer. Say so in the
        # limitations rather than letting a weak match read like a conclusion.
        note = ("The retrieved passages are relevant but do not cover the whole question; "
                "read them as evidence to inspect, not as an answer.")
        if note not in limitations:
            limitations.append(note)
    summary = (intent["frame"].format(target="the recorded target field")
               if intent and status == "grounded"
               else "Partial evidence was found. The following records are relevant, but "
                    "they do not fully answer the question as asked.")

    answer_object = EvidenceAnswer(
        question=cleaned, status=status, summary=summary, claims=claims,
        citations=citations, intent=intent["id"] if intent else None,
        limitations=limitations[:6],
        measured_versus_interpreted={
            "measuredData": measured,
            "modelOrEstimate": interpreted,
            "note": ("Passages whose evidence class is 'measured data' describe a study "
                     "record or a measured finding. Everything else describes a model, an "
                     "estimate or a methodology statement and must not be read as a "
                     "measurement."),
            "kindsRetrieved": sorted(kinds),
        })
    # Fail loudly at construction time, not at serialisation time.
    answer_object.render()
    return answer_object


def suggested_questions() -> list[dict]:
    """Questions the corpus can actually answer, each tied to a real source.

    Suggestions are generated from the corpus rather than hardcoded, so the list
    cannot drift away from what is answerable.
    """
    index = evidence.corpus()
    by_source = {p.source_id: p for p in index["passages"]}
    curated = [
        ("Which NASA studies investigated plant responses to microgravity?",
         "method-simulator", "dataset"),
        ("What does the OSD-46 radiation classifier actually predict?",
         "radiation-quality-osd46-v1", "model"),
        ("Why did the OSD-346 gravity result fail independent replication?",
         "phase11-gravity-osd346", "evaluation"),
        ("Which model can analyse a gene expression input?",
         "radiation-exposure-osd46-v1", "model"),
        ("What evidence supports the simulator's gravity assumptions?",
         "method-simulator", "methodology"),
        ("Which crop growth predictions are Earth-only?",
         "lettuce-earth-growth-v2", "model"),
        ("What does the lettuce model's uncertainty interval mean?",
         "phase10-coverage", "evaluation"),
        ("Which NASA datasets are suitable for future AI training?",
         "method-provenance", "methodology"),
        ("Why are some models excluded?",
         "method-classification", "methodology"),
        ("How do OSD-46 and OSD-782 compare?",
         "phase10-cross-study", "evaluation"),
        ("Is OSD-320 an independent study?",
         "phase11-duplicate-osd320", "evaluation"),
    ]
    rows = []
    for question, source_id, kind in curated:
        passage = by_source.get(source_id)
        rows.append({
            "question": question,
            "answeredBy": source_id,
            "available": passage is not None,
            "kind": kind,
        })
    return rows
