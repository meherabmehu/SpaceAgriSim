"""Phase 12: the scientific AI workflow and saved analyses.

Workflow endpoints are public where they only run a served model (matching the existing
prediction endpoints, which are public), and authenticated where they persist something
that belongs to a person. That split is deliberate: a visitor can reproduce a published
result, but only an account can accumulate private research records.
"""
from __future__ import annotations

import csv
import io
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from app import storage, workflow
from app.science_classification import CATEGORY_NAMES
from app.auth import current_user, optional_user
from app.config.settings import settings

router = APIRouter(tags=["workflow"])

# Per-payload ceiling. The per-account quotas in storage are separate and larger; this one exists
# so a single request cannot be used to burn a whole account's allowance in one insert.
MAX_ANALYSIS_BYTES = 200_000


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    modelId: str = Field(min_length=1, max_length=64)
    inputs: dict[str, float] = Field(
        description="Feature name to numeric value. Must match the model schema exactly.")
    save: bool = Field(default=False, description="Persist the analysis to the calling account.")
    title: str | None = Field(default=None, max_length=120)


class CompatibleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    features: list[str] = Field(min_length=1, max_length=30000)


@router.get("/workflow/models")
def workflow_models():
    """Which models can run, what they accept, and what stops them running."""
    return workflow.model_catalogue()


@router.post("/workflow/compatible")
def workflow_compatible(request: CompatibleRequest):
    """Find models that accept a given feature set, so a caller need not know the ids."""
    return {"compatible": workflow.compatible_models(request.features),
            "featureCount": len(request.features)}


@router.post("/workflow/validate")
def workflow_validate(request: RunRequest):
    """Check an input without running inference, so a form can pre-validate."""
    try:
        validated = workflow.validate_input(request.modelId, request.inputs)
    except workflow.WorkflowError as error:
        raise HTTPException(422, {"error": error.code, "message": error.message,
                                  **error.detail}) from error
    except KeyError as error:
        raise HTTPException(404, "Unknown model") from error
    return {"modelId": request.modelId, "valid": True, "checks": validated["checks"],
            "classification": {"category": validated["classification"].category,
                               "categoryName": CATEGORY_NAMES[
                                   validated["classification"].category]}}


@router.post("/workflow/run")
def workflow_run(request: RunRequest, user: dict | None = Depends(optional_user)):
    """Validate, run, interpret, and optionally persist one analysis.

    Anonymous callers can run any served model; only an authenticated caller can save.
    """
    return _run(request, owner=user)


def _run(request: RunRequest, owner: dict | None):
    if request.save and owner is None:
        raise HTTPException(401, "Authentication is required to save an analysis",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        result = workflow.run_model(request.modelId, request.inputs)
    except workflow.WorkflowError as error:
        status = 404 if error.code == "unclassified-model" else 422
        if error.code == "retired-model":
            status = 410
        if error.code == "external-service":
            # 409, not 422: the request is well formed, it is simply addressed to the wrong
            # surface. The message names the endpoint that does serve this model.
            status = 409
        raise HTTPException(status, {"error": error.code, "message": error.message,
                                     **error.detail}) from error
    except KeyError as error:
        raise HTTPException(404, "Unknown model") from error
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(503, "Verified model artifact unavailable") from error

    if request.save and owner is not None:
        payload = json.dumps(result, sort_keys=True)
        if len(payload.encode("utf-8")) > min(MAX_ANALYSIS_BYTES, settings.max_analysis_bytes):
            raise HTTPException(413, "Analysis payload is too large to save")
        title = (request.title or f"{request.modelId} analysis")[:120]
        try:
            row = storage.save_analysis(owner["id"], request.modelId, title, payload)
        except storage.AnalysisQuotaExceeded as error:
            # 413 for a payload that can never be stored, 409 when the account's current state is
            # what refuses the request: the request itself is valid in the second case.
            status = 413 if error.code == "payload-too-large" else 409
            raise HTTPException(status, {"error": error.code, "message": error.message,
                                         **error.detail}) from error
        result["saved"] = {"id": row["id"], "title": title,
                           "createdAt": row["created_at"]}
    else:
        result["saved"] = None
    return result


@router.post("/workflow/run-and-save")
def workflow_run_and_save(request: RunRequest, user: dict = Depends(current_user)):
    """Authenticated variant that always persists the analysis."""
    return _run(request.model_copy(update={"save": True}), user)


@router.get("/analyses")
def list_analyses(limit: int | None = None, offset: int = 0,
                  user: dict = Depends(current_user)):
    """One page of the caller's saved analyses, newest first.

    Pagination is mandatory rather than optional because the list is unbounded in principle: an
    account that has saved for months should not be answered with every row in one response.
    """
    try:
        storage.purge_expired_analyses()
        rows, total, page = storage.list_analyses(user["id"], limit=limit, offset=offset)
    except Exception as exc:
        raise HTTPException(503, "Saved analyses unavailable") from exc
    return {"analyses": [{"id": row["id"], "title": row["title"],
                          "modelId": row["model_id"], "createdAt": row["created_at"]}
                         for row in rows],
            "pagination": page,
            "usage": storage.analysis_usage(user["id"]),
            "note": "Only analyses belonging to the authenticated account are returned."}


@router.delete("/analyses")
def delete_all_analyses(user: dict = Depends(current_user)):
    """Retention: let an account erase its own saved analyses. Never touches another account."""
    try:
        removed = storage.delete_all_analyses(user["id"])
    except Exception as exc:
        raise HTTPException(503, "Saved analyses unavailable") from exc
    return {"deleted": removed, "scope": "authenticated account only"}


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: str, user: dict = Depends(current_user)):
    row = storage.get_analysis(user["id"], analysis_id)
    if row is None:
        # 404 rather than 403 for another account's id, so the API is not an existence oracle.
        raise HTTPException(404, "Analysis not found")
    return {"id": row["id"], "title": row["title"], "modelId": row["model_id"],
            "createdAt": row["created_at"], "analysis": json.loads(row["payload"])}


