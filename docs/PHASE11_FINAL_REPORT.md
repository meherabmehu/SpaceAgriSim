# Phase 11 — final report

Branch `feat/phase11-nasa-ai-validation`, from verified `origin/main` = `02eac8a`.
Nine commits, no deployment, no UI change, thirteen NASA source files verified by SHA-256.

Every claim below is tied to a committed artifact and the command that regenerates it. Where
a result is negative, it is stated as negative and classified as such.

---

## 1. Commit index

| Commit | Subject |
| --- | --- |
| `5a4cbcd` | docs: establish phase eleven baseline from verified artifacts |
| `b5e1972` | science: the OSD-346 gravity signal is its flight runs, not gravity |
| `b1f550c` | data: expand the discovery scan and prove the best new lead is a duplicate |
| `a1cebc5` | science: no radiation learner beats the served model once the search is nested |
| `6f36bc3` | science: dose is recoverable in principle but empty in practice, and three protocols say so |
| `90ab8f5` | science: the flight effect replicates in ten strata but a new campaign is not guaranteed it |
| `410a502` | science: explanations agree at the top and nowhere else, and no single gene is necessary |
| `9550301` | science: the novelty score fails its own controls, and the failures are informative |
| `ec59754` | demo: make the full retrain path pass its own checksum gate |

---

## 2. Objective-by-objective classification

| # | Objective | Classification | Evidence |
| --- | --- | --- | --- |
| 1 | Improve reliability of existing NASA-trained models | **Rejected by scientific evaluation** | `phase11_radiation_validation.json` |
| 2 | Find new NASA datasets that fix weak models | **Partially completed** (sweep complete; nothing usable found) | `phase11_dataset_discovery.json`, `phase11_duplicate_audit.json` |
| 3 | Narrow Phase 10 scientific uncertainties | **Completed** (four narrowed, one confirmed blocked) | gravity, dose, microbial, OOD artifacts |
| 4 | Improve explainability, uncertainty, OOD | **Partially completed** — explainability and OOD completed; OOD detector rejected on its own controls | `phase11_explainability.json`, `phase11_ood_uncertainty.json` |
| 5 | Evidence-grounded decision support | **Completed** | `phase11_microbial_campaigns.json` prediction interval |
| 6 | Reproducible competition demo | **Completed** | `scripts/demo_phase9.sh`, `docs/PHASE11_COMPETITION_DEMO.md` |
| 7 | Platform quality and merge to `main` | **Completed** | `docs/PHASE11_PLATFORM_QA.md`, this branch merged with `--no-ff` |

---

## 3. Objective 1 — model reliability: **rejected by scientific evaluation**

Six candidate configurations against the served radiation classifiers, one pre-declared
group-aware protocol, promotion bar fixed before the run at 0.02 balanced accuracy plus a
majority of held-out groups.

```
python ml/training/phase11_radiation_validation.py    # ~90 s
```

| Model | Phase 9 committed | Reproduced | Best fixed-k | Nested re-selection | Promoted |
| --- | --- | --- | --- | --- | --- |
| `radiation-quality-osd46-v1` | 0.8981 | **0.8981** | 0.9167 (25 genes) | 0.8611 | **No** |
| `radiation-exposure-osd46-v1` | 0.9097 | **0.9097** | 0.9722 (25 genes) | 0.9097 | **No** |

Three findings, in order of how much they matter:

1. **The apparent win is one array.** The 25-gene panel wins **1 group, loses 0, ties 21** of
   22 both times. A 6-point balanced-accuracy gain on the exposure model is a single held-out
   group changing from wrong to right.
2. **Nested re-selection removes it.** Choosing the configuration inside each outer fold lands
   0.037 *below* the shipped model on quality and exactly level on exposure, with 0 wins and
   0 losses across all 22 groups. The inner loop picks four different configurations across
   folds — it is averaging disagreement, not exploiting a better pipeline.
