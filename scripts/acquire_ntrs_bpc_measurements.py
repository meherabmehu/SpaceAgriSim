"""Phase 15: acquire NASA Biomass Production Chamber (BPC) physiology measurements from NTRS.

Why this exists
---------------
OSDR is a molecular and microbiome archive. It answers "what changed inside the plant", not
"how much biomass, water and CO2 moved through the canopy on day 30". The measurements the
habitat simulator actually needs were published — as NASA technical memoranda and ASEE
fellowship reports — and they live on NTRS, not in OSDR. Three are acquired here:

    19900016137  TM 102788  CO2 and water exchange rates by a wheat crop in NASA's BPC:
                            results from an 86-day study (January to April 1989)
    19910010713  N91-20026  CO2 and water exchange of a soybean stand grown in the BPC
    19900007373  N90-16689  Dynamics of CO2 exchange of a wheat community in a semi-closed
                            environment

These are the closest public thing to the day-resolved growth/water/gas measurements the
simulator assumes. They are **literature measurements**: citable and quotable at page level,
and *not* a harmonised training table. Nothing in this phase trains a model or changes a
simulator coefficient — the numbers are made retrievable and citable, not fitted.

Why the pages are quoted rather than tabulated
----------------------------------------------
The PDFs are scanned typescripts. Page text is extractable but table cells are not reliably
column-aligned, so parsing them into a clean numeric series would risk inventing values that
are not on the page. What is committed instead is the verified page text of the pages that
carry measurement language, with the page number, so any number claimed in the app can be
traced to a page a reader can open.

Provenance discipline
---------------------
Same rule as every earlier acquisition: the PDF is pinned by byte length and SHA-256, a
download that does not match is rejected, and `data/literature/ntrs_bpc` records the
citation record, the page selection and the extraction timestamp.

Run: python scripts/acquire_ntrs_bpc_measurements.py
"""

from __future__ import annotations
import sys

import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
RAW = ROOT / "data" / "raw" / "NTRS"
OUT = ROOT / "data" / "literature" / "ntrs_bpc"
UA = {"User-Agent": "SpaceAgriSim-research/1.0 (NASA NTRS literature acquisition)"}

REPORTS = {
    "19900016137": {
        "label": "TM 102788",
        "focus": "wheat",
        "why": ("86-day closed-chamber wheat study reporting daily CO2 exchange and water "
                "exchange rates in the NASA Biomass Production Chamber — the measurement type "
                "the simulator assumes rather than measures."),
    },
    "19910010713": {
        "label": "N91-20026",
        "focus": "soybean",
        "why": ("CO2 and water exchange of a soybean stand in the same chamber, so a second crop "
                "and a second canopy geometry exist for comparison."),
    },
    "19900007373": {
        "label": "N90-16689",
        "focus": "wheat",
        "why": ("Dynamics of CO2 exchange of a wheat community in a semi-closed environment: how "
                "the exchange rate moves across the growth cycle, not just its final value."),
    },
}

# A page is kept when it carries measurement vocabulary. The thresholds are deliberately
# simple and reviewable; nothing is inferred, only selected.
MEASUREMENT_TERMS = re.compile(
    r"(transpiration|condensat|carbon dioxide exchange|CO2 exchange|net photosynthesis|"
    r"photosynthetic rate|water exchange|gas exchange|yield|biomass|g m-2|mol m-2|"
    r"μmol|micromol)", re.I)


def fetch(url: str, timeout: int = 240) -> bytes:
    if not url.startswith("https://ntrs.nasa.gov/"):
        raise ValueError("Acquisition is restricted to the official NASA NTRS host")
    request = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(request, timeout=timeout) as reply:
        return reply.read()


def pinned_pdf(record_id: str, pinned: dict) -> tuple[bytes, dict]:
    url = f"https://ntrs.nasa.gov/api/citations/{record_id}/downloads/{record_id}.pdf"
    target = RAW / f"{record_id}.pdf"
    pin = pinned.get(record_id)
    if pin and safedata.exists(target):
        payload = safedata.bytes(target)
        if len(payload) == pin["bytes"] and hashlib.sha256(payload).hexdigest() == pin["sha256"]:
            return payload, pin
    payload = fetch(url)
    digest = hashlib.sha256(payload).hexdigest()
    if pin and pin["sha256"] != digest:
        raise RuntimeError(
            f"NTRS {record_id}: downloaded bytes hash to {digest[:16]}…, the pin says "
            f"{pin['sha256'][:16]}…. Upstream changed; review before accepting.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    new_pin = {
        "file": str(target.relative_to(ROOT)),
        "bytes": len(payload),
        "sha256": digest,
        "url": url,
        "pinnedAt": (pin or {}).get("pinnedAt") or datetime.now(timezone.utc).isoformat(),
    }
    return payload, new_pin


