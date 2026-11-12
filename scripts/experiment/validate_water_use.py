"""Validate a controlled-environment water-use export against the trial schema.

    python3 scripts/experiment/validate_water_use.py measurements.csv
    python3 scripts/experiment/validate_water_use.py --emit-template out.csv

Eighteen checks run; the exit status is non-zero if any check fails. Warnings do not fail the
run but are printed and stored in the report, because a trial can be thin without being wrong.

Two refusals are deliberate and are described where they are implemented (checks 15 and 18):

* a day whose two independent water-use estimates disagree beyond the tolerance is **rejected**,
  never averaged in;
* a crop coefficient is only accepted against an **in-situ ET0**, because computing Kc against a
  reanalysis ET0 and calling the result a measured crop coefficient would launder a modelled
  number into a measurement.

This script has never seen a real trial. It validates shape, units, internal consistency and
plausibility; it cannot make a measurement exist.
"""
from __future__ import annotations
import sys as _sys, pathlib as _pathlib   # the repository root holds safedata/
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[2]))
import safedata

import argparse
import csv
import datetime as _dt
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "data" / "experiments" / "water_use_schema"
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ML_TO_MM_PER_M2 = 0.001  # 1 mL spread over 1 m2 is 0.001 mm of water depth

CHECKS = (
    "units_file_present",
    "required_columns",
    "undeclared_columns",
    "unit_declarations",
    "unit_matches_schema",
    "row_parse",
    "required_values",
    "value_ranges",
    "enum_values",
    "cross_field_consistency",
    "row_grain_unique",
    "daily_continuity",
    "timezone_declared",
    "optional_missingness",
    "water_balance_closure",
    "per_plant_plausibility",
    "replication_and_duration",
    "kc_requires_in_situ_et0",
)


@dataclass
class CheckResult:
    name: str
    status: str  # pass | warn | fail
    message: str
    details: list[Any] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"check": self.name, "status": self.status, "message": self.message,
                "details": self.details[:20], "detailCount": len(self.details)}


def load_schema(path: Path = SCHEMA_PATH) -> dict[str, Any]:
    return safedata.load(path)


