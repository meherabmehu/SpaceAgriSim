#!/usr/bin/env python3
"""Phase 13: reproducible latency benchmark for the API surface.

    python3 scripts/benchmark_api.py --write

What this measures: in-process request latency through the FastAPI application object, using
Starlette's TestClient. No network, no TLS, no container, no database tuning.

What this does **not** measure, and must never be reported as: production latency. A deployed
service adds network round trips, TLS termination, a real database connection pool, cold starts
and a shared CPU. These numbers exist to answer one engineering question - is a route doing
anything accidentally quadratic or per-request expensive? - and to make that answer reproducible
when someone changes the code.

Each route is warmed once, then timed over N iterations; percentiles are computed from the raw
samples, which are kept in the artifact so a later run can be compared honestly.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.config.settings import settings  # noqa: E402
from app.main import app  # noqa: E402

OUT = ROOT / "ml" / "evaluation" / "phase13_performance.json"

LETTUCE = {"daysAfterTransplant": 20, "airTemperature": 24, "rootTemperature": 22, "ppfd": 400}
SIM = {"crop": "lettuce", "gravity": 1.0, "radiation": 0.05, "waterAvailability": 100,
       "lightHours": 16, "co2Level": 1000, "simulationDays": 30, "growingArea": 10,
       "earthComparisonMode": "matched", "lightIntensity": 300, "temperature": 24,
       "humidity": 60, "lightSpectrum": "balanced", "waterRecyclingEfficiency": 85}

CASES = [
    ("health", "GET", "/api/health", None),
    ("assistant-ask-direct", "POST", "/api/assistant/ask",
     {"question": "What does the OSD-46 radiation classifier actually predict?"}),
    ("assistant-ask-comparison", "POST", "/api/assistant/ask",
     {"question": "Compare the findings of OSD-314 and OSD-346."}),
    ("assistant-ask-multihop", "POST", "/api/assistant/ask",
     {"question": "Why did the OSD-346 gravity result fail independent replication and what "
                  "evidence would validate it?"}),
    ("assistant-ask-refusal", "POST", "/api/assistant/ask",
     {"question": "How do I bake sourdough bread?"}),
    ("assistant-corpus", "GET", "/api/assistant/corpus", None),
    ("workflow-models", "GET", "/api/workflow/models", None),
    ("workflow-validate", "POST", "/api/workflow/validate",
     {"modelId": "lettuce-earth-growth-v1", "inputs": LETTUCE}),
    ("workflow-run", "POST", "/api/workflow/run",
     {"modelId": "lettuce-earth-growth-v1", "inputs": LETTUCE}),
    ("simulate", "POST", "/api/simulate", SIM),
    ("explorer-datasets", "GET", "/api/datasets", None),
    ("explorer-independent-set", "POST", "/api/explorer/independent-set",
     {"ids": ["OSD-46", "OSD-320", "OSD-346"]}),
]

ITERATIONS = 25


def percentile(samples: list[float], fraction: float) -> float:
    ordered = sorted(samples)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


def run_case(client: TestClient, method: str, path: str, body: dict | None) -> dict:
    def call():
        if method == "GET":
            return client.get(path)
        return client.post(path, json=body)

    first = call()
    samples: list[float] = []
    for _ in range(ITERATIONS):
        started = time.perf_counter()
        response = call()
        samples.append((time.perf_counter() - started) * 1000.0)
        if response.status_code != first.status_code:
            raise RuntimeError(f"{path} returned {response.status_code} after {first.status_code}")

    return {
        "status": first.status_code,
        "iterations": ITERATIONS,
        "medianMs": round(statistics.median(samples), 3),
        "p95Ms": round(percentile(samples, 0.95), 3),
        "maxMs": round(max(samples), 3),
        "minMs": round(min(samples), 3),
        "responseBytes": len(first.content),
        "samplesMs": [round(sample, 3) for sample in samples],
    }


def main() -> int:
    global ITERATIONS
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write the benchmark artifact")
    parser.add_argument("--iterations", type=int, default=ITERATIONS)
    arguments = parser.parse_args()

    ITERATIONS = arguments.iterations

    # A benchmark sends far more requests per minute from one address than a person can. The
    # shipped default budget stays as it is; this script raises it for its own process only, and
    # says so in the artifact, because a run that measured 429 responses would measure the rate
    # limiter instead of the routes.
    previous_budget = settings.general_rate_limit_per_minute
    object.__setattr__(settings, "general_rate_limit_per_minute", 100000)

    client = TestClient(app)
    results = []
    print(f"{'route':28s} {'status':>6s} {'median':>9s} {'p95':>9s} {'max':>9s} {'bytes':>8s}")
    for name, method, path, body in CASES:
        try:
            row = run_case(client, method, path, body)
        except Exception as error:  # noqa: BLE001 - a broken route is a result, not a crash
            row = {"status": "error", "error": str(error)[:200], "iterations": 0}
        row.update({"name": name, "method": method, "path": path})
        results.append(row)
        if row.get("status") != "error":
            print(f"{name:28s} {row['status']:>6d} {row['medianMs']:>8.2f}ms "
                  f"{row['p95Ms']:>8.2f}ms {row['maxMs']:>8.2f}ms {row['responseBytes']:>8d}")

    slowest = max((row for row in results if row.get("status") != "error"),
                  key=lambda row: row["p95Ms"], default=None)
    artifact = {
        "phase": 13,
        "task": "performance-benchmark",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "method": "in-process TestClient, single sandbox CPU",
            "iterations": ITERATIONS,
            "python": sys.version.split()[0],
            "rateLimitRaisedForBenchmark": True,
            "shippedRateLimitUnchanged": previous_budget,
        },
        "results": results,
        "summary": {
            "routes": len(results),
            "errors": sum(1 for row in results if row.get("status") == "error"),
            "slowestP95": slowest["name"] if slowest else None,
            "slowestP95Ms": slowest["p95Ms"] if slowest else None,
        },
        "caveat": ("Local in-process measurements. These are not production latency figures and "
                   "must not be presented as such: no network, TLS, container, cold start or "
                   "shared database is involved. They exist to detect accidental per-request cost "
                   "and to make a comparison reproducible."),
    }

    print()
    if artifact["summary"]["errors"]:
        print(f"routes with errors: {artifact['summary']['errors']}")
    print(f"slowest p95: {artifact['summary']['slowestP95']} "
          f"({artifact['summary']['slowestP95Ms']} ms)")

    object.__setattr__(settings, "general_rate_limit_per_minute", previous_budget)

    if arguments.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(artifact, indent=1, sort_keys=True), encoding="utf-8")
        print(f"written: {OUT.relative_to(ROOT)}")

    return 0 if not artifact["summary"]["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
