"""Phase 10: attempt to recover a gravity signal, and search for a real one.

Two distinct failures are fixed here, and only one of them is a data problem.

The served `gravity-reorientation-osd411-v1` was excluded because 90 degrees of ground
reorientation is not a gravity level. That exclusion is correct and stays. But Phase 9
also left the question "is there a plant study at any partial gravity with processed
expression?" answered only by OSD-480 being 6.2 TB of raw FASTQ. Phase 10 answers it
by searching the metadata of all 231 studies that the sweep found to have a usable
processed matrix, rather than by inspecting one study.

The keyword scan is deliberately generous: anything that could name a non-1g
acceleration is a hit, and hits are then checked by hand in the report. Missing a study
is the expensive error here, not listing one too many.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SWEEP = ROOT / "data" / "metadata" / "phase9_osdr_sweep.json"
CACHE = ROOT / "data" / "metadata" / "osdr_study_metadata"
OUT = ROOT / "ml" / "evaluation" / "phase10_gravity_recovery.json"

API = "https://osdr.nasa.gov/osdr/data/osd/meta/{}"

# Terms that would indicate a graded or partial gravity manipulation. Plain
# "microgravity" is included because a study that manipulates several hardware
# conditions sometimes names them in factors even when the title says microgravity.
PATTERNS = {
    "partialGravity": r"partial[\s-]?gravity|fractional[\s-]?gravity|graded gravity",
    "centrifuge": r"centrifug",
    "explicitGLevel": r"\b0?\.(0[1-9]|[1-9]\d?)\s*g\b|\b(?:0\.16|0\.38|0\.25|0\.5)\s*g\b",
    "lunarOrMarsG": r"\blunar\b|\bmars\b|\bmoon\b",
    "clinostatOrRpm": r"clinostat|random positioning|\bRPM\b|rotating wall",
    "reorientation": r"reorientat|gravitropism|gravitropic",
    "microgravity": r"micro[\s-]?gravity|\bµg\b|spaceflight",
}


def study_metadata(osd: str) -> dict | None:
    """Fetch and cache one study's ISA metadata. Returns None when unavailable."""
    cached = CACHE / f"{osd.replace('-', '')}.json"
    if cached.exists():
        try:
            return json.loads(cached.read_text())
        except json.JSONDecodeError:
            return None
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
    """Title, description, factor names and factor values out of ISA-JSON.

    The nesting is `payload["study"][<OSD id>]["studies"][...]`, not
    `payload["study"]["studies"]`, which is why the first pass returned 11 candidate
    studies with empty titles. Factor *values* are pulled by regex over the payload
    text because their nesting differs study by study.
    """
    entries = (payload.get("study", {}) or {}).values()
    titles, descriptions, factors, organisms = [], [], set(), set()
    for block in entries:
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
    for match in re.finditer(r'"(?:organism|Organism)"[^"]{0,20}?"([A-Z][a-z]+ [a-z]+)"', text):
        organisms.add(match.group(1))
    return {
        "title": (titles[0] if titles else "")[:300],
        "description": (" ".join(descriptions))[:1200],
        "factors": sorted(factors),
        "organisms": sorted(organisms),
    }


def main() -> int:
    sweep = json.loads(SWEEP.read_text())
    usable = sweep["usableProcessedMatrix"]
    print(f"scanning metadata for {len(usable)} studies with a usable processed matrix")

    hits, scanned, unavailable = [], 0, []
    for osd in usable:
        payload = study_metadata(osd)
        if payload is None:
            unavailable.append(osd)
            continue
        scanned += 1
        summary = summarise(payload)
        title = summary["title"]
        factors = summary["factors"]
        haystack = " ".join([summary["title"], summary["description"], *factors])
        matched = {name: bool(re.search(pattern, haystack, re.IGNORECASE))
                   for name, pattern in PATTERNS.items()}
        # A study is a candidate only if it names a gravity manipulation at all.
        if matched["partialGravity"] or matched["explicitGLevel"] or matched["centrifuge"] \
                or matched["clinostatOrRpm"] or matched["lunarOrMarsG"]:
            hits.append({"study": osd, "title": title,
                         "organisms": summary["organisms"][:4],
                         "plantStudy": any(re.search(r"Arabidopsis|Lactuca|lettuce|plant|seed|crop",
                                                     " ".join([title, summary["description"]]),
                                                     re.IGNORECASE) for _ in (0,)),
                         "matched": matched, "factors": factors[:12]})
        if scanned % 40 == 0:
            print(f"  {scanned}/{len(usable)} scanned, {len(hits)} candidates")
        time.sleep(0.05)

    # OSD-411's own limits, measured: the excluded model could only ever see
    # reorientation, never a gravity level.
    import pandas as pd

    annotation = pd.read_csv(ROOT / "data" / "processed" / "osd411_gravity_samples.csv")
    osd411 = {
        "treatmentLevels": sorted(annotation["treatment"].unique().tolist()),
        "tissues": sorted(annotation["materialType"].unique().tolist()),
        "genotypes": sorted(annotation["genotype"].unique().tolist()),
        "samples": int(len(annotation)),
        "gravityLevelsPresent": [1.0],
        "statement": (
            "OSD-411 reorients seedlings by 90 degrees on the ground. Every sample is at "
            "1 g, so no gravity level beyond 1 g exists in the data and no prediction of "
            "partial gravity, lunar or Mars gravity can be derived from it. The exclusion "
            "of the reorientation model is a statement about the labels, not about the "
            "classifier."),
    }

    verdict = ("no-partial-gravity-plant-study-with-processed-expression-found"
               if not hits else "candidates-require-manual-review")
    report = {
        "phase": 10,
        "task": "recover a gravity-level signal, or establish that none is available",
        "searched": {
            "corpus": f"{len(usable)} studies classified as usable-processed-matrix",
            "scanned": scanned,
            "unavailableMetadata": unavailable,
            "method": ("per-study ISA metadata fetched from the OSDR API and scanned for "
                       "gravity-manipulation vocabulary; generous pattern set, candidates "
                       "then reviewed in docs/PHASE10_DOSE_GRAVITY_RECOVERY.md"),
        },
        "candidates": hits,
        "patternHits": {name: sum(1 for hit in hits if hit["matched"][name])
                        for name in PATTERNS},
        "osd411Limits": osd411,
        "verdict": verdict,
        "decision": (
            "No gravity-level model is trained, promoted or claimed. A model that maps "
            "reorientation onto a gravity fraction would be inventing the label it "
            "predicts."),
        "nextAction": (
            "If a candidate with graded gravity and a processed matrix appears, it must be "
            "validated with the group-held-out protocol used here, and its gravity levels "
            "must come from the study's own factor table, not from the hardware "
            "description."),
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(f"\nscanned {scanned}, unavailable {len(unavailable)}, candidates {len(hits)}")
    for hit in hits[:12]:
        print(f"  {hit['study']}: {hit['title'][:110]}")
    print(f"verdict: {verdict} -> wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
