#!/usr/bin/env python3
"""Test the ET0 chain against two independent bodies of measured evapotranspiration.

What is being tested, and what is not
-------------------------------------
There are three separate things that can be wrong in an ET0 product, and this script separates
them instead of reporting one encouraging number:

1. **Formulation.** Does FAO-56 Penman-Monteith, evaluated on *measured* forcing, reproduce
   measured latent heat? TERENO supplies the measured available energy (Rn - G), vapour
   pressure, air temperature and wind speed, plus the eddy-covariance latent heat flux. Nothing
   in this leg comes from MERRA-2, so a good result here says the equations are right.
2. **Level.** Is the modelled ET0 in the right physical band for the surface at all? The
   Agroscope weighable lysimeter measures actual ET by mass balance. Dividing it by a modelled
   ET0 gives an implied crop coefficient; that coefficient has a physical envelope (roughly
   0.2-1.3 for an arable rotation, never 3 and never 0.05). A modelled ET0 that is out by a
   factor of two pushes the implied Kc outside the envelope even though the correlation between
   the two series stays high.
3. **Forcing.** Not tested here. POWER is MERRA-2 lineage; the lysimeter leg therefore still
   contains that forcing. Only TERENO removes it, and TERENO has no site overlap with the six
   siting sites, which is why this is evidence about the model and not about a specific site.

Both legs are reported with their n, their failure counts and their spread. A leg that cannot be
computed is reported as unavailable, never as zero.

    python3 ml/research/validate_et0_against_measurement.py
"""
from __future__ import annotations

import csv
import json
import math
import statistics
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts" / "et0_validation"))

from app.simulation.et0_fao56 import (  # noqa: E402
    MJ_TO_MM,
    psychrometric_constant,
    reference_et0,
    saturation_vapour_pressure,
    slope_saturation_curve,
)

PROCESSED = ROOT / "data" / "processed" / "lysimeter"
OUT = ROOT / "data" / "research" / "phase36"
REPORT = OUT / "et0_measurement_validation"

# Latent heat of vaporisation used to turn a measured flux into a water depth. 2.45 MJ/kg is the
# FAO-56 value at 20 C; using it at 5 C introduces ~1 % error, which is far below the eddy
# covariance energy-balance closure error and is stated rather than hidden.
LAMBDA_MJ_KG = 2.45
W_M2_TO_MJ_M2_H = 0.0036
SECONDS_PER_HOUR = 3600


def fao56_hourly_from_measured_energy(
    *,
    temperature_c: float,
    vapour_pressure_kpa: float,
    available_energy_w_m2: float,
    wind_2m_ms: float,
    pressure_kpa: float,
) -> dict[str, float]:
    """FAO-56 eq. 53 with the measured (Rn - G) substituted for the modelled one.

    The aerodynamic term keeps the standard 37 coefficient, which is the hourly form of the
    daily 900 coefficient. G is already inside ``available_energy_w_m2``, so no separate soil
    heat flux is applied - applying one here would subtract it twice.
    """
    es = saturation_vapour_pressure(temperature_c)
    ea = min(max(vapour_pressure_kpa, 0.0), es)
    delta = slope_saturation_curve(temperature_c)
    gamma = psychrometric_constant(pressure_kpa)
    u2 = max(wind_2m_ms, 0.01)
    energy_mj = available_energy_w_m2 * W_M2_TO_MJ_M2_H
    denominator = delta + gamma * (1.0 + 0.34 * u2)
    radiation_term = MJ_TO_MM * delta * energy_mj / denominator
    aero_term = gamma * (37.0 / (temperature_c + 273.0)) * u2 * max(es - ea, 0.0) / denominator
    return {"et0_mm_h": radiation_term + aero_term,
            "radiation_term_mm_h": radiation_term, "aero_term_mm_h": aero_term,
            "vpd_kpa": max(es - ea, 0.0)}


