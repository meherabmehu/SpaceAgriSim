# NASA Dataset Expansion — Phase 6

**Generated from live official NASA OSDR APIs on 2026-11-07.**
Reproduce with `python scripts/discover_expanded.py`
→ `data/metadata/phase6_discovery.json`
(SHA-256 of that run: `ec8251a6c1ff7f36716ac99ba4489594a6cf753feec4b25efbeca91a6adee864`)

Official endpoints used, exclusively:

* `https://osdr.nasa.gov/osdr/data/osd/meta/{n}` — study metadata
* `https://osdr.nasa.gov/osdr/data/osd/files/{n}` — complete file inventory

No third-party mirrors, scrapers or aggregators were used to establish the
inventory. (CDN redirect to NASA's own `genelab-*-repo-prod.s3.amazonaws.com`
buckets is followed only for file bodies, as the OSDR endpoint requires.)

---

## 1. Scope of the sweep

| Set | Count | Identifiers |
|---|---|---|
| Baseline inventory (re-verified) | 14 | OSD-7, 120, 267, 268, 269, 375, 436, 625, 655, 745, 766, 767, 773, 895 |
| Phase 6 expansion candidates | 11 | OSD-218, 307, 565, 670, 385, 386, 412, 723, 780, 855, 883 |
| **Total queried** | **25** | — |
| **Successfully resolved** | **25** | 0 errors |

The three studies explicitly named in the Phase 6 brief — **OSD-218, OSD-307,
OSD-565** — all exist and were verified.

## 2. Studies surfaced by the expanded search

Beyond the 14 baseline records, targeted OSDR searches for *biomass*, *plant
growth*, *harvest*, *lettuce*, *mizuna*, *radish*, *wheat* and *PPAS/APH*
terms surfaced the following additional, genuinely relevant records:

| Study | Verified title (truncated) | Files | Bytes | Non-omics measurement tables |
|---|---|---|---|---|
| **OSD-780** | Pick-and-eat space crop production flight testing on the ISS (**Plate Count** Assay…) | 5 | 606,375 | **4** |
| **OSD-670** | CI Asteroid Regolith as an In Situ Plant Growth Medium for Space Crop Production | 20 | 35,780,299 | **2** |
| OSD-218 | Plant development on ISS differs from the development on the ground … | 652 | 430,290,408,716 | 0 |
| OSD-307 | Evaluating the Lettuce Metatranscriptome with MinION Sequencing … | 20 | 318,774,761,533 | 0 |
| OSD-565 | Utilizing the KSC Fixation Tube to Conduct Human-Tended Plant Biology Experiments on a Suborbital Spacecraft | 605 | 1,671,019,704,044 | 0 |
| OSD-723 | Substrate Matters: Ionic Silver Alters Lettuce Growth, Nutrient Uptake, and Root Microbiome in a Hydroponic System | 621 | 24,429,368,663 | 0 |
| OSD-385 | Persistence of *E. coli* in the microbiomes of red Romaine lettuce | 413 | 8,344,950,630 | 0 |
| OSD-386 | Persistence of *E. coli* in the microbiomes of mizuna mustard | 414 | 9,317,413,887 | 0 |
| OSD-412 | Spatial characterization of microbial communities on multi-species leafy greens in the Veggie unit | 89 | 4,324,858,292 | 0 |
| OSD-855 | Apollo 17 Challenge System — Seed Germination (Cabbage, Brussels Sprouts, Radish, Lettuce) | 4 | 197,942,417 | 0 |
| OSD-883 | Analysis of Vegetable Seedlings Grown in Contact with Apollo 14 Lunar Surface Fines | 2 | 9,149,203 | 0 |

## 3. The central finding: there is almost no machine-readable biomass data

Of **25** verified plant-relevant OSDR studies, only **five** contain any
non-omics tabular measurement file, and only **one** of those — beyond the
already-acquired OSD-655 — contains plant-relevant numeric measurements with
more than a handful of rows.

