"""Download and verify the NASA technical reports that hold CELSS plant measurements.

Phase 6 searched NASA OSDR, which is a *genomics* archive, and concluded that
transpiration / CO2-assimilation / PPFD-response measurements did not exist.
They do exist - they were published as NASA Technical Memoranda from the Kennedy
Space Center Breadboard Project in the late 1980s and early 1990s, and are
indexed in the NASA Technical Reports Server (NTRS).

This script retrieves those reports by their official NTRS citation IDs, records
SHA-256 checksums, and refuses to proceed if a document cannot be verified.

The PDFs themselves are NOT committed (they are large and publicly
re-downloadable); only this reproducible script and its manifest are.

Run: python scripts/acquire_ntrs_reports.py
Output:
    data/raw/ntrs/{id}.pdf                (gitignored)
    data/metadata/phase7_ntrs_checksums
"""
from __future__ import annotations
import sys

import hashlib
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
RAW = ROOT / "data" / "raw" / "ntrs"
OUT = ROOT / "data" / "metadata" / "phase7_ntrs_checksums"
UA = {"User-Agent": "SpaceAgriSim/1.0 (Phase 7 NASA report recovery)"}

# (NTRS citation id, short label, scientific role)
REPORTS = [
    ("19900016137", "TM-102788",
     "CO2 and water exchange rates by a wheat crop in NASA's Biomass Production "
     "Chamber: 86-day study. Measured stand photosynthesis, dark respiration, "
     "transpiration, PPFD response and temperature response."),
    ("19900009537", "TM-102784",
     "Continuous hydroponic wheat production using a recirculating system. "
     "Per-tray harvest tables (16 biological replicates) and multi-age dry-matter "
     "destructive harvest series."),
    ("19900016140", "TM-103494",
     "System development and early biological tests in NASA's Biomass Production "
     "Chamber. Facility characterisation and early crop trials."),
    ("19910010713", "N91-20026",
     "CO2 and water exchange of a soybean stand grown in the Biomass Production "
     "Chamber (NASA/ASEE summer faculty fellowship report)."),
    ("19940009239", "TM-109192",
     "Biomass Production Chamber air analysis of wheat study (BWT931). VOC and "
     "air-quality survey - investigated and NOT used as a physiology target."),
    ("19900001255", "TM-?",
     "A simple mass balance model of carbon flow in a controlled ecological life "
     "support system. Carbon-flow reference model for cross-checking."),
]

BASE = "https://ntrs.nasa.gov/api/citations/{id}/downloads/{id}.pdf"
ALLOWED_HOST = "https://ntrs.nasa.gov/"
MAX_BYTES = 60_000_000


def fetch(url: str, attempts: int = 3) -> bytes:
    if not url.startswith(ALLOWED_HOST):
        raise ValueError("Acquisition restricted to official NASA NTRS")
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(request, timeout=180) as response:
                if not response.url.startswith(("https://ntrs.nasa.gov/",
                                                "https://ntrs.nasa.gov")):
                    raise ValueError("Unexpected NTRS redirect")
                body = response.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise ValueError("Document exceeds the explicit download budget")
                if not body.startswith(b"%PDF"):
                    raise ValueError("Response is not a PDF document")
                return body
        except (OSError, TimeoutError):
            if attempt == attempts - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    previous = {}
    if safedata.exists(OUT):
        previous = {item["id"]: item for item in safedata.load(OUT)}

    records = []
    for citation_id, label, role in REPORTS:
        target = RAW / f"{citation_id}.pdf"
        url = BASE.format(id=citation_id)
        prior = previous.get(citation_id)
        if safedata.exists(target):
            body = safedata.bytes(target)
            reused = True
        else:
            body = fetch(url)
            target.write_bytes(body)
            reused = False
        digest = hashlib.sha256(body).hexdigest()
        if prior and prior.get("sha256") and prior["sha256"] != digest:
            raise ValueError(
                f"NASA document {citation_id} changed on the server since the "
                f"recorded acquisition ({prior['sha256'][:16]} -> {digest[:16]}); "
                "refusing to silently accept a different document")
        records.append({
            "id": citation_id,
            "label": label,
            "scientificRole": role,
            "url": url,
            "citationUrl": f"https://ntrs.nasa.gov/citations/{citation_id}",
            "sha256": digest,
            "bytes": len(body),
            "pages": _page_count(target),
            "reusedFromCache": reused,
            "verifiedAt": datetime.now(timezone.utc).isoformat(),
        })
        print(f"  {citation_id}  {len(body):>9,} B  {records[-1]['pages']:>3} pages  {label}")

    body = json.dumps(records, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
    OUT.write_text(body, encoding="utf-8")
    print(f"\ndocuments: {len(records)}")
    print(f"manifest : {OUT.relative_to(ROOT)}")
    return 0


def _page_count(path: Path) -> int | None:
    try:
        import pymupdf
        return pymupdf.open(path).page_count
    except Exception:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