3. **The signal cannot be compressed.** L1 sparsity collapses to 0.648/0.472 and
   training-only co-expression modules to 0.222/0.500. Phase 10 showed the radiation
   signature is distributed; Phase 11 shows squeezing it into modules destroys it rather than
   concentrating it.

**Registry unchanged, 8 models.** `calibrated: false` stays on all models where it was set.
Descriptive calibration for the binary model: ECE 0.0489 — explicitly not a calibration claim,
because five bins over 44 arrays cannot validate a curve.

---

## 4. Objective 2 — dataset discovery: **partially completed, nothing usable**

```
python ml/training/phase11_dataset_discovery.py    # ~140 s, 231 studies
python ml/training/phase11_duplicate_audit.py      # 25 studies, pairwise + numeric proof
```

| Question | Candidates | Not catalogued | Usable |
| --- | --- | --- | --- |
| Third microbial campaign | 11 | 9 | **0** |
| Harvest / biomass with environment | **0** | 0 | **0** |
| Another plant radiation study | 13 | 11 | **0** |
| Another crop growth study | 5 | 3 | **0** |

**The dangerous finding, and the most valuable single result in Phase 11:** OSD-320 looked
like the independent radiation study the project has needed since Phase 9 — same Affymetrix
platform, same two genotypes, same two radiation types, same five timepoints, explicit
absorbed-dose column. **It is the same 44 arrays as OSD-46 under a second accession:**

| Check | Result |
| --- | --- |
| Arrays compared | 44 / 44 |
| Probesets compared | 22,810 |
| Minimum correlation | **1.000000** |
| Maximum absolute difference | **0.0** |

A pipeline that accepted it would have reported a perfect-score cross-study replication from
a study compared **against itself**. It was invisible to earlier sweeps because the same array
is written `GSM1506014`, `GSM1506014_1` and `GSM1506014 1` across the two deposits; the audit
now keys on the accession token and reads both name columns.

The audit separates three cases that must never be conflated: `duplicate-measurement`
(OSD-320~OSD-46), `shared-biological-sample-distinct-assay` (OSD-655~OSD-780, 45 shared
VEG-04A plants but chemistry versus plate counts — benign) and
`shared-sample-needs-numeric-check` (the VEG-01 series).

**Consequence: radiation cross-study validation remains blocked by data, and the harvest gap
is now provably unclosable — zero candidates exist in the entire corpus.**

---

## 5. Objective 3 — Phase 10 uncertainties narrowed

### 5a. Gravity: **completed**, and it closes the question

```
python ml/training/phase11_gravity_batch.py
```

Conclusion `osd346-gravity-signal-is-not-separable-from-flight-run`,
`signalSurvivesRunRemoval: false`.

| Test | Result |
| --- | --- |
| Within-run gravity range | **0.192 g = 18 %** of the 1.05 g span |
| Run identifiable from expression | balanced **0.6944** |
| Raw Spearman ρ | 0.7521, within-run permutation p **0.1959** |
| Run-centred ρ | **−0.7981**, p 0.8201 (sign reverses) |
| Between-run ρ | 0.8286, p 0.0416 |
| Within-run ρ | 0.2291, p 0.1104 |
| Gravity levels in more than one run | **0 of 9** |

The Phase 10 number is not overwritten. Its P2 correlation of 0.571 was p 0.0015 under a
**within-light-treatment** null that spans all six runs and centres on zero, versus p 0.196
under a within-run null. That is a **null-specification error**, disclosed in
`phase11_gravity_batch.json` as `C_phase10Correction`; no served claim depended on it.

### 5b. Dose: **completed** — now a mechanism, not a low score

```
python ml/training/phase11_dose_generalization.py    # ~75 s
```

Verdict `dose-is-not-recoverable-at-this-sample-size`. Timepoint is perfectly crossed with
dose, so each timepoint is centred on itself and the confound is **removed** rather than
modelled.

