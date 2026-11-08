# Phase 14 — NASA catalogue expansion and two count-integrity fixes

**Scope:** five NASA OSDR studies acquired by pinned metadata archive, two corpus-count defects
fixed, three tests added that make both classes of defect fail loudly next time.

Nothing in this phase changes a prediction. No model was trained, no coefficient was touched, and
no simulator output moved. What changed is the evidence the platform can retrieve and the honesty
of the counts it publishes about itself.

---

## 1. Why these five studies

The catalogue already had Arabidopsis molecular work (OSD-46, OSD-120, OSD-314, OSD-346, OSD-782),
ISS leafy-green microbiology and nutrition (OSD-267, OSD-268, OSD-269, OSD-655, OSD-745, OSD-766,
OSD-767, OSD-780), a multi-crop ISS system test (OSD-773) and one Antarctic greenhouse
demonstration (OSD-895). The gap was the part of a space-crop programme an advisor actually has to
reason about: **what the crop is grown in, what a substrate change does, whether the edible product
is safe, and what a long stay in orbit does to a leafy green.**

| Study | Version | ISA archive | Samples | Organisms recorded | Why it earns a place |
| --- | --- | --- | --- | --- | --- |
| OSD-59 | 5 | 6,715 B | 2 | *Brassica rapa* | Long-duration mizuna transcriptome — molecular context for the crop the repository already models (OSD-655 harvest, OSD-780 microbial load) |
| OSD-386 | 4 | 239,326 B | 100 | Microbiota | *E. coli* persistence in the mizuna microbiome — the food-safety question on the same crop |
| OSD-670 | 3 | 218,973 B | 83 | *Lactuca sativa*, *Capsicum annuum*, *Raphanus sativus* | Asteroid regolith simulant as a growth medium — substrate substitution instead of hydroponics |
| OSD-723 | 1 | 599,230 B | 309 | Microbiota | Ionic silver in hydroponics: lettuce growth, nutrient uptake, root microbiome — a direct test of a hydroponic intervention |
| OSD-856 | 1 | 28,080 B | 12 | *Lactuca sativa* | Lettuce on simulated lunar soil batch #005 — the Moon-regolith case the simulator can only assume |

Selection was made for **coverage of the reasoning gaps**, not by search score. The discovery
query, its terms and the recorded timestamp are stored in
`data/metadata/phase14_manifest_checksums.json` so the selection is reproducible and reviewable.

## 2. Provenance discipline

`scripts/acquire_phase14_nasa_expansion.py` follows the same rule as the Phase 9 and Phase 10
acquisition scripts:

- each ISA metadata archive is pinned by **byte length and SHA-256** in
  `data/metadata/phase14_manifest_checksums.json`;
- a download whose bytes do not match the pin is **rejected**, never used;
- if the upstream archive size changes for the same version, the script **stops** rather than
  silently accepting new bytes;
- re-running verifies the pinned bytes and does not re-download;
- only the small ISA metadata archives are acquired (6 kB – 599 kB). **No sequencing data was
  downloaded and none is committed.**

Every row carries `status: verified-metadata`, an explicit `trainingEligibility` saying it is
*not a training table and not an input to any served model*, and at least three written
limitations.

## 3. What each study is declared unable to support

The limitations are part of the record, not a footnote — this is what keeps an expanded catalogue
from turning into an overclaimed one.

- **OSD-670** grows plants on a carbonaceous-chondrite **simulant**. A simulant is not lunar or
  Martian regolith; substrate chemistry differs enough that the result does not transfer by
  analogy.
- **OSD-856** used **one** simulated lunar soil batch. Batch chemistry does not generalise to other
  batches or to the Moon.
- **OSD-386** is a **deliberate inoculation** trial: persistence in a challenged microbiome is not
  an estimate of background contamination risk.
- **OSD-723** is **ground hydroponics**, not a spacecraft water loop, so it cannot calibrate the
  simulator's water-recovery fraction.
- **OSD-59** is differential expression, not edible mass; it is context, not a harvest target.

Two new `coverage` rows expose these boundaries in the UI-facing API:

| Feature | Status | Source |
| --- | --- | --- |
| Substrate and regolith | NASA data available for **simulants and substrate substitution, not for actual lunar or Martian regolith** | OSD-670, OSD-856 |
| Edible-product microbiology | NASA data available and modelled as a **within-campaign relative load** | OSD-267/268/269/655/745/780/386/723 |

## 4. The two count defects

Both were the same class of bug: a published number that could drift from the thing it describes.

**(a) The corpus breakdown did not sum to the corpus total.** `/api/assistant/corpus` published
`passages: 47` beside a breakdown of `20 + 8 + 10 + 6 = 44`. Three `classification` passages were
counted in the total and missing from the breakdown. The breakdown is now computed **from the
passages themselves** (`evidence._count_by_kind`) with an explicit `KIND_LABELS` table, so any kind
added later is counted automatically instead of silently vanishing.

**(b) The assistant screen hard-coded the passage count.** The card read
`RETRIEVAL OVER 46 VERIFIED PASSAGES` while the endpoint said 47. Fixed in `34ca5eb` by deriving
the label from the corpus response. Phase 14 adds the test that makes the *practice* fail, not just
the number.

## 5. Tests added

| Test | What it prevents |
| --- | --- |
| `test_corpus_breakdown_sums_to_the_published_total` | A breakdown that does not add up to its own total, and any passage kind invisible in the breakdown |
| `test_assistant_screen_does_not_hard_code_the_passage_count` | A count typed into JSX — the exact defect fixed in `34ca5eb` coming back |
| `test_phase14_study_is_pinned_and_its_bytes_are_present` (×5) | A catalogue row citing an archive that is missing, truncated, or no longer matching its digest |
| `test_phase14_checksums_file_matches_the_catalogue` | The pin file and the manifest drifting apart |
| `test_phase14_studies_declare_what_they_cannot_support` | A study added without limits, or presented as training data |
| `test_actual_dataset_inventory_and_no_cross_crop_claim` (rewritten) | Two views of the catalogue disagreeing — it now asserts equality with the declared manifest instead of a literal study count |

The last one matters beyond this phase: the old test asserted `len(studies) == 20`, which only
restated the number in a second place and would have failed on **every** legitimate acquisition
while never catching a study that existed in one view and not the other.

## 6. Verified results

| Gate | Before | After |
| --- | --- | --- |
| Backend suite | 535 passed / 1 skipped | **545 passed / 1 skipped** |
| Catalogue | 20 studies | **25 studies** (24 pinned in the manifest + 1 candidate) |
| Assistant corpus | 47 passages (breakdown 44) | **52 passages** (breakdown 52) |
| Coverage rows | 15 | **17** |

The acquired studies are immediately retrievable, not merely listed:

| Question asked locally | Status | Claims | Citations |
| --- | --- | --- | --- |
| "What does OSD-856 study?" | grounded | 1 | 1 |
| "Which studies test crops grown on simulated lunar or asteroid soil?" | partial | 2 | 2 |
| "Is there NASA evidence about E. coli on leafy greens?" | partial | 2 | 2 |
| "What is the expected crop yield on the Moon?" | insufficient | 0 | 0 |

The last row is the control: expanding the catalogue did **not** make the assistant willing to
answer a question the evidence still does not cover.

## 7. Limits of this phase

- **Metadata only.** Four of the five studies have processed data behind them that was *not*
  downloaded. Calling a study "in the catalogue" is not the same as calling it analysed, and none
  of the five supports a servable model.
- **No independent validation was added.** Every model remains `trained-exploratory`; OSD-59 and
  OSD-386 concern a crop the repository already models but are not compatible target/predictor
  pairs for it.
- **Selection is judgement, not measurement.** Five studies were chosen for coverage of reasoning
  gaps by a human read of titles and metadata. The discovery terms and the selection are recorded
  so that judgement can be reviewed — not so that it can be mistaken for a systematic review.
- **Licences are read from the archive.** Where the ISA investigation file declares no licence the
  row says so rather than copying a default.