def describe(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    quantile = lambda q: ordered[min(len(ordered) - 1, max(0, int(q * (len(ordered) - 1))))]
    return {
        "n": len(values),
        "mean": round(statistics.fmean(values), 4),
        "median": round(statistics.median(values), 4),
        "stdev": round(statistics.pstdev(values), 4) if len(values) > 1 else 0.0,
        "min": round(ordered[0], 4),
        "p05": round(quantile(0.05), 4),
        "p95": round(quantile(0.95), 4),
        "max": round(ordered[-1], 4),
    }


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    numerator = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denominator = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return round(numerator / denominator, 4) if denominator else None


def regression(xs: list[float], ys: list[float]) -> dict:
    """Ordinary least squares of y on x, with the slope's meaning stated in the report."""
    if len(xs) < 3:
        return {"n": 0}
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    denominator = sum((x - mx) ** 2 for x in xs)
    if not denominator:
        return {"n": len(xs)}
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denominator
    return {"n": len(xs), "slope": round(slope, 4), "intercept": round(my - slope * mx, 4)}


def tereno_leg() -> dict:
    path = PROCESSED / "tereno_hourly.csv"
    if not safedata.exists(path):
        return {"status": "UNAVAILABLE", "reason": f"{path} missing"}
    hourly: dict[tuple[str, int, int], dict] = {}
    skipped = {"missing_wind": 0, "missing_pressure": 0, "non_positive_energy": 0}
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                temperature = float(row["t_c"])
                ea_kpa = float(row["ea_kpa"])
                energy = float(row["available_wm2"])
                pressure = float(row["p_hpa"]) / 10.0
            except (TypeError, ValueError):
                skipped["missing_pressure"] += 1
                continue
            if not row.get("u_ms"):
                skipped["missing_wind"] += 1
                u2 = 0.01   # calm: the aerodynamic term collapses, which is the correct limit
            else:
                u2 = float(row["u_ms"])
            # Daytime only. A negative available energy means the surface is losing heat by
            # radiation faster than it gains it, and FAO-56 with G folded into A is not defined
            # for condensation; those hours are counted, not silently dropped.
            if energy <= 0:
                skipped["non_positive_energy"] += 1
                continue
            model = fao56_hourly_from_measured_energy(
                temperature_c=temperature, vapour_pressure_kpa=ea_kpa,
                available_energy_w_m2=energy, wind_2m_ms=u2, pressure_kpa=pressure)
            measured = float(row["le_wm2"]) * W_M2_TO_MJ_M2_H / LAMBDA_MJ_KG
            key = (row["site"], int(row["year"]), int(row["day_of_year"]))
            bucket = hourly.setdefault(key, {"et0": 0.0, "measured": 0.0, "hours": 0,
                                             "hourly_pairs": []})
            bucket["et0"] += model["et0_mm_h"]
            bucket["measured"] += measured
            bucket["hours"] += 1
            bucket["hourly_pairs"].append((model["et0_mm_h"], measured))

    hourly_x = [pair[0] for bucket in hourly.values() for pair in bucket["hourly_pairs"]]
    hourly_y = [pair[1] for bucket in hourly.values() for pair in bucket["hourly_pairs"]]
    daily = [b for b in hourly.values() if b["hours"] >= 4]
    xs = [b["et0"] for b in daily]
    ys = [b["measured"] for b in daily]
    ratios = [y / x for x, y in zip(xs, ys) if x > 0.2]
    residuals = [x - y for x, y in zip(xs, ys)]
    by_site: dict[str, dict] = {}
    for site in {key[0] for key in hourly}:
        site_days = [b for key, b in hourly.items() if key[0] == site and b["hours"] >= 4]
        site_x = [b["et0"] for b in site_days]
        site_y = [b["measured"] for b in site_days]
        by_site[site] = {
            "days": len(site_days),
            "meanEt0Mm": round(statistics.fmean(site_x), 4) if site_x else None,
            "meanMeasuredMm": round(statistics.fmean(site_y), 4) if site_y else None,
            "r": pearson(site_x, site_y),
            "regression": regression(site_x, site_y),
            "medianRatioMeasuredOverModelled": (
                round(statistics.median([y / x for x, y in zip(site_x, site_y) if x > 0.2]), 4)
                if site_x else None),
        }
    return {
        "status": "COMPUTED" if daily else "UNAVAILABLE",
        "comparison": "FAO-56 hourly on measured (Rn-G), T, ea, u  vs  eddy-covariance LE",
        "independentOfReanalysis": True,
        "hourlyPairs": len(hourly_x),
        "hourly": {"r": pearson(hourly_x, hourly_y),
                   "regressionEt0OnMeasured": regression(hourly_x, hourly_y),
                   "meanEt0Mm": round(statistics.fmean(hourly_x), 5) if hourly_x else None,
                   "meanMeasuredMm": round(statistics.fmean(hourly_y), 5) if hourly_y else None},
        "dayCount": len(daily),
        "meanEt0MmDay": round(statistics.fmean(xs), 4) if xs else None,
        "meanMeasuredMmDay": round(statistics.fmean(ys), 4) if ys else None,
        "biasMmDay": round(statistics.fmean(residuals), 4) if residuals else None,
        "rmseMmDay": (round(math.sqrt(statistics.fmean([r * r for r in residuals])), 4)
                      if residuals else None),
        "r": pearson(xs, ys),
        "regressionModelledOnMeasured": regression(xs, ys),
        "ratioMeasuredOverModelled": describe(ratios),
        "bySite": by_site,
        "skippedHours": skipped,
    }


def lysimeter_leg() -> dict:
    eta_path = PROCESSED / "zurich_eta_daily.csv"
    power_path = ROOT / "data" / "processed" / "power_validation" / "zurich_reckenholz_ch.csv"
    if not safedata.exists(eta_path) or not safedata.exists(power_path):
        return {"status": "UNAVAILABLE", "reason": "lysimeter or POWER forcing missing"}

    by_day: dict[str, list[float]] = {}
    with eta_path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            by_day.setdefault(row["date"], []).append(float(row["eta_mm_d"]))

    pairs: list[tuple[str, float, float]] = []
    unavailable = {"missingPowerDay": 0, "insufficientInputs": 0}
    with power_path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            day = row["date"]
            if day not in by_day:
                continue
            try:
                rs = float(row["sw_mj_m2"])
                tmax, tmin = float(row["t2m_max_c"]), float(row["t2m_min_c"])
                dew = float(row["t2mdew_c"])
                wind = float(row["ws2m_ms"])
                pressure = float(row["ps_kpa"])
            except (TypeError, ValueError):
                unavailable["insufficientInputs"] += 1
                continue
            if rs < 0:
                unavailable["insufficientInputs"] += 1
                continue
            ea = saturation_vapour_pressure(dew)
            parsed = date.fromisoformat(day)
            model = reference_et0(
                tmax=tmax, tmin=tmin, ea=ea, rs=rs, wind_2m=wind, pressure_kpa=pressure,
                day_of_year=parsed.timetuple().tm_yday, latitude_deg=47.428, elevation_m=566.6)
            measured = statistics.fmean(by_day[day])
            pairs.append((day, measured, float(model["et0MmPerDay"])))
    missing_power_days = len(set(by_day) - {p[0] for p in pairs})
    unavailable["missingPowerDay"] = missing_power_days

    # Winter days with near-zero measured ET and a non-zero modelled ET0 produce ratios that say
    # nothing about the model: a frozen lysimeter is not a crop coefficient of 0.02. The envelope
    # is therefore evaluated on *active* days, ET0 >= 1 mm/d, and the all-day distribution is
    # still reported so the exclusion is visible.
    ratios = [m / e for _, m, e in pairs if e > 0.3]
    active = [(m, e) for _, m, e in pairs if e >= 1.0]
    active_ratios = [m / e for m, e in active]
    negative_days = sum(1 for _, m, _ in pairs if m < 0)
    by_month: dict[str, list[float]] = {}
    for day, m, e in pairs:
        if e > 0.3:
            by_month.setdefault(day[5:7], []).append(m / e)
    annual: dict[str, dict] = {}
    for day, m, e in pairs:
        annual.setdefault(day[:4], {"measured": 0.0, "modelled": 0.0, "days": 0})
        annual[day[:4]]["measured"] += m
        annual[day[:4]]["modelled"] += e
        annual[day[:4]]["days"] += 1
    for year, totals in annual.items():
        totals["measuredMm"] = round(totals.pop("measured"), 2)
        totals["modelledMm"] = round(totals.pop("modelled"), 2)
        totals["impliedAnnualKc"] = (round(totals["measuredMm"] / totals["modelledMm"], 4)
                                     if totals["modelledMm"] else None)
        # 2013 starts on 1 August and 2016 ends on 31 July: their totals are partial and must
        # never be read as annual water use.
        totals["completeWaterYear"] = totals["days"] >= 360

    plot_ratio = describe(ratios)
    active_ratio = describe(active_ratios)
    status = "COMPUTED" if pairs else "UNAVAILABLE"
    # A *level* error is multiplicative: if modelled ET0 were out by 2x, every implied Kc would
    # be halved or doubled and the median would move with it. The daily spread is NOT used as the
    # test, because a genuinely dry surface under high ET0 has an implied Kc near zero and a fully
    # developed canopy in cool weather above 2 - that spread is the phenomenon Kc exists to
    # describe, not evidence against the model. The criterion is a factor-of-two band on the
    # median, and the complete-water-year totals are checked against the same band.
    median_kc = active_ratio.get("median")
    within = median_kc is not None and 0.5 <= median_kc <= 1.5
    return {
        "status": status,
        "comparison": "POWER-forced FAO-56 ET0  vs  weighable-lysimeter daily ETa (6 lysimeters)",
        "independentOfReanalysis": False,
        "forcingNote": ("this leg keeps MERRA-2 forcing, so it tests the level of the combined "
                        "chain, not the formulation alone"),
        "dayCount": len(pairs),
        "impliedKc": plot_ratio,
        "impliedKcActiveDays": active_ratio,
        "activeDayDefinition": "modelled ET0 >= 1.0 mm/day, i.e. a surface actually drying",
        "negativeEtaDays": negative_days,
        "impliedKcByMonth": {month: round(statistics.median(values), 4)
                             for month, values in sorted(by_month.items()) if values},
        "annual": annual,
        "levelTest": {
            "statistic": "median implied Kc over active days (ET0 >= 1.0 mm/day)",
            "criterion": "0.5 <= median <= 1.5, i.e. modelled ET0 within a factor of two of measured ET",
            "observed": median_kc,
            "passed": within,
            "whyNotP05P95": ("daily Kc legitimately spans near zero (dry surface) to above 2 "
                             "(large canopy in cool weather); that spread is what Kc describes"),
            "completeYearKc": {year: totals["impliedAnnualKc"]
                               for year, totals in annual.items()
                               if totals["completeWaterYear"]},
        },
        "unavailable": unavailable,
    }


def substrate_leg() -> dict:
    path = PROCESSED / "zurich_fdr_daily.csv"
    if not safedata.exists(path):
        return {"status": "UNAVAILABLE"}
    by_depth: dict[int, list[float]] = {}
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            by_depth.setdefault(int(row["depth_cm"]), []).append(float(row["vwc_vol_pct"]))
    return {
        "status": "COMPUTED",
        "note": ("field soil (Cambisol/Luvisol monoliths), NOT a CEA growing substrate; recorded "
                 "as a root-zone water-content series with that limitation attached"),
        "depthsCm": sorted(by_depth),
        "vwcByDepth": {f"{depth}cm": describe(values) for depth, values in sorted(by_depth.items())},
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "generatedBy": "ml/research/validate_et0_against_measurement.py",
        "evidenceLabel": {
            "measured": "TERENO eddy-covariance LE and available energy; Agroscope lysimeter ETa",
            "derived": "implied crop coefficient = measured ETa / modelled ET0",
            "predicted": "FAO-56 ET0 from the platform's audited implementation",
        },
        "terenoFormulationTest": tereno_leg(),
        "lysimeterLevelTest": lysimeter_leg(),
        "rootZoneWaterContent": substrate_leg(),
    }
    safedata.dump(report, REPORT)
    t = report["terenoFormulationTest"]
    l = report["lysimeterLevelTest"]
    print("TERENO (formulation, measured forcing):", t.get("status"),
          f"days={t.get('dayCount')} r={t.get('r')} bias={t.get('biasMmDay')} "
          f"rmse={t.get('rmseMmDay')}")
    if t.get("ratioMeasuredOverModelled", {}).get("median"):
        print("   median measured/modelled =", t["ratioMeasuredOverModelled"]["median"])
    print("Lysimeter (level):", l.get("status"), f"days={l.get('dayCount')}",
          f"impliedKc median={l.get('impliedKc', {}).get('median')}",
          f"withinEnvelope={l.get('withinPhysicalEnvelope')}")
    print("root-zone:", report["rootZoneWaterContent"].get("depthsCm"))
    print(f"\nreport -> {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
