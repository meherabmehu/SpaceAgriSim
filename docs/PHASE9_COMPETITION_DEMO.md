# Phase 9 competition evidence and demo

## The eleven questions

### 1. What problem does it solve?

Space agriculture needs to know what a crop or a plant is experiencing before
visible damage appears. SpaceAgriSim now answers two narrow questions directly from
plant molecular state, using real NASA data:

- **A1:** which radiation quality did this Arabidopsis receive — none, 100 Gy
  gamma, or 30 Gy Fe-56?
- **A2:** was this sample irradiated at all?

Both are framed as what they are: molecular response classification in a ground-based
study, not yield prediction.

### 2. What dataset was used?

| Property | Value |
| --- | --- |
| Study | NASA OSD-46 (GLDS-46) |
| Organism | *Arabidopsis thaliana*, genotypes WT and atm-1 |
| Platform | Affymetrix ATH1 microarray, log2 normalised |
| Samples | 44 arrays over **22 biological groups** |
| Genes | 22,560 ATH1 probesets collapse to **21,267 gene models** with complete data across all 44 arrays |
| Access | `nasa-osdr` public S3 bucket, checksum-pinned |

Supporting datasets, evaluated and reported: OSD-782 (dose, 36 samples), OSD-411
(gravity, 63), OSD-267 and OSD-269 (ISS lettuce microbiome, 11 and 15).

### 3. What are the features?

150 gene models per model, selected **inside each training fold** by a three-stage
rule: detection filter (expressed in ≥20 % of training samples) → top 1000 by
variance → top 150 by one-way ANOVA F on training labels. 75 of the 150 are chosen by
all 22 folds, so the signature is not an artefact of one fold's selection.

### 4. What is the target?

The measured experimental condition, nothing inferred: `control` / `gamma` / `hze`
for A1, `control` / `irradiated` for A2.

### 5. How many samples?

44 arrays, but the honest number is **22** independent biological units. Splits are
made over groups, so the effective sample size is 22, and every metric is reported
with that.

### 6. What model?

A regularised logistic regression (L2), standardised, on 150 in-fold-selected genes,
serialised into a dependency-free JSON evaluator. Chosen because it is the best
*serialisable* learner: random forest and HistGBM reach comparable accuracy but
cannot be shipped into the runtime without a Python ML stack.

### 7. Which baseline was beaten?

The majority-class baseline. For A1 it scores 0.000 accuracy (every held-out group
is single-class under LOGO); for A2 it scores 0.818 accuracy but 0.500 balanced.
Comparison is on **balanced accuracy**, because raw accuracy would flatter a
majority predictor on the 8:36 imbalance.

### 8. How was leakage prevented?

| Risk | Control |
| --- | --- |
| same biological unit in train and test | leave-one-group-out with an assertion that train/test group sets are disjoint |
| feature selection seeing held-out data | selection refitted inside every fold |
| held-out genes influencing the feature set | variance preselection on z-scored data is refused by a guard (it degenerates to variance 1.0) |
| batch explaining the result | Cramér's V published; γ/HZE verified batch-balanced; A2 re-evaluated on a single batch |
| a suspiciously high score | within-study positive control re-checked before any negative is accepted |

### 9. What are the held-out results?

| Model | Accuracy | Balanced accuracy | Macro F1 | 95 % CI | Permutation p |
| --- | --- | --- | --- | --- | --- |
| A1 quality | 0.932 | 0.898 | 0.906 | 0.864–1.000 | **0.0099** |
| A2 exposure (all) | 0.932 | 0.910 | 0.891 | — | 0.0099 |
| A2 exposure (batch-controlled) | — | **0.969** | — | — | — |

Plus the negatives, which are part of the result: dose 0.361 (p = 0.2475), gravity
0.500 (p = 0.6931), cross-study transfer 0.500 with control recall 0.00 across 16
settings, ISS lettuce microbiome p = 0.904 / 0.794.

### 10. What are the limitations?

