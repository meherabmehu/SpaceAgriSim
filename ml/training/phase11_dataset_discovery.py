"""Phase 11: targeted NASA dataset discovery.

Phase 9 screened every OSDR study for *whether* a processed matrix exists. Phase 10
scanned for gravity vocabulary. Neither asked the questions Phase 11 needs answered:

  M   is there a **third independent microbial campaign**?  Both served microbial
      models rest on two campaigns (VEG-04A and VEG-04B), which is the binding
      limitation on their intervals.
  H   is there **paired environmental and harvest/biomass measurement**?  Mizuna harvest
      has 14 rows and no model is possible; more rows from a *different* design are the
      only thing that changes that.
  R   is there another **plant radiation study** with a dose label and a processed
      matrix?  OSD-46 and OSD-782 are the only two, and their transfer failed.
  C   is there another **crop growth** study with environment -> mass rows?  Lettuce
      rests on four experiments.

Each study's ISA metadata is fetched once and cached, then scored against those four
question-specific vocabularies. The scan is deliberately generous: missing a study is the
expensive error, listing extra candidates only costs review time, and every candidate is
recorded with its factors so the rejection reason is auditable.

Output: `ml/evaluation/phase11_dataset_discovery.json`
Run:    python ml/training/phase11_dataset_discovery.py
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SWEEP = ROOT / "data" / "metadata" / "phase9_osdr_sweep.json"
CACHE = ROOT / "data" / "metadata" / "osdr_study_metadata_phase11"
OUT = ROOT / "ml" / "evaluation" / "phase11_dataset_discovery.json"

API = "https://osdr.nasa.gov/osdr/data/osd/meta/{}"

QUESTIONS = {
    "microbial": {
        "label": "third independent microbial campaign",
        "patterns": [r"\bCFU\b", r"colon(y|ies)[- ]forming", r"aerobic", r"yeast and mould",
                     r"yeast and mold", r"microbiom", r"bacterial (load|count|community)",
                     r"culture[- ]based"],
    },
    "harvest": {
        "label": "paired environment and harvest/biomass measurement",
        "patterns": [r"fresh (mass|weight)", r"dry (mass|weight)", r"\bbiomass\b",
                     r"harvest (mass|weight|index|yield)", r"\byield\b", r"edible mass",
                     r"plant height", r"leaf area"],
    },
    "radiation": {
        "label": "plant radiation study with a dose label",
        "patterns": [r"\bgamma\b", r"ionizing radiation", r"ionising radiation", r"\bHZE\b",
                     r"absorbed dose", r"\bGy\b", r"cesium-137", r"caesium-137",
                     r"proton (beam|irradiation)"],
    },
    "crop_growth": {
        "label": "crop growth study with environmental treatments",
        "patterns": [r"Lactuca", r"lettuce", r"Brassica", r"mizuna", r"\bVEG-?0\d\b",
                     r"plant growth (chamber|unit)", r"nutrient (solution|film)",
                     r"hydropon", r"photosynthetic", r"stomatal"],
    },
}

PLANT = re.compile(r"Arabidopsis|Lactuca|lettuce|Brassica|mizuna|tomato|Solanum|wheat|"
                   r"rice|Oryza|soybean|Glycine|potato|crop|plant|seedling", re.I)


def metadata(osd: str) -> dict | None:
    cached = CACHE / f"{osd.replace('-', '')}.json"
    if cached.exists():
        try:
            return json.loads(cached.read_text())
        except json.JSONDecodeError:
            pass
    try:
        with urllib.request.urlopen(API.format(osd.replace("OSD-", "")), timeout=60) as reply:
            payload = json.loads(reply.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
        return None
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(payload))
    except OSError:
        pass
    return payload


def summarise(payload: dict) -> dict:
    titles, descriptions, factors, organisms = [], [], set(), set()
    for block in (payload.get("study", {}) or {}).values():
        for study in (block.get("studies", []) if isinstance(block, dict) else []) or []:
            if study.get("title"):
                titles.append(str(study["title"]))
            if study.get("description"):
                descriptions.append(str(study["description"]))
            for factor in study.get("factors", []) or []:
                if factor.get("factorName"):
                    factors.add(str(factor["factorName"]))
    text = json.dumps(payload)
    for match in re.finditer(r'"(?:factorName|characteristicCategory)"\s*:\s*"([^"]{1,80})"',
                             text):
        factors.add(match.group(1))
    for match in re.finditer(r'"(?:organism|Organism)"[^"]{0,24}?"([A-Z][a-z]+ [a-z]+)"', text):
        organisms.add(match.group(1))
    return {
        "title": (titles[0] if titles else "")[:300],
        "description": " ".join(descriptions)[:2000],
        "factors": sorted(factors),
        "organisms": sorted(organisms),
    }


def main() -> int:
    sweep = json.loads(SWEEP.read_text())
    usable = sweep["usableProcessedMatrix"]
    already = {"OSD-46", "OSD-782", "OSD-314", "OSD-346", "OSD-411", "OSD-267", "OSD-268",
               "OSD-269", "OSD-745", "OSD-766", "OSD-767", "OSD-773", "OSD-7", "OSD-120",
               "OSD-436", "OSD-625", "OSD-375", "OSD-655", "OSD-780"}
    print(f"scanning {len(usable)} studies with a usable processed matrix "
          f"({len(already)} already catalogued)")

    candidates = {key: [] for key in QUESTIONS}
    scanned, unavailable = 0, []
    for osd in usable:
        payload = metadata(osd)
        if payload is None:
            unavailable.append(osd)
            continue
        scanned += 1
        summary = summarise(payload)
        haystack = " ".join([summary["title"], summary["description"],
                             *summary["factors"]])
        plant = bool(PLANT.search(haystack)) or any(
            "thaliana" in organism or "sativa" in organism for organism in summary["organisms"])
        for key, spec in QUESTIONS.items():
            matched = [pattern for pattern in spec["patterns"]
                       if re.search(pattern, haystack, re.I)]
            if not matched:
                continue
            # Radiation and harvest questions are plant-specific; microbial and growth
            # questions also admit plant-associated samples.
            if key in ("radiation", "harvest") and not plant:
                continue
            candidates[key].append({
                "study": osd,
                "title": summary["title"],
                "plantRelated": plant,
                "organisms": summary["organisms"][:4],
                "matchedPatterns": matched[:6],
                "factors": summary["factors"][:12],
                "alreadyCatalogued": osd in already,
            })
        if scanned % 50 == 0:
            print(f"  {scanned}/{len(usable)} scanned")
        time.sleep(0.03)

    # Rank: uncatalogued plant-related candidates first, then already-known ones, because
    # only a new study can close a gap.
    summary = {}
    for key, spec in QUESTIONS.items():
        rows = candidates[key]
        new = [row for row in rows if not row["alreadyCatalogued"]]
        summary[key] = {
            "question": spec["label"],
            "candidatesTotal": len(rows),
            "candidatesNotYetCatalogued": len(new),
            "topNewCandidates": sorted(new, key=lambda row: -len(row["matchedPatterns"]))[:12],
        }

    result = {
        "phase": 11,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "corpus": {
            "studiesWithUsableProcessedMatrix": len(usable),
            "scanned": scanned,
            "unavailableMetadata": unavailable,
            "alreadyCatalogued": sorted(already),
        },
        "questions": summary,
        "method": (
            "per-study ISA metadata fetched from the OSDR API and scored against four "
            "question-specific vocabularies; generous patterns, every candidate recorded "
            "with its factors so a rejection can be audited"),
        "note": (
            "A keyword candidate is a lead, not a finding. Each lead has to pass the "
            "ten-point check in the Phase 11 data discovery document before anything is "
            "downloaded or trained on."),
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n")

    print(f"\nscanned {scanned}, unavailable {len(unavailable)}")
    for key, value in summary.items():
        print(f"  {key:12s} {value['candidatesTotal']:3d} candidates, "
              f"{value['candidatesNotYetCatalogued']:3d} not yet catalogued")
        for row in value["topNewCandidates"][:4]:
            print(f"      {row['study']:9s} {row['title'][:88]}")
    print(f"-> wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
