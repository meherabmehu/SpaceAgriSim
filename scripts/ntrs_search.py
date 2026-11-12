"""Phase 7 target-driven NASA NTRS search.

The Phase 6 work established that the NASA OSDR public tables contain almost no
machine-readable plant physiology measurements. This script goes after the other
large body of NASA experimental evidence: NASA Technical Reports Server.

Strategy: search for the *measured variable* rather than for dataset identifiers,
because the legacy CELSS / Breadboard Project / Biomass Production Chamber results
were published as technical reports and conference papers, not as tidy datasets.

Every query is recorded with its hit count so that negative findings are
reproducible and nobody has to repeat a fruitless search.

Run: python scripts/ntrs_search.py
Output: data/metadata/phase7_ntrs_search
"""
from __future__ import annotations

import concurrent.futures
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "metadata" / "phase7_ntrs_search"
UA = {"User-Agent": "SpaceAgriSim/1.0 (Phase 7 NASA literature recovery)",
      "Accept": "application/json"}

# Target-driven queries. Each entry is (target_variable, query).
QUERIES: list[tuple[str, str]] = [
    # --- biomass / yield ---
    ("biomass", '"biomass production chamber" wheat'),
    ("biomass", '"biomass production chamber" lettuce'),
    ("biomass", '"biomass production chamber" CELSS yield'),
    ("biomass", "CELSS crop productivity wheat yield"),
    ("biomass", "controlled ecological life support crop biomass"),
    ("biomass", "wheat growth chamber yield NASA"),
    ("biomass", "lettuce controlled environment biomass harvest"),
    ("biomass", '"Breadboard Project" CELSS'),
    ("biomass", "potato CELSS biomass production"),
    ("biomass", "soybean CELSS biomass yield"),
    # --- water ---
    ("water", "biomass production chamber transpiration"),
    ("water", "CELSS transpiration water uptake plants"),
    ("water", "crop evapotranspiration controlled environment NASA"),
    ("water", "plant water management ISS experiment"),
    ("water", "hydroponic water balance NASA crop"),
    ("water", "nutrient film technique wheat water use NASA"),
    # --- gas exchange ---
    ("gas", "wheat canopy photosynthesis carbon dioxide assimilation NASA"),
    ("gas", "CELSS gas exchange oxygen production chamber"),
    ("gas", "crop canopy carbon dioxide uptake controlled environment"),
    ("gas", "plant chamber oxygen evolution measurement NASA"),
    ("gas", "photosynthetic rate wheat stand NASA chamber"),
    # --- light ---
    ("light", "PPFD plant growth NASA LED"),
    ("light", "photoperiod crop yield controlled environment NASA"),
    ("light", "light intensity lettuce biomass response"),
    ("light", "LED spectrum plant growth NASA KSC"),
    ("light", "sulfur microwave lamp plant growth NASA"),
    # --- gravity ---
    ("gravity", "simulated microgravity plant growth biomass clinostat"),
    ("gravity", "altered gravity plant development NASA"),
    ("gravity", "spaceflight plant biomass yield comparison ground"),
    # --- radiation ---
    ("radiation", "plant radiation dose response biomass NASA"),
    ("radiation", "ionizing radiation crop growth effect"),
    ("radiation", "space radiation plant biology experiment"),
    # --- regolith / analogue ---
    ("regolith", "lunar regolith plant growth NASA"),
    ("regolith", "Martian regolith simulant crop growth"),
    # --- controlled environment facilities ---
    ("facility", '"Advanced Plant Habitat"'),
    ("facility", "Veggie plant growth ISS harvest"),
    ("facility", '"Plant Habitat" 01 experiment results'),
    ("facility", "EDEN ISS antarctic greenhouse"),
    # --- stress ---
    ("stress", "controlled environment plant stress measurement NASA"),
]

MAX_PAGES = 2
PAGE_SIZE = 50


