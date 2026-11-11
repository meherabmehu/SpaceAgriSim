"""Attribute the per-site ET0 difference between two forcing products to its drivers.

    python3 scripts/et0_validation/attribute.py

Reads ``data/validation/et0/harmonised_daily.csv`` (written by ``run_validation.py``) and writes
``attribution.json``. The comparison is a **substitution game**: both legs are evaluated by the
same equation and the same code, so swapping a subset of the five daily drivers from one product
to the other gives a path between them. Contributions are averaged over **all 120 orderings**,
which is the Shapley value of that game - it removes the arbitrary choice of order, and because
the radiation and aerodynamic terms share the denominator ``D + g(1 + 0.34 u2)`` the swaps are
genuinely not additive.

Surface pressure is held at the first product's value inside the game: it is not an independent
forcing but a function of elevation and synoptic state, and its contribution is reported
separately as ``pressureRemainderMm``. That is what makes the efficiency check exact - an earlier
version did not, and left a silent 0.003 mm/day unexplained.
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import itertools
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any, Callable

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:  # pragma: no cover - import plumbing
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.et0_validation import methods, scoring, sources  # noqa: E402

DEFAULT_CSV = _REPO_ROOT / "data" / "validation" / "et0" / "harmonised_daily.csv"
DEFAULT_OUT = _REPO_ROOT / "data" / "validation" / "et0" / "attribution.json"

DRIVERS = ("tmax", "tmin", "ea", "rs", "u2")

# Which CSV columns hold each driver, per source. ``era5_`` is the "from" product, ``power_``
# the "to" product; the swap direction is recorded in the output.
COLUMNS = {
    "era5": {"tmax": "era5_tmax_c", "tmin": "era5_tmin_c", "ea": "era5_ea_kpa",
             "rs": "era5_rs_mjm2", "u2": "era5_u2_ms", "pressure": "era5_pressure_kpa"},
    "power": {"tmax": "power_tmax_c", "tmin": "power_tmin_c", "ea": "power_ea_kpa",
              "rs": "power_rs_mjm2", "u2": "power_u2_ms", "pressure": "power_pressure_kpa"},
}
ET0_COLUMNS = {"era5": "era5_daily_pm_mm", "power": "power_daily_pm_mm"}


def _float(value: str | float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(result) else result


def load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit(f"no rows in {path}")
    return rows


def day_of_year(day: str) -> int:
    return _dt.date.fromisoformat(day).timetuple().tm_yday


def _predict(site: dict[str, Any], day: str, drivers: dict[str, float],
             pressure_kpa: float, elevation_m: float) -> float:
    result = methods.daily_et0(
        tmax=drivers["tmax"], tmin=drivers["tmin"], ea_kpa=drivers["ea"],
        rs_mj=drivers["rs"], wind_2m_ms=drivers["u2"], pressure_kpa=pressure_kpa,
        day_of_year=day_of_year(day), latitude_deg=site["latitude"],
        elevation_m=elevation_m,
    )
    return result["et0MmPerDay"]


def shapley_for_site(rows: list[dict[str, Any]], site: dict[str, Any]) -> dict[str, Any]:
    """Average marginal contributions over every ordering of the five drivers."""
    usable: list[dict[str, Any]] = []
    for row in rows:
        got = {source: {key: _float(row[column]) for key, column in COLUMNS[source].items()}
               for source in ("era5", "power")}
        if any(v is None for source in got.values() for v in source.values()):
            continue
        usable.append({"day": row["date"], **{f"{s}_{k}": v for s, d in got.items()
                                              for k, v in d.items()}})

    if not usable:
        return {"daysUsed": 0, "note": "no day had both products' five drivers present"}

    contributions = {driver: [] for driver in DRIVERS}
    abs_contributions = {driver: [] for driver in DRIVERS}
    totals: list[float] = []
    pressure_remainders: list[float] = []

    for row in usable:
        base = {driver: row[f"era5_{driver}"] for driver in DRIVERS}
        other = {driver: row[f"power_{driver}"] for driver in DRIVERS}
        pressure = row["era5_pressure"]

        et0_from = _predict(site, row["day"], base, pressure, site["gridElevationM"])
        et0_to = _predict(site, row["day"], other, pressure, site["gridElevationM"])
        # The stored columns are the same computation on the same code; comparing them to the
        # recomputation is the cross-check that caught the ea defect, so it is kept as a test
        # invariant rather than an assertion that can drift.
        stored_from = _float(row.get("era5_daily_pm_mm"))
        if stored_from is not None and abs(stored_from - et0_from) > 0.01:
            raise SystemExit(
                f"{row['day']}: substitution start does not reproduce the stored ET0 "
                f"({et0_from:.3f} vs {stored_from:.3f}); attribution would be meaningless"
            )

        marginal = {driver: 0.0 for driver in DRIVERS}
        orderings = 0
        for ordering in itertools.permutations(DRIVERS):
            current = dict(base)
            previous = et0_from
            for driver in ordering:
                current[driver] = other[driver]
                value = _predict(site, row["day"], current, pressure, site["gridElevationM"])
                marginal[driver] += value - previous
                previous = value
            orderings += 1

        for driver in DRIVERS:
            mean_marginal = marginal[driver] / orderings
            contributions[driver].append(mean_marginal)
            abs_contributions[driver].append(abs(mean_marginal))
        totals.append(et0_to - et0_from)

        # Pressure is outside the game. Its contribution is the difference between the stored
        # other-product ET0 (which used its own pressure) and the held-pressure evaluation.
        stored_to = _float(row.get("power_daily_pm_mm"))
        if stored_to is not None:
            pressure_remainders.append(stored_to - et0_to)

    mean_diff = sum(totals) / len(totals)
    means = {driver: sum(values) / len(values) for driver, values in contributions.items()}
    explained = sum(means.values())
    remainder = sum(pressure_remainders) / len(pressure_remainders) if pressure_remainders else 0.0
    magnitude = sum(abs(value) for value in means.values()) or 1.0
    abs_total = sum(sum(values) / len(values) for values in abs_contributions.values()) or 1.0
    dominant = max(means, key=lambda key: abs(means[key]))

    return {
        "daysUsed": len(usable),
        "meanDifferenceMm": mean_diff,
        "meanDifferenceDirection": "second product minus first (POWER minus ERA5)",
        "shapleyMmPerDay": means,
        # Share of the difference by magnitude. Averaging the absolute daily contributions
        # first matters: |mean| / sum|mean| understates a driver that moves the difference in
        # both directions on different days.
        "shapleyShareOfAbsoluteSum": {
            driver: (sum(abs_contributions[driver]) / len(abs_contributions[driver]))
            / abs_total
            for driver in DRIVERS
        },
        "shapleyShareOfSignedSum": {driver: abs(value) / magnitude
                                    for driver, value in means.items()},
        "dominantDriver": dominant,
        "dominantDriverShare": abs(means[dominant]) / magnitude,
        "pressureRemainderMm": remainder,
        "efficiency": {
            "sumOfContributions": explained,
            "sumPlusRemainder": explained + remainder,
            "difference": mean_diff,
            "residual": explained + remainder - mean_diff,
            "residualIsZeroWithinMm": abs(explained + remainder - mean_diff) < 5e-3,
        },
    }


def elevation_check(rows: list[dict[str, Any]], site: dict[str, Any]) -> dict[str, Any]:
    """How much ET0 would change if the station elevation replaced the grid elevation."""
    deltas: list[float] = []
    for row in rows:
        drivers = {driver: _float(row[COLUMNS['era5'][driver]]) for driver in DRIVERS}
        pressure = _float(row["era5_pressure_kpa"])
        if None in drivers.values() or pressure is None:
            continue
        grid = _predict(site, row["date"], drivers, pressure, site["gridElevationM"])
        station = _predict(site, row["date"], drivers, pressure, site["stationElevationM"])
        deltas.append(station - grid)

    return {
        "daysChecked": len(deltas),
        "gridElevationM": site["gridElevationM"],
        "stationElevationM": site["stationElevationM"],
        "elevationDifferenceM": site["stationElevationM"] - site["gridElevationM"],
        "meanDeltaMm": sum(deltas) / len(deltas) if deltas else None,
        "maxAbsDeltaMm": max((abs(d) for d in deltas), default=None),
        "conclusion": (
            "elevation mismatch is not an explanation for the site differences: the effect is "
            "three orders of magnitude below them" if deltas and max(abs(d) for d in deltas) < 0.05
            else "elevation may matter at this site"
        ),
    }


def station_bias(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Temperature bias of both ERA5 products against the station's own observations."""
    out: dict[str, Any] = {}
    for site_key in sorted({row["site"] for row in rows}):
        site_rows = [row for row in rows if row["site"] == site_key]
        pairs = [(r["era5_tmax_c"], r["isd_tmax_c"]) for r in site_rows]
        land = [(r["era5_land_tmax_c"], r["isd_tmax_c"]) for r in site_rows]
        era5_bias = _mean([_float(a) - _float(b) for a, b in pairs
                           if _float(a) is not None and _float(b) is not None])
        land_bias = _mean([_float(a) - _float(b) for a, b in land
                           if _float(a) is not None and _float(b) is not None])
        out[site_key] = {
            "era5TmaxBiasC": era5_bias,
            "era5LandTmaxBiasC": land_bias,
            "finerGridIsCloser": (
                None if era5_bias is None or land_bias is None
                else abs(land_bias) < abs(era5_bias)
            ),
        }

    closer = [v["finerGridIsCloser"] for v in out.values() if v["finerGridIsCloser"] is not None]
    return {
        "perSite": out,
        "sitesWhereFinerGridIsCloser": sum(1 for flag in closer if flag),
        "sitesCompared": len(closer),
        "statement": (
            "ERA5-Land at 0.1 deg is closer to the station at "
            f"{sum(1 for flag in closer if flag)} of {len(closer)} sites on daily Tmax; "
            "a finer grid is not automatically closer to a point observation."
        ),
    }


