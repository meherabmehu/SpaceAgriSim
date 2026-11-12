"""Calibrate and audit the deterministic simulation against measured NASA data.

Two distinct jobs, deliberately kept apart:

  1. CALIBRATION  -- compare each crop's `harvest_biomass_g` baseline (edible
     fresh biomass per m^2 per cycle) against genuinely measured values, and
     assign an explicit evidence level. Where no comparable measurement exists
     the parameter stays a documented assumption; it is never "calibrated"
     against a number that does not measure the same thing.

  2. INVARIANTS   -- verify dimensional consistency and mass balance of the
     engine over a parameter sweep.

Normalisation rules (these are the crux; state them or the comparison is junk):
  * `harvest_biomass_g` is per SQUARE METRE per SINGLE CYCLE.
  * EDEN ISS `meanEdibleFreshweightKgM2` is CUMULATIVE across the whole
    experiment phase, whose duration differs by crop.
  * Therefore an EDEN ISS value may only be compared to a cycle baseline when
    the recorded harvest age is close to one cycle length. Otherwise it is
    normalised by the ratio of recorded age to cycle length, and that
    normalisation is flagged as an assumption, not a measurement.

Run: python scripts/calibrate_simulation.py
Output: docs/phase6/simulation_calibration
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
sys.path.insert(0, str(ROOT / "backend"))

from app.config import simulation_constants as constants  # noqa: E402
from app.simulation.crops import get_crop, list_crops  # noqa: E402
from app.simulation import engine, factors, gas_exchange, growth, water  # noqa: E402

OUT = ROOT / "docs" / "phase6" / "simulation_calibration"
EDEN = ROOT / "data" / "processed" / "eden_iss_2018_biomass_summary.csv"


def eden_by_crop() -> dict[str, list[dict]]:
    frame = pd.read_csv(EDEN)
    groups = {"lettuce": [], "tomato": [], "radish": [], "mizuna": []}
    for _, row in frame.iterrows():
        name = str(row["sourceSample"])
        record = {
            "sourceSample": name,
            "harvestAgeDays": float(row["harvestAgeDays"]),
            "meanEdibleFreshweightKgM2": float(row["meanEdibleFreshweightKgM2"]),
        }
        if "Lettuce" in name:
            groups["lettuce"].append(record)
        elif "Tomato" in name:
            groups["tomato"].append(record)
        elif "Radish" in name:
            groups["radish"].append(record)
        elif "Mizuna" in name:
            groups["mizuna"].append(record)
    return groups


def calibrate(measured: dict[str, list[dict]]) -> dict:
    results = {}
    for crop in list_crops():
        rows = measured.get(crop.key, [])
        baseline_kg = crop.harvest_biomass_g / 1000.0
        entry = {
            "crop": crop.key,
            "currentBaselineKgPerM2": baseline_kg,
            "currentCycleDays": crop.growth_duration_days,
            "source": "NASA OSDR OSD-895 EDEN ISS 2018 biomass summary (PDF-derived table)",
            "measurements": rows,
        }
        if not rows:
            entry |= {
                "evidenceLevel": "assumption-only",
                "decision": "retained",
                "reason": "No measured edible fresh mass per m^2 exists for this crop in the acquired NASA data.",
            }
            results[crop.key] = entry
            continue

        ages = np.array([r["harvestAgeDays"] for r in rows])
        values = np.array([r["meanEdibleFreshweightKgM2"] for r in rows])
        # A measurement is cycle-comparable when its harvest age is within 25% of
        # one simulator cycle.
        comparable = np.abs(ages - crop.growth_duration_days) <= 0.25 * crop.growth_duration_days
        entry["comparableMeasurements"] = int(comparable.sum())
        if comparable.any():
            lo, hi = float(values[comparable].min()), float(values[comparable].max())
            mean = float(values[comparable].mean())
            inside = lo <= baseline_kg <= hi
            entry |= {
                "evidenceLevel": "measured-comparable",
                "measuredRangeKgPerM2": [lo, hi],
                "measuredMeanKgPerM2": mean,
                "measuredN": int(comparable.sum()),
                "baselineWithinMeasuredRange": bool(inside),
                "baselineVsMeasuredMeanPercent": float((baseline_kg - mean) / mean * 100.0),
                "decision": "retained-within-measured-range" if inside else "flagged",
                "normalisation": "direct cycle comparison (harvest age within 25% of one simulator cycle)",
            }
        else:
            # Normalise by age ratio. This is an ASSUMPTION of linear accumulation
            # and is recorded as such.
            ratio = crop.growth_duration_days / ages
            normalised = values * ratio
            lo, hi = float(normalised.min()), float(normalised.max())
            mean = float(normalised.mean())
            inside = lo <= baseline_kg <= hi
            entry |= {
                "evidenceLevel": "measured-normalised-assumption",
                "measuredRangeKgPerM2": [lo, hi],
                "measuredMeanKgPerM2": mean,
                "measuredN": int(len(rows)),
                "baselineWithinMeasuredRange": bool(inside),
                "baselineVsMeasuredMeanPercent": float((baseline_kg - mean) / mean * 100.0),
                "decision": "retained-within-measured-range" if inside else "flagged",
                "normalisation": (
                    "values were scaled by cycleDays/harvestAgeDays assuming linear "
                    "cumulative accumulation across multiple harvests. This is an "
                    "ASSUMPTION, not a measured per-cycle figure, so the comparison "
                    "supports plausibility only and is NOT a calibration target."
                ),
            }
        if entry.get("decision") == "flagged":
            # A suggested value is recorded but NOT applied: changing
            # CROP_BASELINES alters numbers shown in the existing UI, so
            # promotion requires explicit owner approval. n is also very small.
            entry["suggestedCalibratedKgPerM2"] = entry["measuredMeanKgPerM2"]
            entry["suggestionStatus"] = (
                "proposed, NOT applied - requires owner approval because it changes "
                "user-visible simulator output, and the supporting n is 2"
            )
        results[crop.key] = entry
    return results


def invariants() -> dict:
    """Dimensional consistency and mass-balance checks across a parameter sweep."""
    checks = []
    failures = []

    def record(name, ok, detail):
        checks.append({"check": name, "passed": bool(ok), "detail": detail})
        if not ok:
            failures.append(name)

    for crop in list_crops():
        for days in (7, 30, 35, 60, 90):
            for area in (0.1, 1.0, 10.0):
                params = engine.SimulationInput(
                    crop=crop.key, gravity=0.38, radiation=0.3,
                    water_availability=70.0, light_hours=16.0, co2_level=1000.0,
                    simulation_days=days, growing_area=area,
                )
                result = engine.run_simulation(params)
                tag = f"{crop.key}/d{days}/a{area}"

                for scenario in (result.space, result.earth):
                    gp = scenario.daily_growth
                    wp = scenario.daily_water
                    label = f"{tag}/{scenario.label}"

                    record(f"growth non-negative [{label}]",
                           all(p.biomass_g >= -1e-9 for p in gp),
                           "all daily standing biomass >= 0")
                    # The always-true identity uses the pre-harvest cut-off on
                    # harvest days; see DailyGrowthPoint's docstring.
                    record(f"mass balance: cumulative = harvested-prior + standing [{label}]",
                           all(abs(p.mass_balance_residual_g) < 1e-6 for p in gp),
                           "production identity holds for every simulated day")
                    record(f"post-harvest standing is zero on harvest days [{label}]",
                           all(p.post_harvest_standing_g == 0.0 for p in gp if p.is_harvest_day),
                           "the crop is cut at the end of a harvest day")
                    record(f"post-harvest standing equals standing on other days [{label}]",
                           all(abs(p.post_harvest_standing_g - p.biomass_g) < 1e-9
                               for p in gp if not p.is_harvest_day),
                           "no biomass is removed on non-harvest days")
                    record(f"standing non-decreasing within a cycle [{label}]",
                           all(gp[i].biomass_g <= gp[i + 1].biomass_g + 1e-6
                               for i in range(len(gp) - 1)
                               if gp[i].cycle == gp[i + 1].cycle),
                           "logistic curve is monotone inside one crop cycle")
                    record(f"harvest only on cycle end [{label}]",
                           all((p.day_in_cycle == crop.growth_duration_days) == p.is_harvest_day
                               for p in gp if p.day > 0),
                           "is_harvest_day iff the cycle boundary is reached")

                    record(f"deficit >= 0 [{label}]",
                           all(p.water_deficit_l >= -1e-9 for p in wp),
                           "no negative water deficit")
                    record(f"supplied <= demand [{label}]",
                           all(p.water_used_l <= p.water_demand_l + 1e-9 for p in wp),
                           "supply cannot exceed demand")
                    record(f"recovered <= supplied [{label}]",
                           all(p.water_recovered_l <= p.water_used_l + 1e-9 for p in wp),
                           "recovery cannot exceed supply")
                    record(f"demand + deficit = supply + deficit consistency [{label}]",
                           all(abs((p.water_demand_l - p.water_deficit_l) - p.water_used_l) < 1e-9
                               for p in wp),
                           "demand - deficit == supplied on every day")

                    record(f"zero water at planting [{label}]",
                           wp[0].water_demand_l == 0.0 if wp else True,
                           "day 0 has no transpiration demand")

                    # Carbon mass balance for the gas exchange module.
                    if scenario.o2_produced_g > 0 and scenario.co2_removed_g > 0:
                        ratio = scenario.o2_produced_g / scenario.co2_removed_g
                        record(f"O2/CO2 stoichiometry [{label}]",
                               abs(ratio - constants.O2_PER_CO2_MASS_RATIO) < 1e-6,
                               f"O2:CO2 = {ratio:.6f}, expected {constants.O2_PER_CO2_MASS_RATIO:.6f} "
                               "(32/44 by photosynthesis stoichiometry)")
                    record(f"harvested + standing = crop yield [{label}]",
                           abs((scenario.harvested_yield_g + scenario.standing_biomass_g)
                               - scenario.crop_yield_g) < 1e-6,
                           "summary totals reconcile")

    return {
        "checksRun": len(checks),
        "failures": failures,
        "allPassed": not failures,
        "checks": checks,
    }


def main() -> int:
    measured = eden_by_crop()
    calibration = calibrate(measured)
    invariant_report = invariants()

    payload = {
        "source": "NASA OSDR OSD-895 EDEN ISS 2018 biomass summary",
        "sourceCaveat": (
            "OSD-895 ships only a PDF (fpls-11-00656.pdf). The CSV used here is a "
            "manual transcription of a table in that paper, not a machine-readable "
            "NASA dataset. Values are EDEN ISS terrestrial-analogue (Antarctic) "
            "greenhouse results, not ISS or lunar/Martian measurements."
        ),
        "normalisationPolicy": (
            "harvest_biomass_g is edible fresh biomass per m^2 per cycle. EDEN ISS "
            "values are cumulative across a phase of differing length. Direct "
            "comparison only when harvest age is within 25% of one cycle; otherwise "
            "age-normalised with a stated linear-accumulation assumption."
        ),
        "calibration": calibration,
        "invariants": invariant_report,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    safedata.dump(payload, OUT)

    print("=" * 78)
    print("CROP CALIBRATION vs EDEN ISS MEASURED EDIBLE FRESH MASS")
    print("=" * 78)
    for key, entry in calibration.items():
        print(f"\n{key}: baseline {entry['currentBaselineKgPerM2']:.3f} kg/m2 "
              f"over {entry['currentCycleDays']} d")
        print(f"  evidence level : {entry['evidenceLevel']}")
        print(f"  decision       : {entry['decision']}")
        if "measuredRangeKgPerM2" in entry:
            lo, hi = entry["measuredRangeKgPerM2"]
            print(f"  measured range : {lo:.2f} - {hi:.2f} kg/m2 (n={entry['measuredN']})")
            print(f"  baseline in range: {entry['baselineWithinMeasuredRange']}  "
                  f"({entry['baselineVsMeasuredMeanPercent']:+.1f}% vs mean)")
        else:
            print(f"  reason         : {entry['reason']}")
    print()
    print("=" * 78)
    print(f"INVARIANTS: {invariant_report['checksRun']} checks, "
          f"allPassed={invariant_report['allPassed']}")
    if invariant_report["failures"]:
        for name in invariant_report["failures"][:20]:
            print("  FAIL:", name)
    print("=" * 78)
    print(f"written: {OUT.relative_to(ROOT)}")
    return 0 if invariant_report["allPassed"] else 1


if __name__ == "__main__":
    sys.exit(main())