def fetch(url: str, attempts: int = 3) -> dict:
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, TimeoutError):
            if attempt == attempts - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def search(target: str, query: str) -> dict:
    records = []
    total = 0
    for page in range(MAX_PAGES):
        params = urllib.parse.urlencode({
            "q": query, "page.size": PAGE_SIZE, "page.number": page + 1,
        })
        try:
            payload = fetch(f"https://ntrs.nasa.gov/api/citations/search?{params}")
        except Exception as exc:  # pragma: no cover - network dependent
            return {"target": target, "query": query, "error": repr(exc),
                    "hits": 0, "downloadable": 0, "records": []}
        total = payload.get("stats", {}).get("total", 0)
        results = payload.get("results", [])
        for item in results:
            # NTRS reports the asset class in `type` (usually "STI") and the real
            # format in `mimetype`. Select on the URL extension instead of the type
            # tag, which varies across legacy records.
            downloads = item.get("downloads") or []
            pdfs = []
            for entry in downloads:
                links = entry.get("links") or {}
                url = links.get("original") or links.get("pdf") or entry.get("href")
                if not url:
                    continue
                if url.lower().endswith(".pdf") or \
                        str(entry.get("mimetype", "")).lower() == "application/pdf":
                    pdfs.append({"url": url, "name": entry.get("name"),
                                 "mimetype": entry.get("mimetype")})
            records.append({
                "id": item.get("id"),
                "title": item.get("title"),
                "stiType": item.get("stiType"),
                "publicationYear": (item.get("publications") or [{}])[0].get("publicationDate", "")[:4],
                "center": (item.get("center") or {}).get("name"),
                "distribution": item.get("distribution"),
                "downloadsAvailable": item.get("downloadsAvailable"),
                "pdfLinks": ["https://ntrs.nasa.gov" + d["url"]
                             if d["url"].startswith("/") else d["url"] for d in pdfs],
                "pdfNames": [d["name"] for d in pdfs],
                "abstract": (item.get("abstract") or "")[:600],
            })
        if len(results) < PAGE_SIZE:
            break
        time.sleep(0.2)
    return {
        "target": target,
        "query": query,
        "hits": total,
        "downloadable": sum(1 for r in records if r["pdfLinks"]),
        "records": records,
    }


def main() -> int:
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda pair: search(*pair), QUERIES))

    # De-duplicate candidate documents across all queries.
    documents: dict[str, dict] = {}
    for result in results:
        for record in result["records"]:
            key = str(record["id"])
            if key not in documents:
                documents[key] = dict(record, matchedTargets=set(), matchedQueries=set())
            documents[key]["matchedTargets"].add(result["target"])
            documents[key]["matchedQueries"].add(result["query"])
    for document in documents.values():
        document["matchedTargets"] = sorted(document["matchedTargets"])
        document["matchedQueries"] = sorted(document["matchedQueries"])

    with_pdf = {k: v for k, v in documents.items() if v["pdfLinks"]}
    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "NASA Technical Reports Server public search API (ntrs.nasa.gov/api/citations/search)",
        "queryCount": len(QUERIES),
        "queries": [{k: v for k, v in r.items() if k != "records"} for r in results],
        "documentsFound": len(documents),
        "documentsWithPdf": len(with_pdf),
        "documents": sorted(documents.values(), key=lambda d: str(d["id"])),
    }
    body = json.dumps(payload, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(body, encoding="utf-8")

    print(f"queries           : {len(QUERIES)}")
    print(f"unique documents  : {len(documents)}")
    print(f"with PDF download : {len(with_pdf)}")
    print()
    print(f"{'target':<10} {'hits':>7} {'dl':>5}  query")
    for result in results:
        print(f"{result['target']:<10} {result['hits']:>7} {result['downloadable']:>5}  {result['query'][:70]}")
    print()
    print("Top downloadable candidates by target coverage:")
    ranked = sorted(with_pdf.values(), key=lambda d: (-len(d["matchedTargets"]), str(d["title"])))
    for document in ranked[:25]:
        print(f"  {document['id']} [{','.join(document['matchedTargets'])}] "
              f"{str(document['title'])[:88]}")
    print(f"\nwritten: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
