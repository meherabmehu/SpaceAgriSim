"""Phase 29: build the light-quality stress dataset from a verified, licensed source.

The source
----------
"Optimising Spectral Composition in Hydroponic Lettuce Cultivation: The Role of Green Light, Open
Data", Zenodo record 20394352, DOI 10.5281/zenodo.20394352, CC BY 4.0. Acquired in Phase 26; this
script does not re-download it, it re-verifies the file already in the repository against the
SHA-256 recorded in `data/metadata/phase26_acquisition_manifest.json` and refuses to build if the
bytes differ.

The design, transcribed from the workbook's own `Treatment_metadata` sheet
--------------------------------------------------------------------------
Red Batavia lettuce, 200 umol/m2/s PPFD, 16 h photoperiod for every treatment, harvested at 35 days
after sowing. Four treatments:

    regime   green-light fraction                       relative planting density
    Control  ~5.08 % (red-blue dominant)                1.00
    T1       24 % fixed                                1.00
    T2       16 % week 1, 24 % week 2, 32 % week 3      1.00
    T3       same schedule as T2                       1.25

That last row is why this dataset cannot support a continuous spectrum response surface: T3 changes
two things at once (spectrum and density), and the spectrum itself moves through the experiment in
T2 and T3. Both facts are recorded per regime and carried into every API response.

What is built
-------------
* `light_spectrum_treatments.csv`  - the design, one row per regime, with the two caveats encoded.
* `light_stress_harvest.csv`       - per-plant destructive harvest traits, long format preserved
                                     from the workbook so nothing is merged that the source kept
                                     separate.
* `light_stress_photosynthesis.csv`- per-plant MultispeQ traits at 28 and 35 days after sowing.
* `light_stress_pigments.csv`      - per-sample leaf pigment and antioxidant assays, by leaf
                                     position.
* `light_stress_quality.json`      - what was read, what was dropped and why, with counts.

What is never done
------------------
No value is imputed, no missing cell is filled from a mean, no unit is converted silently, and no
observation is removed except where the source marks it as not measured (an empty cell). Exclusion
counts are reported per trait.

Run: python ml/research/build_light_stress_dataset.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from nasa_pipeline import save_json, stamp  # noqa: E402

RAW = ROOT / "data" / "raw" / "phase26" / "zenodo-greenlight-2024-lettuce" / \
    "green_light_lettuce_open_data_(1).xlsx"
MANIFEST = ROOT / "data" / "metadata" / "phase26_acquisition_manifest.json"
OUT_DIR = ROOT / "data" / "processed" / "phase29"

DATASET_ID = "zenodo-greenlight-2024-lettuce"
DOI = "10.5281/zenodo.20394352"
LICENSE = "CC BY 4.0"

# The workbook's `Treatment_metadata` sheet, transcribed verbatim into machine-readable form.
# `greenFractionAssumed`: the control sheet states "approx. 5.08 %", which is the source's own
# estimate, not a measured spectrum. It is carried as an approximation and labelled as one.
TREATMENTS = [
    {"regime": "control", "sourceLabel": "Control",
     "description": "Red-blue dominant control spectrum",
     "greenFractionPct": 5.08, "greenFractionIsApproximate": True,
     "greenRegimeFixed": True, "relativePlantingDensity": 1.00,
     "confoundsSpectrumWithDensity": False,
     "spectrumVariesDuringExperiment": False},
    {"regime": "t1", "sourceLabel": "T1",
     "description": "Fixed green-enriched spectrum, 24 % green throughout",
     "greenFractionPct": 24.0, "greenFractionIsApproximate": False,
     "greenRegimeFixed": True, "relativePlantingDensity": 1.00,
     "confoundsSpectrumWithDensity": False,
     "spectrumVariesDuringExperiment": False},
    {"regime": "t2", "sourceLabel": "T2",
     "description": "Incrementally increasing green: 16 % week 1, 24 % week 2, 32 % week 3",
     "greenFractionPct": 24.0, "greenFractionIsApproximate": False,
     "greenRegimeFixed": False, "relativePlantingDensity": 1.00,
     "confoundsSpectrumWithDensity": False,
     "spectrumVariesDuringExperiment": True,
     "greenFractionByWeekPct": [16.0, 24.0, 32.0]},
    {"regime": "t3", "sourceLabel": "T3",
     "description": "Same incremental spectrum as T2 at 25 % higher planting density",
     "greenFractionPct": 24.0, "greenFractionIsApproximate": False,
     "greenRegimeFixed": False, "relativePlantingDensity": 1.25,
     "confoundsSpectrumWithDensity": True,
     "spectrumVariesDuringExperiment": True,
     "greenFractionByWeekPct": [16.0, 24.0, 32.0]},
]
COMMON_CONDITIONS = {"ppfdUmolPerM2S": 200.0, "photoperiodHours": 16.0,
                     "dailyLightIntegralMolPerM2Day": 200.0 * 16.0 * 3600.0 / 1e6,
                     "crop": "lettuce", "cultivar": "Red Batavia",
                     "harvestDaysAfterSowing": 35}

HARVEST_TRAITS = {
    "Fresh weight": ("freshWeightG", "g"),
    "Dry weight": ("dryWeightG", "g"),
    "Leaf area": ("leafAreaMm2", "mm2"),
    "Leaf number": ("leafNumber", "count"),
    "Length of longest leaf": ("longestLeafMm", "mm"),
    "Rosette width at widest point": ("rosetteWidthMm", "mm"),
    "Width of widest leaf": ("widestLeafMm", "mm"),
}
PHOTO_TRAITS = {
    "FvP_over_FmP": "fvPOverFmP",
    "NPQt": "npqT",
    "Phi2": "phi2",
    "PhiNPQ": "phiNPQ",
    "PhiNO": "phiNO",
    "LEF": "linearElectronFlux",
    "qL": "qL",
    "SPAD": "spad",
    "leaf_thickness": "leafThickness",
}
PIGMENT_TRAITS = {
    "Chlorophyll a": "chlorophyllAMgPerGFw",
    "Chlorophyll b": "chlorophyllBMgPerGFw",
    "Total chlorophyll": "totalChlorophyllMgPerGFw",
    "Total carotenoids": "totalCarotenoidsMgPerGFw",
    "Total flavonoids": "totalFlavonoidsMgQePerGFw",
    "Total polyphenols": "totalPolyphenolsMgGaePerGFw",
    "Antioxidant activity": "antioxidantActivityUmQe",
}


def verify_raw() -> dict:
    manifest = json.loads(MANIFEST.read_text())
    entry = manifest["datasets"][DATASET_ID]
    recorded = entry["files"][0]["sha256"]
    body = RAW.read_bytes()
    actual = hashlib.sha256(body).hexdigest()
    if actual != recorded:
        raise SystemExit(
            f"refusing to build: {RAW.name} hashes to {actual[:16]}... but the manifest recorded "
            f"{recorded[:16]}...")
    return {"path": str(RAW.relative_to(ROOT)), "sha256": actual, "bytes": len(body),
            "verifiedAgainstManifest": True}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw = verify_raw()
    label_to_regime = {t["sourceLabel"]: t["regime"] for t in TREATMENTS}

    design = pd.DataFrame(TREATMENTS)
    for key, value in COMMON_CONDITIONS.items():
        design[key] = value
    design_path = OUT_DIR / "light_spectrum_treatments.csv"
    design.to_csv(design_path, index=False)

    # ---- destructive harvest (long format in the source) -------------------------------
    harvest_sheet = pd.read_excel(RAW, sheet_name="Destructive_harvest")
    rows, dropped = [], {}
    for variable, (column, unit) in HARVEST_TRAITS.items():
        subset = harvest_sheet[harvest_sheet.Variable == variable]
        if subset.empty:
            dropped[variable] = "not present in the source sheet"
            continue
        missing = int(subset.Value.isna().sum())
        if missing:
            dropped[variable] = f"{missing} unmeasured cells left out"
        for _, record in subset.iterrows():
            if pd.isna(record.Value):
                continue
            rows.append({
                "studyId": DATASET_ID,
                "regime": label_to_regime[record.Treatment],
                "observationNumber": int(record.Observation_number_within_treatment),
                "trait": column,
                "unit": unit,
                "value": float(record.Value),
            })
    harvest = pd.DataFrame(rows)
    harvest_path = OUT_DIR / "light_stress_harvest.csv"
    harvest.to_csv(harvest_path, index=False)

    # ---- photosynthesis (MultispeQ) -----------------------------------------------------
    multispeq = pd.read_excel(RAW, sheet_name="MultispeQ")
    photo_rows, photo_missing = [], {}
    for column, name in PHOTO_TRAITS.items():
        missing = int(multispeq[column].isna().sum())
        if missing:
            photo_missing[name] = missing
        for _, record in multispeq.iterrows():
            if pd.isna(record[column]):
                continue
            photo_rows.append({
                "studyId": DATASET_ID,
                "regime": label_to_regime[record.Treatment],
                "daysAfterSowing": int(record.DAS),
                "trait": name,
                "unit": _photo_unit(name),
                "value": float(record[column]),
            })
    photosynthesis = pd.DataFrame(photo_rows)
    photo_path = OUT_DIR / "light_stress_photosynthesis.csv"
    photosynthesis.to_csv(photo_path, index=False)

    # ---- pigments ------------------------------------------------------------------------
    assays = pd.read_excel(RAW, sheet_name="Postharvest_assays")
    pigment_rows, pigment_dropped = [], {}
    for variable, name in PIGMENT_TRAITS.items():
        subset = assays[assays.Variable == variable]
        if subset.empty:
            pigment_dropped[variable] = "not present in the source sheet"
            continue
        if subset.Value.isna().any():
            pigment_dropped[variable] = f"{int(subset.Value.isna().sum())} unmeasured cells"
        for _, record in subset.iterrows():
            if pd.isna(record.Value):
                continue
            pigment_rows.append({
                "studyId": DATASET_ID,
                "regime": label_to_regime[record.Treatment],
                "leafPosition": str(record.Leaf_position).lower(),
                "trait": name,
                "unit": str(record.Unit),
                "value": float(record.Value),
            })
    pigments = pd.DataFrame(pigment_rows)
    pigment_path = OUT_DIR / "light_stress_pigments.csv"
    pigments.to_csv(pigment_path, index=False)

    quality = {
        "schema": "spaceagrisim.phase29_light_stress_dataset/1",
        "generatedAt": stamp(),
        "source": {"dataset": DATASET_ID, "doi": DOI, "license": LICENSE,
                   "file": raw,
                   "citation": ("Zenodo record 20394352, 'Optimising Spectral Composition in "
                                "Hydroponic Lettuce Cultivation: The Role of Green Light, Open "
                                "Data'. Author list per the Zenodo landing page.")},
        "design": {"treatments": len(TREATMENTS), "commonConditions": COMMON_CONDITIONS,
                   "confoundedTreatment": "t3 (spectrum and planting density both change)",
                   "timeVaryingSpectrum": ["t2", "t3"],
                   "designNote": ("Four regimes, not a gradient. The dataset supports comparing "
                                  "named spectral regimes. It does not support fitting a "
                                  "continuous response surface in green-light fraction, because "
                                  "only two regimes hold a fixed spectrum and one of them is the "
                                  "control.")},
        "records": {
            "harvestRows": int(len(harvest)),
            "harvestPerTrait": {k: int(v) for k, v in
                                harvest.groupby("trait").size().to_dict().items()},
            "photosynthesisRows": int(len(photosynthesis)),
            "photosynthesisPerTrait": {k: int(v) for k, v in
                                       photosynthesis.groupby("trait").size().to_dict().items()},
            "pigmentRows": int(len(pigments)),
            "pigmentPerTrait": {k: int(v) for k, v in
                                pigments.groupby("trait").size().to_dict().items()},
        },
        "exclusions": {"harvest": dropped, "photosynthesisMissingCells": photo_missing,
                       "pigments": pigment_dropped},
        "transformations": [
            "long-format source kept long; no trait was pivoted into another's place",
            "treatment labels mapped to lower-case regime ids; the source label is kept in the "
            "design table as sourceLabel",
            "no unit conversion, no imputation, no outlier removal",
        ],
        "limits": [
            "One experiment, one cultivar (Red Batavia), one light level (200 umol/m2/s), one "
            "photoperiod (16 h).",
            "PPFD and photoperiod are constant across regimes, so this dataset cannot identify a "
            "light-intensity or daily-light-integral response.",
            "Ambient CO2 is not reported and not varied; nothing here supports a CO2 response.",
            "Green-light fraction is given by the source as a percentage of the spectrum, not as a "
            "measured spectral power distribution; the control value is the source's own "
            "approximation.",
        ],
    }
    save_json(OUT_DIR / "light_stress_quality.json", quality)
    print(json.dumps({"raw": raw, "rows": quality["records"], "exclusions": quality["exclusions"]},
                     indent=1)[:1800])


def _photo_unit(name: str) -> str:
    return {"fvPOverFmP": "fraction", "npqT": "dimensionless", "phi2": "fraction",
            "phiNPQ": "fraction", "phiNO": "fraction", "linearElectronFlux": "dimensionless",
            "qL": "fraction", "spad": "spad-index", "leafThickness": "mm"}[name]


if __name__ == "__main__":
    main()
