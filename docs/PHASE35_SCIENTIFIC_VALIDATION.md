# Phase 35 — Scientific validation

Phase 34 measured what each model does outside the campaign it was fitted on. Phase 35 turns those
measurements into a decision that reaches the user, and asks the question the numbers had left open:
*which of these models may be presented as a forecast?*

## 1. The verdict scheme

`ml/research/phase35_evidence_verdicts.py` derives one verdict per registered model from committed
evaluation files and model cards. Nothing is typed in by hand; `--check` fails when a card and the
evidence disagree.

| verdict | meaning | decision grade |
|---|---|---|
| `passes-independent-check` | an independent campaign scored it and every pre-declared criterion was met | yes |
| `fails-independent-check` | an independent campaign scored it and the criterion was missed | no |
| `no-independent-check` | only within-study performance exists — not a failure, not validation | no |
| `withdrawn` | retained as a documented negative result, not served | no |

Three criteria are used, each stated by the artifact before this phase:

* the lettuce v3 holdout criterion (`MAPE <= 30 %`, fixed before the measurement);
* the mizuna v2 evidence rule (`evidenceBasis.rule`: beat the baseline, positive held-out R² on
  every campaign, permutation p < 0.05 on both campaigns, conformal coverage within 5 points of
  nominal);
* interval coverage outside the fitted study, for which the destructive bound is used — a nominal
  90 % interval that contains **none** of six independent treatment means has failed as an interval,
  whatever tolerance one prefers.

## 2. Result per model

| model | independent check | measured | verdict |
|---|---|---|---|
| lettuce-earth-growth-v1 | cross-campaign interval coverage | 0 of 6 treatment means covered, ratio median 3.655 (1.905–5.493) | fails |
| lettuce-earth-growth-v2 | cross-campaign interval coverage | 0 of 6, ratio median 3.212 (1.674–5.375) | fails |
| lettuce-earth-growth-v3 | Touliatos 2016 holdout + coverage | 41.59 % MAPE against 30 %; coverage 6 of 6 | fails |
| mizuna-microbial-relative-load-v2 | campaign-held-out R², permutation, pooled coverage | 0.444 (VEG-04A) / 0.373 (VEG-04B), p = 0.0 both, coverage 110/123 = 0.8943 (nominal 0.90) | passes |
| radiation-quality-osd46-v1 | none | within-study balanced accuracy only | no check |
| radiation-exposure-osd46-v1 | none | within-study balanced accuracy only | no check |
| tomato-flight-response-v1 | none | out-of-fold 0.9167 on 36 samples / 21 plants, one experiment | no check |
| mizuna-harvest-v1 | campaign holdout | R² −0.333 vs baseline −0.138 | withdrawn |
| mizuna-microbial-load-v1 | campaign holdout | R² −0.55 / −0.58 | withdrawn |

`lettuce-earth-growth-v3` is the case worth reading twice: six of six independent means fall inside
its interval, and the model still fails, because a pre-registered accuracy criterion was missed at
41.59 %. Coverage is not accuracy, and the verdict does not let a passing count outvote a failed
criterion. The artifact records both.

## 3. The one status change, and why it is a derivation

`mizuna-microbial-relative-load-v2` moved from `experimental` to `validated-exploratory`.

Its card already contained the rule that defines that status. Three terms were true
(beats the baseline: pooled R² 0.509; positive held-out R² on every campaign: 0.444 and 0.373;
permutation p = 0.0 on both with 200 permutations). The fourth term was a boolean,
`intervalsEmpiricallyCalibrated`, that was `false` only because the cross-campaign coverage had never
been measured. Phase 34 measured it: 110 of 123 samples covered, 0.8943 against a nominal 0.90,
inside the rule's own ±5-point tolerance.

The script therefore scores that term from the measurement and records what changed:

```
"intervalsEmpiricallyCalibratedEvidence":
  "ml/evaluation/phase34_cross_campaign_coverage.json: pooled cross-campaign coverage 0.8943
   against a nominal 0.90"
```

