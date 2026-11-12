# Phase 11 — microbial models

The microbial evidence rests on two VEG-04 campaigns. Phase 11 asked three questions:
does the headline effect survive a harder test, what can a *new* campaign expect, and is a
third campaign obtainable at all.

Evidence: `ml/evaluation/phase11_microbial_campaigns`,
`ml/evaluation/phase11_dataset_discovery`.

```
python ml/training/phase11_microbial_campaigns.py    # ~3 s
```

---

## 1. Start from the committed number, not a re-derived one

The Phase 7 headline is a flight-versus-ground contrast in culturable aerobic load on leaf
tissue: **+3.0626** log10 CFU/g in VEG-04A and **+2.6392** in VEG-04B. Both are reproduced
exactly before anything below is compared to them:

| Campaign | Phase 7 committed | Phase 11 reproduced | |
| --- | --- | --- | --- |
| VEG-04A | +3.0626 | **+3.0626** | reproduced |
| VEG-04B | +2.6392 | **+2.6392** | reproduced |

---

## 2. Two things Phase 7 did not check

Phase 7's numbers use aerobic leaf tissue only — 5 flight / 15 ground samples in A and
31 / 72 in B — while the table holds **292** quantified samples across four tissues and two
assays. That leaves two gaps:

**Composition.** VEG-04A sampled leaf, root, soil and wick. **VEG-04B sampled leaf only.**
A pooled contrast can move because the sampling mix moved. Ignoring this is how a
composition artefact gets reported as a biological replication.

**Dependence.** Samples cluster inside pillows (8–12 independent units per campaign). A
sample-level interval over 120 ground samples is roughly √(120/12) ≈ 3.2× too narrow, so
every interval here resamples whole units.

---

## 3. The effect is present in ten strata, and the intervals say so

Flight minus ground in every (campaign, tissue, assay) stratum, cluster bootstrap over
units:

| Stratum | Δ log10 CFU/g | n flight / ground | 95 % CI |
| --- | --- | --- | --- |
| VEG-04A leaf aerobic | **+3.06** | 5 / 15 | [+2.32, +3.83] |
| VEG-04A leaf yeast & mould | **+2.24** | 5 / 15 | [+1.34, +2.96] |
| VEG-04A root aerobic | −0.12 | 2 / 4 | [−0.28, +0.02] |
| VEG-04A root yeast & mould | **+0.76** | 4 / 4 | [+0.09, +1.42] |
| VEG-04A soil aerobic | +0.15 | 16 / 12 | [−0.18, +0.47] |
| VEG-04A soil yeast & mould | +0.40 | 12 / 12 | [−0.10, +0.89] |
| VEG-04A wick aerobic | +0.55 | 2 / 4 | [−0.05, +1.15] |
| VEG-04A wick yeast & mould | **+2.36** | 4 / 4 | [+1.65, +3.19] |
| VEG-04B leaf aerobic | **+2.64** | 31 / 72 | [+1.94, +3.25] |
| VEG-04B leaf yeast & mould | **+1.97** | 21 / 48 | [+1.59, +2.34] |

Two patterns matter, and neither is the pooled average.

**Every positive effect is positive in both campaigns, and both assays, on the tissue that
matters.** Leaf tissue gives +3.06 / +2.24 in A and +2.64 / +1.97 in B — four independent
estimates, all with cluster-bootstrap intervals excluding zero.

**The effect is tissue-specific, not general.** Soil shows +0.15 and +0.40 with intervals
spanning zero; root aerobic is essentially flat at −0.12. The flight signature is on
edible leaf, which is what the model predicts, and it does **not** extend to the growth
medium. That is a narrower claim than "flight increases microbial load" and a more useful
one.

`6 of 10` strata are positive with an interval excluding zero. The four that are not are
soil and root — small effects on non-edible tissue, not contradictions.

---

## 4. Composition does not explain the replication

Contrast recomputed with each campaign reweighted to the other's tissue/assay mix:

| Quantity | Value |
| --- | --- |
| VEG-04A raw, all tissues | +1.675 |
| VEG-04B raw, all tissues | +2.366 |
| VEG-04B at VEG-04A's mix | **+2.305** |
| VEG-04A at VEG-04B's mix | **+2.733** |

Note how the raw all-tissue numbers **invert the ranking** of the leaf-only numbers
(+1.675 vs +2.366, against +3.06 vs +2.64): VEG-04A's average is dragged down by its own
soil and root strata, which B never sampled. Anyone quoting an all-tissue mean without
stratifying would report that B has the larger effect, and would be reporting the sampling
mix.

After standardising, both campaigns remain in the same range (+2.31 and +2.73), so the
replication is not a composition artefact.

**Limitation, stated plainly:** VEG-04B contributes leaf tissue only, so standardising can
reach only the two shared leaf strata. The root, soil and wick strata cannot be compared
across campaigns **at all**. The conclusion is about the shared strata.

---

## 5. What a new campaign can expect — and it is not a point prediction

Random-effects pooling (DerSimonian–Laird) of the two campaign effects, with the cluster
bootstrap intervals converted to standard errors:

| Quantity | Value |
| --- | --- |
| Pooled effect | **+2.820** |
| 95 % CI on the pooled mean | [+2.327, +3.314] |
| τ² | 0.0000 |
| I² | **0.0 %** |
| Cochran Q | 0.629 |
| **95 % prediction interval for a new campaign** | **[−0.377, +6.018]** |

This is the single most decision-relevant number in the microbial work, and it is
deliberately unflattering.

The confidence interval [+2.33, +3.31] says the *average* effect is clear. The prediction
interval **includes zero**: a new campaign's contrast could plausibly be slightly negative.
With two campaigns τ² is weakly identified, and I² = 0 % with two studies mostly means two
studies cannot demonstrate heterogeneity — it does not mean heterogeneity is absent.

So the platform may say: *the direction of the effect has replicated twice and is likely
positive, but a specific new campaign is not guaranteed a positive contrast.* It may not
say a third campaign's load can be predicted.

---

## 6. The third campaign does not exist

The 231-study discovery sweep is the answer to "can another NASA dataset supply the third
campaign". Nine uncatalogued microbial candidates were found and **none is a crop-microbial
load campaign**:

| Candidate | What it actually is |
| --- | --- |
| OSD-385, OSD-386 | deliberate *E. coli* / *Salmonella* challenge on lettuce and mizuna — a contamination study, not an environmental load measurement |
| OSD-146, OSD-170, OSD-280 | mouse faecal, aircraft bioaerosol, astronaut salivary microbiomes — different host, different question |

**Blocked by data.** The microbial models stay at two campaigns, the prediction interval
stays wide, and no third-campaign validation is claimed. Full sweep in
`PHASE11_NASA_DATA_DISCOVERY.md`.

---

## 7. Registry status

The microbial models are **not re-promoted** and **not re-scoped** by this work. What
changed is the evidence around them, not the models:

| Item | Status |
| --- | --- |
| Phase 7 headline contrast reproduced | **Completed** (exact) |
| Stratum-wise contrasts with cluster intervals | **Completed** |
| Composition standardisation | **Completed**, with the shared-strata limitation recorded |
| Random-effects pooled effect and prediction interval | **Completed** |
| Third campaign | **Blocked by data** |
| Absolute-load prediction for a new campaign | **Rejected by scientific evaluation** — the campaign offset is not a function of any available feature |
| Registry change | **None** — 8 models unchanged |

The absolute-load claim stays refused for the reason Phase 7 established: the campaign
offset (~1.6 log between A and B) is a property of handling, sampling and baseline
contamination, and must come from that campaign's own baseline samples.