| Study | Non-omics measurement tables | What they actually measure |
|---|---|---|
| OSD-655 | 12 | VEG-04A harvest mass, irrigation logs, chemistry, plate counts |
| OSD-745 | 17 | VEG-01/03A lettuce elemental, phenolic, anthocyanin, ORAC assays |
| **OSD-780** | **4** | **VEG-04A/B microbial plate counts (CFU) — newly acquired** |
| **OSD-670** | **2** | **Asteroid-regolith substrate chemistry — newly acquired** |
| **OSD-120** | **1** | **Image↔sample correlation index — newly acquired** |

Every other study in the sweep is **entirely omics**: RNA-seq, microarray,
amplicon/diversity, metagenomics, metatranscriptomics or methylation.

### Why this matters

The Phase 6 brief asks for new models on *measured biomass, harvest fresh mass,
harvest dry mass, repeated growth observations, water uptake, transpiration, CO₂
assimilation and O₂ evolution*. The verified inventory shows:

* **No new biomass or harvest-mass table exists** in the OSDR public corpus for
  these crops beyond OSD-655's 14 usable VEG-04A endpoints.
* **No transpiration, water-uptake, CO₂-assimilation or O₂-evolution measurement
  table** exists in any of the 25 studies. OSD-655 records irrigation *supplied*,
  which is a management input, not physiological demand.
* **OSD-895 (EDEN ISS)** ships only `OSD-895_sup_fpls-11-00656.pdf` — a 4.3 MB
  paper. Its biomass numbers are a table *inside a PDF*, not a machine-readable
  dataset. The repository's `eden_iss_2018_biomass_summary.csv` is therefore a
  **manual transcription from literature**, and is labelled as such.
* The 204 "Morphometric Photography" files in OSD-120 are images, and the one
  tabular supplement is a filename↔sample index with no numeric phenotype. No
  image-derived phenotype table exists to train on.

**Consequence, stated plainly:** Phase 6 cannot honestly train a new
biomass/growth/water/gas-exchange NASA model. The data does not exist in
machine-readable public form. Section 5 of `docs/PHASE6_PROGRESS.md` records
these as *blocked (data)* rather than filling the gap with fabricated or
proxy-labelled data.

## 4. Data volume context

The corpus is dominated by sequencing data, which is correctly *not* downloaded:

| Study | Inventory size | Dominant category |
|---|---|---|
| OSD-565 | 1.67 TB | GeneLab Processed RNA-Seq (513 files) |
| OSD-767 | 599 GB | GeneLab Processed RNA-Seq (563 files) |
| OSD-375 | 463 GB | RNA-Seq (97 files) |
| OSD-218 | 430 GB | GeneLab Processed RNA-Seq (544 files) |
| OSD-120 | 364 GB | GeneLab Processed RNA-Seq (608 files) |
| OSD-307 | 319 GB | Metatranscriptomics (19 files) |

Phase 6 downloads only the selected processed tables actually used for science,
consistent with the brief's instruction not to pull entire genomic repositories.

## 5. Studies verified but deliberately not used for ML

| Study | Reason |
|---|---|
| OSD-7, 120, 218, 375, 565, 767 | Transcriptomic only. Expression is not a biomass label. OSD-767 is already used for the *molecular-context* classifier, which is its correct scope. |
| OSD-436 | Altered-gravity microarray; molecular response only, no continuous gravity phenotype |
| OSD-625 | Methylation sequencing; no plant yield phenotype |
| OSD-267, 268, 269, 766, 412, 385, 386, 723 | Amplicon/metagenomic community composition; no host plant measurement |
| OSD-773 | XROOTS hardware characterisation via amplicon sequencing |
| OSD-307 | Metatranscriptomic community function |
| OSD-855, 883 | Apollo-era germination imagery/reports; no machine-readable numeric table |
| OSD-670 | Substrate chemistry only; the 12 morphometric files are photographs |

## 6. Positive outcome of the expansion

Exactly one new NASA measurement dataset proved scientifically usable:
**OSD-780 VEG-04A/B plate counts** — 203 unique samples of measured culturable
aerobic and yeast/mould load with measured tissue fresh weight, spanning two
flight campaigns, two lighting spectra, leaf/root/soil/wick/swab tissues, and a
sanitised/unsanitised treatment. This dataset is sufficient to support a
genuinely new, honestly-scoped model, and it does not exist in the prior
inventory. See `docs/NASA_MEASUREMENT_INVENTORY.md` and
`docs/ML_TRAINING_REPORT.md`.