What this promotion does **not** claim:

* it does not extend beyond a campaign that supplies its own baseline samples — the served scope
  still requires a campaign reference, and the card's own caveat says two campaigns are not a sample
  of campaigns;
* it does not make the absolute-scale load prediction valid (still withdrawn as v1);
* it does not survive the removal of the relative-load estimand.

The honest caveat: the rule was written before the measurement, but the *application* of a
pre-written rule to a freshly measured number is a judgement, and it is recorded as one rather than
presented as an automatic consequence.

## 4. What a user now sees

* **Model registry (`/#predictions`)** — every card carries a badge (`Independent check passed`,
  `Independent check failed`, `No independent check`) and, where a check failed, the measurement that
  failed it.
* **Prediction responses** — every route returns `evidenceVerdict` and `decisionGrade`, and for any
  model that is not decision grade the same sentence is appended to `warnings`, so an API consumer
  cannot receive the number without its status.
* **Prediction panels** — the verdict renders as a sentence above the value, styled as a warning,
  not a tooltip.
* **Scientific-status panel** — its prose is computed: “1 of 7 is currently decision grade: 3 failed
  an independent check, 3 have never been scored by one.” It previously asserted, unconditionally,
  that no served model reports calibrated probabilities.
* **Audit** — 34 new checks assert the verdict exists, matches the evidence file, is not decision
  grade when its check failed, and reaches the caller; 202 checks in total, 0 failed.

## 5. What was *not* done, and why

**No model was trained.** The phase's remit allowed a replacement where data volume, feature quality,
grouping and validation design justify one. None of the available additions clears that bar:
the candidates found in the Phase 34 and Phase 35 searches are treatment-mean tables (no
replication structure), remote-sensing products (wrong system), or transcriptomic experiments without
measured yields. Training on them would have produced a fitted number with no independent check —
exactly the failure this phase exists to prevent.

**The three failing lettuce models were not withdrawn from serving.** Their prediction routes stay
available, under `deprecated`/experimental status, with the failure sentence attached, because the
Phase 19–34 negative results are the reproducibility record for the v3 improvement and because the
advertised capability (an exploratory regression with a stated domain) is exactly what they provide.
What changed is that no surface now presents them as validated. `servedScope` is asserted non-empty
by the tests for each of them.

**The tomato calibration stays one experiment.** 36 samples from 21 plants, out-of-fold, ECE 0.1621,
`calibrated: false`. It is reported as an out-of-fold measurement on one experiment and nothing more.

## 6. Open limitations (unchanged in severity)

1. **No measured reference ET.** FAO-56 Penman-Monteith and Hargreaves-Samani are published physics
   validated against the FAO-56 worked examples, not against measured lysimeter water use in a
   controlled environment. Workstream 4 verified the implementation (units, paths, plausibility
   bounds) and found no measured series to validate against.
2. **Lettuce intervals do not transfer** to an independent campaign (v1 0/6, v2 0/6); v3's own
   holdout fails its 30 % criterion at 41.59 %.
3. **Two campaigns are not a sample of campaigns.** The mizuna interval radius is calibrated on 35
   pillows in two campaigns; a third campaign's offset must come from its own baseline samples.
4. **No LED spectral response surface.** Searches returned papers and a .docx data sheet; no
   machine-readable experiment with per-plant outcomes was found.
5. **No fractional-gravity growth data.** OSD-480 (1.41 TB) and GLDS-251 are transcriptomic and
   morphological; no controlled-environment edible-biomass yield versus g-level exists in the
   repositories searched, so the gravity-related gap retains its original severity.
6. **Substrate moisture / irrigation telemetry**: the only relevant open dataset found is open-field
   mineral-soil drip irrigation (Mendeley `10.17632/c837v6p8ph.2`), which cannot validate a
   controlled-environment substrate water balance.

Each of these is a missing measurement, not a missing feature. Documenting them does not close them.
