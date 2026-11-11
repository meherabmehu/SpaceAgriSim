"""Generate synthetic fixtures that exercise the water-use validator.

    python3 scripts/experiment/make_synthetic_fixture.py

These files are **not measurements** and cannot be mistaken for any: every ``notes`` cell begins
with ``SYNTHETIC FIXTURE``, the filename contains ``SYNTHETIC_FIXTURE_not_a_measurement``, and the
numbers are generated from a closed-form toy model purely so that each of the validator's checks
has something that trips it. They exist so the validator is tested against defects it must catch,
including the comfortable possibility that it silently passes everything.

Do not cite any value in these files. Do not copy them into a results directory.
"""
from __future__ import annotations

import argparse
import copy
import csv
import datetime as _dt
import json
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "data" / "experiments" / "water_use_schema.json"
LABEL = "SYNTHETIC FIXTURE - not a measurement"
PLANTS = ("A01", "A02", "A03", "A04", "A05", "A06")
DAYS = 42
START = _dt.date(2026, 3, 1)


def _rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for plant_index, plant in enumerate(PLANTS):
        treatment = "well_watered" if plant_index < 3 else "deficit"
        for day in range(DAYS):
            date = START + _dt.timedelta(days=day)
            # Toy water balance, not biology: the point is that the arithmetic closes.
            canopy = round(0.055 + 0.002 * day, 4)
            moisture_start = 34.0 + (day % 5) * 0.4
            moisture_end = moisture_start - 2.2 + (day % 3) * 0.1
            substrate_l = 1.2
            storage_change_ml = (moisture_end - moisture_start) / 100.0 * substrate_l * 1000.0
            inflow = 420.0 if treatment == "well_watered" else 260.0
            gravimetric = inflow * 0.86
            drainage = max(inflow - gravimetric - storage_change_ml, 0.0)
            rows.append({
                "trial_id": "FIXTURE-TRIAL-001",
                "site_id": "fixture-chamber",
                "chamber_id": "C1",
                "plant_id": plant,
                "replicate": str((plant_index % 3) + 1),
                "treatment": treatment,
                "species": "Lactuca sativa",
                "growth_stage": "vegetative",
                "date": date.isoformat(),
                "timezone": "Asia/Dhaka",
                "substrate": "coir-perlite",
                "canopy_area_m2": f"{canopy}",
                "water_input_ml": f"{inflow:.1f}",
                "drainage_ml": f"{drainage:.1f}",
                "substrate_moisture_start_pct": f"{moisture_start:.1f}",
                "substrate_moisture_end_pct": f"{moisture_end:.1f}",
                "substrate_volume_l": f"{substrate_l:.2f}",
                "water_use_gravimetric_ml": f"{gravimetric:.1f}",
                "tmin_c": "18.4",
                "tmax_c": "24.9",
                "rh_mean_pct": "68.0",
                "photoperiod_h": "16.0",
                "qc_flag": "ok",
                "et0_mm": "3.10",
                "et0_source": "in_situ",
                "et0_method": "FAO-56 Penman-Monteith, in-chamber sensor set",
                "ppfd_umol_m2_s": "410",
                "co2_ppm": "620",
                "air_temp_mean_c": "21.6",
                "notes": LABEL,
            })
    return rows


def _defect_unit_mismatch(rows: list[dict[str, str]], units: dict[str, str]):
    units = dict(units)
    units["water_input_ml"] = "L"  # parses fine, wrong by 1000x
    return rows, units


def _defect_missing_required(rows: list[dict[str, str]], units: dict[str, str]):
    rows = copy.deepcopy(rows)
    for row in rows:
        row["canopy_area_m2"] = ""
    return rows, units


def _defect_balance_broken(rows: list[dict[str, str]], units: dict[str, str]):
    rows = copy.deepcopy(rows)
    for row in rows[::7]:
        row["water_use_gravimetric_ml"] = f"{float(row['water_use_gravimetric_ml']) * 2.4:.1f}"
    return rows, units


