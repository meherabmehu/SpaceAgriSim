"""Acquire and normalize the small public OSD-895 ISA biomass metadata table.

This source reports crop/cycle summaries from the terrestrial EDEN ISS
greenhouse analogue. It is intentionally *not* used to train a yield model:
the rows mix species, cultivars, harvest protocols and summary ranges.
"""
from __future__ import annotations
import sys

import csv
import hashlib
import json
import shutil
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
RAW = ROOT / "data" / "raw" / "OSD-895"
METADATA = ROOT / "data" / "metadata"
PROCESSED = ROOT / "data" / "processed"
URL = "https://osdr.nasa.gov/geode-py/ws/studies/OSD-895/download?source=datamanager&file=OSD-895_metadata_OSD-895-ISA.zip"
NAME = "OSD-895_metadata_OSD-895-ISA.zip"


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    archive = RAW / NAME
    if not safedata.exists(archive):
        request = urllib.request.Request(URL, headers={"User-Agent": "SpaceAgriSim/2.0 scientific audit"})
        with urllib.request.urlopen(request, timeout=90) as response:
            archive.write_bytes(response.read(1_000_000))
    if archive.stat().st_size != 72_795:
        raise ValueError("Unexpected OSD-895 archive size")
    unpacked = RAW / "metadata"
    if safedata.exists(unpacked):
        shutil.rmtree(unpacked)
    with zipfile.ZipFile(archive) as zf:
        if any(Path(name).is_absolute() or ".." in Path(name).parts for name in zf.namelist()):
            raise ValueError("Unsafe archive member")
        zf.extractall(unpacked)
    table = next(unpacked.glob("a_*plant-material-biomass_ECSO.txt"))
    with table.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    with (PROCESSED / "eden_iss_2018_biomass_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sourceSample", "harvestAgeDays", "meanEdibleFreshweightKgM2", "edibleFreshweightRangeGm2", "abovegroundDryBiomassGm2", "belowgroundDryBiomassGm2"])
        writer.writeheader()
        for row in rows:
            writer.writerow({"sourceSample": row["Sample Name"], "harvestAgeDays": row["Parameter Value[Age At Sample Harvest]"], "meanEdibleFreshweightKgM2": row["Parameter Value[Mean Edible Freshweight]"], "edibleFreshweightRangeGm2": row["Parameter Value[Edible Freshweight Range]"], "abovegroundDryBiomassGm2": row["Parameter Value[Aboveground Dry Biomass]"], "belowgroundDryBiomassGm2": row["Parameter Value[Belowground Dry Biomass]"]})
    record = {"id": "OSD-895", "title": "Biomass Production of the EDEN ISS Space Greenhouse in Antarctica During the 2018 Experiment Phase", "sourceUrl": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-895", "sourceType": "NASA OSDR terrestrial analogue", "downloadUrl": URL, "license": "Public OSDR access; retain attribution and comply with OSDR terms", "licenseUrl": "https://science.nasa.gov/reference/osdr-help-terms-and-conditions/", "file": {"path": "data/raw/OSD-895/" + NAME, "bytes": archive.stat().st_size, "sha256": hashlib.sha256(safedata.bytes(archive)).hexdigest()}, "processedTable": "data/processed/eden_iss_2018_biomass_summary.csv", "rowCount": len(rows), "targets": ["mean edible freshweight (kg/m2)", "aboveground/belowground dry biomass (g/m2)", "harvest age (days)"], "classification": "useful for scientific calibration", "trainingEligibility": "not trainable as a general model without cycle-level observations and protocol harmonization", "limitations": ["Terrestrial Antarctica analogue, not spaceflight.", "Rows mix species/cultivars and batch/spread harvest conventions.", "Freshweight range field must not be expanded into pseudo-replicates.", "Metadata table reports summaries rather than independent plant-level time series."], "acquiredAt": datetime.now(timezone.utc).isoformat()}
    safedata.dump({"datasets": [record]}, METADATA / "phase2_nasa_candidates")
    print(json.dumps({"id": record["id"], "rows": len(rows), "sha256": record["file"]["sha256"]}, indent=2))


if __name__ == "__main__":
    main()