| Timepoint | within-timepoint ρ |
| --- | --- |
| 1 h | +0.8433 |
| 3 h | **−0.6852** |
| 24 h | +0.1054 |
| 72 h | +0.6325 |
| mean | +0.2240, p **0.158** |

The mean is not the finding; **the sign reversal is**. A single dose axis would not change
direction at three hours, and scoring each timepoint alone shows Phase 10's heterogeneity was
not an artefact of the global framing. The unseen-dose check agrees: 10 Gy samples land at a
median predicted **84.8 Gy**, and only 75 % sit between the 0 and 100 Gy anchors against a
permutation null whose median is 1.0 (no discriminating power, said so in the artifact).

`radiation-dose-osd782-v1` stays excluded, now for a stated reason: the labels are valid and
the expression response to 10 and 100 Gy is not separable as a dose axis would require.

### 5c. Microbial: **completed**

```
python ml/training/phase11_microbial_campaigns.py    # ~3 s
```

Phase 7's headline reproduced exactly (+3.0626 / +2.6392) before anything was compared to it.

| Result | Value |
| --- | --- |
| Strata positive with CI excluding zero | **6 of 10** |
| Tissue specificity | leaf +3.06/+2.24 and +2.64/+1.97; soil +0.15/+0.40 spanning zero; root aerobic −0.12 |
| Raw all-tissue means | A +1.675, B +2.366 — **ranking inverts** the leaf-only numbers |
| Composition-standardised | B at A's mix **+2.305**, A at B's mix **+2.733** |
| Pooled effect | **+2.820**, 95 % CI [+2.327, +3.314], I² 0.0 % |
| **Prediction interval for a new campaign** | **[−0.377, +6.018]** |

That last row is the decision-support result and it **includes zero on purpose**: the average
effect is clear, a specific new campaign is not guaranteed a positive contrast. Limitation
recorded: VEG-04B sampled leaf only, so standardisation reaches only the two shared strata.

### 5d. OOD: **rejected by scientific evaluation**

```
python ml/training/phase11_ood_uncertainty.py    # ~30 s
```

Two scores, three controls, expectations fixed before the run:

| Score | duplicate AUC | platform-shift AUC | held-out groups | passed |
| --- | --- | --- | --- | --- |
| Mahalanobis, 10 PCs | 0.702 ✗ | **0.016 ✗** | 0.471 ✓ | 1/3 |
| Nearest-neighbour correlation | 0.033 ✓ | **0.310 ✗** | 0.505 ✓ | 2/3 |

Verdict `ood-score-not-validated-by-any-available-control`. The direction matters: a
platform-shifted study scores *lower* than the training data itself, i.e. the detector calls a
real shift "more familiar than the original". Three structural causes are documented
— standardisation deletes the mean shifts that constitute a platform shift; in-sample
Mahalanobis is inflated by √((n−1)/(n−p)) ≈ 1.13 at this size; and platform is confounded with
assay and preparation. **No threshold is emitted; `thresholdValidated: false`.**

---

## 6. Objective 4 — explainability: **completed**, with rank-1 claims rejected

```
python ml/training/phase11_explainability.py    # ~10 min
```

| Measure | Quality model | Exposure model |
| --- | --- | --- |
| Top-40 panel Jaccard vs deployed | 0.704 (0.482–0.905) | 0.828 (0.702–0.905) |
| Rank-1 gene present | **100 %** of folds | **100 %** of folds |
| Genes in every fold panel | 19 of 115 | 26 of 70 |
| Top-5 overlap between learners | **0.80** | **1.00** |
| Spearman across the panel | **+0.016** | undefined |
| Panel genes with **zero** permutation drop | 0.95–1.00 | 0.90–1.00 |

**Every pair of learners agrees on the top five and disagrees about the rest**, and permuting
any single panel gene leaves the held-out prediction unchanged. Three independent methods now
agree the radiation signature is distributed: Phase 10 permutation, Phase 11 module
compression failing, Phase 11 single-gene permutation.

