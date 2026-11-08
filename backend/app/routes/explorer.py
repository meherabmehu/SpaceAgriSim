"""Phase 12: dataset explorer endpoints.

Read-only. The explorer's job is to make the independence of a study set explicit, so
these routes report relations rather than a flat accession list.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app import explorer

router = APIRouter(tags=["explorer"])

MAX_SET_ITEMS = 200


class IndependentSetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[str] = Field(min_length=0, max_length=MAX_SET_ITEMS)


@router.get("/explorer/datasets")
def explorer_datasets(q: str = ""):
    rows = explorer.dataset_rows()
    if q:
        needle = q.lower()
        rows = [row for row in rows
                if needle in row["id"].lower()
                or needle in (row["title"] or "").lower()
                or any(needle in organism.lower() for organism in row["organisms"])]
    return {"datasets": rows, "count": len(rows),
            "independentStudyCount": sum(1 for row in rows if row["countsAsIndependentStudy"]),
            "note": ("Accession count is not study count. Redundant deposits are listed so "
                     "the data remains reachable, but they are excluded from independent "
                     "counts.")}


@router.get("/explorer/overlaps")
def explorer_overlaps():
    return explorer.overlaps()


@router.get("/explorer/datasets/{study_id}")
def explorer_dataset(study_id: str):
    rows = {row["id"]: row for row in explorer.dataset_rows()}
    row = rows.get(study_id.upper())
    if row is None:
        raise HTTPException(404, "Unknown dataset")
    relations = [relation for relation in explorer.overlaps()["relations"]
                 if row["id"] in relation["pair"]]
    return {**row, "relations": relations,
            "relationMeaning": explorer.RELATION_MEANING,
            "countsAsIndependentStudy": row["countsAsIndependentStudy"]}


@router.post("/explorer/independent-set")
def explorer_independent_set(request: IndependentSetRequest):
    """Reduce a study list to a defensible independent set before any counting."""
    return explorer.independent_set([item.upper() for item in request.ids])