def _columns(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {entry["name"]: entry for entry in
            schema["requiredColumns"] + schema["optionalColumns"] + schema["derivedColumns"]}


def _number(value: str | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        result = float(text)
    except ValueError:
        return None
    return None if math.isnan(result) else result


def emit_template(csv_path: Path) -> Path:
    """Write the header-only template and its units file.

    Deliberately **no example rows**: a template with plausible-looking numbers gets cited as
    data by somebody eventually, so the file has a header and nothing else.
    """
    schema = load_schema()
    columns = _columns(schema)
    names = [entry["name"] for entry in
             schema["requiredColumns"] + schema["optionalColumns"]]
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(names)
    units_path = csv_path.with_suffix(".units")
    safedata.dump({"schemaVersion": schema["schemaVersion"],
         "units": {name: columns[name]["unit"] for name in names}}, units_path)
    return units_path


def validate(csv_path: Path, units_path: Path | None = None,
             schema_path: Path = SCHEMA_PATH) -> dict[str, Any]:
    schema = load_schema(schema_path)
    columns = _columns(schema)
    required_names = [entry["name"] for entry in schema["requiredColumns"]]
    optional_names = [entry["name"] for entry in schema["optionalColumns"]]
    declared_names = required_names + optional_names + [c["name"] for c in schema["derivedColumns"]]
    rules = schema["qualityRules"]
    results: list[CheckResult] = []

    units_path = units_path or csv_path.with_suffix(".units")
    units: dict[str, str] = {}
    if safedata.exists(units_path):
        payload = safedata.load(units_path)
        units = payload.get("units") or {}
        results.append(CheckResult("units_file_present", "pass",
                                  f"read {units_path.name} with {len(units)} declarations"))
    else:
        results.append(CheckResult(
            "units_file_present", "fail",
            f"units file {units_path.name} is missing; without it a column in the wrong unit "
            "parses as a valid number and the error is silent",
        ))

    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        header = [name.strip() for name in (reader.fieldnames or [])]
        rows = [{k.strip(): (v if v is not None else "") for k, v in row.items()}
                for row in reader]

    missing_required = [name for name in required_names if name not in header]
    results.append(CheckResult(
        "required_columns", "fail" if missing_required else "pass",
        ("missing required column(s): " + ", ".join(missing_required)) if missing_required
        else f"all {len(required_names)} required columns present",
        missing_required,
    ))

    undeclared = [name for name in header if name not in declared_names]
    results.append(CheckResult(
        "undeclared_columns", "warn" if undeclared else "pass",
        ("column(s) not in the schema: " + ", ".join(undeclared)) if undeclared
        else "no undeclared columns", undeclared,
    ))

    undeclared_units = [name for name in header if name not in units]
    results.append(CheckResult(
        "unit_declarations", "fail" if undeclared_units else "pass",
        ("no unit declared for: " + ", ".join(undeclared_units)) if undeclared_units
        else "every column has a declared unit", undeclared_units,
    ))

    mismatched = []
    for name in header:
        if name in units and name in columns:
            expected = columns[name]["unit"]
            if units[name].strip() != expected:
                mismatched.append({"column": name, "declared": units[name], "schema": expected})
    results.append(CheckResult(
        "unit_matches_schema", "fail" if mismatched else "pass",
        ("unit mismatch on " + ", ".join(f"{m['column']} ({m['declared']} vs {m['schema']})"
                                         for m in mismatched)) if mismatched
        else "declared units match the schema exactly",
        mismatched,
    ))

    numeric_names = [name for name in header
                     if name in columns and columns[name]["type"] in ("number", "integer")]
    unparsable: list[dict[str, Any]] = []
    for position, row in enumerate(rows, start=2):
        for name in numeric_names:
            raw = row.get(name, "")
            if str(raw).strip() == "":
                continue
            if _number(raw) is None:
                unparsable.append({"line": position, "column": name, "value": raw})
    results.append(CheckResult(
        "row_parse", "fail" if unparsable else "pass",
        f"{len(unparsable)} unparsable numeric value(s)" if unparsable
        else f"{len(rows)} rows parsed", unparsable,
    ))

    missing_values: list[dict[str, Any]] = []
    for position, row in enumerate(rows, start=2):
        for name in required_names:
            if str(row.get(name, "")).strip() == "":
                missing_values.append({"line": position, "column": name})
    results.append(CheckResult(
        "required_values", "fail" if missing_values else "pass",
        f"{len(missing_values)} empty required value(s)" if missing_values
        else "no empty required values", missing_values,
    ))

    out_of_range: list[dict[str, Any]] = []
    for position, row in enumerate(rows, start=2):
        for name in numeric_names:
            value = _number(row.get(name))
            if value is None:
                continue
            limits = columns[name]
            if "minimum" in limits and value < limits["minimum"]:
                out_of_range.append({"line": position, "column": name, "value": value,
                                     "minimum": limits["minimum"]})
            if "maximum" in limits and value > limits["maximum"]:
                out_of_range.append({"line": position, "column": name, "value": value,
                                     "maximum": limits["maximum"]})
    results.append(CheckResult(
        "value_ranges", "fail" if out_of_range else "pass",
        f"{len(out_of_range)} value(s) outside the schema range" if out_of_range
        else "all numeric values inside their declared ranges", out_of_range,
    ))

    bad_enum: list[dict[str, Any]] = []
    for position, row in enumerate(rows, start=2):
        for name in header:
            entry = columns.get(name)
            if entry and entry.get("enum"):
                value = str(row.get(name, "")).strip()
                if value and value not in entry["enum"]:
                    bad_enum.append({"line": position, "column": name, "value": value,
                                     "allowed": entry["enum"]})
    results.append(CheckResult(
        "enum_values", "fail" if bad_enum else "pass",
        f"{len(bad_enum)} value(s) outside their enum" if bad_enum
        else "every enumerated value is allowed", bad_enum,
    ))

    # --- cross-field rules -------------------------------------------------------------
    violations: list[dict[str, Any]] = []
    for position, row in enumerate(rows, start=2):
        tmax, tmin = _number(row.get("tmax_c")), _number(row.get("tmin_c"))
        if tmax is not None and tmin is not None and tmax < tmin:
            violations.append({"line": position, "rule": "temperature_order",
                               "tmax": tmax, "tmin": tmin})
        drainage, inflow = _number(row.get("drainage_ml")), _number(row.get("water_input_ml"))
        if drainage is not None and inflow is not None and drainage > inflow:
            violations.append({"line": position, "rule": "drainage_not_above_input",
                               "drainage": drainage, "input": inflow})
        if str(row.get("qc_flag", "")).strip() in ("suspect", "rejected") and not str(
                row.get("notes", "")).strip():
            violations.append({"line": position, "rule": "qc_requires_note",
                               "qc_flag": row.get("qc_flag")})
        area = _number(row.get("canopy_area_m2"))
        if area is not None and area > 10.0:
            violations.append({"line": position, "rule": "canopy_area_plausible", "area": area})
        start = _number(row.get("substrate_moisture_start_pct"))
        end = _number(row.get("substrate_moisture_end_pct"))
        inflow_value = _number(row.get("water_input_ml")) or 0.0
        if start is not None and end is not None and start == end and inflow_value > 0:
            violations.append({"line": position, "rule": "storage_change_consistent"})
    results.append(CheckResult(
        "cross_field_consistency", "fail" if violations else "pass",
        f"{len(violations)} cross-field violation(s)" if violations
        else "all cross-field rules satisfied", violations,
    ))

    seen: dict[tuple[str, str, str], int] = {}
    duplicates: list[dict[str, Any]] = []
    for position, row in enumerate(rows, start=2):
        key = (str(row.get("trial_id", "")).strip(), str(row.get("plant_id", "")).strip(),
               str(row.get("date", "")).strip())
        if key in seen:
            duplicates.append({"line": position, "firstLine": seen[key], "key": list(key)})
        else:
            seen[key] = position
    results.append(CheckResult(
        "row_grain_unique", "fail" if duplicates else "pass",
        ("duplicate (trial_id, plant_id, date) row(s): the grain is one plant-day") if duplicates
        else "every plant-day appears once", duplicates,
    ))

    gaps: list[dict[str, Any]] = []
    by_plant: dict[str, list[_dt.date]] = {}
    for row in rows:
        text = str(row.get("date", "")).strip()
        if not ISO_DATE.match(text):
            continue
        try:
            stamp = _dt.date.fromisoformat(text)
        except ValueError:
            continue
        by_plant.setdefault(str(row.get("plant_id", "")).strip(), []).append(stamp)
    for plant, dates in by_plant.items():
        unique = sorted(set(dates))
        for earlier, later in zip(unique, unique[1:]):
            gap = (later - earlier).days
            if gap - 1 > rules["maxDateGapDays"]:
                gaps.append({"plant": plant, "from": earlier.isoformat(),
                             "to": later.isoformat(), "missingDays": gap - 1})
    results.append(CheckResult(
        "daily_continuity", "warn" if gaps else "pass",
        f"{len(gaps)} gap(s) longer than {rules['maxDateGapDays']} day(s)" if gaps
        else "no missing days between observations", gaps,
    ))

    zones = {str(row.get("timezone", "")).strip() for row in rows
             if str(row.get("timezone", "")).strip()}
    results.append(CheckResult(
        "timezone_declared", "pass" if len(zones) == 1 else "fail",
        (f"single timezone declared: {zones.pop()}") if len(zones) == 1
        else ("no timezone declared" if not zones else
              f"{len(zones)} different timezone values in one file: {sorted(zones)}"),
    ))

    coverage: dict[str, Any] = {}
    for name in optional_names:
        if name not in header:
            continue
        filled = sum(1 for row in rows if str(row.get(name, "")).strip() != "")
        coverage[name] = {"filled": filled, "rows": len(rows),
                          "fraction": (filled / len(rows)) if rows else 0.0}
    sparse = {name: info for name, info in coverage.items()
              if info["fraction"] < 0.5 and info["filled"] > 0}
    results.append(CheckResult(
        "optional_missingness", "warn" if sparse else "pass",
        ("optional column(s) below 50 % coverage: " + ", ".join(sorted(sparse))) if sparse
        else "optional coverage is complete or absent", sorted(sparse),
    ))

    # --- water balance closure ---------------------------------------------------------
    tolerance = float(rules["balanceClosureTolerancePct"])
    rejected: list[dict[str, Any]] = []
    closures: list[float] = []
    for position, row in enumerate(rows, start=2):
        inflow = _number(row.get("water_input_ml"))
        drainage = _number(row.get("drainage_ml"))
        storage_l = _number(row.get("substrate_volume_l"))
        start = _number(row.get("substrate_moisture_start_pct"))
        end = _number(row.get("substrate_moisture_end_pct"))
        gravimetric = _number(row.get("water_use_gravimetric_ml"))
        area = _number(row.get("canopy_area_m2"))
        if None in (inflow, drainage, storage_l, start, end, gravimetric) or not area:
            continue
        storage_change_ml = (end - start) / 100.0 * storage_l * 1000.0
        balance_ml = inflow - drainage - storage_change_ml
        denominator = max(abs(balance_ml), 1.0)
        closure = abs(balance_ml - gravimetric) / denominator * 100.0
        closures.append(closure)
        if closure > tolerance:
            rejected.append({"line": position, "plant": row.get("plant_id"),
                             "date": row.get("date"), "balanceMl": balance_ml,
                             "gravimetricMl": gravimetric, "closurePct": closure})
    results.append(CheckResult(
        "water_balance_closure", "fail" if rejected else "pass",
        (f"{len(rejected)} day(s) outside the {tolerance:.0f} % closure tolerance: the day is "
         "rejected, not averaged in") if rejected
        else (f"all {len(closures)} days closed within {tolerance:.0f} %"),
        rejected,
    ))

    suspicious: list[dict[str, Any]] = []
    for position, row in enumerate(rows, start=2):
        inflow = _number(row.get("water_input_ml"))
        drainage = _number(row.get("drainage_ml"))
        area = _number(row.get("canopy_area_m2"))
        if None in (inflow, drainage) or not area:
            continue
        water_use_mm = (inflow - drainage) * ML_TO_MM_PER_M2 / area
        if water_use_mm > 25.0:
            suspicious.append({"line": position, "plant": row.get("plant_id"),
                               "date": row.get("date"), "waterUseMm": water_use_mm})
    results.append(CheckResult(
        "per_plant_plausibility", "warn" if suspicious else "pass",
        ("water use above 25 mm/d on " + str(len(suspicious)) + " day(s)") if suspicious
        else "per-plant water use is inside a physically plausible range", suspicious,
    ))

    plants = {str(row.get("plant_id", "")).strip() for row in rows
              if str(row.get("plant_id", "")).strip()}
    treatments: dict[str, set[str]] = {}
    for row in rows:
        treatments.setdefault(str(row.get("treatment", "")).strip(), set()).add(
            str(row.get("plant_id", "")).strip())
    thin = {name: len(members) for name, members in treatments.items()
            if len(members) < rules["minReplicatesPerTreatment"]}
    dates = sorted({str(row.get("date", "")).strip() for row in rows if ISO_DATE.match(
        str(row.get("date", "")).strip())})
    trial_days = len(dates)
    problems = []
    if thin:
        problems.append("treatment(s) below the minimum replication: " + ", ".join(
            f"{name} ({count})" for name, count in sorted(thin.items())))
    if trial_days < rules["minTrialDays"]:
        problems.append(f"trial covers {trial_days} day(s), below the {rules['minTrialDays']}-day "
                        "minimum")
    results.append(CheckResult(
        "replication_and_duration", "warn" if problems else "pass",
        " | ".join(problems) if problems
        else f"{len(plants)} plants across {len(treatments)} treatment(s) over {trial_days} day(s)",
        problems,
    ))

    # --- the Kc refusal ------------------------------------------------------------------
    kc_offenders: list[dict[str, Any]] = []
    if "kc_measured" in header:
        for position, row in enumerate(rows, start=2):
            kc = _number(row.get("kc_measured"))
            if kc is None:
                continue
            source = str(row.get("et0_source", "")).strip()
            if source != "in_situ":
                kc_offenders.append({"line": position, "kc": kc,
                                     "et0_source": source or "(absent)"})
    results.append(CheckResult(
        "kc_requires_in_situ_et0", "fail" if kc_offenders else "pass",
        (f"{len(kc_offenders)} row(s) report a crop coefficient against a non-in-situ ET0; "
         "a Kc computed from reanalysis ET0 is a modelled ratio, not a measurement")
        if kc_offenders else "no crop coefficient is reported against a non-in-situ ET0",
        kc_offenders,
    ))

    failures = [result for result in results if result.status == "fail"]
    warnings = [result for result in results if result.status == "warn"]
    return {
        "file": str(csv_path),
        "schema": {"path": str(schema_path), "version": schema["schemaVersion"]},
        "rowCount": len(rows),
        "verdict": "FAIL" if failures else ("PASS_WITH_WARNINGS" if warnings else "PASS"),
        "checks": [result.as_dict() for result in results],
        "failedChecks": [result.name for result in failures],
        "warnings": [result.name for result in warnings],
        "note": ("This validator inspects shape, units and internal consistency. It cannot "
                 "establish that a measurement was made."),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", nargs="?", help="measurement CSV to validate")
    parser.add_argument("--units", help="companion units record (default: same stem, .units suffix)")
    parser.add_argument("--schema", default=str(SCHEMA_PATH))
    parser.add_argument("--emit-template", metavar="PATH",
                        help="write a header-only template and its units file, then exit")
    parser.add_argument("--report", help="write the JSON report here")
    args = parser.parse_args(argv)

    if args.emit_template:
        units_path = emit_template(Path(args.emit_template))
        print(f"wrote header-only template {args.emit_template} and {units_path}")
        print("no example rows are written on purpose: a plausible-looking row gets cited as data")
        return 0

    if not args.csv:
        parser.error("a CSV path is required unless --emit-template is used")

    report = validate(Path(args.csv), Path(args.units) if args.units else None,
                      Path(args.schema))
    for check in report["checks"]:
        marker = {"pass": "ok  ", "warn": "warn", "fail": "FAIL"}[check["status"]]
        print(f"[{marker}] {check['check']:24s} {check['message']}")
    print(f"\nverdict: {report['verdict']}  ({report['rowCount']} rows)")
    if args.report:
        safedata.dump(report, Path(args.report))
        print(f"report written to {args.report}")
    return 1 if report["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
