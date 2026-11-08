#!/usr/bin/env bash
# Phase 9 reproducible demo.
#
# Verifies provenance, retrains both served models from the pinned NASA files,
# checks that the metrics match what the documentation claims, and shows a live
# prediction through the API.
#
# Every step is idempotent. Nothing here deploys anything.
#
# Usage:
#   scripts/demo_phase9.sh              # full run (retrains, ~6 minutes)
#   scripts/demo_phase9.sh --fast       # skip retraining, check the committed state
#   scripts/demo_phase9.sh --no-server  # skip the live API section
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"
FAST=0
SERVER=1
for argument in "$@"; do
  case "$argument" in
    --fast) FAST=1 ;;
    --no-server) SERVER=0 ;;
    *) echo "unknown option: $argument" >&2; exit 2 ;;
  esac
done

step() { printf '\n\033[1m== %s\033[0m\n' "$1"; }

step "1/7 Verify every NASA source file by checksum"
python3 scripts/acquire_phase9.py
echo "Every file above was matched against a pinned SHA-256."

if [ "$FAST" -eq 0 ]; then
  step "2/7 Retrain both served models (deterministic, seed 20261107)"
  # Order matters. Retraining regenerates the artifacts, the Phase 10 explanation step
  # re-attaches the explanation metadata that training alone does not write, and the
  # registry is rebuilt last so its checksums describe the files that now exist. Skipping
  # the middle step and then verifying checksums is what made the full demo fail before
  # Phase 11: every metric reproduced, and the gate still refused the artifacts.
  python3 ml/training/train_radiation_osd46.py
  python3 ml/training/phase10_explain_radiation.py
  python3 scripts/build_registry.py
  echo "Artifacts and registry regenerated. Only trainedAt/generatedAt and the checksums"
  echo "change; every metric is bit-identical, which step 3 asserts next."
else
  step "2/7 Skipped retraining (--fast); using the committed artifacts"
fi

step "3/7 Assert the documented metrics still hold"
python3 - <<'PY'
import json, sys
from pathlib import Path

report = json.loads(Path("ml/evaluation/phase9_osd46_radiation.json").read_text())
# These are the SHIPPED learner's numbers, not the best learner's: the artifact
# serialises the best *linear* family because tree ensembles cannot be exported to
# the dependency-free evaluator. For exposure that means logistic_l2 (0.910) ships
# even though gradient boosting scored higher (0.924) in evaluation.
expected = {
    "quality": {"learner": "logistic_l2", "balancedAccuracy": 0.898, "pValue": 0.0099, "groups": 22},
    "exposure": {"learner": "logistic_l2", "balancedAccuracy": 0.910, "pValue": 0.0099, "groups": 22},
}
failures = []
for task, want in expected.items():
    got = report["tasks"][task]
    bal = got["learners"][want["learner"]]["balancedAccuracy"]
    p = got["permutation"]["pValue"]
    if abs(bal - want["balancedAccuracy"]) > 0.002:
        failures.append(f"{task}: balanced accuracy {bal:.4f} != {want['balancedAccuracy']}")
    if abs(p - want["pValue"]) > 1e-4:
        failures.append(f"{task}: permutation p {p} != {want['pValue']}")
    if report["biologicalGroups"] != want["groups"]:
        failures.append(f"{task}: {report['biologicalGroups']} groups != {want['groups']}")
    print(f"  {task:9s} shipped {want['learner']} balanced {bal:.3f}  "
          f"p={p:.4f}  groups={report['biologicalGroups']}")
if failures:
    print("\n".join(failures), file=sys.stderr)
    raise SystemExit("documented metrics did not reproduce")
print("  metrics match the documentation")
PY

step "4/7 Verify registry checksums and run the scientific test suite"
python3 scripts/package_runtime_data.py
( cd backend && python3 -m pytest -q tests/test_phase9_models.py )

step "5/7 Show the interval calibration, the corrected transfer reading, and the recovered signals"
python3 - <<'PY'
import json
from pathlib import Path
r = json.loads(Path("ml/evaluation/phase9_rnaseq_candidates.json").read_text())
for result in r["results"]:
    if "bestLearner" in result:
        best = result["learners"][result["bestLearner"]]["balancedAccuracy"]
        print(f"  {result['modelId']:32s} balanced {best:.3f}  "
              f"p={result['permutation']['pValue']:.4f}  -> {result['verdict']}")
    else:
        print(f"  {result['task']:32s} balanced {result['balancedAccuracy']:.3f}  "
              f"-> {result['verdict']} (accuracy {result['accuracy']:.3f} is misleading)")
excluded = sorted(p.stem for p in Path("ml/evaluation/excluded").glob("*.json"))
print(f"  excluded from the registry: {', '.join(excluded)}")

