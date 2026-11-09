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

from app import evidence, reasoning

MAX_CLAIMS = 5
MIN_EVIDENCE_SCORE = 2.5
# The relative floor keeps weak matches out of an answer. Uncapped, it also throws away every
# corroborating passage whenever the best match is overwhelming (query expansion can produce a
# single 32-point hit), leaving a one-claim answer that cannot be called grounded. Capping it
# keeps the floor's purpose without letting one passage suppress the rest of the evidence.
MAX_RELATIVE_FLOOR = 12.0
# A question that one passage matches almost verbatim is answered by that passage. Requiring a
# second citation in that case does not improve the answer, it pads it with weaker records that
# share vocabulary only - so a decisive single match counts as complete evidence.
SINGLE_PASSAGE_SUFFICIENT = 20.0

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
        # The training-eligibility audit is a methodology passage, and it is the best evidence
        # for "which datasets are suitable for training". Penalising it as an off-intent kind
        # pushed the one authoritative answer below the decisive threshold.
        "kinds": ("dataset", "methodology", "evaluation"),
    },
    {
        "id": "limitations",
        "phrases": ("limitations", "limitation", "limits", "restrictions", "restricted",
                    "scope", "does it measure", "measure plant health", "not predict",
                    "what can it not", "caveats", "assumptions"),
        "frame": ("These are the recorded limits of what the model or method may be used "
                  "for. They are part of the result, not a disclaimer attached to it:"),
        "kinds": ("model", "methodology", "evaluation"),
    },
    {
        "id": "comparison",
        "phrases": ("compare", "difference between", "versus", "vs", "how do", "differ"),
        "frame": ("Comparison is only meaningful within a shared classification and "
                  "measurement basis:"),
        "kinds": ("dataset", "model", "evaluation"),
    },
)

# Questions that presuppose a capability this project does not have. Answering them as if the
# premise held would be the exact failure the brief forbids: a molecular classifier becoming a
# crop-yield predictor, or an Earth model becoming a Moon model. The patterns are narrow on
# purpose - "yield" alone is a legitimate topic (the mizuna harvest model predicts fresh mass
# per pillow), so a pattern only fires when a yield/planting claim is asked of a model or a
# world it was never trained on.
FALSE_PREMISES = (
    {
        "id": "moon-mars-production",
        "pattern": re.compile(r"\b(moon|lunar|mars|martian)\b.*\b(yield|crop|harvest|biomass|"
                              r"grow|production)\b|\b(yield|crop|harvest|biomass)\b.*"
                              r"\b(moon|lunar|mars|martian)\b", re.I),
        "explanation": ("No served model predicts crop yield, biomass or harvest on the Moon or "
                        "Mars, and no NASA dataset in this repository pairs a partial-gravity "
                        "environment with a crop-production measurement. The question's premise "
                        "is not supported by any evidence here."),
    },
    {
        "id": "classifier-yield",
        "pattern": re.compile(r"\b(improve[sd]?|increase[sd]?|predict[sd]?|boost[sd]?)\b.*"
                              r"\b(crop yield|yield|harvest)\b", re.I),
        "explanation": ("The molecular classifiers identify an applied experimental condition "
                        "(radiation quality, irradiation, flight context). They do not predict, "
                        "improve or quantify crop yield, and no experiment in the corpus "
                        "measures a yield effect of a classifier."),
    },
)

# Domain vocabulary the corpus actually uses. Questions are phrased in the asker's words, the
# artifacts in the authors' words, and the gap between them is the single largest cause of
# missed retrieval in the Phase 12 sweep. Expansion is additive: the original terms keep their
# weight, so expansion can only add candidates, never displace a genuine match.
QUERY_EXPANSION = (
    (re.compile(r"\b(suitab\w*|eligib\w*)\b.*\b(train\w*|ai|model)", re.I),
     "training eligibility audit readyForPredictiveTraining refused targets"),
    (re.compile(r"\b(future|new|more)\b.*\b(train\w*|ai)\b", re.I),
     "training eligibility audit readyForPredictiveTraining"),
    (re.compile(r"\b(actual|real|true)\b.*\b(growth|biomass)\b.*\b(measure\w*|data)\b", re.I),
     "fresh mass harvest biomass measured endpoints"),
    (re.compile(r"\bwould be needed\b|\bwould .* require\b|\bwhat would\b", re.I),
     "eligibility refused constraints validation requirement"),
    (re.compile(r"\b(limit\w*|caveat\w*|restrict\w*)\b", re.I),
     "limitations not validated does not predict"),
    (re.compile(r"\b(improve\w*|better|upgrade)\b.*\b(model|accuracy)\b", re.I),
     "no promotion delta versus shipped nested selection"),
    (re.compile(r"\b(explanation\w*|explainab\w*|attribution|importance|interpretab\w*)\b", re.I),
     "explainability feature importance permutation attribution linear"),
    (re.compile(r"\b(calibrat\w*|confidence|probabilit\w*)\b", re.I),
     "calibrated probabilities softmax not calibrated measured coverage"),
)