| Claim | Status |
| --- | --- |
| "These are the genes the model weighs most" | **Supported** |
| "This gene drives the prediction" | **Rejected** — 90–100 % zero-drop |
| "This gene causes the response" | **Rejected** — attribution, not intervention |
| "The ranked list 1–40 is meaningful" | **Rejected** — rank correlation 0.016 |

No UI change: the caveat text and documentation carry the narrowing.

---

## 7. Objective 6 — competition demo: **completed**

| Run | Wall clock | Result |
| --- | --- | --- |
| `./scripts/demo_phase9.sh --fast` | ~5 s | passes |
| `./scripts/demo_phase9.sh` | ~11 min | **passes** (EXIT=0) |

The full run **failed before Phase 11** with
`ValueError: Model checksum verification failed: radiation-quality-osd46-v1` — not a metric
failure. Retraining dropped the Phase 10 explanation metadata and never rebuilt the registry.
Fixed by ordering: **train → explain → build_registry → verify**. After that, the diff between
committed and regenerated artifacts is only `trainedAt`/`generatedAt` and the resulting
SHA-256s; every measured number is bit-identical.

---

## 8. Objective 7 — platform QA: **completed**

| Gate | Command | Result |
| --- | --- | --- |
| Backend | `pytest -q` with `SPACEAGRISIM_TEST_POSTGRES_URL` | **291 passed** |
| Registry | `scripts/verify_model_registry.py` | **40/40** |
| Lint | `npm run lint` | clean |
| Types | `npm run typecheck` | clean |
| Build | `npm run build` | 11.77 s |
| End-to-end | `npx playwright test` (3 viewports) | **27 passed** |
| UI preservation | `git diff --stat 02eac8a -- frontend/` | **empty** |
| Screenshots | `scripts/compare_ui_screenshots.py` | `ui-extended-layout-preserved`, 0 px layout drift |

Two environment faults recorded as environment faults, not code defects: Playwright browsers
missing `libnspr4` (27 failed → `install-deps` → 27 passed on the same commit), and the demo
ordering bug above.

**Nothing was deployed.** No Render push, no production host, no UI redesign.

---

## 9. Rejected experiments, kept on the record

| Rejected | What it returned | Why it is not evidence |
| --- | --- | --- |
| 3-class classification, leave-one-dose-level-out | balanced **0.0000** every fold | a classifier trained on two levels cannot emit the third — a category error wearing a result's clothes |
| AUC between an unseen level and its nearest training level | 0.0903 / 0.0000 / 1.0000, null centred at **0.3403** | every split reused a training level as the reference class; a null off chance is the tell |
| Leave-one-dose-level-out ridge, scored by ρ | observed −0.5371, null centred at **−0.7434** | extrapolation from two anchors; a null not centred on zero supports nothing |
| 25-gene panel as a model upgrade | +0.019 / +0.063, **1 win, 0 losses, 21 ties** | one array; collapsed to ≤0 under nested re-selection |
| Co-expression modules | 0.222 / 0.500 | destroys the distributed signal |
| L1 sparsity | 0.648 / 0.472 | collapses |
| OOD threshold | no score passed its controls | 1/3 and 2/3 |
| Hyper-parameter search on mizuna harvest (14 points) | not repeated | Phase 10 already rejected it; zero harvest data exists |
| Synthetic training rows | refused | would manufacture the evidence the model rests on |
| OSD-320 as independent validation | **excluded** | numerically identical to OSD-46 |

---

## 10. Unchanged from Phase 10, verified rather than asserted

