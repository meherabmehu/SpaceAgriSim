# Phase 10 — Work Report

**Repo:** `github.com/meherabmehu/SpaceAgriSim`
**Branch history:** `feat/phase10-advanced-nasa-ai`, `feat/phase10-osd346-replication`
**Merged into `main` at:** `0257473` (verified on the remote, not just locally)
**Scope of this report:** everything committed from `b1946b9` (Phase 9 tip) to `0257473`

---

## সারসংক্ষেপ (বাংলা)

এই ফেজে আমরা মডেলের সংখ্যা বাড়াইনি — আটটাই আছে। যা করেছি তা হলো, প্ল্যাটফর্মটি যে দাবিগুলো করছিল, সেগুলো মেপে যাচাই করা। চার জায়গায় মাপা ফল আর লেখা কথা মিলল না, এবং সেগুলো ঠিক করা হয়েছে:

1. **ইন্টারভ্যাল** — ৯০% দাবি করেও আসলে ৮১–৮৫% কভার করছিল। এখন গ্রুপ-লেভেল কনফর্মাল দিয়ে ৯৯.২%, লেটুসে CV+ দিয়ে ৯৩.৯–৯৬.১%।
2. **ব্যাখ্যা (XAI)** — রেডিয়েশন মডেল দুটির জন্য হুবহু (exact) ব্যাখ্যা যোগ হয়েছে; এটি দেখায় কোনও একটি জিন এককভাবে সিদ্ধান্ত নির্ধারণ করে না (সর্বোচ্চ ০.০০৩৭), তাই এগুলো "বায়োমার্কার" নয়।
3. **দুর্বল মডেল** — মিজুনা হারভেস্টের ১৪টি সারিতে কোনও মডেলই সম্ভব নয় (সর্বোচ্চ R² −০.১০৬, মানে গড়ের চেয়েও খারাপ)। লেটুস v3 ও tomato-র নতুন ভার্সন বানানো হয়নি।
4. **ক্রস-স্টাডি ট্রান্সফার** — চারটি harmonisation-ই ব্যর্থ; তবে টার্গেট স্টাডির নিজের signal আছে (timepoint ধরে রাখলে ০.৮১২), শুধু নতুন cell-এ টেকে না।

তারপর দুটি নতুন NASA ডেটাসেট যোগ হয়েছে (OSD-314, OSD-346)। OSD-314-এ ০ g বনাম ০.৩৪ g পার্থক্য ১.০০০ balanced accuracy দিয়েছিল — চমকপ্রদ। কিন্তু OSD-346-এ সেটি **পুনরুৎপাদন হয়নি**। এটি নিজের সবচেয়ে চমকপ্রদ ফলকেই নিজে পরীক্ষা করে ব্যর্থ ঘোষণা করা — এবং সেটাই এখানে সবচেয়ে মূল্যবান ফল।

**কোনও মডেল পরিবর্তন করা হয়নি, কিছুই ডিপ্লয় করা হয়নি।**

---

## 1. What was asked and what was delivered

Phase 10 asked for model improvement, dose/gravity recovery, cross-study validation, XAI, uncertainty calibration, dataset expansion, a registry/API pass, and documentation. All of it is delivered, and **three of the required investigations ended in a negative result that is now documented rather than hidden**.

| # | Track | Outcome |
| --- | --- | --- |
| 1 | Interval calibration (uncertainty) | 4 models recalibrated, 2 from a broken 81–85 % to 99.2 % |
| 2 | Explainable AI | Exact attributions for both radiation classifiers, identity residual ≤ 8.9e-16 |
| 3 | Weak-model audit | 3 models audited, 0 promoted, 1 proven impossible |
| 4 | Cross-study validation | 4 harmonisations rejected; scope of the negative corrected twice |
| 5 | Dose recovery | Exclusion **stands**, but its stated reason was wrong and is fixed |
| 6 | Gravity recovery | Real partial-gravity studies found and analysed |
| 7 | Dataset expansion | 17 → 19 NASA datasets |
| 8 | Registry/API pass | 8 models, 0 findings, 40/40 integrity checks |
| 9 | Documentation | 11 Phase 10 documents |
| 10 | Competition demo | One command, full audit trail in ~6 s |

