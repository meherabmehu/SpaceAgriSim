# Phase 7 — ML Training

Part B asks for a training-eligibility matrix, training only where measured data
supports it, grouped or study-held-out evaluation, a comparison of baselines
against linear/Ridge/RF/GBM, no deep learning on tiny data, and improvement of
the four existing models — especially the microbial cross-experiment transfer
failure.

The headline is deliberately uncomfortable: **of the 12 recovered NTRS targets,
none qualifies for predictive training, and of everything in the project only one
task was retrained.** Phase 6 counted measurements and inferred trainability;
Phase 7 separates them.

Machine-readable matrix: `data/metadata/phase7_training_eligibility`.

---

## 1. Eligibility matrix

`scripts/build_training_eligibility.py` derives the twelve NTRS verdicts from the
measurement catalog, so an eligibility claim cannot drift from the status of the
underlying measurement. It also re-states the four shipped models and lists nine
tasks that are **deliberately not trained**.

| Task | Eligibility | Trainable | Trained |
|---|---|---|---|
| `mizuna-harvest-v1` | statistical | yes | kept as-is |
| `mizuna-microbial-load-v1` | statistical | yes | superseded |
| `mizuna-microbial-relative-load-v2` | statistical | yes | **new in Phase 7** |
| `lettuce-earth-growth-v1` | statistical | yes | kept as-is |
| `tomato-flight-response-v1` | statistical | yes | kept as-is |
| NTRS targets 1–2 (biomass series, harvest yield) | statistical | yes in principle | **not trained** — see below |
| NTRS targets 3, 4, 5, 6, 8 (water, transpiration, recovery, CO₂, irradiance) | plausibility-only | no | used as bounds in Part C |
| NTRS targets 9, 12 (PPFD/photoperiod, stress) | insufficient | no | refused |
| NTRS targets 7, 10, 11 (O₂, gravity, radiation) | insufficient | no | refused |

**Zero tasks are rated `ready`.** That is the finding, not an oversight.

### Why the two "statistical" NTRS targets are still not trained

They are replicated enough to model descriptively, and that is exactly why
training them would be a mistake. Wheat grain dry matter from one chamber, one
cultivar and one institution has no transfer target in this project: the
simulator models lettuce, tomato and radish, on a fresh-weight edible basis.
A model fitted there would produce a number with a plausible-looking R² and no
population it applies to. They are used instead as **bounds** on the simulator's
growth curve in `PHASE7_SCIENTIFIC_CALIBRATION.md`, which is a weaker claim and
an honest one.

### Why target 9 is refused despite being measured

PPFD/photoperiod response has three operating points (534 µmol/m²/s at 20 h,
660 at 24 h, 530 at 20 h) and each has a yield. They also differ in chamber
sealing, nutrient-control maturity and a documented copper deficiency in
Phase IV. Fitting a response surface to that would produce a confident curve with
no identifying variation behind it — the failure mode this whole phase is meant
to stop.

## 2. The one model that was retrained, and why

`mizuna-microbial-load-v1` was the strongest candidate in the project: 123 leaf
samples, 35 pillows, two NASA campaigns, a clean measured target. It beat its
baseline within pooled data (MAE 1.087 vs 1.718) and it still failed to transfer:
leave-one-experiment-out R² was **−0.55** (VEG-04A held out) and **−0.58**
(VEG-04B held out), worse than predicting the training mean in both.

Phase 7 diagnosed the failure before trying to fix it. The measured contrasts:

| Campaign | Flight mean | Ground mean | Difference | n (flight / ground) |
|---|---|---|---|---|
| VEG-04A | 5.62 | 2.55 | **+3.06 log** | 5 / 15 |
| VEG-04B | 3.61 | 0.98 | **+2.64 log** | 31 / 72 |

The **effect replicates**. Both campaigns show the same sign and a similar
magnitude (+2.6 to +3.1 log, a 435–1155× fold difference). What does not
replicate is the campaign's **absolute level**: VEG-04B sits about 1.6 log below
VEG-04A overall, for reasons that are properties of the campaign (handling,
sampling protocol, baseline contamination), not functions of any feature present
in both.

So the offset is not learnable from the features, and no learner could recover it.
The fix is therefore not a better model but a **narrower estimand**:

    v1 target:  y = log10(1 + CFU/g)                       (absolute, unidentifiable across campaigns)
    v2 target:  z = (y − campaign mean) / campaign sd       (relative, transferable)

v2 drops experiment identity from the feature set (after centring it would be
collinear with the removed offset) and reports the absolute scale separately, as
a **measured effect with an interval**, plus an explicit
`absoluteScaleProtocol` requiring the caller to supply the campaign's own
baseline mean and sd. Predicting the campaign mean is refused in the artifact
itself.

### Result

| Target | Held-out VEG-04A R² | Held-out VEG-04B R² | Verdict |
|---|---|---|---|
| v1 absolute (RF) | −0.269 | −0.893 | does not transfer |
| v2 relative, Ridge | 0.445 | 0.137 | transfers weakly |
| **v2 relative, RF** | **0.444** | **0.373** | **transfers** |
| v2 relative, GBM | 0.548 | 0.000 | degenerate on B |

The improvement is attributable to the **estimand change, not a more flexible
learner**: the same learners still fail on the absolute target. RandomForest is
shipped over Ridge because it is the only learner that transfers with a useful
margin on *both* campaigns, and over GBM because GBM collapsed to the mean on
VEG-04B (R² exactly 0.000) — a textbook sign of a flexible learner fitting noise
at n = 123.

### Guarding against a lucky split

With two campaigns and 123 samples, a positive held-out R² could be luck, so the
entire leave-one-campaign-out procedure was re-run 200 times with the target
permuted **within** each campaign (preserving its scale structure):

| Campaign | Observed R² | Null mean R² | Null sd | Permutation p |
|---|---|---|---|---|
| VEG-04A | 0.444 | −0.174 | 0.203 | 0.000 (0/200) |
| VEG-04B | 0.373 | −0.149 | 0.143 | 0.000 (0/200) |

The observed transfer sits well outside the null distribution.

### Why v2 is still not called "validated"

The project's promotion rule requires beating the baseline, positive held-out
study R², **and** conformal coverage within 5 points of nominal. v2's group-aware
split-conformal interval achieves **empirical coverage 0.849 against a 0.90
nominal** — 5.1 points short. The artifact therefore records
`evidenceStatus: "experimental"` and labels its interval
"UNCALIBRATED descriptive residual range". A rule that only ever produces
promotions is not a rule.

## 3. Reproducibility

- `ml/requirements-training.txt` pins the interpreter and every library that
  touched an artifact (python 3.13.16, numpy 2.3.5, pandas 2.2.3, scikit-learn
  1.6.1, scipy 1.17.1).
- Every registry entry records the same versions under `environment`.
- **Artifacts are versioned, never overwritten.** `mizuna-microbial-load-v1`
  remains on disk and registered; v2 is a new file with a new id, and its
  `supersedes` field names the model it displaces without deleting it.
- Nothing is registered as validated by omission: an artifact with no
  `evidenceStatus` is reported as `experimental` by the registry reader.

## 4. Deep learning

Not used, and the reason is arithmetic rather than taste: the largest measured
target has 123 samples across 35 groups and 2 campaigns. A network of any
non-trivial capacity is unidentifiable at that size, and its reported error would
be optimistically biased whatever the grouping discipline — because with two
groups there is no way to hold out a third and learn how badly it generalises.