# Phase 10: what each served interval actually covers, on held-out groups.
conformal = json.loads(Path("ml/evaluation/phase10_conformal.json").read_text())
decision = json.loads(Path("ml/evaluation/phase10_uncertainty_decision.json").read_text())
print("  interval coverage, nominal 0.90 (split was the Phase 9 method):")
for model_id, choice in decision["decisions"].items():
    measured = conformal["models"][model_id]["summary"]
    print(f"    {model_id:34s} split {measured['split']['empiricalCoverage']:.3f}"
          f" -> {choice['adopted']} {choice['achievedCoverage']:.3f}")

transfer = json.loads(Path("ml/evaluation/phase10_cross_study.json").read_text())
reference = transfer["withinStudyReference"]
matched = reference["protocolSensitivity"]["timepointHeldOut"]
print(f"  cross-study: {transfer['verdict']}; the target's own contrast is "
      f"{reference['balancedAccuracy']:.3f} with cells held out "
      f"(95% CI {reference['bootstrapCi95'][0]:.2f}-{reference['bootstrapCi95'][1]:.2f}) "
      f"and {matched:.3f} with timepoints held out, so the negative is about "
      f"transfer, not about the absence of signal")

# Phase 10: the two Phase 9 exclusions, re-measured with protocols matched to design.
dose = json.loads(Path("ml/evaluation/phase10_dose_recovery.json").read_text())
protocols = dose["protocols"]
print(f"  dose labels: valid ({dose['labelsAvailable']['values']} Gy), and the answer "
      f"depends on the split:")
print(f"    hold out (dose,timepoint) cell -> balanced {protocols['A_cellHeldOut']['balancedAccuracy']:.3f}"
      f"   hold out whole timepoint -> {protocols['B_timepointHeldOut']['balancedAccuracy']:.3f}"
      f" (p={protocols['B_timepointHeldOut']['permutation']['pCorrected']})")

replication = json.loads(
    Path("ml/evaluation/phase10_partial_gravity_replication.json").read_text())
p1 = replication["P1_binaryReplication"]
graded = replication["P2_gradedRegression"]
print(f"  OSD-346 replication: 0 g vs 0.25-0.38 g -> balanced "
      f"{p1['balancedAccuracy']:.3f}"
      f"{' (collapsed, null degenerate)' if p1['permutation']['degenerate'] else ''}; "
      f"graded 0-1 g rho {graded['correlation']['observedSpearman']:.3f} "
      f"(p={graded['correlation']['pCorrected']}) -> replicated "
      f"{replication['replicated']}")

gravity = json.loads(Path("ml/evaluation/phase10_partial_gravity.json").read_text())
primary = gravity["primaryContrast"]
print(f"  partial gravity, OSD-314 at {gravity['design']['gravityLevelsG']} g in orbit:")
print(f"    uG vs 0.34 g inside flight -> balanced {primary['balancedAccuracy']:.3f} "
      f"(p={primary['permutation']['pCorrected']}), corroborated by "
      f"{min(gravity['corroboration']['withinFlightContrasts'].values())} DE genes; "
      f"not served, because n=17 in one mission; not replicated in OSD-346")
PY

step "6/7 Phase 11 evidence, including the results that are negative on purpose"
python3 - <<'PY'
import json
from pathlib import Path

root = Path("ml/evaluation")


def load(name):
    return json.loads((root / name).read_text())


gravity = load("phase11_gravity_batch.json")
print(f"  OSD-346 gravity: {gravity['conclusion']}")
print(f"    signal survives removing the flight run: {gravity['signalSurvivesRunRemoval']}")

discovery = load("phase11_dataset_discovery.json")
microbial = discovery["questions"]["microbial"]
harvest = discovery["questions"]["harvest"]
corpus = discovery["corpus"]
print(f"  dataset sweep: {corpus['scanned']} of "
      f"{corpus['studiesWithUsableProcessedMatrix']} studies with a usable matrix, "
      f"{len(corpus['unavailableMetadata'])} metadata failures")
print(f"    harvest or biomass candidates: {harvest['candidatesNotYetCatalogued']} "
      f"(zero, so the mizuna harvest gap cannot be closed with more rows from this corpus)")
print(f"    new microbial candidates: {microbial['candidatesNotYetCatalogued']}, "
      f"none a crop load campaign")

audit = load("phase11_duplicate_audit.json")
proof = audit["numericProof"]
duplicate = next(row for row in audit["duplicates"]
                 if row["classification"] == "duplicate-measurement")
print(f"    {duplicate['studies'][0]} is a second deposit of {duplicate['studies'][1]}: "
      f"{proof['arraysCompared']} arrays, {proof['probesetsCompared']} probesets, "
      f"minimum r {proof['minimumCorrelation']:.6f}, "
      f"maximum |diff| {proof['maximumAbsoluteDifference']}")
print(f"    overlaps checked: {audit['studiesChecked']} studies, "
      f"{len(audit['duplicates'])} paired overlaps classified, "
      f"{len(audit['overlaps'])} further overlaps")

