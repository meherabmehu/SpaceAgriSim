#!/usr/bin/env python3
"""Phase 30: build the processed tables for the two acquired datasets.

Inputs are immutable raw files under data/raw/phase30/, each hash-recorded in
data/metadata/phase30_acquisition_manifest.json. Nothing here downloads, edits a raw file, converts a
unit silently or fills a blank.

Dataset 1 — controlled-environment wheat (Zenodo 10.5281/zenodo.17764612, CC BY 4.0)
    One row per harvested sub-plot (719) plus one row per experiment (39). The experiment is the unit
    of independence: sub-plots inside one chamber share the environment and the operator, so a model
    that treats them as replicates would shrink every interval by the within-run correlation. The
    environment is aggregated with the arithmetic mean over the sub-plot rows of one experiment, and
    whenever it changed inside a run the sub-plot minimum, maximum and a `VariesWithinExperiment`
    flag are stored beside the mean instead of pretending the mean is the treatment.

Dataset 2 — lettuce across published studies (Zenodo 10.5281/zenodo.14640245, CC BY 4.0)
    One row per published treatment mean (53), each keeping the citation of the study it came from.
    These are means reported by other authors: `observationKind=published-treatment-mean` and
    `isRawMeasurement=false` travel with every row. The grouping key for validation is the study, not
    the row, because several papers contribute two to four treatments.

Units
    Every column carries its unit in the manifest's unit map. Two source columns (`Light_D`,
    `Light_L`) mix a photon sum with a per-day quantity and cannot be identified from the workbook;
    they are carried as `lightIntegralDayUnidentified` / `...NightUnidentified` with unit null and
    `modelled: false`, so nothing downstream can quietly use them.

    python3 ml/research/build_phase30_datasets.py            # build
    python3 ml/research/build_phase30_datasets.py --check    # verify raw hashes and tables
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "phase30"
OUT = ROOT / "data" / "processed" / "phase30"
MANIFEST = ROOT / "data" / "metadata" / "phase30_acquisition_manifest.json"

WHEAT_XLSX = "wheat_yields.xlsx"
LETTUCE_XLSX = "lue_dataset.xlsx"

# Raw column -> stored column. The raw header is in row 1 (units) and row 2 (names); the mapping is
# spelled out rather than positional so a reordered workbook fails loudly instead of silently.
WHEAT_COLUMNS = {
    "Exp_ID": ("experimentId", "identifier"),
    "System": ("system", "category"),
    "Tresh_date": ("threshingDate", "date"),
    "Grain_kg_m2": ("grainYieldKgPerM2", "kg/m2"),
    "Grain_wg_std": ("grainMassPerSpikeMg", "mg"),
    "Spike_nb_m2": ("spikesPerM2", "count/m2"),
    "Grain_nb_m2": ("grainsPerM2", "count/m2"),
    "Grain_spike": ("grainsPerSpike", "count"),
    # The workbook's own units row declares `[%]` for Harvest_index and `[g m⁻² d⁻¹]` for Grain_fill.
    # Both were stored under a unit that contradicted that row: `harvestIndex` was declared a
    # "fraction" while the column holds percent (median 42.6, range 0.7-60.5), and
    # `grainFillMgPerDay` was declared "mg/day" while the column holds grams per square metre per
    # day (median 19.3, which is 0.79 kg/m2 of grain over a ~40-day fill). The stored names and
    # units now carry what the source declares, with no conversion applied to the values.
    "Harvest_index": ("harvestIndexPct", "%"),
    "Grain_fill": ("grainFillGPerM2Day", "g/m2/day"),
    "Grain_fill_rate": ("grainFillRate", "unstated in source"),
    "LUE": ("lightUseEfficiencyGPerMol", "g/mol"),
    "Prod_yr": ("annualisedYieldKgPerM2Yr", "kg/m2/yr"),
    "Thresh_res_kg_m2": ("threshingResidueKgPerM2", "kg/m2"),
    "Biomass_kg_m2": ("biomassKgPerM2", "kg/m2"),
    "Avg_plant_height": ("plantHeightCm", "cm"),
    "CCL": ("cycleLengthDays", "day"),
    "Anthesis_len": ("anthesisLengthDays", "day"),
    "Light_SUM": ("lightSumMolPerM2", "mol/m2"),
    "Light_D": ("lightIntegralDayUnidentified", None),
    "Light_L": ("lightIntegralNightUnidentified", None),
    "Mean_PPFD": ("meanPpfdUmolPerM2S", "umol/m2/s"),
    "Mean_Photo": ("photoperiodHours", "h/day"),
    "CO2_AVG": ("co2Ppm", "ppm"),
    "Temp_AVG": ("airTemperatureC", "degC"),
    "Temp_SUM": ("temperatureSumDegCDay", "degC.day"),
    "Humid_AVG": ("relativeHumidityPct", "%"),
    "Borders": ("borderRows", "category"),
    "Position_ID": ("positionId", "identifier"),
}

ENV_FIELDS = ("meanPpfdUmolPerM2S", "photoperiodHours", "co2Ppm", "airTemperatureC",
              "relativeHumidityPct", "lightIntegralDayUnidentified", "cycleLengthDays")
REQUIRED_ENVIRONMENT = ("meanPpfdUmolPerM2S", "photoperiodHours", "co2Ppm", "airTemperatureC",
                        "relativeHumidityPct", "cycleLengthDays")

LETTUCE_COLUMNS = {
    "id": ("sourceRowId", "identifier"),
    "Study": ("studyLabel", "identifier"),
    "Reference": ("citation", "text"),
    " \tCO2 \t": ("co2Ppm", "ppm"),
    "Photoperiod ": ("photoperiodHours", "h/day"),
    "PPFD": ("ppfdUmolPerM2S", "umol/m2/s"),
    "DLI ": ("dailyLightIntegralMolPerM2Day", "mol/m2/day"),
    "Plant age": ("plantAgeDays", "day"),
    "Cumulative DLI": ("cumulativeDliMolPerM2", "mol"),
    "Density": ("plantDensityPerM2", "plant/m2"),
    "Shoot DW at harvest ": ("shootDryMassG", "g"),
    "LUESDW": ("lightUseEfficiencyDryGPerMol", "g/mol"),
    "LUESFW": ("lightUseEfficiencyFreshGPerMol", "g/mol"),
    "mols_per_kg": ("molsPerKg", "mol/kg"),
}

TRANSFORMATIONS = [
    "column names mapped to unit-carrying names; the map is in this file's builder",
    "no imputation: blanks stay blank and coverage is reported per field",
    "no unit conversion: published units are carried in the column name",
    "experiment-level aggregation computes the mean of sub-plot yields and refuses to average an "
    "environment that changed within an experiment (reported as a range instead)",
    "literature rows are labelled observationKind=published-treatment-mean; they are means "
    "reported by other authors, not plants weighed in this repository",
]

REJECTED = [
    {"doi": "10.5281/zenodo.8410252", "source": "Zenodo",
     "title": "Piikkio2023 lettuce 3D pointcloud dataset for fresh weight estimation",
     "reason": "licence field is null, so it is not redistributable and cannot be committed"},
    {"doi": "10.5281/zenodo.20759414", "source": "Zenodo", "bytes": 39_000_000_000,
     "reason": "39 GB, and the variability it varies is fertigation rather than light or temperature"},
    {"doi": "10.5281/zenodo.22004997", "source": "Zenodo",
     "reason": "measures the light environment only; no crop response variable"},
    {"doi": "10.5281/zenodo.20394352", "source": "Zenodo",
     "reason": "a reanalysis of the Greenlight trial already used for workflow C; adding it would "
               "double-count one experiment rather than add an independent one"},
    {"doi": "10.5281/zenodo.17712088", "source": "Zenodo",
     "reason": "simulation output, not measurement"},
    {"doi": "10.5281/zenodo.16271245", "source": "Zenodo",
     "reason": "pak choi; wrong species for every modelled crop"},
    {"doi": "10.5281/zenodo.14529253", "source": "Zenodo",
     "reason": "wheat SPAD readings; the response variable is a chlorophyll index, not biomass or "
               "yield"},
    {"doi": "10.5281/zenodo.22280237", "source": "Zenodo",
     "reason": "spinach far-red timing, 22 KB: one treatment series with no yield response variable"},
    {"doi": "10.5061/dryad.73n5tb3d4", "source": "Dryad", "bytes": 8_000_000_000,
     "reason": "8 GB of UAV imagery only; download also returned 401 without an account"},
    {"doi": "10.5281/zenodo.5797817", "source": "Zenodo",
     "title": "Long time series (2001-2015) high-resolution crop yield and water productivity "
              "dataset of China",
     "reason": ("field-scale yield and water productivity from remote sensing over maize and wheat. "
                "It contains no deficit treatment, no water-application gradient and therefore no "
                "crop-specific Ky; it cannot support a water-deficit yield-loss claim.")},
    {"doi": "10.5281/zenodo.7895889", "source": "Zenodo",
     "title": "Data of crop yield derived from H2020 Diverfarming project",
     "reason": ("field-grown mandarin with alley crops under control and regulated deficit "
                "irrigation. Wrong species and system for this platform's crops, and the design does "
                "not report a yield response factor.")},
    {"doi": "10.5061/dryad.gqnk98skd", "source": "Dryad",
     "title": ("Water stress and insect herbivory interactively reduce crop yield while the insect "
               "pollination benefit is conserved"),
     "reason": ("faba bean field experiment where water stress is crossed with herbivory and "
                "pollination. The water effect cannot be separated from the biotic treatments, so it "
                "cannot produce a crop water-production function.")},
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return value
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _clean(row.get(key, "")) for key in fields})


def _range(values: list[float]) -> dict[str, Any] | None:
    present = [value for value in values if isinstance(value, float)]
    if not present:
        return None
    return {"n": len(present), "min": round(min(present), 4), "max": round(max(present), 4),
            "distinct": len({round(value, 6) for value in present})}


# ------------------------------------------------------------------------------- wheat


def build_wheat() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    workbook = openpyxl.load_workbook(RAW / WHEAT_XLSX, read_only=True, data_only=True)
    sheet = workbook["Data"]
    rows = list(sheet.iter_rows(values_only=True))
    units_row, header = rows[0], rows[1]
    position = {str(name).strip(): index for index, name in enumerate(header) if name}
    missing = [name for name in WHEAT_COLUMNS if name not in position]
    if missing:
        raise SystemExit(f"wheat workbook is missing expected columns: {missing}")

    # The units row is the source's own declaration, so it is read and published verbatim next to
    # the unit this builder declares. It used to be unpacked into a local and dropped, which is how
    # two stored units ended up contradicting the file they came from without anything noticing.
    source_units: dict[str, str] = {}
    for source, (stored, _unit) in WHEAT_COLUMNS.items():
        cell = units_row[position[source]]
        declared = "" if cell is None else str(cell).strip()
        if not declared:
            raise SystemExit(f"wheat workbook declares no unit for column {source!r}")
        source_units[stored] = declared

    subplots: list[dict[str, Any]] = []
    excluded: dict[str, int] = {}
    for raw in rows[2:]:
        record: dict[str, Any] = {}
        for source, (stored, _unit) in WHEAT_COLUMNS.items():
            value = raw[position[source]]
            if _unit in {"identifier", "category", "date"} or _unit is None:
                record[stored] = "" if value is None else str(value).strip()
            else:
                number = _float(value)
                record[stored] = "" if number is None else number
        experiment = str(record.get("experimentId", "")).strip()
        # One sentinel row in the workbook carries the literal string "Cluster_false" in the id
        # column; it is a summary artefact, not a harvested sub-plot.
        if not experiment or not re.fullmatch(r"Exp\d+", experiment):
            excluded["rows without a real experiment id (summary artefact)"] = excluded.get(
                "rows without a real experiment id (summary artefact)", 0) + 1
            continue
        subplots.append(record)

    by_experiment: dict[str, list[dict[str, Any]]] = {}
    for row in subplots:
        by_experiment.setdefault(row["experimentId"], []).append(row)

    aggregates: list[dict[str, Any]] = []
    for experiment in sorted(by_experiment):
        members = by_experiment[experiment]
        yields = [row["grainYieldKgPerM2"] for row in members
                  if isinstance(row.get("grainYieldKgPerM2"), float)]
        aggregate: dict[str, Any] = {
            "experimentId": experiment,
            "system": members[0].get("system", ""),
            "subplotRows": len(members),
            "yieldRows": len(yields),
            "grainYieldKgPerM2Mean": round(statistics.fmean(yields), 6) if yields else "",
            "grainYieldKgPerM2Sd": (round(statistics.stdev(yields), 6)
                                   if len(yields) > 1 else ""),
            "grainYieldKgPerM2Min": round(min(yields), 6) if yields else "",
            "grainYieldKgPerM2Max": round(max(yields), 6) if yields else "",
        }
        for field in ("biomassKgPerM2", "harvestIndexPct"):
            values = [row[field] for row in members if isinstance(row.get(field), float)]
            aggregate[f"{field}Mean"] = round(statistics.fmean(values), 6) if values else ""
        for field in ENV_FIELDS:
            # A LIST, not a set: iterating a set to compute a mean silently drops repeats, which
            # understates the number of sub-plots behind every environment value.
            values = [row[field] for row in members if isinstance(row.get(field), float)]
            if not values:
                aggregate[field] = ""
                continue
            aggregate[field] = round(statistics.fmean(values), 6)
            aggregate[f"{field}SubplotValues"] = len(values)
            aggregate[f"{field}SubplotMin"] = round(min(values), 6)
            aggregate[f"{field}SubplotMax"] = round(max(values), 6)
            aggregate[f"{field}VariesWithinExperiment"] = bool(max(values) - min(values) > 1e-9)
        aggregates.append(aggregate)

    complete = [row for row in aggregates
                if isinstance(row.get("grainYieldKgPerM2Mean"), float)
                and all(row.get(field) not in ("", None) for field in REQUIRED_ENVIRONMENT)]
    varying = {field: sum(1 for row in aggregates
                          if row.get(f"{field}VariesWithinExperiment") is True)
               for field in ENV_FIELDS}

    quality = {
        "rawSha256": sha256(RAW / WHEAT_XLSX),
        "subplotRows": len(subplots),
        "experimentRows": len(aggregates),
        "experimentsWithYieldAndEnvironment": len(complete),
        "experimentsWhereEnvironmentVariesWithinTheRun": varying,
        "excluded": excluded,
        "environmentRanges": {
            field: _range([row[field] for row in aggregates
                           if isinstance(row.get(field), float)])
            for field in REQUIRED_ENVIRONMENT},
        "yieldRange": _range([row["grainYieldKgPerM2Mean"] for row in aggregates]),
        "unitMap": {stored: {"unit": unit, "modelled": unit is not None}
                    for _source, (stored, unit) in WHEAT_COLUMNS.items()},
        # The workbook's own units row, verbatim. Published beside `unitMap` so a reader can see
        # that the stored unit is a translation of a declared one rather than an assertion.
        "sourceUnits": source_units,
    }
    quality["unitMap"]["lightIntegralDayUnidentified"]["why"] = (
        "the workbook's units row tags this column `[s]`, which is not a unit for a photon "
        "integral and does not reconcile with anything around it: the neighbouring column carries "
        "a value three orders of magnitude larger, and neither matches Light_SUM divided by the "
        "cycle length. Unidentifiable, so it is carried for fidelity and never modelled or "
        "converted.")
    quality["unitMap"]["lightIntegralNightUnidentified"]["why"] = (
        "same unidentified quantity as the day column, tagged `[s]` by the workbook and recorded "
        "for fidelity only")
    return subplots, aggregates, quality


# ----------------------------------------------------------------------------- lettuce


def _study_key(label: str) -> str:
    """Collapse "(Pennisi et al., 2019)" and "(Pennisi et al., 2020)" to one study group.

    Several publications report more than one treatment. Those treatments are not independent of
    each other, so the grouping key for cross-study validation is the study, not the row: a fold
    that holds out one treatment of a study and trains on its sibling has leaked.
    """
    text = label.strip("() ").split(",")[0].strip()
    tokens = [token for token in re.split(r"\s+", text) if token]
    return tokens[0] if tokens else text


def build_lettuce() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    workbook = openpyxl.load_workbook(RAW / LETTUCE_XLSX, read_only=True, data_only=True)
    sheet = workbook["dataset"]
    rows = list(sheet.iter_rows(values_only=True))
    header = rows[0]
    position = {str(name).strip(): index for index, name in enumerate(header) if name}
    missing = [name.strip() for name in LETTUCE_COLUMNS if name.strip() not in position]
    if missing:
        raise SystemExit(f"lettuce workbook is missing expected columns: {missing}")

    records: list[dict[str, Any]] = []
    for raw in rows[2:]:
        label = raw[position["Study"]]
        if label in (None, ""):
            continue
        record: dict[str, Any] = {
            "observationKind": "published-treatment-mean",
            "isRawMeasurement": False,
            "crop": "lettuce",
        }
        for source, (stored, unit) in LETTUCE_COLUMNS.items():
            value = raw[position[source.strip()]]
            if unit in {"identifier", "text"}:
                record[stored] = "" if value is None else str(value).strip()
            else:
                number = _float(value)
                record[stored] = "" if number is None else number
        record["studyKey"] = _study_key(record.get("studyLabel", ""))
        records.append(record)

    studies = {record["studyKey"] for record in records}
    quality = {
        "rawSha256": sha256(RAW / LETTUCE_XLSX),
        "rows": len(records),
        "studies": len(studies),
        "treatmentsPerStudy": {
            key: sum(1 for record in records if record["studyKey"] == key)
            for key in sorted(studies)},
        "coverage": {
            field: sum(1 for record in records if record[field] not in ("", None))
            for field in ("co2Ppm", "photoperiodHours", "ppfdUmolPerM2S",
                          "dailyLightIntegralMolPerM2Day", "plantAgeDays",
                          "cumulativeDliMolPerM2", "plantDensityPerM2", "shootDryMassG")},
        "ranges": {
            field: _range([record[field] for record in records])
            for field in ("shootDryMassG", "co2Ppm", "photoperiodHours", "ppfdUmolPerM2S",
                          "plantDensityPerM2")},
        "unitMap": {stored: {"unit": unit, "modelled": unit not in {"identifier", "text"}}
                    for _source, (stored, unit) in LETTUCE_COLUMNS.items()},
    }
    return records, quality


# --------------------------------------------------------------------------------- main


def build() -> dict[str, Any]:
    subplots, aggregates, wheat = build_wheat()
    lettuce_rows, lettuce = build_lettuce()
    _write_csv(OUT / "cea_wheat_subplots.csv", subplots)
    _write_csv(OUT / "cea_wheat_experiments.csv", aggregates)
    _write_csv(OUT / "lettuce_multistudy.csv", lettuce_rows)

    payload = {
        "schema": "spaceagrisim.phase30_datasets/1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "datasets": {
            "cea-wheat-apogee": {
                "id": "cea-wheat-apogee",
                "name": "Indoor wheat (cv. Apogee) under fully controlled environmental conditions",
                "publisher": "Zenodo",
                "doi": "10.5281/zenodo.17764612",
                "license": "CC BY 4.0",
                "file": WHEAT_XLSX,
                "sourceSheet": "Data (Data S2, wheat yields)",
                "crop": "wheat",
                "cultivar": "Apogee",
                "system": "indoor vertical farm, controlled-environment chambers",
                "observationUnit": "harvested sub-plot within one experiment",
                "independenceUnit": "experiment (chamber run)",
                "processedFiles": ["data/processed/phase30/cea_wheat_subplots.csv",
                                   "data/processed/phase30/cea_wheat_experiments.csv"],
                "notAcquired": {
                    "file": "20260801_Data_S1_EnvironmentalConditions.zip",
                    "bytes": 33322741,
                    "reason": ("the chamber climate-computer logs. Data S2 already carries the "
                               "per-experiment environment means computed by the data authors, and "
                               "the raw logs would add no independent information to a model fitted "
                               "at experiment level."),
                },
                **wheat,
            },
            "lettuce-multistudy-lue": {
                "id": "lettuce-multistudy-lue",
                "name": "Lettuce light-use-efficiency compilation across published studies",
                "publisher": "Zenodo",
                "doi": "10.5281/zenodo.14640245",
                "license": "CC BY 4.0",
                "file": LETTUCE_XLSX,
                "sourceSheet": "dataset",
                "crop": "lettuce",
                "cultivar": "mixed across studies",
                "system": "controlled environment, mixed across studies",
                "observationUnit": "published treatment mean",
                "independenceUnit": "study",
                "derivedFrom": ("a compilation of published lettuce light-use-efficiency "
                                "experiments; the source workbook cites the underlying study on "
                                "every row and that citation is preserved as `citation`"),
                "processedFiles": ["data/processed/phase30/lettuce_multistudy.csv"],
                **lettuce,
            },
        },
        "rejected": REJECTED,
        "transformations": TRANSFORMATIONS,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (OUT / "quality.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    if arguments.check:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))["datasets"]
        for name, path in (("cea-wheat-apogee", WHEAT_XLSX),
                           ("lettuce-multistudy-lue", LETTUCE_XLSX)):
            if sha256(RAW / path) != manifest[name]["rawSha256"]:
                raise SystemExit(f"raw file changed for {name}")
        for entry in manifest.values():
            for processed in entry["processedFiles"]:
                if not (ROOT / processed).is_file():
                    raise SystemExit(f"processed table missing: {processed}")
        print("phase30 raw files and processed tables match the committed manifest")
        return 0
    payload = build()
    wheat = payload["datasets"]["cea-wheat-apogee"]
    lettuce = payload["datasets"]["lettuce-multistudy-lue"]
    print(f"wheat: {wheat['experimentRows']} experiments "
          f"({wheat['experimentsWithYieldAndEnvironment']} with yield and environment), "
          f"{wheat['subplotRows']} sub-plot rows")
    print(f"lettuce: {lettuce['rows']} treatments from {lettuce['studies']} published studies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