**17 commits.** Registry: **8 models, unchanged.** Nothing deployed.

---

## 2. Intervals said 90 % and delivered 85 %

Phase 9 shipped intervals that admitted `empiricallyCalibrated: false` with coverage 0.811 and 0.849. That honesty was right and the defect was real.

| Model | Phase 9 measured | Adopted method | Phase 10 measured |
| --- | --- | --- | --- |
| `mizuna-microbial-relative-load-v2` | 0.849 | group-level conformal | **0.992** |
| `mizuna-microbial-load-v1` | 0.811 | group-level conformal | **0.992** |
| `lettuce-earth-growth-v1` | untested | CV+ | **0.939** |
| `lettuce-earth-growth-v2` | untested | CV+ | **0.961** |

The scientific finding: **every row-level method stalled between 0.862 and 0.886** no matter how the quantile was built. That is a broken exchangeability assumption, not bad arithmetic — rows are tissues inside a pillow, so a row-level interval answered a question nobody asks. Switching the unit to the biological group fixed it, at a published cost in width (3.40 vs 2.44 SD).

Also found and fixed: the study was **not deterministic** — identical inputs gave 0.878 and 0.886 — because `RandomForestRegressor(n_jobs=-1)` sums split gains in a completion-dependent order. `n_jobs=1` is now pinned and a test re-runs a slice to prove stability.

---

## 3. The explanations are exact, and they say the genes are not biomarkers

Both radiation classifiers are linear-softmax evaluators, so attribution needs no surrogate: the per-gene contributions **reconstruct the served logits** to 8.9e-16 (quality) and 0.0 (exposure). SHAP was deliberately not used.

Two results matter more than any top-gene list:

- **No single gene is necessary.** Permutation importance refit inside each held-out fold: the largest drop from removing any one of the 150 deployed genes is **0.0037** balanced accuracy (quality, baseline 0.958) and **0.0000** (exposure, baseline 0.986). The signal is distributed — these are a *signature, not biomarkers*.
- **Selection is unstable at the edges.** 75 of 150 (quality) and 95 of 150 (exposure) genes are chosen in all 22 leave-one-group-out folds; **6** and **9** are chosen in fewer than half.

Models with no valid explanation method return **404**, not a mimic's guess.

Three bugs were caught by testing, not review: an all-zero class-0 coefficient row that would have read "control contributes nothing"; in-sample permutation importance reporting a meaningless 1.000; and a binary model scored against 3-class labels giving an impossible 0.333.

---

## 4. The weak models are evidence-limited, not method-limited

| Model | Mean baseline | Shipped | Best attempt | Verdict |
| --- | --- | --- | --- | --- |
| `mizuna-harvest-v1` (14 rows, 10 groups, 1 experiment) | R² −0.138 | — | RF R² **−0.106** | **no model possible** |
| `lettuce-earth-growth-v2` (1,648 rows, 4 experiments) | R² −0.054 | **0.870 / 34.92 MAE** | 0.868 / 35.33 | **no v3** |
| `tomato-flight-response-v1` (36 samples, 21 plants) | — | 0.917 acc | none run | no search |

The trap avoided in the first row: random forest beats the mean baseline by 0.03 R² *while still being worse than the mean*. The bar was fixed at **R² > 0 before the run**. No synthetic augmentation was used anywhere, and every registry status byte is identical to Phase 9 (asserted by test).

---

## 5. Cross-study: the negative was over-attributed, twice

Four label-free harmonisations (z-score, rank, quantile-map, training-only pathway modules) all collapse to the majority class: **balanced accuracy 0.500, control recall 0.00**.

What the negative *means* depended on which within-study reference you measure:

| Within-OSD-782 reference | Balanced accuracy | Interval / p |
| --- | --- | --- |
| hold out (dose, timepoint) cells | 0.438 | [0.300, 0.591] |
| hold out whole timepoints | **0.812** | p = 0.001 |

