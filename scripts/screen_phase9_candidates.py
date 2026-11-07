"""Screen the sweep's usable studies for Phase 9 Priority C (crop microbiome).

The broad sweep answers "what exists". This narrows it to "what could support the
model families the brief asks for", which is the question that decides whether a
crop-microbiome model is buildable at all.

A study qualifies for a microbiome model only if it publishes a **processed
taxonomic abundance table** (OTU/ASV/taxonomy matrix). A raw amplicon FASTQ
deposit does not qualify: this project does not run a QIIME/DADA2 pipeline, and
inventing one mid-phase would put an unvalidated pipeline under a scientific claim.

Output: data/metadata/phase9_candidate_screen.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from sweep_phase9_osdr import BUCKET, list_objects  # noqa: E402

METADATA = ROOT / "data" / "metadata"

TAXONOMY_TABLE = ("otu", "asv", "taxonom", "phyla", "genus", "species_abundance",
                  "relabund", "relative_abundance", "counts_gl16s")
CROP = ("lactuca", "lettuce", "brassica", "mizuna", "solanum", "tomato", "cucumis",
        "capsicum", "solanum_tuberosum", "potato", "arabidopsis", "oryza", "rice",
        "glycine", "soybean", "triticum", "wheat", "medicago", "pisum", "pea")
MICROBIOME = ("microbiom", "16s", "its_", "amplicon", "metagenom", "bacteria",
              "fungal", "community", "rhizosphere", "endophyt")


def all_objects(study: str, max_pages: int = 4) -> list[dict]:
    objects, token, pages = [], None, 0
    while pages < max_pages:
        prefix = f"{study}/"
        suffix = f"&continuation-token={token}" if token else ""
        url = f"{BUCKET}/?list-type=2&prefix={prefix}&max-keys=1000{suffix}"
        import urllib.request
        request = urllib.request.Request(url, headers={"User-Agent": "SpaceAgriSim/3.0"})
        with urllib.request.urlopen(request, timeout=45) as response:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.read())
        ns = "{http://s3.amazonaws.com/doc/2006-03-01/}"
        objects.extend({"key": item.find(f"{ns}Key").text,
                        "bytes": int(item.find(f"{ns}Size").text)}
                       for item in root.findall(f"{ns}Contents"))
        node = root.find(f"{ns}NextContinuationToken")
        token = node.text if node is not None else None
        pages += 1
        if not token:
            break
    return objects


def screen(study: str, objects: list[dict]) -> dict | None:
    keys = [item["key"] for item in objects]
    joined = " ".join(keys).lower()
    taxonomy_tables = sorted({key for key in keys
                              if key.endswith((".csv", ".tsv", ".txt"))
                              and any(signal in key.lower() for signal in TAXONOMY_TABLE)})
    crops = sorted({crop for crop in CROP if crop in joined})
    microbial = sorted({signal for signal in MICROBIOME if signal in joined})
    if not crops and not taxonomy_tables:
        return None
    qualifies = bool(taxonomy_tables)
    return {
        "study": study,
        "objects": len(objects),
        "bytes": sum(item["bytes"] for item in objects),
        "cropSignals": crops,
        "microbiomeSignals": microbial[:6],
        "taxonomyTables": taxonomy_tables[:6],
        "quadrant": ("crop-microbiome" if crops and microbial else
                     "crop-only" if crops else "microbiome-only"),
        "verdict": ("candidate-processed-taxonomy-table" if qualifies
                    else "rejected-no-processed-taxonomy-table"),
    }


def main() -> int:
    sweep = json.loads((METADATA / "phase9_osdr_sweep.json").read_text())
    usable = sweep["usableProcessedMatrix"]
    results = []
    for index, study in enumerate(usable, 1):
        try:
            objects = all_objects(study)
        except Exception as error:  # a transient failure must not fake a rejection
            results.append({"study": study, "error": str(error)})
            continue
        record = screen(study, objects)
        if record:
            results.append(record)
        if index % 50 == 0:
            print(f"  … screened {index}/{len(usable)}")

    candidates = [r for r in results
                  if r.get("verdict") == "candidate-processed-taxonomy-table"]
    crop_microbiome = [r for r in candidates if r.get("quadrant") == "crop-microbiome"]
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "data/metadata/phase9_osdr_sweep.json",
        "studiesScreened": len(usable),
        "studiesMatchingAnySignal": len([r for r in results if "verdict" in r]),
        "candidatesWithTaxonomyTable": len(candidates),
        "cropMicrobiomeCandidates": len(crop_microbiome),
        "rankingRule": ("A processed taxonomic abundance table is required. Raw "
                        "amplicon reads are rejected because quantifying them "
                        "would need an unvalidated pipeline inside this phase."),
        "results": results,
    }
    (METADATA / "phase9_candidate_screen.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(f"\nscreened {len(usable)} studies with processed matrices")
    print(f"  candidates with a processed taxonomy table: {len(candidates)}")
    print(f"  crop + microbiome quadrant: {len(crop_microbiome)}")
    for record in crop_microbiome[:15]:
        print(f"    {record['study']:10s} {', '.join(record['cropSignals'])[:40]:42s} "
              f"{record['taxonomyTables'][0] if record['taxonomyTables'] else '-'}")
    print("wrote data/metadata/phase9_candidate_screen.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
