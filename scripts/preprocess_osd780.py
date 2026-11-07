"""Build the OSD-780 VEG-04A/B microbial-load table from measured plate counts.

Source files (acquired by scripts/acquire_phase6.py, checksums in
data/metadata/phase6_checksums.json):
    LSDS-128_Plate Count_Aerobic_Plate_Count_TRANSFORMED.csv
    LSDS-128_Plate Count_Yeast_Mold_Plate_Count_Transformed.csv
    OSD-780_dictionary_DataDictionary_OSD-780.csv

What the measurement is (per the NASA data dictionary):
    colony_forming_unit_per_gram_fresh_weight_per_swab  -> CFU per gram of the
    fresh leaf/swab material actually weighed for that assay.

What it is NOT:
    * not harvest biomass, not yield, not growth rate;
    * `fresh_weight_gram` is the mass of the tissue subsample taken for the
      assay, so it must never be used as a biomass label.

Sample-name grammar (observed, not documented upstream):
    <experiment>_<environment>_<tissue>[_pillow<N>|_Sample<N>]_<spectrum>
        [_<treatment>][_harvest<N>]
    experiment : VEG04A | VEG04B
    environment: F  -> flight, GC -> ground control
    tissue     : leaf | Swab
    spectrum   : red | blue
    treatment  : clean (sanitised) | unclean (unsanitised)

Run: python scripts/preprocess_osd780.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw" / "OSD-780"
OUT = DATA / "processed" / "mizuna_microbial_load.csv"
REPORT = DATA / "metadata" / "osd780_quality_report.json"

AEROBIC = "LSDS-128_Plate Count_Aerobic_Plate_Count_TRANSFORMED.csv"
YEAST = "LSDS-128_Plate Count_Yeast_Mold_Plate_Count_Transformed.csv"

# Observed tissue codes, including the numbered soil replicates.
#   leaf | Swab | root | wick | soil_1 | soil_2 | soil_3
PATTERN = re.compile(
    r"^(?P<experiment>VEG04[AB])"
    r"_(?P<environment>GC|F)"
    r"_(?P<tissue>leaf|Swab|root|wick|soil_(?P<soilrep>\d))"
    r"(?:_pillow(?P<pillow>\d+)|_Sample(?P<swab>\d+))"
    r"_(?P<spectrum>red|blue)"
    r"(?:_(?P<treatment>clean|unclean))?"
    r"(?:_harvest(?P<harvest>\d+))?$"
)


def parse_names(names: pd.Series) -> pd.DataFrame:
    parsed = names.astype(str).str.extract(PATTERN)
    parsed["environment"] = parsed["environment"].map({"F": "flight", "GC": "ground"})
    parsed["tissue"] = parsed["tissue"].replace({"Swab": "swab"}).str.replace(
        r"^soil_\d$", "soil", regex=True)
    parsed["treatment"] = parsed["treatment"].fillna("unspecified")
    parsed["harvest"] = pd.to_numeric(parsed["harvest"], errors="coerce")
    # A biological unit is one pillow within one experiment arm. Swab samples are
    # surface swabs of a pillow and are grouped with that pillow's arm.
    parsed["unit"] = (
        parsed["experiment"].fillna("?")
        + "-" + parsed["environment"].fillna("?")
        + "-pillow" + parsed["pillow"].fillna("swab")
    )
    return parsed


def load(path: Path, assay: str) -> pd.DataFrame:
    frame = pd.read_csv(path, encoding="utf-8-sig")
    frame = frame.rename(columns={frame.columns[0]: "sample"})
    # The last row of the aerobic sheet is an artefactual all-NaN row.
    frame = frame[frame["sample"].notna()].copy()
    parsed = parse_names(frame["sample"])
    frame = pd.concat([frame.reset_index(drop=True), parsed.reset_index(drop=True)], axis=1)
    frame["assay"] = assay
    frame["cfuPerG"] = pd.to_numeric(
        frame["colony_forming_unit_per_gram_fresh_weight_per_swab"], errors="coerce")
    frame["cfuPerSwab"] = pd.to_numeric(
        frame["colony_forming_units_per_swab"], errors="coerce")
    frame["freshWeightG"] = pd.to_numeric(frame["fresh_weight_gram"], errors="coerce")
    frame["parsed"] = parsed["experiment"].notna()
    return frame


def main() -> int:
    aerobic = load(RAW / AEROBIC, "aerobic")
    yeast = load(RAW / YEAST, "yeast_mould")

    long = []
    for frame in (aerobic, yeast):
        keep = frame.loc[frame["parsed"], [
            "sample", "assay", "experiment", "environment", "tissue", "pillow",
            "swab", "spectrum", "treatment", "harvest", "unit",
            "freshWeightG", "cfuPerG", "cfuPerSwab",
        ]].copy()
        keep["cfuPerG"] = pd.to_numeric(keep["cfuPerG"], errors="coerce")
        # A zero colony count is a genuine measured "no growth" result and is
        # retained as log10(1+0) = 0. It must not be dropped as missing.
        keep["log10CfuPerG"] = np.log10(1.0 + keep["cfuPerG"].clip(lower=0))
        long.append(keep)
    table = pd.concat(long, ignore_index=True)

    table = table.sort_values(["assay", "experiment", "environment", "tissue", "unit", "sample"])
    table = table.reset_index(drop=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT, index=False, lineterminator="\n")

    report = {
        "source": "NASA OSDR OSD-780 (LSDS-128 VEG-04A/B plate counts)",
        "files": [AEROBIC, YEAST],
        "rowsWritten": int(len(table)),
        "byAssay": {k: int(v) for k, v in table["assay"].value_counts().items()},
        "unparsedSampleNames": {
            "aerobic": int((~aerobic["parsed"]).sum()),
            "yeast_mould": int((~yeast["parsed"]).sum()),
        },
        "missingTarget": int(table["cfuPerG"].isna().sum()),
        "target": "colony_forming_unit_per_gram_fresh_weight_per_swab (CFU per g fresh weight)",
        "alternateTarget": "colony_forming_units_per_swab (CFU per swab) - a DIFFERENT unit, not interchangeable with CFU/g",
        "tissueLevels": sorted(table["tissue"].dropna().astype(str).unique().tolist()),
        "targetTransform": "log10(1 + CFU per g); measured zero counts retained as 0",
        "groupingVariable": "unit = experiment + environment + pillow (biological replicate)",
        "factorLevels": {
            column: sorted(table[column].dropna().astype(str).unique().tolist())
            for column in ("assay", "experiment", "environment", "tissue", "spectrum", "treatment")
        },
        "unitsNote": (
            "freshWeightG is the mass of the tissue subsample taken for the assay. "
            "It is NOT harvest biomass, standing biomass or yield and must never be "
            "used as a biomass label."
        ),
        "limitations": [
            "Plate counts measure culturable aerobic / yeast-mould load only; they are a lower bound on total microbial load.",
            "Swab and leaf samples are different sampling geometries and are not interchangeable measurements.",
            "VEG04A and VEG04B are separate experiments; cross-experiment generalisation must be tested explicitly.",
            "clean vs unclean is a sample-preparation state (sanitised vs unsanitised leaf), not a plant-health label.",
        ],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False) + "\n")

    print(json.dumps({k: report[k] for k in
                      ("rowsWritten", "byAssay", "unparsedSampleNames",
                       "missingTarget", "factorLevels")}, indent=2))
    print(f"\nwritten: {OUT.relative_to(ROOT)}")
    print(f"written: {REPORT.relative_to(ROOT)}")
    print("\ntarget summary by assay / environment / tissue:")
    print(table.groupby(["assay", "experiment", "environment", "tissue"])["log10CfuPerG"]
          .agg(["count", "mean", "std", "min", "max"]).round(3).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