Phase 9 implied harmonisation was the obstacle. The first Phase 10 reading said the target had no signal at all. **Both were single-protocol conclusions.** The target does carry a learnable contrast; it does not survive an unseen (dose, timepoint) cell, and that is the condition a cross-study transfer actually faces. So the transfer negative stands and harmonisation stays implicated — but is *not proven* to be the cause, because it cannot be separated from the target's cell-level batch structure.

---

## 6. Dose and gravity: both exclusions stand, both explanations were wrong

### Dose

The `absorbedDoseGy` label is **valid** — 0 / 10 / 100 Gy, full factorial against four timepoints. Phase 9 called it unusable. The real confound is narrower: each (dose, timepoint) cell is one sequencing batch.

| Protocol on the same 36 libraries | Balanced accuracy | p |
| --- | --- | --- |
| hold out one (dose, timepoint) cell | **0.111** (worse than chance) | — |
| hold out one whole timepoint | **0.611** | 0.0005 |
| hold out one whole timepoint, ordinal | ρ = 0.197, monotone | 0.0155 |

The split was deciding the answer. Below-chance is the signature of a fold measuring batch membership. Nothing is promoted — 36 libraries in one genotype cannot support a dose predictor — so the exclusion stands on better evidence than before.

### Gravity

The claim that no partial-gravity plant study with processed expression existed came from inspecting **one** deposit. Fetching the ISA metadata of **all 231** studies with a usable processed matrix found **two** graded-gravity plant experiments. Both are now catalogued.

**OSD-314** (Arabidopsis on ISS, subset centrifuged to **0.34 g in orbit**, 17 libraries): the within-flight 0 g vs 0.34 g contrast reaches balanced accuracy **1.000** (p = 0.0055), corroborated by the deposit's own **8,478–13,504** differentially expressed genes.

**OSD-346** (phytochrome mutants, blue light, six commanded levels 0–1 g, 36 libraries, *every library a flight sample*): the independent test.

| Analysis | Result |
| --- | --- |
| 0 g vs 0.25–0.38 g, held-out light treatment | **0.500**, collapsed, permutation null degenerate |
| 0 g vs all partial 0.1–0.38 g | 0.450, p = 1.00 (null *not* degenerate) |
| 0 g vs 0.1 g | 0.875, p = 0.085 (8 libraries) |
| graded ridge on realised g, 0–1 g | **ρ = 0.571, p = 0.0015**, not monotone, MAE 0.21 g |
| rank separation per level | significant at 0.64/0.65 g only |
| phyA-trained classifier on phyB | 0.667 |

**The OSD-314 headline does not replicate.** A graded signal is real and statistically clear, but it emerges at **0.6 g and above**; the sharp microgravity-vs-0.34 g distinction is absent in every framing tried. Genotype, light spectrum and batch structure remain indistinguishable on 36 libraries — and batch is the worrying one, since neither deposit carries a sequencing-run identifier.

### One methodological catch worth keeping

A classifier that collapses to a single class makes the permutation null a **point mass**, so the resulting p = 1.0 means *"no power"*, not *"no effect"*. The helper now detects a degenerate null and labels it, and a power note sits beside the collapsed result. That was a live trap in the first version of this analysis.

---

## 7. Registry and API: prove it, don't assert it

`ml/training/phase10_registry_api_audit.py` does not trust the registry. Per model it checks: artifact exists and its SHA-256 matches, every claimed metric equals the artifact's, no excluded candidate is served, no stated coverage falls short, no explanation is inexact, no model cites an uncatalogued study, and the API serves exactly the registry.

**Result: 8 models, 0 findings, 40/40 integrity checks.**

It found two real gaps, both fixed and both *understating* what exists: the radiation artifacts never advertised the explanation capability they had, and `verify_model_registry.py` had been counting explanation files as orphan models.

---

## 8. Verification evidence (run on merged `main`)

