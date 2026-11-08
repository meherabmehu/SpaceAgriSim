"""Phase 13: decomposition, multi-hop retrieval, false premises, and the benchmark itself.

The Phase 12 assistant tests prove citation integrity. These tests prove the reasoning layer
that sits on top of it did not pay for its extra usefulness with integrity: every claim is
still a verbatim sentence of the passage it cites, refusing is still the right answer when the
corpus is silent, and a question that assumes a capability the project does not have is never
labelled a grounded answer.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import assistant, assistant_eval, evidence, reasoning
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


# ------------------------------------------------------------------ entity extraction

def test_accessions_are_extracted_in_first_mention_order():
    assert reasoning.entities("Compare OSD-346 with OSD-314 and OSD-46") == \
        ["OSD-346", "OSD-314", "OSD-46"]


def test_gl_style_accessions_normalise_to_osd_ids():
    assert reasoning.entities("GLDS-46 and OSD 782") == ["OSD-46", "OSD-782"]


def test_model_slugs_are_recognised_but_ordinary_hyphenated_words_are_not():
    found = reasoning.entities("what does radiation-quality-osd46-v1 predict about "
                               "space-flight radiation-response")
    assert found == ["radiation-quality-osd46-v1"]


# ------------------------------------------------------------------- decomposition

def test_comparison_produces_one_retrieval_per_entity():
    plan = reasoning.decompose("Compare the findings of OSD-314 and OSD-346.")
    assert plan.is_comparison
    kinds = [sub.kind for sub in plan.sub_questions]
    assert kinds.count("entity") == 2
    entities = {sub.entity for sub in plan.sub_questions if sub.kind == "entity"}
    assert entities == {"OSD-314", "OSD-346"}


def test_a_single_entity_question_is_not_split():
    plan = reasoning.decompose("What does the OSD-46 classifier predict?")
    assert not plan.is_comparison
    assert len(plan.sub_questions) == 1


def test_conjunction_splits_only_when_both_halves_stand_alone():
    split = reasoning.decompose("Why did the OSD-346 result fail and what evidence would "
                                "validate it?")
    assert len(split.sub_questions) == 2
    unsplit = reasoning.decompose("OSD-314 and OSD-346 were both flown")
    assert len(unsplit.sub_questions) == 1


def test_sub_question_count_is_bounded():
    plan = reasoning.decompose("Compare OSD-7, OSD-46, OSD-314, OSD-346 and OSD-782.")
    assert len(plan.sub_questions) <= reasoning.MAX_SUBQUESTIONS


def test_plan_is_deterministic():
    first = reasoning.decompose("Compare OSD-314 and OSD-346.")
    second = reasoning.decompose("Compare OSD-314 and OSD-346.")
    assert first.to_dict() == second.to_dict()


# ---------------------------------------------------------------------- follow-ups

def test_pronoun_followup_inherits_only_the_entity():
    resolved = reasoning.resolve_followup(
        "What about its replicate design?", ["Tell me about OSD-346."])
    assert resolved is not None
    assert "OSD-346" in resolved
    assert "replicate design" in resolved
    assert "Tell me about" not in resolved


def test_followup_is_ignored_without_context_or_without_a_pronoun():
    assert reasoning.resolve_followup("What about its design?", None) is None
    assert reasoning.resolve_followup("What does OSD-46 predict?",
                                      ["Tell me about OSD-346."]) is None


# --------------------------------------------------------------- multi-hop answers

def test_comparison_cites_both_named_entities(client):
    body = client.post("/api/assistant/ask",
                       json={"question": "Compare the findings of OSD-314 and OSD-346."}).json()
    cited = {citation["sourceId"] for citation in body["citations"]}
    assert {"OSD-314", "OSD-346"} <= cited
    assert len(body["plan"]["subQuestions"]) > 1
    # one claim per entity, so the comparison rests on separate passages
    answered = [claim["answers"] for claim in body["claims"]]
    assert len(set(answered)) >= 2


def test_every_sub_question_that_found_evidence_is_answered(client):
    body = client.post("/api/assistant/ask",
                       json={"question": "Why did the OSD-346 gravity result fail and what "
                                         "evidence would validate it?"}).json()
    assert body["status"] in {"grounded", "partial"}
    assert body["plan"]["multiHop"] is True
    assert body["claims"]


def test_entity_named_but_never_retrieved_is_a_recorded_gap(client):
    """A named accession with no evidence must block the grounded label."""
    body = client.post("/api/assistant/ask",
                       json={"question": "Compare OSD-46 and OSD-9999."}).json()
    gaps = [gap["entity"] for gap in body["coverageGaps"]]
    assert "OSD-9999" in gaps
    assert body["status"] != "grounded"


# ------------------------------------------------------------------ false premises

@pytest.mark.parametrize("question", [
    "What crop yield will the OSD-46 classifier predict on the Moon?",
    "By how much did the radiation classifier improve crop yield?",
])
def test_a_question_assuming_an_absent_capability_is_not_grounded(client, question):
    body = client.post("/api/assistant/ask", json={"question": question}).json()
    assert body["status"] != "grounded"
    assert body["refusal"] == "unsupported-premise"
    assert "not supported" in body["summary"].lower() or \
           "do not predict" in body["summary"].lower() or \
           "does not support" in body["summary"].lower()


def test_asking_why_a_capability_is_absent_is_answerable_normally(client):
    """'Why can it not predict X' is a question about the limitation, not an assumption."""
    body = client.post("/api/assistant/ask",
                       json={"question": "Why can the lettuce model not predict Mars crop "
                                         "yield?"}).json()
    assert body["refusal"] != "unsupported-premise"
    assert body["claims"]


def test_premise_guard_prefers_corrective_evidence(client):
    body = client.post("/api/assistant/ask",
                       json={"question": "What crop yield will the OSD-46 classifier predict "
                                         "on the Moon?"}).json()
    text = " ".join(claim["text"] for claim in body["claims"]).lower()
    assert "yield" in text or "does not predict" in text or "not a measurement" in text


# ------------------------------------------------------------- integrity invariants

def test_every_claim_is_still_a_verbatim_sentence_of_its_passage(client):
    """The whole point of the upgrade: more useful answers must not mean looser citation."""
    texts = {passage.id: passage.text for passage in evidence.corpus()["passages"]}
    for question in ("Compare the findings of OSD-314 and OSD-346.",
                     "Which NASA datasets are suitable for training AI models?",
                     "What makes the radiation classifiers scientifically useful?"):
        body = client.post("/api/assistant/ask", json={"question": question}).json()
        for claim in body["claims"]:
            assert claim["quote"] in texts[claim["passageId"]], question
            assert 1 <= claim["citation"] <= len(body["citations"])


def test_unsupported_questions_still_refuse_with_no_citations(client):
    body = client.post("/api/assistant/ask",
                       json={"question": "How do I bake sourdough bread?"}).json()
    assert body["status"] == "insufficient"
    assert body["refusal"] == "insufficient-evidence"
    assert body["claims"] == [] and body["citations"] == []


def test_context_is_bounded_and_validated(client):
    assert client.post("/api/assistant/ask",
                       json={"question": "and its design?",
                             "context": ["a", "b", "c"]}).status_code == 422
    assert client.post("/api/assistant/ask",
                       json={"question": "and its design?",
                             "context": ["x" * 500]}).status_code == 422
    assert client.post("/api/assistant/ask",
                       json={"question": "and its design?", "context": [],
                             "extra": 1}).status_code == 422


# --------------------------------------------------------------------- the benchmark

def test_benchmark_meets_every_expectation():
    """The gate. If a change breaks an expectation, this fails rather than degrading quietly."""
    report = assistant_eval.evaluate(assistant.answer)
    assert report["metrics"]["statusAccuracy"] >= 0.95
    assert report["metrics"]["citationHitRate"] >= 0.95
    assert report["metrics"]["citationCompleteness"] >= 0.95
    assert report["metrics"]["refusalCorrectness"] == 1.0
    assert report["metrics"]["entityCoverage"] == 1.0
    assert report["metrics"]["unsupportedClaimRate"] == 0.0
    assert report["failures"] == [], assistant_eval.format_summary(report)


def test_benchmark_covers_every_required_category():
    categories = set(assistant_eval.load_benchmark()["categories"]) \
        if "categories" in assistant_eval.load_benchmark() else \
        {item["category"] for item in assistant_eval.load_benchmark()["items"]}
    assert {"direct_factual", "multi_hop", "dataset_comparison", "model_scope",
            "scientific_limitations", "dataset_suitability", "missing_evidence",
            "adversarial_injection", "unsupported_claim"} <= categories


def test_scoring_flags_a_fabricated_claim():
    """The scorer must be able to fail, or a green result means nothing."""
    item = {"id": "x", "category": "direct_factual", "question": "q",
            "expectStatus": "grounded", "mustCiteAny": ["OSD-46"]}
    citations = [{"sourceId": "OSD-46", "kind": "dataset"}]
    fabricated = {"status": "grounded",
                  "citations": citations,
                  "claims": [{"text": "Lettuce yield tripled on the Moon.",
                              "quote": "Lettuce yield tripled on the Moon.",
                              "citation": 1, "passageId": "dataset::OSD-46"}]}
    score = assistant_eval.score_item(item, fabricated, {"dataset::OSD-46": "Real text."}, 1.0)
    assert score["unsupportedClaims"] == 1
