# Phase 34 — scientific validation

Phase 34 asked five audit findings a single question: **measured coverage inside the fitted
campaign is not coverage.** This document states the method, the numbers, and what each number is
allowed to be used for.

Two studies were produced. Both read shipped artifacts through the same code the API uses
(`app.research.load_model`, `predict_values`, `inverse_target_transform`), so what is measured is
the served model, not a re-fit of it. Neither study trains anything.

```
ml/research/phase34_tomato_calibration.py      -> ml/evaluation/phase34_probability_calibration
ml/research/phase34_cross_campaign_coverage.py -> ml/evaluation/phase34_cross_campaign_coverage
ml/research/phase34_record_measurements.py     -> writes those numbers into the five model cards
```

`phase34_record_measurements.py --check` fails if a card and its evidence file disagree, so a card
cannot drift away from its own measurement.

## 1. Probability calibration — `tomato-flight-response-v1`

**Question.** The classifier serves `predict_proba`. Is that number a probability, or a ranking?

**Method.** Every scored probability is out of fold under the committed 4-fold stratified-group
split (`ml/evaluation/tomato_splits`): the two tissues of a plant stay in one fold, so no
plant is in the fold that scored it. Hard-label accuracy is recomputed from those same
probabilities and asserted equal to the artifact's 0.9167. Intervals come from 2000 bootstrap
resamples **over plants**, not over rows. No rescaling is fitted: a nested temperature search would
need to refit folds whose input expression matrix is not vendored here, and fitting on the scored
rows would be an in-sample number, which is not reported.

| metric | value | 95 % plant-resampled interval |
|---|---|---|
| log loss | 0.2827 | 0.1881 – 0.3902 |
| Brier | 0.0810 | 0.0440 – 0.1255 |
| top-label ECE (10 bins) | 0.1621 | 0.1357 – 0.2342 |

* 36 samples from 21 plants, base rate 0.5, mean maximum probability 0.7908.
* Of 7 predictions at or above 0.9, **0 were wrong**; the ECE still says the confidence is not
  the accuracy.
* Served scaling: **none**. The card records `measured: true`, `calibrated: false`.

**What this closes and what it does not.** The finding was "the card does not say whether class
probabilities are calibrated; no calibration analysis is recorded". It now says so, with numbers
and intervals. It does **not** make the probabilities calibrated, and nothing in the served text
claims they are. The interpretation the card carries is the measurement's own: treat the score as
a ranking of recorded flight context, not as the probability the class is correct, and not as a
statement about plant health, stress or yield.

## 2. Cross-campaign interval coverage

### 2.1 Lettuce — an independent greenhouse campaign

**Independent campaign.** Wicharuck et al. 2024, PeerJ 12:e17085 (CC BY 4.0): six treatment means,
two cultivars × three vertical levels, 28 DAT, air/root 27.5 °C, 12 h, PPFD 322/391/697
µmol m⁻² s⁻¹ → DLI 13.9/16.9/30.1, 600 plants m⁻². The models' inputs are reconstructed from the
study's own reported conditions; nothing is interpolated.

**Arithmetic that had to be got right.** v1 and v2 predict fresh mass **per plant** and serve an
absolute radius. v3 predicts fresh yield **per square metre** and serves conformal quantiles on
the log per-area target, which the route then divides by planting density. Applying either
interval shape to the other's prediction unit produces a 56× error, so each model's own served
arithmetic is reproduced and the six means are converted to the served unit before comparison.
Predictions were also divided by the campaign's own density before any ratio was formed.

| model | within-campaign coverage (WUR, leave-one-experiment-out) | independent campaign | ratio median (min–max) |
|---|---|---|---|
| `lettuce-earth-growth-v1` | 0.9393 | **0 / 6** | 3.655 (1.905 – 5.493) |
| `lettuce-earth-growth-v2` | 0.9606 | **0 / 6** | 3.212 (1.674 – 5.375) |
| `lettuce-earth-growth-v3` | 0.8993 | **6 / 6** | 1.163 (0.606 – 1.863) |

Read that table carefully, because it is easy to read it wrongly:

* v1 and v2 **over-predict the independent campaign by roughly 3×**, and their 90 % intervals do
  not contain a single independent treatment mean. The within-campaign 0.96 was measuring the
  spread of four plant-factory experiments, not the distance to a greenhouse.
* v3 covering 6 of 6 is **coverage, not accuracy**. Six correlated means from one greenhouse are
  not a validation set, a wide interval covers by width, and v3's declared independent holdout
  (Touliatos et al. 2016) failed its pre-registered 30 % MAPE criterion (41.6 %). That failure
  stands and the card still states it.
