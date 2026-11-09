#!/usr/bin/env python3
"""Compatibility shim: the reference-ET0 physics now lives in product code.

    backend/app/simulation/et0_fao56.py

It moved there because `app.et0` and the simulator's water path both import it, and a research
folder is not on the import path of a deployed service. Everything is re-exported here so that
scripts and notebooks written against the old location keep working.

    python3 ml/research/et0_fao56.py     # prints the three published-example checks
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.simulation.et0_fao56 import *  # noqa: F401,F403,E402
from app.simulation.et0_fao56 import (  # noqa: F401,E402
    MJ_TO_MM, PAR_FRACTION_OF_GLOBAL, MOL_PAR_PER_MJ, SOLAR_CONSTANT,
    actual_vapour_pressure_from_dewpoint, actual_vapour_pressure_from_mean_rh,
    actual_vapour_pressure_from_rh_extremes, atmospheric_pressure, clear_sky_radiation,
    daily_light_integral, extraterrestrial_radiation, hargreaves_et0,
    mean_saturation_vapour_pressure, net_longwave, net_radiation, psychrometric_constant,
    reference_et0, run_published_examples, saturation_vapour_pressure,
    slope_saturation_curve, wind_at_2m,
)

if __name__ == "__main__":
    for row in run_published_examples():
        extra = ", ".join(f"{k} {v:.2f}" for k, v in row.items()
                          if k in ("ra", "rs") and v is not None)
        print(f"{row['example']}: published {row['publishedMmPerDay']} mm/day, "
              f"computed {row['computedMmPerDay']:.2f} mm/day  ({extra})")
