# NASA dataset inventory

Verified 2026-11-06 against the official OSDR metadata and file APIs. All counts below were computed from retrieved metadata, not inferred from study titles. Full file lists, URLs, sizes, restrictions and acquisition status are in `data/metadata/dataset_manifest.json`.

| Study | Organism | Study sample names | Files | Assay types |
|---|---|---:|---:|---|
| [OSD-267](https://osdr.nasa.gov/bio/repo/data/studies/OSD-267) | Lactuca sativa, Microbiota | 12 | 213 | 16S, ITS |
| [OSD-268](https://osdr.nasa.gov/bio/repo/data/studies/OSD-268) | Lactuca sativa | 13 | 196 | 16S, ITS |
| [OSD-269](https://osdr.nasa.gov/bio/repo/data/studies/OSD-269) | Lactuca sativa | 15 | 106 | 16S |
| [OSD-745](https://osdr.nasa.gov/bio/repo/data/studies/OSD-745) | Lactuca sativa | 60 | 55 | Anthocyanin Content, Inductively Coupled Plasma Optical Emission Spectroscopy, Oxygen Radical Absorbance Capacity, Phenolic Compound Content, Photography |
| [OSD-766](https://osdr.nasa.gov/bio/repo/data/studies/OSD-766) | Solanum lycopersicum | 142 | 571 | 16S, ITS |
| [OSD-767](https://osdr.nasa.gov/bio/repo/data/studies/OSD-767) | Solanum lycopersicum | 36 | 638 | RNA Sequencing (RNA-Seq) |
| [OSD-773](https://osdr.nasa.gov/bio/repo/data/studies/OSD-773) | Brassica rapa, Lactuca sativa, Pisum sativum, Raphanus sativus, Solanum lycopersicum, Triticum aestivum | 156 | 315 | 16S, ITS |
| [OSD-7](https://osdr.nasa.gov/bio/repo/data/studies/OSD-7) | Arabidopsis thaliana | 36 | 46 | DNA microarray |
| [OSD-120](https://osdr.nasa.gov/bio/repo/data/studies/OSD-120) | Arabidopsis thaliana | 90 | 851 | Photography, RNA Sequencing (RNA-Seq) |
| [OSD-436](https://osdr.nasa.gov/bio/repo/data/studies/OSD-436) | Arabidopsis thaliana | 21 | 22 | DNA microarray |
| [OSD-625](https://osdr.nasa.gov/bio/repo/data/studies/OSD-625) | Arabidopsis thaliana | 16 | 19 | CCS long read DNA Enzymatic Methyl Sequencing |
| [OSD-375](https://osdr.nasa.gov/bio/repo/data/studies/OSD-375) | Brachypodium distachyon | 48 | 99 | RNA Sequencing (RNA-Seq) |
| [OSD-655](https://osdr.nasa.gov/bio/repo/data/studies/OSD-655) | Brassica rapa | 37 | 22 | Inductively Coupled Plasma Optical Emission Spectroscopy, Oxygen Radical Absorbance Capacity, Phenolic Compound Content |

Study counts represent unique names in the study-material sample list; they are not necessarily independent plants, assay observations or training rows. Version is the API investigation version; it may differ from the web portal selected version.

## Acquired measurements

28 actual files were acquired: 27 small CSVs from OSD-655 and OSD-745, plus the STAR unnormalized gene-count matrix from OSD-767. The CSVs include data dictionaries, original assay tables, transformed assays, irrigation and harvested mass. The gene matrix is 33,562 genes by 36 specimens. Checksums and exact download timestamps are recorded.

OSD-655 supports 14 labeled mizuna pillow harvest observations after exclusion of ten missing mass outcomes. OSD-745 has nutritional/elemental assays, not a direct crop yield response table. OSD-767 supports molecular flight-versus-ground classification with 36 samples grouped into 21 plants.

OSD-267/268/269 and OSD-766/773 include microbial assays; their crop-associated descriptions do not make the microbiome values biomass measurements. OSD-436 concerns short parabolic-flight altered gravity, not crop production at lunar or Martian gravity. OSD-7/120/625/375 molecular endpoints are not interchangeable with harvest labels.

## Reuse and rights

[NASA API documentation](https://api.nasa.gov/) describes file and metadata access. [OSDR terms](https://science.nasa.gov/reference/osdr-help-terms-and-conditions/) apply. Public availability does not imply every contributed file is copyright-free. Cite study investigators and associated publications; no NASA endorsement or validation is claimed. [OSD-655 catalog entry](https://catalog.data.gov/dataset/pick-and-eat-space-crop-production-flight-testing-on-the-international-space-station-eleme) declares public access and a US government works license link.