def page_texts(payload: bytes) -> list[tuple[int, str]]:
    """Extract (page_number, text) pairs. Page numbers are 1-based, as a reader counts them."""
    import pymupdf  # imported here so the rest of the script runs without the PDF stack

    document = pymupdf.open(stream=payload, filetype="pdf")
    pages = []
    for index, page in enumerate(document, start=1):
        text = re.sub(r"[ \t]+", " ", page.get_text()).strip()
        pages.append((index, text))
    return pages


def citation(record_id: str) -> dict:
    payload = fetch(f"https://ntrs.nasa.gov/api/citations/{record_id}")
    record = json.loads(payload.decode("utf-8"))
    return {
        "id": record_id,
        "title": (record.get("title") or "").strip(),
        "abstract": re.sub(r"\s+", " ", (record.get("abstract") or "")).strip(),
        "stiType": record.get("stiType"),
        "publications": record.get("publications") or [],
        "url": f"https://ntrs.nasa.gov/citations/{record_id}",
        "pdfUrl": (f"https://ntrs.nasa.gov/api/citations/{record_id}/downloads/"
                   f"{record_id}.pdf"),
    }


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    state = safedata.load(OUT) if safedata.exists(OUT) else {"reports": {}, "pins": {}}
    pins = state.setdefault("pins", {})
    reports = state.setdefault("reports", {})

    for record_id, meta in REPORTS.items():
        payload, pin = pinned_pdf(record_id, pins)
        pins[record_id] = pin
        pages = page_texts(payload)
        selected = []
        for number, text in pages:
            if len(text) < 200:
                continue
            hits = sorted({match.lower() for match in MEASUREMENT_TERMS.findall(text)})
            if len(hits) < 2:
                continue
            # A page counts as a measurement page when it names at least two measurement
            # concepts and carries actual quantities — decimal values or a run of plain
            # numbers. Requiring both is what keeps prose pages out.
            numeric = len(re.findall(r"\d+\.\d+", text))
            integers = len(re.findall(r"\b\d{1,4}\b", text))
            if not (numeric >= 3 or integers >= 15):
                continue
            selected.append({
                "page": number,
                "terms": hits,
                "decimalValues": numeric,
                "plainNumbers": integers,
                "excerpt": re.sub(r"\s+", " ", text)[:1400],
            })
        cite = citation(record_id)
        reports[record_id] = {
            **cite,
            "label": meta["label"],
            "focus": meta["focus"],
            "whyItMatters": meta["why"],
            "pages": len(pages),
            "measurementPages": selected,
            "pin": {key: pin[key] for key in ("file", "bytes", "sha256", "url")},
            "extractedAt": datetime.now(timezone.utc).isoformat(),
            "extractionNote": (
                "Scanned typescript. Page text is extracted verbatim; table cells are not "
                "parsed into a numeric series, because mis-columned OCR would invent values "
                "that are not on the page. Each excerpt is quoted with its page number."),
        }
        print(f"{record_id} {meta['label']}: {len(pages)} pages, "
              f"{len(selected)} measurement pages, sha256 {pin['sha256'][:16]}…")

    state["discovery"] = {
        "endpoint": "https://ntrs.nasa.gov/api/citations/search",
        "queries": ["Biomass Production Chamber gas exchange",
                    "CELSS crop water use transpiration condensate",
                    "wheat canopy photosynthesis CELSS daily",
                    "controlled ecological life support system crop yield data",
                    "BPC wheat study yield biomass NASA Kennedy"],
        "selectionRule": ("Reports were kept when the full text was downloadable from NTRS and "
                          "the text reports CO2 and/or water exchange for a crop canopy grown in "
                          "the NASA BPC. Record 20040090219 describes the ideal dataset (daily "
                          "nutrient, water and CO2 data for wheat) but NTRS publishes no "
                          "downloadable file for it, so it is cited as a reference only and not "
                          "acquired. Nothing was reconstructed from its abstract."),
        "recordedAt": datetime.now(timezone.utc).isoformat(),
    }
    safedata.dump(state, OUT)

    total = sum(len(entry["measurementPages"]) for entry in reports.values())
    print(f"\nwrote {OUT.relative_to(ROOT)} — {len(reports)} reports, {total} measurement pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