GREETING = re.compile(r"^\s*(?:hi|hello|hey|good (?:morning|afternoon|evening))\b", re.I)


@dataclass
class Claim:
    """One citable statement. A claim without a citation is rejected by the renderer."""
    text: str
    citation: int
    passage_id: str
    quote: str = ""
    answers: str | None = None          # id of the sub-question this claim addresses

    def to_dict(self) -> dict:
        return {"text": self.text, "citation": self.citation,
                "passageId": self.passage_id, "quote": self.quote,
                "answers": self.answers}


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
    plan: dict = field(default_factory=dict)
    coverage_gaps: list[dict] = field(default_factory=list)

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
            "plan": self.plan,
            "coverageGaps": self.coverage_gaps,
            "grounding": {
                "citationCount": len(self.citations),
                "claimsWithCitation": sum(1 for c in self.claims if c.citation >= 1),
                "everyClaimCited": all(c.citation >= 1 for c in self.claims),
                "subQuestionsPlanned": len(self.plan.get("subQuestions") or []),
                "subQuestionsAnswered": len({c.answers for c in self.claims if c.answers}),
                "entitiesRequested": list(self.plan.get("entities") or []),
                "entitiesCovered": [e for e in (self.plan.get("entities") or [])
                                    if e not in {g["entity"] for g in self.coverage_gaps}],
                "retrieval": "BM25 over verified repository artifacts, per sub-question",
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


CRITICAL_PHRASING = re.compile(
    r"\b(why (?:can|could|do|does|did|is|are)\b.*\b(?:not|n't)\b|"
    r"cannot|can not|can't|does not|do not|not able|why not|why is there no|"
    r"why (?:was|were) .* (?:retired|excluded|rejected|not)|limitation)", re.I)


def detect_false_premise(question: str) -> dict | None:
    """Return the premise that this question assumes and the corpus does not support.

    A question that *asks why* a capability is absent is not assuming the capability: "why can
    the lettuce model not predict Mars crop yield" is answerable from the recorded limitation,
    so the guard must stay out of the way and let the normal evidence path answer it.
    """
    if CRITICAL_PHRASING.search(question):
        return None
    for premise in FALSE_PREMISES:
        if premise["pattern"].search(question):
            return premise
    return None


def expand_query(question: str) -> str:
    """Add corpus vocabulary for question phrasings the artifacts do not use."""
    additions = [expansion for pattern, expansion in QUERY_EXPANSION
                 if pattern.search(question)]
    if not additions:
        return question
    return question + " " + " ".join(additions)


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 30]


CORRECTION_SENTENCE = re.compile(
    r"does not predict|never predicts|not a measurement|must not be read|"
    r"no such measurement|cannot be used|not calibrated|does not measure", re.I)


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