| Item | Value |
| --- | --- |
| Registry | **8 models**, 2 exclusions |
| Dataset catalogue | **19 datasets** |
| Interval coverage | 0.9919 ×2 (microbial, group level), lettuce 0.9606 / 0.9393 |
| Cross-study transfer | 0.4375 cells held out vs 0.8125 timepoints held out |
| Dose (Phase 10 protocols) | 0.1111 cells / 0.6111 timepoints / ρ 0.1965 |
| OSD-314 partial gravity | balanced 1.000, p 0.0055, **not served** |

---

## 11. What Phase 11 did not do

- **No deployment**, by instruction.
- **No UI change** — zero frontend diff.
- **No model promoted** — the phase's central scientific result is that the challengers do not
  survive honest evaluation.
- **No cross-study radiation validation** — blocked by data, since the only candidate is a
  duplicate.
- **No third microbial campaign** — blocked by data.
- **No new harvest measurements** — blocked by data, provably: zero candidates exist.
- **No validated OOD threshold** — rejected on the detector's own controls.
- **No crop-yield, lunar-growth or Mars-growth prediction** anywhere in this phase.

---

## 12. সারসংক্ষেপ (Bengali summary)

ফেজ ১১-এ নতুন কোনো মডেল প্রচলিত (promote) করা হয়নি — কারণ সৎ মূল্যায়নে কোনো প্রার্থী টিকেনি।
ছয়টি বিকল্প শিখন-পদ্ধতি একই গ্রুপ-ভিত্তিক প্রোটোকলে পরীক্ষা করে দেখা গেছে, আপাত উন্নতিটি
মাত্র **একটি হোল্ড-আউট গ্রুপ** থেকে এসেছে (১ জয়, ২১ সমান), এবং ভেতরে-ভেতরে কনফিগারেশন
নির্বাচন করলে সেই উন্নতিও শূন্য হয়ে যায়।

সবচেয়ে গুরুত্বপূর্ণ আবিষ্কার: **OSD-320 আসলে OSD-46-এরই দ্বিতীয় কপি** — ৪৪টি অ্যারে,
২২,৮১০টি প্রোবসেট, r = 1.000000, সর্বোচ্চ পার্থক্য 0.0। এটি স্বতন্ত্র যাচাই হিসেবে ব্যবহার
হলে নিজের সঙ্গে নিজের তুলনা করে নিখুঁত স্কোর দেখানো যেত। এখন একটি ডুপ্লিকেট-ডিটেক্টর আছে।

তিনটি ফেজ ১০ অনিশ্চয়তা সংকুচিত হয়েছে: OSD-346-এর গ্র্যাভিটি সংকেত আসলে ফ্লাইট-রানের,
গ্র্যাভিটির নয়; OSD-782-এর ডোজ ৩৬টি লাইব্রেরিতে পুনরুদ্ধারযোগ্য নয়; এবং মাইক্রোবিয়াল
ফ্লাইট-প্রভাব দুটি ক্যাম্পেইনেই টিকে আছে, কিন্তু **নতুন ক্যাম্পেইনের জন্য পূর্বাভাস
ব্যবধান [−0.377, +6.018] শূন্যকে অন্তর্ভুক্ত করে** — তাই কোনো নির্দিষ্ট নতুন ক্যাম্পেইনের
নিশ্চিত পূর্বাভাস দেওয়া হয়নি।

আউট-অফ-ডিস্ট্রিবিউশন স্কোর তার নিজের নিয়ন্ত্রণেই ব্যর্থ হয়েছে, তাই কোনো থ্রেশহোল্ড
ঘোষণা করা হয়নি। ব্যাখ্যাগুলো শীর্ষে একমত, কিন্তু কোনো একটি জিন এককভাবে সিদ্ধান্ত নেয় না।

সব গেট পাস: ২৯১টি ব্যাকএন্ড টেস্ট, ৪০/৪০ রেজিস্ট্রি চেক, ২৭টি এন্ড-টু-এন্ড টেস্ট, এবং
ফ্রন্টএন্ডে কোনো পরিবর্তন নেই। **কোথাও ডিপ্লয় করা হয়নি।**