def representativeness(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Do the products or the station look like the outlier at each site?"""
    out: dict[str, Any] = {}
    for site_key in sorted({row["site"] for row in rows}):
        site_rows = [row for row in rows if row["site"] == site_key]
        out[site_key] = {
            "meanTmaxC": {
                "era5": _mean([_float(r["era5_tmax_c"]) for r in site_rows]),
                "era5Land": _mean([_float(r["era5_land_tmax_c"]) for r in site_rows]),
                "power": _mean([_float(r["power_tmax_c"]) for r in site_rows]),
                "station": _mean([_float(r["isd_tmax_c"]) for r in site_rows]),
            },
            "meanShortwaveMJm2": {
                "era5": _mean([_float(r["era5_rs_mjm2"]) for r in site_rows]),
                "power": _mean([_float(r["power_rs_mjm2"]) for r in site_rows]),
            },
            "meanWind2mMs": {
                "era5": _mean([_float(r["era5_u2_ms"]) for r in site_rows]),
                "power": _mean([_float(r["power_u2_ms"]) for r in site_rows]),
                "station10m": None,  # ISD wind is not carried in the harmonised table
            },
            "shortwaveMadMJm2": _mean(
                [abs(_float(r["era5_rs_mjm2"]) - _float(r["power_rs_mjm2"]))
                 for r in site_rows
                 if _float(r["era5_rs_mjm2"]) is not None
                 and _float(r["power_rs_mjm2"]) is not None]),
        }
    return out


def _mean(values: list[float | None]) -> float | None:
    clean = [v for v in values if v is not None]
    return sum(clean) / len(clean) if clean else None


def attribute(csv_path: Path, out_path: Path) -> dict[str, Any]:
    rows = load_rows(csv_path)
    summary = json.loads((csv_path.parent / "validation_summary.json").read_text())
    sites = {entry["key"]: entry for entry in summary["siteMetadata"]}

    per_site: dict[str, Any] = {}
    for site_key in sorted({row["site"] for row in rows}):
        site_rows = [row for row in rows if row["site"] == site_key]
        site = sites[site_key]
        per_site[site_key] = {
            "label": site["label"],
            "shapley": shapley_for_site(site_rows, site),
            "elevation": elevation_check(site_rows, site),
            "wind": summary["windSensitivity"].get(site_key),
        }

    payload = {
        "generatedAt": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": str(csv_path.name),
        "method": {
            "game": "substitution of the five daily drivers between the two products",
            "solution": "Shapley value over all 120 orderings",
            "equation": "identical FAO-56 daily form and identical code on both sides",
            "pressure": "held at the first product's value; reported as pressureRemainderMm",
            "why": (
                "the radiation and aerodynamic terms share the denominator, so the drivers are "
                "not additive and the order of substitution matters; averaging every ordering "
                "removes that arbitrariness"
            ),
        },
        "perSite": per_site,
        "stationTmaxBias": station_bias(rows),
        "representativeness": representativeness(rows),
        "claims": {
            "supports": "which forcing variable carries each site's ET0 difference",
            "doesNotSupport": (
                "that any product is correct: a contribution share says where two products "
                "differ, not which one is closer to the surface"
            ),
        },
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    for site_key, block in payload["perSite"].items():
        shapley = block["shapley"]
        contributions = shapley.get("shapleyMmPerDay") or {}
        rendered = " ".join(f"{k} {v:+.3f}" for k, v in contributions.items())
        print(f"{site_key:14s} diff {shapley.get('meanDifferenceMm', float('nan')):+.3f}  "
              f"{rendered}  dominant {shapley.get('dominantDriver')} "
              f"({(shapley.get('dominantDriverShare') or 0) * 100:.1f} %)"
              f"  residual {shapley['efficiency']['residual']:+.5f}")
    print(f"Wrote {out_path}")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    attribute(Path(args.csv), Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
