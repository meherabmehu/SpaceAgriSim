# Phase 11 — the gravity replication disagreement, resolved

Phase 10 left a hard contradiction. OSD-314 separated microgravity from 0.34 g at
balanced accuracy **1.000**; OSD-346, the independent replication, did not (0.500), yet
reported a statistically clear **graded** signal (ρ 0.571, p 0.0015) that Phase 10 could
not explain.

Phase 10 also stated that neither deposit carries a sequencing-run identifier.

**That statement was wrong for OSD-346**, and correcting it resolves the contradiction.

Evidence: `ml/evaluation/phase11_gravity_batch.json`,
`ml/training/phase11_gravity_batch.py`.

---

## The metadata Phase 10 missed

OSD-346's ISA sample table has a `Comment[Run]` column and a harvest date. Reading them:

| Flight run | Harvest date | Gravity levels in that run |
| --- | --- | --- |
| SG1 Run 1 | 2013-03-29 | 0 g only |
| SG1 Run 2 | 2013-05-09 | 0.08 – 0.13 g |
| SG1 Run 3 | 2013-05-18 | 0.25 – 0.39 g |
| SG1 Run 4 | 2013-05-24 | 0.64 – 1.00 g |
| SG2 Run 1 | 2014-11-14 | 0.38 – 0.65 g |
| SG2 Run 2 | 2014-11-21 | 0.68 – 0.92 g |

**Each flight run carried one gravity band.** Gravity is nested inside run, and run is
nested inside mission-year (2013 vs 2014). A model that recovers 0 → 1 g across the whole
series is simultaneously recovering flight run, sequencing batch, and year.

OSD-314, by contrast, has **100 metadata columns and not one of them is a run, batch, lane
or date**. Its 1.000 can be neither attributed to biology nor cleared of batch — the
structure is simply unrecorded.

---

## Four measurements

Protocols were fixed before the run.

### B1 — how confounded is gravity with run?

| Quantity | Value |
| --- | --- |
| Flight runs | 6 |
| Commanded levels appearing in more than one run | **0 of 9** |
| Full gravity range | 1.05 g |
| Mean within-run gravity range | **0.192 g (18 % of the full range)** |
| PC1 variance explained by run | **0.30** |

### B2 — how strong is the batch effect?

Can expression alone identify the flight run? Folds are genotype × light treatment, so
the classifier cannot use genotype or light as a shortcut to the run.

**Out-of-sample run accuracy: 0.694 (balanced 0.694)** over 6 classes. Runs are strongly
separable in expression, so any label nested inside run is predictable from the batch
effect alone.

### B3 — does the gravity signal survive run removal?

| View | Spearman | Design-appropriate null | p |
| --- | --- | --- | --- |
| Raw features, within-run permutation | 0.752 | [0.689, 0.774] | **0.196** |
| Run-centred features | −0.798 | [−0.823, −0.724] | 0.820 |
| Between-run component (run means, n = 6) | **0.829** | — | 0.042 |
| Within-run component (deviations) | 0.229 | [−0.335, 0.355] | 0.110 |

Read the first row carefully. The observed correlation of 0.752 falls **inside** the null
distribution, because shuffling gravity *within* a run barely moves anything — every
library in a run is already at nearly the same g. That null is informative here (60 % of
labels change per permutation, null SD 0.022), so the p-value is trustworthy. The raw
correlation is exactly what the run structure alone produces.

The signal lives in the **between-run** component (ρ 0.829 across 6 run means, p 0.042)
and is absent **within** runs (ρ 0.229, p 0.110, with a null SD of 0.176 — this test had
power).

### B4 — is the wide-range question answerable at all?

Removing run variation leaves 18 % of the gravity range. **Not identifiable.** The
wide-range graded signal and the flight run are the same variable.

---

## The correction to Phase 10

Phase 10's P2 permuted gravity within **light treatment**. Every light treatment spans all
six runs, so that null mixes gravity across runs, destroys the nesting, and centres on
zero — making a correlation measured across runs look overwhelming.

| | Spearman | p |
| --- | --- | --- |
| Phase 10, null within light treatment | 0.571 | **0.0015** |
| Phase 11, null within flight run | 0.752 | **0.196** |

The number was not wrong. **The null it was compared against was.** No served claim
depended on it: Phase 10's headline was already the negative P1 result, and nothing was
promoted.

---

## What this does and does not establish

**Does:**

- OSD-346's graded "gravity" signal is statistically indistinguishable from its flight-run
  structure.
- The wide-range gravity question cannot be answered from OSD-346, because gravity and run
  are the same factor.
- OSD-314's 1.000 remains unexplained and unattributable, because it records no batch
  structure.

**Does not:**

- Say gravity has no effect on the plant transcriptome. The within-run estimate is
  ρ 0.229 (p 0.110) on 36 libraries — a weak positive trend, not a null.
- Say OSD-314's result was a batch artefact. There is no batch field to check.
- Rehabilitate Phase 10's graded signal.
- Support any Moon or Mars growth prediction. Nothing here is a crop-growth measurement,
  and no model is served.

---

## Researcher request (prepared, NOT sent)

OSD-346 needs no request: its ISA table already carries the run identifier, and this
analysis used it.

OSD-314 does. Its archive records no run, batch, lane or harvest date, so its 1.000 cannot
be attributed to biology or to processing. What would settle it:

> For OSD-314 / GLDS-314, please provide the sequencing run identifiers
> (flowcell/lane or GEO/SRA SRR accessions) and library preparation batch identifiers for
> the 17 libraries, together with the harvest date of each sample.

**This request has not been sent and no reply is claimed.** It is recorded so it can be
sent, and so nobody assumes it was answered.

---

## Status

| Item | Classification |
| --- | --- |
| Run identifiers recovered for OSD-346 | **Completed** (from the ISA table) |
| Confound quantified | **Completed** |
| Phase 10 P2 corrected | **Completed** |
| Batch effect measured | **Completed** |
| OSD-314 batch structure | **Blocked by data** (not recorded in the deposit) |
| Wide-range gravity model | **Rejected by scientific evaluation** (unidentifiable) |
| Registry change | **None** |
