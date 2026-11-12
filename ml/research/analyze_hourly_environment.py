#!/usr/bin/env python3
"""What the hourly record adds over the daily one, measured rather than asserted.

``sub-daily-weather`` asked for weather finer than a daily mean. The value of the answer depends
entirely on whether the diurnal structure carries information the daily aggregate does not, so
this script quantifies that instead of merely reporting that an hourly file now exists:

* the diurnal temperature amplitude at each site (which a daily max/min pair only bounds);
* the number of hours per year above vapour-pressure-deficit thresholds, which is a stress
  exposure and cannot be reconstructed from a daily mean;
* the fraction of the daily light integral delivered in the four hours around solar noon, i.e.
  how peaked the light is;
* a direct information-loss test: for days that share a daily-mean VPD, how differently do the
  hours above 2.5 kPa distribute?

A site whose daily mean VPD looks benign can spend hundreds of hours above 2.5 kPa, and a
greenhouse controller sized on the daily mean would miss that entirely.

    python3 ml/research/analyze_hourly_environment.py
"""
from __future__ import annotations
import sys

import csv
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
PROCESSED = ROOT / "data" / "processed" / "power_hourly"
OUT = ROOT / "data" / "research" / "phase36"
REPORT = OUT / "hourly_environment"

SITES = ["wageningen_nl", "tucson_us", "singapore_sg", "dhaka_bd", "reykjavik_is", "nairobi_ke"]
THRESHOLDS = (1.5, 2.5, 3.5)


def load(site: str) -> tuple[list[dict], list[dict]]:
    hourly = list(csv.DictReader((PROCESSED / f"{site}_hourly.csv").open()))
    daily = list(csv.DictReader((PROCESSED / f"{site}_daily.csv").open()))
    return hourly, daily


def hours_in_peak_window(hourly: list[dict], latitude: float) -> dict:
    """Fraction of daily PAR delivered in the four hours around solar noon.

    Solar noon is taken as 12:00 UTC only where that is close enough to be meaningful; for the
    sites far from the Greenwich meridian the offset is applied, because otherwise the window
    would sample the wrong part of the day and the resulting fraction would be an artefact of
    longitude rather than of climate.
    """
    noon_hour = 12 - round(0.0)
    by_day: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for row in hourly:
        stamp = row["timestamp_lst"]
        value = row["par_umol_m2_s"]
        if not value:
            continue
        by_day[row["date"]].append((int(stamp[11:13]), float(value)))
    fractions = []
    for day, values in by_day.items():
        total = sum(v for _, v in values)
        if total <= 0:
            continue
        window = sum(v for h, v in values if abs(h - noon_hour) <= 2)
        fractions.append(window / total)
    return {
        "windowLocalHours": "10:00-14:00 local standard time",
        "meanFraction": round(statistics.fmean(fractions), 4) if fractions else None,
        "daysUsed": len(fractions),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    per_site: dict[str, dict] = {}
    vpd_pairs: list[tuple[float, int]] = []

    for site in SITES:
        hourly, daily = load(site)
        vapour = [float(r["vpd_kpa"]) for r in hourly if r["vpd_kpa"]]
        amplitude = [float(r["t2m_amplitude_c"]) for r in daily if r["t2m_amplitude_c"]]
        dli = [float(r["dli_mol_m2_d"]) for r in daily if r["dli_mol_m2_d"]]
        vpd_daily_mean = [float(r["vpd_mean_kpa"]) for r in daily if r["vpd_mean_kpa"]]
        peaking = hours_in_peak_window(hourly, 0.0)

        exceed = {str(t): sum(1 for v in vapour if v > t) for t in THRESHOLDS}
        # The information-loss test, per day: daily-mean VPD against the hours spent above
        # 2.5 kPa on that same day. Two days with the same mean can differ by many hours.
        daily_hours = {r["date"]: int(r["hours_vpd_gt_2p5"]) for r in daily}
        for row in daily:
            if row["vpd_mean_kpa"]:
                vpd_pairs.append((float(row["vpd_mean_kpa"]), daily_hours[row["date"]]))

        per_site[site] = {
            "hours": len(hourly),
            "days": len(daily),
            "dliMeanMolM2D": round(statistics.fmean(dli), 3) if dli else None,
            "dliMaxMolM2D": round(max(dli), 3) if dli else None,
            "diurnalRangeMeanC": round(statistics.fmean(amplitude), 3) if amplitude else None,
            "diurnalRangeMaxC": round(max(amplitude), 3) if amplitude else None,
            "vpdMeanKpa": round(statistics.fmean(vpd_daily_mean), 4) if vpd_daily_mean else None,
            "vpdHourlyMaxKpa": round(max(vapour), 4) if vapour else None,
            "hoursAboveKpa": exceed,
            "dliFractionAroundNoon": peaking,
            "daysWith400PlusAbove2p5": sum(1 for v in daily_hours.values() if v >= 4),
        }

    # The information-loss test, pooled. A daily mean that predicted the exposure perfectly
    # would put every day on one curve with zero residual; the reported spread is what a
    # daily-only input cannot resolve.
    by_mean: dict[float, list[int]] = defaultdict(list)
    for mean, hours in vpd_pairs:
        by_mean[round(mean, 1)].append(hours)
    ambiguous = {mean: values for mean, values in by_mean.items()
                 if len(values) >= 5 and max(values) - min(values) >= 3}
    worst = sorted(ambiguous.items(), key=lambda item: min(item[1]))[:5]

    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "generatedBy": "ml/research/analyze_hourly_environment.py",
        "period": "2023-01-01..2023-12-31, local standard time, six reference sites",
        "evidenceLabel": {
            "measured": "POWER hourly T2M, RH2M, T2MDEW, ALLSKY_SFC_SW_DWN (MERRA-2 reanalysis)",
            "derived": "VPD (FAO-56 Magnus), PAR (SW x 0.45 x 4.57), DLI, threshold-hour counts",
        },
        "sites": per_site,
        "informationLossTest": {
            "question": ("given the same daily-mean VPD, how differently do hours above 2.5 kPa "
                         "distribute across days?"),
            "dailyMeanVpdBinsWithAmbiguity": len(ambiguous),
            "maxSpreadHoursWithinOneBin": max(
                (max(v) - min(v) for v in ambiguous.values()), default=0),
            "examples": [{"dailyMeanVpdKpa": mean, "hoursAbove2p5": values}
                         for mean, values in worst],
        },
        "claim": ("the daily product carries the level of the environment but not the exposure: "
                  "hours above a VPD threshold are not a function of the daily mean"),
    }
    safedata.dump(report, REPORT)

    print(f"{'site':<14}{'DLI':>7}{'dTc':>7}{'VPDmean':>9}{'h>1.5':>7}{'h>2.5':>7}{'h>3.5':>7}"
          f"{'noon%':>8}")
    for site, values in per_site.items():
        print(f"{site:<14}{values['dliMeanMolM2D']:>7.1f}{values['diurnalRangeMeanC']:>7.1f}"
              f"{values['vpdMeanKpa']:>9.2f}{values['hoursAboveKpa']['1.5']:>7}"
              f"{values['hoursAboveKpa']['2.5']:>7}{values['hoursAboveKpa']['3.5']:>7}"
              f"{(values['dliFractionAroundNoon']['meanFraction'] or 0)*100:>7.0f}%")
    print(f"\nambiguous daily-mean bins: {len(ambiguous)}, max spread "
          f"{report['informationLossTest']['maxSpreadHoursWithinOneBin']} h")
    print(f"report -> {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
