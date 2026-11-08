# Phase 11 — NASA dataset discovery

A targeted search of all **231** OSDR studies that hold a usable processed matrix, scored
against the four questions Phase 11 actually needs answered rather than against "is there
another dataset".

Evidence: `ml/evaluation/phase11_dataset_discovery.json`,
`ml/evaluation/phase11_duplicate_audit.json`.

## What was searched, and for what

| Question | Vocabulary | Candidates | Not yet catalogued |
| --- | --- | --- | --- |
| Third independent **microbial** campaign | CFU, colony-forming, aerobic, yeast & mould, microbiome, bacterial load/community | 11 | 9 |
| **Harvest / biomass** paired with environment | fresh mass, dry mass, biomass, harvest index, yield, edible mass, plant height, leaf area | **0** | 0 |
| Another plant **radiation** study with a dose label | gamma, ionizing, HZE, absorbed dose, Gy, Cs-137, proton | 13 | 11 |
| Another **crop growth** study | Lactuca, lettuce, Brassica, mizuna, VEG-0x, hydroponic, photosynthetic | 5 | 3 |

231 of 231 metadata payloads were retrieved; none was unavailable. Patterns were
deliberately generous — missing a study is the expensive error.

---

## The headline result: the "independent" radiation study is a duplicate

**OSD-320**, *"Gamma radiation and HZE treatment of seedlings in Arabidopsis"*, looked like
the discovery that would unblock the Phase 10 deadlock. It has:

- the **same Affymetrix platform** as OSD-46, so harmonisation would be trivial;
- the **same two genotypes** (wild type, atm-1);
- the **same two radiation types** (Cs-137 gamma, Fe-56 HZE);
- the **same five post-treatment timepoints**;
- an explicit `Parameter Value[absorbed radiation dose]` column.

It is not an independent study. **Its 44 samples are the same arrays as OSD-46**, deposited
under a second accession. The values are identical to the last bit:

| Check | Result |
| --- | --- |
| Arrays compared | 44 of 44 |
| Probesets compared | 22,810 |
| Minimum correlation | **1.000000** |
| Maximum absolute difference | **0.0** |

A pipeline that had accepted OSD-320 as a validation study would have reported a
cross-study "replication" at perfect accuracy from a study compared **against itself**.
That is the single most dangerous failure this catalogue could have produced, and the
Phase 9 sweep could not see it because it classified studies individually.

### Why the duplicate is hard to see

The two deposits write the same array three different ways:

| Where | OSD-46 | OSD-320 |
| --- | --- | --- |
| ISA `Sample Name` | `GSM1506014 1` (space) | `GSM1506014` |
| ISA `Source Name` | `GSM1506014` | `seedling,1.5h_after_Gamma,WT rep1` |
| Expression matrix column | `GSM1506014_1` | `GSM1506014` |

A name-based check that reads one column, or that strips only underscore suffixes, reports
**zero overlap** for a pair of identical studies. The first version of this audit did
exactly that. The fix keys on the accession token and reads both name columns, and only
then does the pair collide at 44 of 44.

---

## Consequence: cross-study radiation validation is still blocked

Phase 10's open item was *"find a transfer target whose own contrast survives an unseen
cell"*. OSD-320 was the best candidate in the corpus and it is not independent. The other
radiation candidates are genuinely separate deposits but are DNA-damage-response mutants:

| Study | Samples | What it is | Why not a transfer target |
| --- | --- | --- | --- |
| OSD-498 | 16 | SOG1 / MYB3R DNA-damage response | different biology (repair pathway mutants), no matching dose series |
| OSD-502 | 8 | as above | too few libraries |
| OSD-508 | 36 | as above | different biology |

**Radiation cross-study transfer therefore remains blocked by data, not by method.**

---

## Other overlaps found, and why they are not duplicates

| Pair | Shared samples | Classification |
| --- | --- | --- |
| OSD-320 ~ OSD-46 | 44 (100 %) | **duplicate measurement** — identical values, proven |
| OSD-267 ~ OSD-269 | 9 (69 %) | shared biological sample, needs numeric check |
| OSD-268 ~ OSD-269 | 9 (64 %) | shared biological sample, needs numeric check |
| OSD-655 ~ OSD-780 | 45 (61 %) | **shared biological sample, distinct assay** |

The last row matters for the microbial question. OSD-655 holds element/phenolic chemistry
from VEG-04 plants; OSD-780 holds plate counts from the same plants. Sharing samples is
legitimate and expected — one experiment, several assays, several accessions. It is *not*
the same as duplicate data, and conflating the two would either hide a real duplicate or
wrongly discard a real study.

The audit now classifies each overlap as `duplicate-measurement`,
`shared-biological-sample-distinct-assay`, or `shared-sample-needs-numeric-check`, so the
distinction is made per pair rather than assumed.

---

## The four questions, answered

### Third microbial campaign — **not found**

Nine uncatalogued candidates, and none is a NASA crop-microbial load campaign comparable
to VEG-04A/B:

- OSD-385 and OSD-386 are *E. coli* / *Salmonella* food-safety challenge studies on
  lettuce and mizuna — a deliberate contamination experiment, not an environmental
  microbial load measurement.
- OSD-146, OSD-170 and OSD-280 are mouse faecal, aircraft bioaerosol and astronaut salivary
  microbiomes — different host, different question.

**The microbial models stay limited to two campaigns.** Their intervals cannot become
predictive for a third campaign, and no such claim is made.

### Harvest / biomass — **not found, exactly as expected**

**Zero** plant studies in the 231 matched the harvest vocabulary. This is the strongest
possible confirmation of Phase 10's conclusion that `mizuna-harvest-v1` cannot be rescued:
there is no additional genuine harvest measurement anywhere in the corpus, let alone one
with a compatible design. Hyperparameter search remains the wrong response, and Phase 10
already stopped it.

### Radiation — **candidates found, all unsuitable**

Thirteen candidates; OSD-320 excluded as a duplicate, the SOG1/MYB3R series excluded as
different biology with too few libraries. No new transfer target.

### Crop growth — **nothing usable**

OSD-385/386 are contamination studies; OSD-522 is Arabidopsis proteomics. No new
environment → mass rows for lettuce.

---

## Ten-point check applied to the one serious candidate

| # | Check | OSD-320 |
| --- | --- | --- |
| 1 | Official accession verified | Yes, OSD-320 v4 |
| 2 | Organism | *Arabidopsis thaliana*, WT and atm-1 |
| 3 | Treatment | Cs-137 gamma and Fe-56 HZE, five timepoints |
| 4 | Independent biological units | 22 groups |
| 5 | Labels and units | `absorbed radiation dose`, Gy |
| 6 | Processed data available | Yes, 23.8 MB probeset matrix |
| 7 | Metadata completeness | Good — dose, dose rate, energy, device |
| 8 | Batch / mission effects | Not recorded |
| 9 | File integrity | Pinned by SHA-256 |
| 10 | Independent validation possible? | **No — same arrays as OSD-46** |

Checks 1–9 all pass. Check 10 fails, and it is the only one that matters.

---

## Status

| Item | Classification |
| --- | --- |
| 231-study targeted scan | **Completed** |
| Duplicate detector built and applied to 25 studies | **Completed** |
| OSD-320 duplicate proven numerically | **Completed** |
| Third microbial campaign | **Blocked by data** (none exists in the corpus) |
| Additional harvest measurements | **Blocked by data** (zero candidates) |
| Radiation transfer target | **Blocked by data** (only candidate is a duplicate) |
| New datasets added to catalogue | **None** — nothing passed the ten-point check |
| Registry change | **None** |
