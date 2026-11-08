#!/usr/bin/env python3
"""Phase 12 demo: the AI layer, and the four refusals that make it trustworthy.

Runs against the app in-process, so it needs no server and no network. Every line it
prints is a real API response; nothing here is a mocked or trimmed-down path.

    python3 scripts/demo_phase12.py
"""
from __future__ import annotations

import pathlib
import sys
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

LETTUCE = {"daysAfterTransplant": 20, "airTemperature": 24,
           "rootTemperature": 22, "ppfd": 400}
failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


def rule(title: str) -> None:
    print(f"\n  \033[1m{title}\033[0m")


def main() -> int:
    client = TestClient(app)

    rule("the research assistant answers from retrieved evidence, and cites it")
    question = "Is OSD-320 an independent replication of OSD-46?"
    answer = client.post("/api/assistant/ask", json={"question": question}).json()
    print(f"    Q: {question}")
    print(f"    status: {answer['status']}  intent: {answer['intent']}")
    for claim in answer["claims"][:3]:
        print(f"      [{claim['citation']}] {claim['text'][:120]}")
    for citation in answer["citations"][:3]:
        print(f"      cite {citation['sourceId']:28s} {citation['evidenceClass']:16s} "
              f"{citation['localReference']}")
    check(answer["status"] in {"grounded", "partial"}, "the duplicate question answered")
    check(bool(answer["citations"]), "a grounded answer must carry citations")
    check(all(claim["citation"] >= 1 for claim in answer["claims"]),
          "every claim must point at a retrieved passage")
    split = answer["measuredVersusInterpreted"]
    print(f"      measured data: {split['measuredData'] or 'none'}")
    print(f"      model/estimate: {split['modelOrEstimate']}")

    rule("refusal 1: a question the corpus cannot answer is refused, not invented")
    off = client.post("/api/assistant/ask",
                      json={"question": "How do I bake sourdough bread?"}).json()
    print(f"    status: {off['status']}  refusal: {off['refusal']}  "
          f"claims: {len(off['claims'])}  citations: {len(off['citations'])}")
    check(off["status"] == "insufficient", "an off-corpus question must be insufficient")
    check(not off["citations"], "a refusal must not cite anything")

    rule("refusal 2: a molecular classifier will not run on environmental inputs")
    gene_model = "radiation-quality-osd46-v1"
    mismatch = client.post("/api/workflow/run",
                           json={"modelId": gene_model, "inputs": LETTUCE})
    detail = mismatch.json()["detail"]
    print(f"    POST /workflow/run {gene_model} with temperature and light -> "
          f"HTTP {mismatch.status_code} ({detail['error']})")
    print(f"      expected {detail['expectedFamily']} inputs, "
          f"received {detail['providedFamily']} inputs, "
          f"{len(detail['missing'])} gene features missing")
    check(mismatch.status_code == 422, "family mismatch must be refused")

    rule("refusal 3: a physically impossible value is rejected, not clamped")
    impossible = client.post("/api/workflow/run",
                             json={"modelId": "lettuce-earth-growth-v2",
                                   "inputs": {**LETTUCE, "airTemperature": 900}})
    print(f"    900 C air temperature -> HTTP {impossible.status_code} "
          f"({impossible.json()['detail']['error']})")
    check(impossible.status_code == 422, "an impossible temperature must be rejected")

    rule("refusal 4: a retired model still refuses to answer with a number")
    retired = client.post("/api/workflow/run",
                          json={"modelId": "mizuna-microbial-load-v1",
                                "inputs": {"experiment": 1}})
    print(f"    mizuna-microbial-load-v1 -> HTTP {retired.status_code} "
          f"({retired.json()['detail']['error']})")
    check(retired.status_code == 410, "a retired model must return 410")

    rule("a valid run returns the number, its domain check, limitations and provenance")
    run = client.post("/api/workflow/run",
                      json={"modelId": "lettuce-earth-growth-v2", "inputs": LETTUCE}).json()
    print(f"    prediction: {run['output']['prediction']:.4g} {run['output'].get('unit')}")
    print(f"    kind: {run['output']['kind']}  isMeasurement: {run['output']['isMeasurement']}"
          f"  calibrated: {run['output']['calibrated']}")
    print(f"    inside training domain: {run['validation']['insideTrainingDomain']}  "
          f"checks: {', '.join(run['validation']['checksApplied'])}")
    print(f"    provenance: {run['provenance']['sourceStudy']} "
          f"(sha256 {run['provenance']['artifactSha256'][:12]}…)")
    for limitation in run["limitations"][:2]:
        print(f"      limit: {limitation[:110]}")
    check(run["output"]["isMeasurement"] is False, "an output is not a measurement")
    check(run["output"]["calibrated"] is False, "no model is served as calibrated")

    rule("saved analyses belong to one account, and only that account")
    def account(label: str) -> dict[str, str]:
        email = f"demo-{label}-{uuid.uuid4().hex[:6]}@example.test"
        token = client.post("/api/auth/register",
                            json={"email": email,
                                  "password": "CorrectHorseBattery1!"}).json()["accessToken"]
        return {"Authorization": f"Bearer {token}"}

    alice, bob = account("alice"), account("bob")
    saved = client.post("/api/workflow/run", headers=alice,
                        json={"modelId": "lettuce-earth-growth-v2", "inputs": LETTUCE,
                              "save": True, "title": "Demo: lettuce at 20 days"}).json()
    analysis_id = saved["saved"]["id"]
    print(f"    alice saved {analysis_id[:8]}… ({saved['saved']['title']})")
    print(f"    bob sees {len(client.get('/api/analyses', headers=bob).json()['analyses'])} "
          f"analyses; GET alice's id -> HTTP "
          f"{client.get(f'/api/analyses/{analysis_id}', headers=bob).status_code}")
    export = client.get(f"/api/analyses/{analysis_id}/export/csv", headers=alice)
    prediction_row = [line for line in export.text.splitlines()
                      if line.startswith("prediction,")][0]
    print(f"    export row: {prediction_row}")
    check(export.status_code == 200, "the owner can export their analysis")
    check(client.get(f"/api/analyses/{analysis_id}", headers=bob).status_code == 404,
          "another account must not read the analysis")
    check(float(prediction_row.split(",")[1]) == run["output"]["prediction"],
          "the exported number must equal the API number")

    rule("the dataset explorer never counts a duplicate deposit twice")
    overlaps = client.get("/api/explorer/overlaps").json()
    print(f"    {overlaps['accessionCount']} accessions -> "
          f"{overlaps['independentStudyCount']} independent studies; "
          f"{overlaps['relationCounts']['duplicate-measurement']} duplicate, "
          f"{overlaps['relationCounts']['shared-sample-different-assay']} shared material, "
          f"{overlaps['relationCounts']['unverified-overlap']} unverified pairs")
    print(f"    OSD-320: {overlaps['redundantDeposits']['OSD-320']['reason'][:150]}…")
    reduced = client.post("/api/explorer/independent-set",
                          json={"ids": ["OSD-46", "OSD-320", "OSD-655", "OSD-780"]}).json()
    print(f"    requested 4 -> independent {reduced['independentCount']}: "
          f"{reduced['independent']}")
    for dropped in reduced["dropped"]:
        print(f"      drop {dropped['id']}: {dropped['relation']} "
              f"(conflicts with {dropped['conflictsWith']})")
    check(reduced["independentCount"] == 2, "the duplicate and shared pair must be dropped")

    rule("every model states its scientific category and calibration status")
    catalogue = client.get("/api/workflow/models").json()["models"]
    for model in catalogue:
        print(f"    {model['modelId']:34s} cat {model['category']}  "
              f"{model['inputFamily']:16s} {model['runStatus']:10s} "
              f"calibrated={model['calibration']['calibrated']}")
    check(len(catalogue) == 8, "all eight models must be listed")
    check(all(model["calibration"]["calibrated"] is False for model in catalogue),
          "no served model may claim calibration")

    print()
    if failures:
        for failure in failures:
            print(f"  \033[31mFAILED: {failure}\033[0m")
        return 1
    print("  \033[32mPhase 12 checks passed.\033[0m Four refusals, one citation trail, "
          "zero fabricated answers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