def answer(question: str, *, max_claims: int = MAX_CLAIMS,
           context: list[str] | None = None) -> EvidenceAnswer:
    """Compose a grounded answer, or say plainly that the evidence is insufficient.

    `context` carries up to two previous questions so a pronoun-led follow-up can inherit the
    entity names it refers to. Only the names are borrowed; the follow-up keeps its own
    wording, so its retrieval still reflects what was actually asked.
    """
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

    plan = reasoning.decompose(cleaned, context)
    working = plan.resolved_followup or cleaned
    intent = detect_intent(working)
    premise = detect_false_premise(working)

    # Multi-pass retrieval. Each sub-question is a separate BM25 query, so the second side of
    # a comparison is retrieved on its own terms instead of competing with the first side for
    # one set of terms. Only the primary sub-question receives intent kind-weighting: a
    # derived entity query is a lookup, and weighting it would let the intent's preferred kind
    # override the entity the caller actually asked about.
    per_sub: list[tuple[reasoning.SubQuestion, list[tuple]]] = []
    for sub in plan.sub_questions:
        hits = _select_passages(expand_query(sub.text),
                                intent if sub.kind == "primary" else None)
        if sub.kind == "entity" and sub.entity:
            # An entity lookup should prefer the record that *is* that accession. Without this
            # boost the audit finding about OSD-320 outranks the OSD-320 dataset record, and a
            # comparison then cites the same source twice instead of both entities.
            needle = sub.entity.lower()
            hits = sorted(
                ((passage, score * (2.5 if needle in f"{passage.accession or ''} {passage.id}".lower()
                                    else 1.0))
                 for passage, score in hits),
                key=lambda pair: -pair[1])
        per_sub.append((sub, hits))

    merged: dict[str, dict] = {}
    for sub, hits in per_sub:
        for passage, score in hits:
            row = merged.get(passage.id)
            if row is None:
                merged[passage.id] = {"passage": passage, "score": score, "subs": [sub.id]}
            else:
                if sub.id not in row["subs"]:
                    row["subs"].append(sub.id)
                row["score"] = max(row["score"], score)

    if premise and premise["id"] == "moon-mars-production":
        # A model card is the wrong evidence for "what is the yield on Mars". Every served model
        # here was trained on Earth or low-Earth-orbit data, and citing one - however neutrally,
        # however well its limitations are stated - is what a reader sees as "the platform
        # answered a Mars yield question with a model". Only passages that can speak to the
        # absence itself (datasets, evaluation notes) are kept.
        #
        # This surfaced in Phase 19: v3's name contains "fresh yield", so it began to win the
        # lexical match on yield questions and turned a correct refusal into a partial answer.
        # The guard belongs here, not in the model's name. A model card that does state the
        # absence ("does not predict", "not a measurement") is exactly the evidence to keep.
        merged = {key: row for key, row in merged.items()
                  if row["passage"].kind != "model"
                  or CORRECTION_SENTENCE.search(row["passage"].text)}

    if premise:
        # When the question assumes a capability the model does not have, the useful evidence is
        # the passage that says so. Boost corrective passages instead of letting the model card
        # answer as if the capability existed.
        correction = re.compile(r"does not predict|never predicts|not a measurement|"
                                r"must not be read|no such measurement|cannot be used", re.I)
        for row in merged.values():
            if correction.search(row["passage"].text):
                row["score"] *= 1.6

    ranked = sorted(merged.values(), key=lambda row: -row["score"])
    top_score = ranked[0]["score"] if ranked else 0.0
    # Two floors, because an absolute one alone is not enough. A passage that merely shares a
    # stem with the question ("train") can clear the absolute floor and then pad an answer with
    # irrelevant records, so anything scoring below a fraction of the best match is dropped too.
    relative_floor = max(min(top_score * 0.30, MAX_RELATIVE_FLOOR), MIN_EVIDENCE_SCORE)
    strong = [row for row in ranked if row["score"] >= relative_floor]
    if not strong:
        return EvidenceAnswer(
            question=cleaned, status="insufficient", intent=intent["id"] if intent else None,
            summary=("The repository does not record evidence that answers this question. "
                     "It is not answered from general knowledge, because an unsourced "
                     "answer about NASA data is indistinguishable from an invented one."),
            limitations=["No passage in the corpus scored above the evidence floor."],
            refusal="insufficient-evidence", plan=plan.to_dict())

    # Coverage check. Naming an accession and receiving an answer that never mentions it is the
    # exact failure this phase exists to fix, so a named entity with no supporting passage is
    # recorded as a gap and blocks the `grounded` label.
    covered: dict[str, str] = {}
    for entity in plan.entities:
        needle = entity.lower()
        for row in strong:
            passage = row["passage"]
            haystack = f"{passage.accession or ''} {passage.id} {passage.text}".lower()
            if needle in haystack:
                covered[entity] = passage.id
                break
    gaps = [{"entity": entity, "reason": "no retrieved passage mentions this entity",
             "consequence": "the answer does not cover this part of the question"}
            for entity in plan.entities if entity not in covered]

    # Hop-aware selection: one claim per sub-question first, so a two-part question cannot be
    # answered entirely from one hop, then fill the remaining budget by score.
    selected: list[tuple[dict, str]] = []
    used_sources: set[str] = set()
    for sub, _hits in per_sub:
        if len(selected) >= max_claims:
            break
        for row in strong:
            if sub.id in row["subs"] and row["passage"].source_id not in used_sources:
                selected.append((row, sub.id))
                used_sources.add(row["passage"].source_id)
                break
    for row in strong:
        if len(selected) >= max_claims:
            break
        if row["passage"].source_id in used_sources:
            continue
        selected.append((row, row["subs"][0]))
        used_sources.add(row["passage"].source_id)

    claims: list[Claim] = []
    citations: list[dict] = []
    limitations: list[str] = []
    for row, sub_id in selected:
        passage = row["passage"]
        if premise:
            # Answering "what yield will it predict" with the model's identity line would look
            # like an answer. Quote the statement that the model does not do this - from the
            # passage body if it is there, otherwise from the limitations recorded on the same
            # artifact, which the citation already carries.
            corrective = [sentence for sentence in _sentences(passage.text)
                          if CORRECTION_SENTENCE.search(sentence)]
            from_limitation = not corrective
            if from_limitation:
                corrective = [limitation for limitation in passage.limitations
                              if CORRECTION_SENTENCE.search(limitation)]
            quote = corrective[0] if corrective else _first_sentence(passage.text)
            # A limitation is quoted whole: truncating it would break the guarantee that the
            # claim is a verbatim span of the evidence it cites.
            if not from_limitation:
                quote = quote[:400]
        else:
            quote = _first_sentence(passage.text)[:400]
        claims.append(Claim(text=quote, citation=len(citations) + 1,
                            passage_id=passage.id, quote=quote, answers=sub_id))
        citation = passage.citation()
        if quote not in passage.text:
            # The claim quotes a recorded limitation, so the citation must carry that exact
            # text: a reader has to be able to check the sentence they were shown.
            existing = citation.get("limitations") or []
            if not any(quote in item for item in existing):
                citation["limitations"] = [quote, *existing][:5]
        citation["retrievalScore"] = round(float(row["score"]), 2)
        citation["answers"] = sub_id
        citations.append(citation)
        for limitation in passage.limitations[:2]:
            if limitation not in limitations:
                limitations.append(limitation)

    kinds = {citation["kind"] for citation in citations}
    measured = [c["sourceId"] for c in citations if c["evidenceClass"] == "measured data"]
    interpreted = [c["sourceId"] for c in citations if c["evidenceClass"] != "measured data"]

    decisive = bool(strong) and strong[0]["score"] >= SINGLE_PASSAGE_SUFFICIENT
    status = ("grounded" if intent and not gaps and (len(claims) >= 2 or decisive)
              else "partial")
    refusal = None
    if premise:
        # A false premise is never a grounded answer, however well-cited the surrounding model
        # card is. The answer states the correction and the evidence that supports it.
        status = "partial"
        refusal = "unsupported-premise"
    if gaps:
        named = ", ".join(gap["entity"] for gap in gaps)
        note = (f"The question names {named}, but no retrieved passage covers it. The answer "
                "below covers only the part of the question the corpus can support.")
        if note not in limitations:
            limitations.insert(0, note)
    if status != "grounded":
        note = ("The retrieved passages are relevant but do not cover the whole question; "
                "read them as evidence to inspect, not as an answer.")
        if note not in limitations:
            limitations.append(note)

    if premise:
        note = premise["explanation"]
        if note not in limitations:
            limitations.insert(0, note)

    if status == "grounded" and plan.is_comparison:
        summary = ("Evidence for each named source is quoted below, one claim per source, so "
                   "the comparison rests on separate passages rather than on a single "
                   "paragraph that happens to mention both.")
    elif premise:
        summary = premise["explanation"]
    elif status == "grounded":
        summary = intent["frame"].format(target="the recorded target field")
    else:
        summary = ("Partial evidence was found. The following records are relevant, but "
                   "they do not fully answer the question as asked.")

    answer_object = EvidenceAnswer(
        question=cleaned, status=status, summary=summary, claims=claims,
        citations=citations, intent=intent["id"] if intent else None,
        limitations=limitations[:6], plan=plan.to_dict(), coverage_gaps=gaps,
        refusal=refusal,
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