radiation = load("phase11_radiation_validation.json")
for model_id, model in radiation["models"].items():
    nested = model["nestedSelection"]
    print(f"  {model_id}: shipped {model['fidelity']['phase9CommittedBalancedAccuracy']:.4f} "
          f"reproduced exactly -> nested re-selection "
          f"{nested['nestedBalancedAccuracy']:.4f} "
          f"(delta {nested['deltaVersusShipped']:+.4f}), promoted {model['anyPromoted']}")

dose = load("phase11_dose_generalization.json")
print(f"  OSD-782 dose: {dose['verdict']}")
print(f"    within-timepoint rho "
      f"{dose['P1_withinTimepointRanking']['meanWithinTimepointSpearman']:+.4f} "
      f"(p={dose['P1_withinTimepointRanking']['permutation']['pCorrected']}), "
      f"sign flips at 3 h")

campaigns = load("phase11_microbial_campaigns.json")
pooled = campaigns["S4_randomEffects"]
print(f"  microbial flight effect: pooled {pooled['pooledEffect']:+.3f} "
      f"(95% CI {pooled['ci95'][0]:+.3f} to {pooled['ci95'][1]:+.3f}), "
      f"prediction interval for a NEW campaign {pooled['predictionInterval95'][0]:+.3f} to "
      f"{pooled['predictionInterval95'][1]:+.3f} - it includes zero, on purpose")

ood = load("phase11_ood_uncertainty.json")
print(f"  OOD novelty score: {ood['verdict']}")
for name, block in ood["scores"].items():
    print(f"    {name:34s} passes {block['controlsPassed']} of 3 controls "
          f"(duplicate AUC {block['control1_duplicate']['auc']:.3f}, "
          f"platform shift AUC {block['control2_platformShift']['auc']:.3f})")
print(f"    threshold validated: {ood['thresholdValidated']}")
PY

if [ "$SERVER" -eq 1 ]; then
  step "7/7 Live prediction through the API"
  ( cd backend && python3 -m uvicorn app.main:app --port 8011 --log-level warning ) &
  SERVER_PID=$!
  trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
  for _ in $(seq 1 40); do
    curl -sf http://127.0.0.1:8011/api/health > /dev/null && break
    sleep 0.5
  done
  python3 - <<'PY'
import json, urllib.request

base = "http://127.0.0.1:8011/api"

def post(path, payload):
    request = urllib.request.Request(
        base + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(request).read())

model = "radiation-quality-osd46-v1"
profiles = json.loads(urllib.request.urlopen(
    f"{base}/models/{model}/reference-profiles").read())
print(f"  {profiles['label']}")
for label in profiles["classLabels"]:
    expression = dict(zip(profiles["features"], profiles["profiles"][label]))
    answer = post(f"/predict/{model}", {"expression": expression})
    probabilities = ", ".join(f"{k} {v:.2f}" for k, v in answer["probabilities"].items())
    print(f"  {label:8s} centroid -> {answer['prediction']:8s} ({probabilities})")

# The API must refuse a partial gene vector rather than invent values.
partial = {profiles["features"][0]: 1.0}
try:
    post(f"/predict/{model}", {"expression": partial})
    raise SystemExit("FAILED: a partial expression vector was accepted")
except urllib.error.HTTPError as error:
    detail = json.loads(error.read())["detail"]
    print(f"  partial vector -> HTTP {error.code} "
          f"({detail['error']}, missing {detail['missingGeneCount']} genes)")

# Phase 10: the explanation must reconstruct the served logits, and must admit
# that no single gene is individually necessary.
explanation = json.loads(urllib.request.urlopen(
    f"{base}/models/{model}/explanation").read())
print(f"  explanation: {explanation['method']}")
print(f"    identity residual {explanation['identityResidual']:.2e}, "
      f"{explanation['selectionStability']['genesSelectedInEveryFold']} genes chosen in "
      f"all {explanation['selectionStability']['folds']} folds")
print(f"    largest single-gene permutation drop: "
      f"{explanation['singleGeneDependence']['maxMeanDrop']:.4f} -> "
      f"{'signal is distributed' if explanation['singleGeneDependence']['signalIsDistributed'] else 'a gene matters'}")

# Models with no valid explanation method must 404 rather than return a surrogate.
try:
    urllib.request.urlopen(f"{base}/models/lettuce-earth-growth-v2/explanation")
    raise SystemExit("FAILED: a tree ensemble returned an explanation")
except urllib.error.HTTPError as error:
    print(f"  lettuce explanation -> HTTP {error.code} (no valid method, no stub)")
PY
else
  step "7/7 Skipped the live API section (--no-server)"
fi

printf '\n\033[1mDemo complete.\033[0m Two models served with exact explanations, four negatives documented, intervals calibrated on held-out groups.\n'
