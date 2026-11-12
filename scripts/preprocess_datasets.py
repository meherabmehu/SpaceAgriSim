"""Build measured NASA tables; preserve missing outcomes instead of inventing them."""
from __future__ import annotations
import sys as _sys, pathlib as _pathlib   # the repository root holds safedata/
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1]))
import safedata

import csv
import json
import re

from nasa_pipeline import DATA, ROOT, save_json, stamp, validate


def read_csv(path):
    # NASA supplements include legacy Windows-1252 degree symbols.
    body = safedata.bytes(path)
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = body.decode("cp1252")
    return list(csv.reader(text.splitlines()))


def preprocess():
    import numpy as np
    import pandas as pd

    validate()
    destination = DATA / "processed"
    destination.mkdir(exist_ok=True)
    raw = DATA / "raw" / "OSD-655"
    irrigation, harvest = [], []
    missing_mass = []
    for environment, water_file, mass_file in [
        ("flight", "OSD-655_sup_Veg-04-FlightWater.csv", "OSD-655_sup_VEG-04-Flight-Mass.csv"),
        ("ground", "OSD-655_sup_VEG-04-GroundControlWater.csv", "OSD-655_sup_VEG-04-GroundControl-Mass.csv"),
    ]:
        water_rows = read_csv(raw / water_file)
        day_row = next(r for r in water_rows if len(r) > 1 and r[1] == "DAI")
        days = [int(day) for day in day_row[2:27]]
        mass_rows = read_csv(raw / mass_file)
        mass_header = mass_rows[0]
        water_totals = {}
        for row in water_rows:
            if len(row) < 27 or not row[1].isdigit():
                continue
            pillow = int(row[1])
            values = []
            for day, entry in zip(days, row[2:27]):
                if entry.strip() in ("", "---", "NA"):
                    continue
                value = float(entry)
                values.append(value)
                irrigation.append({"studyId": "OSD-655", "experiment": "VEG04A", "environment": environment, "pillow": pillow, "group": f"{environment}-{pillow}", "dayAfterInitiation": day, "waterSuppliedMl": value, "spectrum": "red" if pillow <= 6 else "blue"})
            if abs(sum(values) - float(row[27])) > 0.01:
                raise ValueError(f"Irrigation total mismatch for {environment} pillow {pillow}")
            water_totals[pillow] = sum(values) / 1000
        for row in mass_rows[1:]:
            if not row or row[0] not in ("Flight", "Control"):
                continue
            padded = row + [""] * max(0, len(mass_header) - len(row))
            item = dict(zip(mass_header, padded))
            pillow = int(re.search(r"(\d+)$", item["SN"]).group(1))
            if not item["Total (g)"].strip():
                missing_mass.append(f"{environment}-{pillow}")
                continue
            harvest.append({"studyId": "OSD-655", "experiment": "VEG04A", "crop": "mizuna", "environment": environment, "pillow": pillow, "group": f"pillow-{pillow}", "spectrum": "red" if pillow <= 6 else "blue", "waterSuppliedL": water_totals[pillow], "establishedPlants": int(item["# Established"]), "harvestFreshMassG": float(item["Total (g)"])})
    frames = {"mizuna_harvest": pd.DataFrame(harvest), "mizuna_irrigation": pd.DataFrame(irrigation)}
    for name, frame in frames.items():
        frame.to_csv(destination / f"{name}.csv", index=False, lineterminator="\n")
        frame.to_parquet(destination / f"{name}.parquet", index=False)
    counts_file = next((DATA / "raw" / "OSD-767").glob("*STAR_Unnormalized_Counts*.csv"))
    counts = pd.read_csv(counts_file, index_col=0)
    if counts.isna().any().any() or (counts.to_numpy() < 0).any():
        raise ValueError("Invalid RNA-seq count matrix")
    metadata = safedata.load(DATA / "metadata" / "OSD-767_meta")
    samples = {s["name"]: s for s in metadata["study"]["OSD-767"]["studies"][0]["materials"]["samples"]}
    if set(counts.columns) != set(samples):
        raise ValueError("RNA count headers must match official sample metadata exactly")
    rows = []
    for sample in counts.columns:
        environment = "flight" if "-Flt-" in sample else "ground"
        # Group both tissues from the same plant, preserving leading-zero anomalies by int conversion.
        plant = int(re.search(r"-SN(\d+)-", sample).group(1))
        rows.append({"sample": sample, "studyId": "OSD-767", "environment": environment, "group": f"{environment}-{plant}", "tissue": "root" if "-Root-" in sample else "leaf", "spectrum": "blue" if "-Blue_" in sample else "red"})
    pd.DataFrame(rows).to_csv(destination / "tomato_samples.csv", index=False, lineterminator="\n")
    log_cpm = np.log1p(counts.div(counts.sum(axis=0), axis=1) * 1_000_000).T
    log_cpm.to_parquet(destination / "tomato_log_cpm.parquet")
    quality = {
        "generatedAt": stamp(), "source": "NASA OSDR OSD-655 and OSD-767", "pipelineVersion": 1,
        "mizunaHarvest": {"rows": len(harvest), "missingOutcomePillows": missing_mass, "droppedMissingOutcomes": len(missing_mass), "experiments": 1, "independentCohorts": 2, "targetUnit": "g fresh mass/pillow", "waterUnit": "L supplied over recorded irrigation events", "assumptions": ["Pillows 1-6 red-rich; 7-12 blue-rich, confirmed by official sample metadata.", "Mass supplements use VEG04A only; VEG04B chemistry is not joined.", "Missing harvests are excluded, never coded as zero.", "Irrigation is a management measurement, not measured transpiration or demand."]},
        "mizunaIrrigation": {"rows": len(irrigation), "missingPolicy": "--- and blank excluded; numeric zero retained; irregular event dates are not daily demand", "unit": "mL supplied/event"},
        "tomatoRna": {"samples": len(rows), "genes": len(counts), "plants": len({r['group'] for r in rows}), "normalization": "log1p(count / sample library sum * 1e6)", "label": "recorded flight vs ground experimental context, not stress severity", "geneMissingValues": 0},
    }
    save_json(DATA / "metadata" / "quality_report", quality)
    print(json.dumps(quality, indent=2))


if __name__ == "__main__":
    preprocess()