- **Quality and dose are confounded in A1.** 100 Gy γ and 30 Gy Fe-56 differ in both
  dimensions, so the model separates conditions — it does not prove a pure
  "quality" effect.
- **A2 is batch-confounded** on the full set (Cramér's V 0.715); the batch-controlled
  0.969 is the defensible figure.
- **A single ground-based study**, one organism, one platform, 22 groups.
- **No yield, biomass, survival or production inference** is possible from this data.
- **No absorbed-dose prediction** and **no partial-gravity claim**.
- **Probabilities are uncalibrated** softmax scores, not confidence intervals.
- **Cross-study transfer failed**, so the model should not be assumed to generalise to
  RNA-seq or to another genotype.

### 11. How does a user interact with it?

Open the AI prediction center, choose a class centroid on either radiation card, and
read the prediction together with its balanced accuracy, permutation p-value, group
count, batch association and the batch-controlled figure. Centroids are labelled
synthetic on screen and in the payload.

---

## Reproducible demo script

Everything below is automated in `scripts/demo_phase9.sh`. Run it with `--fast` to
check the committed state in seconds, or without arguments to re-verify every
checksum and retrain both models (about six minutes). It asserts the documented
metrics rather than printing them, so a drift fails the script.

```bash
# 0. prerequisites
python3 -m pip install -r backend/requirements-dev.txt
cd backend && python3 -m uvicorn app.main:app --port 8000 &
cd ../frontend && npm ci && npm run dev

# 1. verify provenance: download and checksum every NASA file
python3 scripts/acquire_phase9.py
#    -> 13 files, each verified by byte length and SHA-256

# 2. confirm the repository-wide sweep (optional, ~85 s)
python3 scripts/sweep_phase9_osdr.py --start 1 --end 900
#    -> 587 studies, 231 with usable processed matrices

# 3. retrain from scratch (deterministic)
python3 ml/training/train_radiation_osd46.py
#    -> A1 0.932/0.898 p=0.0099, A2 0.932/0.910, batch-controlled 0.969

# 4. package artifacts for the runtime and verify integrity
python3 scripts/package_runtime_data.py
cd backend && python3 -m pytest -q      # 261 passed

# 5. see the models answer
curl -s localhost:8000/api/models/radiation-quality-osd46-v1/reference-profiles > /tmp/p.py
python3 - <<'EOF'
import json, urllib.request
p = json.load(open('/tmp/p.py'))
body = {"expression": dict(zip(p["features"], p["profiles"]["hze"]))}
request = urllib.request.Request(
    "http://localhost:8000/api/predict/radiation-quality-osd46-v1",
    data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
print(json.dumps(json.loads(urllib.request.urlopen(request).read()), indent=2))
EOF
#    -> prediction "hze", probabilities ~0.9998, with p-value and confound attached

# 6. prove it refuses bad input (422, not a confident guess)
#    send only one gene -> expression-feature-mismatch, missingGeneCount 149

# 7. browser suite and visual regression
cd frontend && npx playwright test          # 24 passed across three viewports
cd .. && python3 scripts/visual_regression.py
#    -> 9 of 9 captures pass; dashboard 0.002-0.003 %, new cards 0.00-0.30 %
```

## The three-minute pitch

1. **The claim is narrow and it holds.** Two radiation classifiers from real NASA
   microarray data, validated on 22 held-out biological groups, at p = 0.0099 after
   correction, with the batch confound published as a number rather than a caveat.
2. **Two candidates were killed.** Absorbed dose and gravity reorientation looked
   promising and failed. Their evaluations are committed, not deleted, and a test
   asserts they cannot be reached from the API. Model count was never the goal.
3. **The negative result is a finding.** A microarray-trained radiation classifier
   does not transfer to RNA-seq — 16 hyperparameter settings all collapse to the
   majority class while the within-study control scores 0.977. That is what a
   competition entry should be able to say about its own limits.
4. **The search was systematic.** 587 studies swept, 231 with usable matrices, six
   with taxonomy tables — and the sweep corrected an earlier belief that no
   crop-microbiome data existed, even though the corrected data still cannot support
   a model.
