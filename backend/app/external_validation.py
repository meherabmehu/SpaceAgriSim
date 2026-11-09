"""External validation status for the lettuce model, plus the one check that can be run today.

The screening artifact records what each candidate source publishes and why it is or is not usable.
Only one part of that is executable: whether the model's own applicability domain refuses a source
that sits outside it. That check runs here, against the live model, so the page cannot claim a
refusal the API does not actually perform.
"""

from __future__ import annotations

import json
from functools import lru_cache

from app.research import DATA, load_model

SCREEN = DATA / "literature" / "external_validation_screen.json"
MODEL_ID = "lettuce-earth-growth-v2"
# The refused candidate's own reported conditions, transcribed in the screening artifact.
OUT_OF_DOMAIN_POINT = {"daysAfterTransplant": 28.0, "airTemperature": 17.0,
                       "rootTemperature": 17.0, "ppfd": 400.0}


@lru_cache(maxsize=1)
def _screen() -> dict | None:
    if not SCREEN.is_file():
        return None
    return json.loads(SCREEN.read_text())


def _domain_check() -> dict:
    """Ask the served model whether it will answer the out-of-domain point.

    The refusal has to come from the model's declared domain, not from a copy of it kept here,
    otherwise this panel could keep saying "refused" after the domain was widened.
    """
    try:
        model = load_model(MODEL_ID)
    except (KeyError, FileNotFoundError, ValueError) as exc:
        return {"available": False, "reason": f"model artifact unavailable ({type(exc).__name__})"}
    domain = model.get("domain", {})
    violations = []
    for feature, value in OUT_OF_DOMAIN_POINT.items():
        bounds = domain.get(feature)
        if not bounds:
            continue
        if value < bounds["min"] or value > bounds["max"]:
            violations.append({"feature": feature, "value": value,
                               "domain": [bounds["min"], bounds["max"]]})
    return {
        "available": True,
        "modelId": MODEL_ID,
        "point": OUT_OF_DOMAIN_POINT,
        "flaggedOutOfDistribution": bool(violations),
        "violations": violations,
        "means": ("The served model's declared domain excludes this source. A caller still gets a "
                  "number, but the response is flagged outOfDistribution with the violated bounds "
                  "attached, so it cannot be read as a validated prediction. Flagging is correct "
                  "behaviour; it is not evidence about accuracy."),
    }


def payload() -> dict:
    screen = _screen()
    if screen is None:
        return {
            "available": False,
            "reason": "data/literature/external_validation_screen.json is not in this deployment",
            "domainCheck": _domain_check(),
        }
    return {
        "available": True,
        "schema": screen.get("schema"),
        "requirement": screen.get("requirement", {}),
        "trainingSource": screen.get("trainingSource", {}),
        "candidates": screen.get("candidates", []),
        "conclusion": screen.get("conclusion", {}),
        "domainCheck": _domain_check(),
        "scopeNote": ("Screening of candidate external sources for the lettuce model. A candidate "
                      "is only usable when all four model inputs are reported per observation; "
                      "study averages are not substituted for them."),
    }
