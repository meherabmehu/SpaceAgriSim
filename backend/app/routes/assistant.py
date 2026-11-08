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

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import assistant as assistant_module
from app import evidence
from app.auth import current_user

router = APIRouter(tags=["assistant"])


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=evidence.MAX_QUESTION_CHARS)
    maxClaims: int = Field(default=5, ge=1, le=8)


@router.post("/assistant/ask")
def ask(request: AskRequest):
    """Answer a question from verified repository evidence, with mandatory citations."""
    try:
        result = assistant_module.answer(request.question, max_claims=request.maxClaims)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return result.render()


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


@router.get("/assistant/health")
def assistant_health():
    stats = evidence.stats()
    return {
        "status": "ready",
        "mode": "deterministic-extractive",
        "externalModelConfigured": False,
        "passages": stats["passages"],
        "quarantined": stats["quarantined"],
        "note": ("The assistant answers without any external language model. An optional "
                 "model may rephrase a retrieved answer, but it is never the source of a "
                 "citation and it cannot add evidence."),
    }
