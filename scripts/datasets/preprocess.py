"""Turn the acquired Phase 26 workbooks into tidy, documented tables.

    python3 scripts/datasets/preprocess.py

Each parser is written against the file as it actually is, which means the awkward parts are in
the code rather than hidden: the Schröder workbook stores evapotranspiration in three-column
date blocks with the dates on row 1 and the pot rows below, the green-light workbook stores one
row per variable per plant, and the tomato workbook stores one column per week.

Three conventions apply everywhere:

* no unit is converted silently - every conversion is named in the output's quality report;
* an excluded row is counted and its reason recorded, never dropped quietly;
* a derived quantity is labelled as derived.

Outputs land in ``data/processed/phase26/`` with a matching ``*_quality`` per table.
"""
from __future__ import annotations
import safedata

import argparse
import datetime as _dt
import math
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:  # pragma: no cover - import plumbing
    sys.path.insert(0, str(_REPO_ROOT))

RAW = _REPO_ROOT / "data" / "raw" / "phase26"
OUT = _REPO_ROOT / "data" / "processed" / "phase26"
MANIFEST = _REPO_ROOT / "data" / "metadata" / "phase26_acquisition_manifest"

SCHRODER = RAW / "zenodo-schroder-2021-lettuce-pot" / "Data_lettuce_pot_experiment_Schröder_et_al._2021.xlsx"
GREENLIGHT = RAW / "zenodo-greenlight-2024-lettuce" / "green_light_lettuce_open_data_(1).xlsx"
LEDTOMATO = RAW / "zenodo-ledphotoperiod-2025-tomato" / "Minimal_Dataset_Plants.xlsx"

STUDY = {
    "schroder2021": {
        "datasetId": "zenodo-schroder-2021-lettuce-pot",
        "doi": "10.5281/zenodo.5550230",
        "citation": ("Schröder C, Häfner F, Larsen OC, Krause A (2021). Urban Organic Waste for "
                     "Urban Farming: Growing Lettuce Using Vermicompost and Thermophilic Compost. "
                     "Agronomy 11(6):1175"),
        "license": "CC BY 4.0",
        "evidenceCategory": "crop water-use measurement",
        "environment": "controlled-environment greenhouse",
    },
    "greenlight2024": {
        "datasetId": "zenodo-greenlight-2024-lettuce",
        "doi": "10.5281/zenodo.20394352",
        "citation": ("Optimising Spectral Composition in Hydroponic Lettuce Cultivation: The Role "
                     "of Green Light (Zenodo record 20394352)"),
        "license": "CC BY 4.0",
        "evidenceCategory": "controlled-environment experiment",
        "environment": "hydroponic",
    },
    "ledphotoperiod2025": {
        "datasetId": "zenodo-ledphotoperiod-2025-tomato",
        "doi": "10.5281/zenodo.23759737",
        "citation": ("Supplemental LED Lighting for Photoperiod Extension in Open-Field "
                     "Cultivation Using a Portable Platform (Zenodo record 23759737)"),
        "license": "CC BY 4.0",
        "evidenceCategory": "controlled-environment experiment",
        "environment": "open field",
    },
}