| Gate | Result |
| --- | --- |
| Backend suite | **291 passed** (including the live PostgreSQL round-trip) |
| Playwright, 3 viewports | **27 passed**; 54/54 with `--repeat-each=2` |
| Visual regression | **9/9 baselines** (mission 0.003–0.005 %, radiation 0.000 %) |
| ESLint / `tsc --noEmit` / production build | clean / clean / ✓ |
| Registry integrity | **40/40** |
| Registry-vs-artifact audit | **0 findings** |
| Demo script | runs the whole phase end to end in **~6 s** |

**UI preservation.** The only visual addition is the explanation block, appended at the very end of the radiation card. Measured, not assumed: width identical on all three viewports, height +82 px (desktop/tablet) and +215 px (mobile), and the region above the new block differs by **0.16 %** of pixels (antialiasing plus a scrollbar strip on a taller page). An earlier mid-card placement moved 4.5–7 % of pixels above it and was rejected.

---

## 9. What is deliberately *not* claimed

- No model was added, removed, or had its status changed. Registry: 8 models.
- No dose, gravity, lunar or Mars prediction is served.
- No gene is called a biomarker (max single-gene effect 0.0037).
- No yield inferred from expression; no sequencing abundance converted to CFU counts.
- No synthetic augmentation; no training example was manufactured.
- Coverage figures are measured on 35 pillows / 4 experiments, not guarantees.
- Nothing was deployed to Render or any production environment.
- Local test results are **not** presented as production verification.

---

## 10. Honest status line

The strongest single number this phase produced — balanced accuracy 1.000 for microgravity versus 0.34 g — was produced by me, then tested by me in a second mission, and it **failed**. The repository now says so in four documents, in the demo output, and in the artifact's own `nextAction` field, with a test asserting the wording so it cannot be quietly dropped.

That is the correct outcome for a research codebase. A result that survives one independent test is a finding; one that does not is a cautionary example, and the honest place to discover that is inside the project rather than in someone else's review.

---

## 11. Where to look

| Document | Contents |
| --- | --- |
| `docs/PHASE10_FINAL_REPORT.md` | The main technical report, 8 sections |
| `docs/PHASE10_UNCERTAINTY.md` | Interval calibration |
| `docs/PHASE10_EXPLAINABLE_AI.md` | Exact attributions and stability |
| `docs/PHASE10_WEAK_MODEL_AUDIT.md` | Why each weak model is weak |
| `docs/PHASE10_CROSS_STUDY_VALIDATION.md` | Transfer, with both protocols |
| `docs/PHASE10_DOSE_GRAVITY_RECOVERY.md` | Dose and gravity, including the failed replication |
| `docs/PHASE10_NASA_DATASET_EXPANSION.md` | The 231-study scan |
| `docs/PHASE10_MODEL_IMPROVEMENTS.md` | Adopted vs rejected, with numbers |
| `docs/PHASE10_REGISTRY_API.md` | The audit |
| `docs/PHASE10_COMPETITION_DEMO.md` | The 5-minute demo |
| `docs/PHASE10_BASELINE.md` | Starting state, measured |

Every claim above traces to a JSON artifact under `ml/evaluation/` and a script under
`ml/training/`. To reproduce:

```bash
./scripts/demo_phase9.sh --fast          # whole audit trail, ~6 s
python ml/training/phase10_registry_api_audit.py
python ml/training/phase10_partial_gravity_osd346.py
```

---

## 12. Recommended next steps

1. **Explain why OSD-314 and OSD-346 disagree.** Candidates: genotype (wild type vs phytochrome mutants), light spectrum (red/dark vs blue), or batch structure. Only a third mission with wild-type plants and a sequencing-run identifier can separate them.
2. **Request sequencing-run identifiers** from both missions — the batch question is one email, not one analysis.
3. **Find a transfer target whose own contrast survives an unseen cell.** Every conclusion about harmonisation stays blocked until then.
4. **Get a third microbial campaign** — the only thing that turns a two-campaign calibration into a predictive interval.
5. **Stop re-tuning `mizuna-harvest-v1`.** It has 14 rows and one experiment. Collect harvests, not hyperparameters.