@router.delete("/analyses/{analysis_id}", status_code=204)
def delete_analysis(analysis_id: str, user: dict = Depends(current_user)):
    if not storage.delete_analysis(user["id"], analysis_id):
        raise HTTPException(404, "Analysis not found")
    return Response(status_code=204)


# Characters that make a spreadsheet treat a cell as a formula rather than as text. A CSV is a
# file a user opens in Excel, LibreOffice or Sheets, and quoting a value does not stop it being
# evaluated - the field delimiter is removed before the cell is parsed. The standard mitigation is
# a leading apostrophe, which the spreadsheet reads as "the rest is literal text".
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _csv_text(value) -> str:
    """A free-text cell that cannot become a formula and does not read as a Python `None`.

    Only applied to text fields (titles, quotations). Numbers keep their exact representation:
    prefixing `-0.5` would turn a measurement into the string `'-0.5`.
    """
    if value is None:
        return ""
    text = str(value)
    return "'" + text if text[:1] in _FORMULA_PREFIXES else text


def _csv_rows(rows: list[list]) -> str:
    """Serialise rows with the `csv` module, so quoting and line breaks are RFC 4180.

    The previous export built its lines with f-strings and wrapped the title in bare quotes, so a
    title containing a quote, a comma or a newline produced a file that no parser can read back:
    `Harvest "best case", review` split into three columns and the remainder of the title became
    its own record. The two `#` attribution lines are single-cell rows by design and survive the
    writer unchanged.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerows(rows)
    return buffer.getvalue()


@router.get("/analyses/{analysis_id}/export/{fmt}")
def export_analysis(analysis_id: str, fmt: Literal["json", "csv", "md"],
                    user: dict = Depends(current_user)):
    """Export one saved analysis. Numbers come from the stored payload, unmodified."""
    row = storage.get_analysis(user["id"], analysis_id)
    if row is None:
        raise HTTPException(404, "Analysis not found")
    analysis = json.loads(row["payload"])
    base = f"spaceagrisim-analysis-{analysis_id[:8]}"

    if fmt == "json":
        body = json.dumps(analysis, indent=2, sort_keys=True)
        media, name = "application/json", f"{base}"
    elif fmt == "csv":
        rows: list[list] = [
            ["# SpaceAgriSim saved AI analysis"],
            ["# Model output and model interpretation only - NOT a measurement"],
            ["field", "value"],
            ["analysis_id", _csv_text(analysis_id)],
            ["title", _csv_text(row["title"])],
            ["model_id", _csv_text(analysis["modelId"])],
            ["created_at", _csv_text(row["created_at"])],
            ["prediction", _csv_text(analysis["output"].get("prediction"))],
            ["output_kind", _csv_text(analysis["output"].get("kind"))],
            ["calibrated", _csv_text(analysis["output"].get("calibrated"))],
            ["category", _csv_text(analysis["scientificClassification"].get("category"))],
        ]
        for name_, value in analysis["inputs"].items():
            rows.append([f"input_{name_}", _csv_text(value)])
        for index, claim in enumerate(analysis["evidence"].get("claims", []), start=1):
            rows.append([f"citation_{index}", _csv_text(claim["text"])])
        body = _csv_rows(rows)
        media, name = "text/csv", f"{base}.csv"
    else:
        evidence = analysis.get("evidence", {})
        rows = [f"# SpaceAgriSim analysis: {row['title']}", "",
                f"- Model: `{analysis['modelId']}`",
                f"- Created: {row['created_at']}",
                f"- Scientific category: {analysis['scientificClassification'].get('category')} "
                f"({analysis['scientificClassification'].get('categoryName')})",
                f"- Output kind: {analysis['output'].get('kind')}",
                f"- Prediction: {analysis['output'].get('prediction')} "
                f"{analysis['output'].get('unit') or ''}",
                f"- Calibrated: {analysis['output'].get('calibrated')}", "",
                "## Interpretation", analysis.get("interpretation", ""), "",
                "## Limitations"]
        rows += [f"- {item}" for item in analysis.get("limitations", [])]
        rows += ["", "## Evidence"]
        for index, claim in enumerate(evidence.get("claims", []), start=1):
            rows.append(f"{index}. {claim['text']}")
        rows += ["", "## Citations"]
        for index, citation in enumerate(evidence.get("citations", []), start=1):
            rows.append(f"{index}. {citation['title']} ({citation['sourceId']}) — "
                        f"{citation['evidenceClass']}")
        rows += ["", "Model output and model interpretation, not a measured plant observation."]
        body = "\n".join(rows) + "\n"
        media, name = "text/markdown", f"{base}.md"

    return Response(body, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{name}"',
                             "Cache-Control": "no-store"})