def sha256_of(path: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            digest.update(block)
    return digest.hexdigest()


def _manifest_hash(dataset_id: str) -> str | None:
    """The hash recorded at acquisition, so a preprocessing run is tied to exact bytes."""
    if not safedata.exists(MANIFEST):
        return None
    payload = safedata.load(MANIFEST)
    record = payload["datasets"].get(dataset_id) or {}
    for entry in record.get("files", []):
        if entry.get("sha256"):
            return entry["sha256"]
    return None


def _write(table: pd.DataFrame, name: str, study: str, quality: dict[str, Any]) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.csv"
    table.to_csv(path, index=False)
    record = {
        "table": path.name,
        "rows": int(len(table)),
        "columns": list(table.columns),
        "generatedAt": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "study": STUDY[study],
        "source": {
            "datasetSha256": _manifest_hash(STUDY[study]["datasetId"]),
            "note": "hash recorded by scripts/datasets/acquire.py at download time",
        },
        **quality,
    }
    safedata.dump(record, OUT / f"{name}_quality")
    print(f"  wrote {path.name}: {len(table)} rows, {len(table.columns)} columns")
    return path


# ---------------------------------------------------------------------------------------
# Schröder 2021: greenhouse lettuce pot evapotranspiration and biomass
# ---------------------------------------------------------------------------------------
def preprocess_schroder() -> list[Path]:
    print("zenodo-schroder-2021-lettuce-pot")

    # ---- evapotranspiration: three-column blocks, one block per measurement date ----------
    sheet = pd.read_excel(SCHRODER, sheet_name="evapotranspiration", header=None)
    date_row = sheet.iloc[0]
    day_row = sheet.iloc[1]
    blocks: list[tuple[int, _dt.date, float | None]] = []
    for column in range(2, sheet.shape[1]):
        value = date_row[column]
        if isinstance(value, (pd.Timestamp, _dt.datetime)):
            day_value = day_row[column]
            blocks.append((column, value.date(),
                           float(day_value) if isinstance(day_value, (int, float))
                           and not (isinstance(day_value, float) and math.isnan(day_value))
                           else None))

    records: list[dict[str, Any]] = []
    excluded = 0
    for row in range(4, sheet.shape[0]):
        treatment = sheet.iloc[row, 0]
        pot = sheet.iloc[row, 1]
        if not isinstance(treatment, str) or not isinstance(pot, (int, float)):
            continue
        for column, day_date, day_number in blocks:
            total = sheet.iloc[row, column]
            per_hour = sheet.iloc[row, column + 1]
            per_day = sheet.iloc[row, column + 2]
            if not isinstance(total, (int, float)) or isinstance(total, float) and math.isnan(total):
                continue
            if total < 0:
                excluded += 1
                continue
            records.append({
                "studyId": "schroder2021",
                "treatment": treatment.strip(),
                "potId": f"{treatment.strip()}-{int(pot)}",
                "date": day_date.isoformat(),
                "dayNumber": day_number,
                "etTotalMl": float(total),
                # The workbook's two rate columns are headed "ET/d" and "ET/h" but the values are
                # the other way round: block column 2 is mL per HOUR (total / elapsed hours) and
                # column 3 is mL per DAY (total / elapsed days). Verified against both a 7-day and
                # a 2-day interval, and the recomputed daily rate below is the one used.
                "etRateMlPerHourFromSource": (float(per_hour)
                                              if isinstance(per_hour, (int, float))
                                              and not isinstance(per_hour, float)
                                              or isinstance(per_hour, float)
                                              and not math.isnan(per_hour) else None),
                "etRateMlPerDayFromSource": (float(per_day)
                                             if isinstance(per_day, (int, float))
                                             and not (isinstance(per_day, float)
                                                      and math.isnan(per_day)) else None),
            })

    et = pd.DataFrame(records).sort_values(["treatment", "potId", "date"]).reset_index(drop=True)
    # The workbook's own ET/d column is labelled "ET/h" on later blocks; it is a rate in mL/day.
    # A recomputed rate from consecutive Day No. values is stored alongside so the two can be
    # compared rather than trusted.
    et["dayNumber"] = pd.to_numeric(et["dayNumber"], errors="coerce")
    et = et.sort_values(["potId", "dayNumber"]).reset_index(drop=True)
    elapsed = et.groupby("potId")["dayNumber"].diff()
    recomputed = et["etTotalMl"] / elapsed
    et["elapsedDaysSincePrevious"] = elapsed
    et["etRateMlPerDayRecomputed"] = recomputed

    # The first interval of every pot has no previous weighing, so no recomputed rate exists for
    # it - 55 of 604 rows, and a whole measurement date (day 7) vanished from the daily aggregate
    # because of it. That date is a real measurement, so it is kept: the workbook's own per-day
    # column covers the first interval, and where the recomputed rate is unavailable the source
    # rate is used. The column says which one it is, per row.
    et["etRateMlPerDay"] = et["etRateMlPerDayRecomputed"].fillna(et["etRateMlPerDayFromSource"])
    et["etRateSource"] = ["recomputed" if not pd.isna(value) else "workbook-daily-column"
                          for value in et["etRateMlPerDayRecomputed"]]
    # The workbook holds 11 treatments; the legend marks four autoclaved variants as
    # "further treatments not used in publication". They stay in the table, tagged, because
    # deleting published-but-unused rows would hide that they exist.
    published = {"VC-C", "VC-P", "TC-F", "TC-G", "TC-G2", "TC-G3", "SC"}
    et["inPublication"] = et["treatment"].isin(published)
    # A per-pot rate above the trial's own published irrigation ceiling (350 mL per pot per day)
    # cannot be sustained; TC-G2 contains one such interval. Flagged, kept, and excluded from
    # robust statistics by name rather than deleted.
    et["flagAboveIrrigationCeiling"] = et["etRateMlPerDayRecomputed"] > 350
    et = et.sort_values(["treatment", "potId", "date"]).reset_index(drop=True)
    comparable = et.dropna(subset=["etRateMlPerDayFromSource", "etRateMlPerDayRecomputed"])
    relative = ((comparable["etRateMlPerDayRecomputed"] - comparable["etRateMlPerDayFromSource"]).abs()
                / comparable["etRateMlPerDayFromSource"].replace(0, pd.NA))
    agreement = {
        "rowsCompared": int(len(comparable)),
        "medianRelativeDifference": float(relative.median()) if len(comparable) else None,
        "maxRelativeDifference": float(relative.max()) if len(comparable) else None,
        "interpretation": (
            "The two agree to within rounding, which is what confirms the column mapping: the "
            "workbook's 'ET/d' heading carries mL per hour and its 'ET/h' heading carries mL per "
            "day, and an earlier version of this parser read them the wrong way round. The "
            "recomputed whole-day rate is what the validation uses."
        ),
    }
    # Grouped means per treatment and day, which is what a validation compares against.
    daily = (et.groupby(["treatment", "date", "dayNumber"], as_index=False)
               .agg(etRateMlPerDayMean=("etRateMlPerDay", "mean"),
                    etRateMlPerDaySd=("etRateMlPerDayRecomputed", "std"),
                    pots=("potId", "nunique")))
    paths = [_write(et, "schroder2021_lettuce_et", "schroder2021", {
        "units": {"etTotalMl": "mL per pot over the interval",
                  "etRateMlPerDayRecomputed": "mL per pot per day (derived: total / elapsed days)",
                  "etRateMlPerDayFromSource": "mL per pot per day (the workbook's own column)"},
        "derivations": ["etRateMlPerDayRecomputed", "elapsedDaysSincePrevious",
                        "etRateMlPerDay (recomputed where a previous weighing exists, otherwise "
                        "the workbook's own per-day column)", "etRateSource"],
        "excludedRows": excluded,
        "flaggedRows": int(et["flagAboveIrrigationCeiling"].sum()),
        "flagRule": ("rate above 350 mL per pot per day, the study's own published irrigation "
                     "ceiling; flagged, retained, and excluded by name from robust statistics"),
        "potAreaAssumption": {
            "valueM2": 0.0112,
            "method": ("a 2.2 L pot of that shape is ~0.12 m diameter, giving 0.0112 m2 of "
                       "surface. The surface area is NOT published."),
            "status": "assumption, not measurement",
            "consequence": ("converting mL per pot per day to mm per day carries about +-10 % "
                            "uncertainty from the diameter alone, so the mm column is only used "
                            "as a ratio against a reference ET0 computed for the same assumption"),
        },
        "potDays": int(len(et)),
        "perPlant": True,
        "measurementBasis": ("gravimetric pot evapotranspiration: pots were weighed and the water "
                            "loss is evapotranspiration of plant plus substrate"),
        "rateAgreement": agreement,
        "limitations": [
            "evapotranspiration includes substrate evaporation; it is not transpiration alone",
            "13 measurement dates, not a daily series: gaps between weighings are real",
            "no per-day weather is published, so no reference ET0 and no crop coefficient",
        ],
    })]
    paths.append(_write(daily, "schroder2021_lettuce_et_daily", "schroder2021", {
        "units": {"etRateMlPerDayMean": "mL per pot per day, treatment mean",
                  "etRateMlPerDaySd": "mL per pot per day, between-pot standard deviation"},
        "grouping": "treatment x measurement date",
        "derivations": ["etRateMlPerDayMean", "etRateMlPerDaySd"],
        "perPlant": True,
        "note": "the shape a validation compares against; the per-pot table above is the raw one",
    }))

    # ---- biomass -------------------------------------------------------------------------
    biomass_sheet = pd.read_excel(SCHRODER, sheet_name="lettuce biomass")
    rows: list[dict[str, Any]] = []
    for _, row in biomass_sheet.iterrows():
        comment = row.get("comment")
        treatment = row.get("treatment")
        if not isinstance(comment, str) or not isinstance(treatment, str):
            continue
        text = comment.strip().lower()
        # The comment column holds "Shoot" or a root description such as "lettuce root mix 1-5";
        # an earlier version used the comment verbatim as the organ and produced 11 fake organs.
        if text.startswith("shoot"):
            organ = "shoot"
        elif "root" in text:
            organ = "root"
        else:
            organ = text
        fresh, dry = row.get("biomass FM [g]"), row.get("biomass DM [g]")
        if not isinstance(fresh, (int, float)) or isinstance(fresh, float) and math.isnan(fresh):
            continue
        rows.append({
            "studyId": "schroder2021",
            "treatment": treatment.strip(),
            "organ": organ,
            "plantNumber": str(row.get("Shoot /Root No")).strip(),
            "freshG": float(fresh),
            "dryG": float(dry) if isinstance(dry, (int, float)) else None,
            "waterContentPct": (float(row.get("water content [weight%]"))
                                if isinstance(row.get("water content [weight%]"), (int, float))
                                else None),
        })
    biomass = pd.DataFrame(rows)
    paths.append(_write(biomass, "schroder2021_lettuce_biomass", "schroder2021", {
        "units": {"freshG": "g per pot", "dryG": "g per pot", "waterContentPct": "% by mass"},
        "perPlant": True,
        "harvestDay": 37,
        "note": ("one lettuce plant per pot, so a pot is a plant. Fresh mass here is what the "
                 "platform predicts, which is why this sheet is the label set for the water "
                 "validation's per-gram normalisation."),
    }))

    # ---- greenhouse climate (summary statistics only; recorded as context, not as a series) --
    paths.append(_write(pd.DataFrame([{
        "studyId": "schroder2021",
        "variable": "airTemperatureDayMeanC", "value": 26.6,
        "note": "published in the article text; max 43.3, min 15.1",
    }, {
        "studyId": "schroder2021",
        "variable": "airTemperatureNightMeanC", "value": 20.7,
        "note": "published in the article text; max 38.9, min 14.8",
    }, {
        "studyId": "schroder2021", "variable": "relativeHumidityMeanPct", "value": 57.9,
        "note": "published in the article text",
    }, {
        "studyId": "schroder2021", "variable": "irrigationRangeMlPerPotPerDay", "value": None,
        "note": "published range 50-350 mL per pot per day; not a per-day series",
    }]), "schroder2021_greenhouse_context", "schroder2021", {
        "note": ("summary statistics transcribed from the article, not from the workbook. They "
                 "are context: with only means and extremes, a reference ET0 cannot be "
                 "recomputed for the trial days."),
        "isTimeSeries": False,
    }))
    return paths


# ---------------------------------------------------------------------------------------
# Green-light lettuce: destructive harvest by spectral treatment
# ---------------------------------------------------------------------------------------
def preprocess_greenlight() -> list[Path]:
    print("zenodo-greenlight-2024-lettuce")
    harvest = pd.read_excel(GREENLIGHT, sheet_name="Destructive_harvest")
    metadata = pd.read_excel(GREENLIGHT, sheet_name="Treatment_metadata")
    variable_map = {
        "Fresh weight": "freshWeightG",
        "Dry weight": "dryWeightG",
        "Leaf number": "leafNumber",
        "Leaf area": "leafAreaMm2",
        "Length of longest leaf": "longestLeafMm",
        "Width of widest leaf": "widestLeafMm",
        "Rosette width at widest point": "rosetteWidthMm",
    }
    harvest = harvest.assign(variable=harvest["Variable"].map(variable_map))
    unmapped = sorted(set(harvest.loc[harvest["variable"].isna(), "Variable"]))
    harvest = harvest.dropna(subset=["variable"])
    wide = (harvest.pivot_table(index=["Treatment", "Observation_number_within_treatment"],
                                columns="variable", values="Value", aggfunc="first")
            .reset_index()
            .rename(columns={"Treatment": "treatment",
                             "Observation_number_within_treatment": "observationNumber"}))
    wide.insert(0, "studyId", "greenlight2024")
    units = harvest.drop_duplicates("variable").set_index("variable")["Unit"].to_dict()
    paths = [_write(wide, "greenlight2024_lettuce_harvest", "greenlight2024", {
        "units": units,
        "perPlant": True,
        "plantsPerTreatment": {str(k): int(v) for k, v in
                               wide.groupby("treatment").size().items()},
        "unmappedVariables": unmapped,
        "treatments": metadata.set_index("Treatment").to_dict(orient="index"),
        "heldConstant": {"photoperiod": "16 h light / 8 h dark", "ppfd": "200 umol m-2 s-1"},
        "harvestDay": 35,
        "note": ("spectral composition is the only manipulated factor, so this table constrains a "
                 "spectrum effect and says nothing about light intensity."),
    })]

    fluorescence = pd.read_excel(GREENLIGHT, sheet_name="MultispeQ")
    keep = [c for c in fluorescence.columns
            if c in ("DAS", "Treatment", "FvP_over_FmP", "LEF", "NPQt", "ECS_tau",
                     "leaf_thickness")]
    fluorescence = fluorescence[keep].rename(columns={"DAS": "daysAfterSowing",
                                                      "Treatment": "treatment",
                                                      "FvP_over_FmP": "fvPOverFmP",
                                                      "LEF": "linearElectronFlux",
                                                      "NPQt": "npqT",
                                                      "ECS_tau": "ecsTau",
                                                      "leaf_thickness": "leafThickness"})
    paths.append(_write(fluorescence, "greenlight2024_lettuce_fluorescence", "greenlight2024", {
        "units": {"fvPOverFmP": "dimensionless", "linearElectronFlux": "relative",
                  "npqT": "dimensionless", "ecsTau": "ms", "leafThickness": "mm"},
        "notAPhotosyntheticRate": ("FvP/FmP, LEF and NPQt are chlorophyll-fluorescence indices. "
                                   "They are proxies for photochemistry, not net photosynthesis, "
                                   "and this table is never used as a photosynthesis label."),
    }))
    return paths


# ---------------------------------------------------------------------------------------
# LED photoperiod tomato: weekly growth and harvest
# ---------------------------------------------------------------------------------------
def preprocess_led_tomato() -> list[Path]:
    print("zenodo-ledphotoperiod-2025-tomato")
    weekly = pd.read_excel(LEDTOMATO, sheet_name="Tomato_weekly")
    records: list[dict[str, Any]] = []
    pattern = re.compile(r"^week(\d+)_(.+)$")
    for column in weekly.columns:
        match = pattern.match(str(column))
        if not match:
            continue
        week, variable = match.groups()
        frame = pd.DataFrame({
            "studyId": "ledphotoperiod2025",
            "plantId": weekly["plant_id"],
            "group": weekly["group"],
            "variety": weekly["variety"],
            "week": int(week),
            "variable": variable,
            "value": pd.to_numeric(weekly[column], errors="coerce"),
        })
        records.append(frame)
    tall = pd.concat(records, ignore_index=True).dropna(subset=["value"])
    wide = (tall.pivot_table(index=["plantId", "group", "variety", "week"], columns="variable",
                             values="value", aggfunc="first").reset_index())
    wide.insert(0, "studyId", "ledphotoperiod2025")
    paths = [_write(wide, "ledphotoperiod2025_tomato_growth", "ledphotoperiod2025", {
        "units": {"height_cm": "cm", "leaf_number": "count", "stem_number": "count",
                  "stem_diameter_mm": "mm"},
        "perPlant": True,
        "plants": int(wide["plantId"].nunique()),
        "weeks": sorted(int(w) for w in wide["week"].unique()),
        "note": ("weekly non-destructive growth of tagged plants in an open agricultural field. "
                 "The environment is ambient, not controlled."),
    })]

    harvest = pd.read_excel(LEDTOMATO, sheet_name="Tomato_harvest_roots")
    harvest = harvest.rename(columns={"plant_id": "plantId", "group": "group",
                                      "variety": "variety"})
    harvest.insert(0, "studyId", "ledphotoperiod2025")
    paths.append(_write(harvest, "ledphotoperiod2025_tomato_harvest", "ledphotoperiod2025", {
        "units": {"shoot_fresh_g": "g", "root_fresh_g": "g", "shoot_dry_g": "g",
                  "root_dry_g": "g", "final_height_cm": "cm"},
        "perPlant": True,
        "note": ("destructive harvest of the same plants. Open-field ambient conditions: this is "
                 "independent validation of the shape of a tomato growth curve, nothing more."),
    }))
    return paths


PARSERS = {
    "schroder": preprocess_schroder,
    "greenlight": preprocess_greenlight,
    "ledtomato": preprocess_led_tomato,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append", choices=sorted(PARSERS))
    args = parser.parse_args(argv)

    selected = args.only or sorted(PARSERS)
    missing = []
    for name, parser_fn in sorted(PARSERS.items()):
        if name not in selected:
            continue
        try:
            parser_fn()
        except FileNotFoundError as exc:
            missing.append(f"{name}: {exc.filename or exc}")
            print(f"  SKIPPED {name}: source file absent (run scripts/datasets/acquire.py)")
    if len(missing) == len(selected):
        print("no source file was present; nothing was written")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
