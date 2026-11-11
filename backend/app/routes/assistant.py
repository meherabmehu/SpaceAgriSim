"""Phase 12: the NASA evidence-grounded research assistant API.

Every answer carries citations, an explicit evidence class, and the limitations of what
was retrieved. When the corpus cannot support an answer, the endpoint returns
`status: "insufficient"` with HTTP 200 rather than an error, because "the repository does
not record this" is a correct and useful answer.

Rate limiting for these endpoints is handled by the existing middleware, which already
applies a per-address budget to every `/api` route; the assistant adds a smaller
per-request size bound because a long question is a sign of pasted document content
rather than a question.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app import assistant as assistant_module
from app import evidence, llm

router = APIRouter(tags=["assistant"])


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=evidence.MAX_QUESTION_CHARS)
    maxClaims: int = Field(default=5, ge=1, le=8)
    # Follow-up support: the previous questions, newest last. Only the entity names are borrowed
    # (see reasoning.resolve_followup), so a pronoun-led question keeps its own wording, and the
    # list is bounded so it cannot be used to smuggle a document into the retrieval query.
    context: list[str] = Field(default_factory=list, max_length=2)
    # Narration is opt-in per request and absent by default, so the deterministic answer is the
    # response unless the caller asks for prose. It can only restate claims that already exist.
    explain: bool = False


@router.post("/assistant/ask")
def ask(request: AskRequest):
    """Answer a question from verified repository evidence, with mandatory citations."""
    for previous in request.context:
        if len(previous) > evidence.MAX_QUESTION_CHARS:
            raise HTTPException(422, "Each context question is limited to "
                                     f"{evidence.MAX_QUESTION_CHARS} characters")
    try:
        result = assistant_module.answer(request.question, max_claims=request.maxClaims,
                                         context=request.context)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    payload = result.render()
    if request.explain:
        payload["explanation"] = llm.explain(payload, request.question)
    return payload


@router.get("/assistant/suggestions")
def suggestions():
    return {"suggestions": assistant_module.suggested_questions(),
            "note": ("Generated from the corpus, so a suggestion is only listed when the "
                     "source that answers it is present.")}


@router.get("/assistant/corpus")
def corpus_stats():
    """What the assistant can see. Served so the corpus is auditable, not a black box."""
    return evidence.stats()


@router.get("/assistant/evidence/{passage_id}")
def evidence_detail(passage_id: str):
    """The full text and citation record behind one claim."""
    passage = evidence.passage_by_id(passage_id)
    if passage is None:
        raise HTTPException(404, "Unknown evidence passage")
    return {
        "id": passage.id,
        "kind": passage.kind,
        "title": passage.title,
        "text": passage.text,
        "citation": passage.citation(),
    }


@router.get("/assistant/provider")
def assistant_provider():
    """Whether optional narration is configured. Booleans only - never a key, never a token."""
    config = llm.LLMConfig.from_env()
    return {
        "config": config.describe(),
        "guards": {
            "evidenceOnly": True,
            "citationMarkersPerSentence": True,
            "accessionsValidated": True,
            "quantitiesValidated": True,
            "forbiddenAssertionsBlocked": True,
            "deterministicFallback": True,
        },
        "note": ("A provider may only restate retrieved claims. Its output is rejected and the "
                 "deterministic summary returned if it names an accession or quantity that is "
                 "not in the citations, omits a citation marker, or asserts a validated yield. "
                 "The disabled default is the configuration that was benchmarked."),
    }


@router.get("/assistant/health")
def assistant_health():
    stats = evidence.stats()
    config = llm.LLMConfig.from_env()
    return {
        "status": "ready",
        "mode": "deterministic-extractive",
        "externalModelConfigured": config.enabled,
        "passages": stats["passages"],
        "quarantined": stats["quarantined"],
        "note": ("The assistant answers without any external language model. An optional "
                 "model may rephrase a retrieved answer, but it is never the source of a "
                 "citation and it cannot add evidence."),
    }
