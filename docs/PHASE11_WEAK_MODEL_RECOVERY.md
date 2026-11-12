# Phase 11 — weak model recovery

Two models were weak enough to be worth attacking: the excluded dose classifier
(`radiation-dose-osd782-v1`) and the harvest model (`mizuna-harvest-v1`). One turned out to
be recoverable in principle but empty in practice; the other is blocked by data and now
provably so.

Evidence: `ml/evaluation/phase11_dose_generalization`,
`ml/evaluation/phase11_dataset_discovery`.

```
python ml/training/phase11_dose_generalization.py    # ~75 s
```

---

## 1. The dose model: what Phase 10 left open

Phase 9 excluded `radiation-dose-osd782-v1` at balanced accuracy 0.361, p 0.2475. Phase 10
corrected the *reason*: the labels are valid — OSD-782 is a full factorial
3 doses × 4 timepoints × 3 replicates design with an explicit `absorbedDoseGy` column — and
the batch confound is not in the labels, it is in the design. Phase 10 then measured the
model honestly:

| Phase 10 protocol | Score |
| --- | --- |
| leave-one-(dose, timepoint)-cell-out, 3-class | 0.1111 |
| leave-one-timepoint-out, 3-class | 0.6111 |
| leave-one-timepoint-out, ordinal ρ | 0.1965 |
| per-timepoint ρ | 1 h 0.264 · 3 h −0.053 · 24 h 0.632 · 72 h 0.685 |

The unresolved question: **is that a dose signal partly masked by timepoint, or a timepoint
signal that a balanced design let the dose label ride along on?**

---

## 2. The design allows the confound to be removed, not modelled

Dose is perfectly crossed with timepoint (3 doses in every one of 4 timepoints). Each
timepoint is therefore centred by its own mean, which deletes every between-timepoint
difference gene by gene while leaving the within-timepoint dose contrast untouched. What
remains cannot be time.

### P1 — within-timepoint dose ranking

Model trained on the other three timepoints, then Spearman computed *inside* the held-out
timepoint over its 9 samples. Mean across the four timepoints:

| Timepoint | ρ (within timepoint) | predicted mean, 0 / 10 / 100 Gy |
| --- | --- | --- |
| 1 h | **+0.8433** | 15.3 / 28.5 / 66.2 |
| 3 h | **−0.6852** | 68.6 / 19.1 / 22.2 |
| 24 h | +0.1054 | 35.4 / 37.0 / 37.6 |
| 72 h | +0.6325 | 20.2 / 42.7 / 47.1 |
| **mean** | **+0.2240** | — |

Permutation null (dose shuffled within timepoint, 2000 draws): median −0.0131, 95 % range
[−0.422, 0.422], **p = 0.158**. Not significant.

The mean is the wrong thing to stare at. **The sign reverses between timepoints**: 1 h and
72 h order dose correctly, 3 h inverts it, 24 h is flat. A single dose axis that operates
within a timepoint would not change direction at 3 hours. Phase 10 saw the same
heterogeneity (0.264 / −0.053 / 0.632 / 0.685) and could not explain it; P1 shows it is not
an artefact of the global framing, because it survives when each timepoint is scored alone.

### P2 — does an unseen dose level behave as an ordered state?

Train a boundary through the 0 and 100 Gy anchors, then ask where the middle level lands:

| Anchor median, 0 Gy | Anchor median, 100 Gy | Middle-level (10 Gy) median |
| --- | --- | --- |
| 0.081 | 99.574 | **84.786** |

The anchors order correctly, so the fit is sane — and the 10 Gy samples land at 84.8 Gy,
almost on top of the 100 Gy anchor. Only **75 %** fall strictly between the anchors, against
a permutation null whose median is **1.000** (p = 0.999).

Two things follow, and both matter:

- **The test has no discriminating power.** Under shuffling the anchors are so far apart that
  almost any sample lands between them, so a null at the ceiling cannot certify anything. It
  is reported as a weak, non-informative check rather than dropped.
- **What it does show is directional**: the middle dose looks like the top dose. Three dose
  levels do not sit on one axis in this data; 10 Gy and 100 Gy are closer to each other than
  either is to 0 Gy, in expression space, which is what the 3 h inversion in P1 says too.

---

## 3. Three protocols rejected while building this, kept on the record

All three would have produced a publishable-looking number and all three were wrong. They
are in `rejectedExperiments` in the artifact.

| Protocol | What it returned | Why it is not evidence |
| --- | --- | --- |
| 3-class classification, leave-one-dose-level-out | balanced accuracy **0.0000** on every fold | A classifier trained on two levels cannot emit the third, so 0.000 measures the protocol, not the data |
| AUC between an unseen level and its nearest training level | AUC 0.0903 / 0.0000 / 1.0000, null centred at **0.3403** | every split reused a training level as the reference class, fixing the AUC by construction; a null off 0.5 is the tell that it is not a permutation test |
| leave-one-dose-level-out ridge, scored by ρ | observed −0.5371, null centred at **−0.7434** | extrapolating from two anchors puts the held-out level thousands of Gy away; a null that is not centred on zero cannot support a claim in either direction |

The 0.0000 row is the one worth keeping. It reads like a damning result about the data and
is purely a category error. Every later protocol in this document is checked for a null
centred on its chance value *before* its p-value is read.

---

## 4. Verdict on the dose model

**`dose-is-not-recoverable-at-this-sample-size`.**

| Item | Result |
| --- | --- |
| Timepoint confound removed rather than modelled | Completed |
| Within-timepoint ranking positive | No — mean ρ 0.224, p 0.158, and the sign flips at 3 h |
| Unseen-dose behaviour consistent with one ordered axis | No — 10 Gy sits at 84.8 Gy |
| Registry status | **Unchanged**: `radiation-dose-osd782-v1` stays excluded |

The exclusion is now supported by a specific mechanism rather than a low score: **the dose
labels are valid, and the expression response to 10 Gy and 100 Gy is not separable in the
way a dose axis would require.** Phase 10's concern was that the model was weak for
procedural reasons; Phase 11 shows it is weak for biological reasons, at 36 libraries.

---

## 5. The harvest model: blocked by data, now provably

`mizuna-harvest-v1` fails at R² −0.138 with 14 endpoints in a single experiment, and Phase 10
refused synthetic augmentation and stopped hyper-parameter search. Phase 11's job was to ask
whether a *different* NASA dataset could supply the missing rows.

The 231-study sweep answered it: **zero** studies in the corpus carry harvest or biomass
measurements paired with an environmental gradient for a leafy crop. Not few — zero,
across every study with a usable processed matrix. Details in
`PHASE11_NASA_DATA_DISCOVERY.md`.

| Item | Classification |
| --- | --- |
| Hyper-parameter search on 14 points | **Rejected by scientific evaluation** (Phase 10, not repeated) |
| Synthetic training rows | **Rejected by scientific evaluation** — would manufacture the evidence |
| Additional real harvest measurements from OSDR | **Blocked by data** — none exist |
| Registry status | **Unchanged**; the model keeps its failure documented rather than hidden |

This is a closed question. Any future attempt to improve mizuna harvest by adding OSDR rows
can be rejected by pointing at the sweep.
