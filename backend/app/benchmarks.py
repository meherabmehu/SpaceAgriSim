"""The measured-versus-modelled numbers, assembled in one place for the UI.

Everything here is read from artifacts that were produced by scripts, not typed into this file:

* `data/derived/bpc_benchmark.json` - NASA TM 102788 Biomass Production Chamber measurements
  held against the simulator under the chamber's own operating point (Phase 16).
* the leafy-green planning anchor derived from NTRS 20250001897 (Phase 18), which lives inside
  the same artifact.
* `co2_factor` from the live model, evaluated at three concentrations, so the CO2 panel can never
  disagree with the code that produces the number.

The one thing this module deliberately does not do is rank the numbers. They come from different
questions - a wheat gas-exchange campaign, a leafy-microgreen planning figure, and three crop
models - and a table that sorted them would imply a comparison that does not exist.
"""

from __future__ import annotations

import json
from functools import lru_cache

from app.research import DATA
from app.config import simulation_constants as constants
from app.simulation.factors import co2_factor

BPC_BENCHMARK = DATA / "derived" / "bpc_benchmark.json"
CO2_POINTS = (420.0, 1000.0, 3000.0)


@lru_cache(maxsize=1)
def _artifact() -> dict | None:
    if not BPC_BENCHMARK.is_file():
        return None
    return json.loads(BPC_BENCHMARK.read_text())


def co2_response() -> dict:
    """The CO2 growth factor the model actually applies, at reference concentrations.

    The factor is evaluated by calling the model, so this panel cannot drift from the engine.
    The measured optimum is reported next to it because the factor keeps rising above it while
    the published soybean data do not - a limitation, not something to smooth over.
    """
    points = [{"ppm": ppm, "factor": round(co2_factor(ppm), 3),
               "relativeToAmbient": round(co2_factor(ppm) / co2_factor(constants.EARTH_AMBIENT_CO2_PPM), 3)}
              for ppm in CO2_POINTS]
    return {
        "points": points,
        "ambientPpm": constants.EARTH_AMBIENT_CO2_PPM,
        "measuredOptimumPpm": constants.CO2_MEASURED_OPTIMUM_PPM,
        "form": "factor = c / (c + 150), normalised to ambient",
        "limitation": (
            f"Above {constants.CO2_MEASURED_OPTIMUM_PPM:.0f} ppm the factor still rises, but the "
            "published soybean chamber data show a supraoptimal response at higher CO2. The model "
            "warns at runtime instead of pretending the curve bends; the factor was deliberately "
            "not bent to fit a four-point abstract."),
        "evidenceStatus": "the curve is a model assumption; only the optimum is measured",
    }


def payload() -> dict:
    artifact = _artifact()
    benchmarks: dict = {"co2": co2_response()}

    if artifact is None:
        benchmarks["bpc"] = None
        benchmarks["leafyAnchor"] = None
        benchmarks["availability"] = {
            "available": False,
            "reason": "data/derived/bpc_benchmark.json is not present in this deployment",
            "howToRebuild": "python scripts/benchmark_bpc_vs_simulation.py",
        }
    else:
        benchmarks["bpc"] = {
            "measured": artifact.get("measured", {}),
            "simulated": artifact.get("simulated", {}),
            "ratios": artifact.get("ratios", {}),
            "source": artifact.get("measured_source", {}),
            "caveats": artifact.get("caveats", []),
            "purpose": artifact.get("purpose", ""),
        }
        benchmarks["leafyAnchor"] = artifact.get("leafy_anchor")
        benchmarks["freshProductivity"] = artifact.get("fresh_productivity", {})
        benchmarks["availability"] = {"available": True, "artifact": str(BPC_BENCHMARK.name)}

    return {
        "schema": "spaceagrisim.benchmarks/1",
        "benchmarks": benchmarks,
        "reading": [
            "Nothing in these tables was used to tune the simulator; they are held against it.",
            "The BPC grew wheat to grain. The simulator models lettuce, tomato and radish, so the "
            "per-area comparison answers 'is the model on the right order of magnitude?' and not "
            "'is the crop model validated?'.",
            "The leafy-green anchor is planning arithmetic from a NASA reference document, not a "
            "harvest record.",
            "CO2 factor values are evaluated by the model at request time; only the optimum is "
            "measured.",
        ],
        "disclaimer": "Exploratory estimates and quoted measurements; not a validated model.",
    }