* PeerJ 2024 was already used as a development check before this measurement, so this is a
  **cross-campaign measurement, not an untouched holdout**. No criterion is re-scored against it.

Cards: `interval.crossCampaign` carries the numbers and the study, and `servedScope` states the
measurement in one sentence so the API response cannot present the interval as a general 90 %
claim.

### 2.2 Mizuna — two flight campaigns, both directions

**Design.** `mizuna-microbial-load-v1` (absolute log10 CFU/g) and
`mizuna-microbial-relative-load-v2` (within-campaign relative target) were each calibrated on one
VEG-04 campaign and evaluated on the other, in both directions. The conformal radius is the 90th
percentile of absolute residuals on the calibration campaign, applied unchanged to the held-out
campaign; the two directions are then pooled. Calibration and evaluation sets never share a
campaign, so this is not calibration and evaluation on the same observations.

| model | calibrated on → evaluated on | radius | covered | achieved |
|---|---|---|---|---|
| v1 | VEG-04A → VEG-04B | 1.1363 | 93 / 103 | 0.9029 |
| v1 | VEG-04B → VEG-04A | 1.1115 | 17 / 20 | 0.8500 |
| v1 | **pooled** | — | **107 / 123** | **0.8699** |
| v2 | VEG-04A → VEG-04B | 1.1363 | 93 / 103 | 0.9029 |
| v2 | VEG-04B → VEG-04A | 1.1115 | 17 / 20 | 0.8500 |
| v2 | **pooled** | — | **110 / 123** | **0.8943** |

Within-campaign coverage was 0.9919 for both. Across campaigns it is 0.87–0.89 against a nominal
0.90 — the interval degrades only mildly, which is the useful result, but it is not exact
coverage and the card says so. Context already measured and still standing: the campaign offset is
real and not a function of the features (VEG-04A +3.06 log, VEG-04B +2.64 log, with VEG-04B
sitting ~1.6 log lower), which is why both cards state that a third campaign's offset must come
from that campaign's own baseline samples.

### 2.3 Why the interval shapes differ, and why that is not a bug

`interval.radius` (absolute, v1/v2 lettuce, both mizuna) and `interval.logResidual*` (multiplicative,
lettuce v3) are different statistics. The measurement above reproduces each model's own served
shape rather than imposing one. Mixing them was the first bug this phase hit — v3 appeared to
cover 0/6 with a 56× ratio until the per-area target was divided by the campaign density.

## 3. Effect on the audit

| | before Phase 34 | after |
|---|---|---|
| documented gaps | 5 | **0** |
| resolved gaps | 3 (all Phase 32) | 7 (3 Phase 32, 4 Phase 34) |
| checks run | 161 | 168 |
| checks failed | 0 | 0 |

Nothing was lowered: the gap severities, `PIXEL_BUDGET`, the 30 % MAPE criterion, the 240 kB
bundle budget and every test expectation are unchanged. A gap is resolved here only by recording a
measurement — including the two measurements that came out **badly** (v1 and v2 at 0/6). A
documentation gap about missing measurement is closed by a measurement; a model that fails its
accuracy criterion keeps failing it.

## 4. Capability: what actually improved

* The tomato classifier now publishes its probability quality instead of leaving it undetermined.
* Three lettuce models and two mizuna models now state, in their served scope, what their interval
  does outside the campaign it was fitted on.
* Two false statements were removed from served text: the mizuna cards' claim that no second
  campaign exists.
* **No new prediction capability was added.** No model was trained, promoted, reinstated or
  retired in this phase, and no threshold moved. Two of the five findings resolved into negative
  results — v1 and v2 do not transfer — which is the correct outcome to report for them.

## 5. Limitations that remain open, and are documented rather than hidden

1. Two campaigns bound a campaign offset; they do not estimate its distribution, so neither mizuna
   card can promise coverage on a third campaign.
2. Lettuce v1/v2 fail the independent campaign outright below ~5.5× their in-campaign coverage
   claim; they remain served, with the failure written into `servedScope` and the interval block.
3. v3's independent holdout failure (Touliatos, 41.6 % MAPE vs 30 %) is unchanged and not
   offset by the 6/6 coverage result.
4. The tomato calibration is one experiment (OSD-767, 21 plants); no cross-experiment classifier
   exists to calibrate on, and a nested temperature fit would need the unfetched expression
   matrix.
5. No measured reference ET, substrate-moisture series or LED-spectrum response dataset was
   acquired this phase (see `PHASE34_DATA_ACQUISITION.md`), so no new water or light response
   model was built.