def _defect_duplicate_row(rows: list[dict[str, str]], units: dict[str, str]):
    rows = copy.deepcopy(rows)
    rows.insert(5, dict(rows[4]))
    return rows, units


def _defect_bad_temperature_order(rows: list[dict[str, str]], units: dict[str, str]):
    rows = copy.deepcopy(rows)
    rows[3]["tmin_c"] = "31.0"
    rows[3]["tmax_c"] = "22.0"
    return rows, units


def _defect_kc_without_in_situ(rows: list[dict[str, str]], units: dict[str, str]):
    rows = copy.deepcopy(rows)
    for row in rows:
        row["kc_measured"] = "0.94"
        row["et0_source"] = "reanalysis"
    return rows, units


def _defect_out_of_range(rows: list[dict[str, str]], units: dict[str, str]):
    rows = copy.deepcopy(rows)
    rows[9]["rh_mean_pct"] = "118.0"
    return rows, units


def _defect_qc_without_note(rows: list[dict[str, str]], units: dict[str, str]):
    rows = copy.deepcopy(rows)
    rows[11]["qc_flag"] = "rejected"
    rows[11]["notes"] = ""
    return rows, units


def _defect_date_gap(rows: list[dict[str, str]], units: dict[str, str]):
    rows = copy.deepcopy(rows)
    return [row for row in rows if row["date"] != (START + _dt.timedelta(days=10)).isoformat()], units


def _defect_thin_replication(rows: list[dict[str, str]], units: dict[str, str]):
    rows = copy.deepcopy(rows)
    return [row for row in rows if row["plant_id"] in ("A01", "A04")], units


DEFECTS = {
    "clean": lambda rows, units: (rows, units),
    "unit_mismatch": _defect_unit_mismatch,
    "missing_required": _defect_missing_required,
    "balance_broken": _defect_balance_broken,
    "duplicate_row": _defect_duplicate_row,
    "bad_temperature_order": _defect_bad_temperature_order,
    "kc_without_in_situ": _defect_kc_without_in_situ,
    "out_of_range": _defect_out_of_range,
    "qc_without_note": _defect_qc_without_note,
    "date_gap": _defect_date_gap,
    "thin_replication": _defect_thin_replication,
}


def write_fixture(name: str, rows: list[dict[str, str]], units: dict[str, str],
                  out_dir: Path = FIXTURE_DIR) -> Path:
    suffix = "" if name == "clean" else f"__defect_{name}"
    csv_path = out_dir / f"SYNTHETIC_FIXTURE_not_a_measurement{suffix}.csv"
    units_path = out_dir / f"SYNTHETIC_FIXTURE_not_a_measurement{suffix}.units.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    units_path.write_text(json.dumps(
        {"schemaVersion": "1.0.0", "fixtureLabel": LABEL, "units": units}, indent=2) + "\n",
        encoding="utf-8")
    return csv_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=str(FIXTURE_DIR),
                        help="where to write the fixtures (default: beside this script)")
    args = parser.parse_args(argv)
    # `--out-dir` used to be parsed and then ignored: `write_fixture` wrote to the module-level
    # FIXTURE_DIR regardless, so asking for a temporary directory silently modified the repository.
    out_dir = Path(args.out_dir).expanduser().resolve()

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    columns = {entry["name"]: entry for entry in
               schema["requiredColumns"] + schema["optionalColumns"]}
    base_rows = _rows()
    # Units are declared for every column the fixtures can carry, including the optional ones
    # a defect introduces, so a defect never fails for the unintended reason of a missing
    # declaration.
    base_units = {name: columns[name]["unit"]
                  for name in ("kc_measured", "et0_source", "notes", *base_rows[0])}

    written = []
    for name, defect in DEFECTS.items():
        rows, units = defect(copy.deepcopy(base_rows), base_units)
        written.append(write_fixture(name, rows, units, out_dir))

    print(f"wrote {len(written)} fixtures to {out_dir}")
    print(f"every row is labelled: {LABEL}")
    print("defects covered: " + ", ".join(sorted(DEFECTS)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
