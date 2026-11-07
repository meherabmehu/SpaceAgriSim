# Phase 9 NASA dataset discovery

How the datasets were found, what the access path actually is, and how the search
was made systematic instead of relying on prior inspection.

## The access path

The OSDR GEODE REST API (`osdr.nasa.gov/geode-py/ws/api/...`) returns **403 or 404
for every endpoint tried**, and the GeneLab visualisation site is a single-page
application with no public JSON API. Both were verified from this environment.

The working path is the **NASA OSDR Open Data S3 bucket**, which the AWS Open Data
Registry documents as `arn:aws:s3:::nasa-osdr` in `us-west-2` with no access
restrictions:

```
https://nasa-osdr.s3.us-west-2.amazonaws.com/?list-type=2&prefix=<OSD-ID>/
https://nasa-osdr.s3.us-west-2.amazonaws.com/<OSD-ID>/<version>/<subdir>/<file>
```

Listing returns XML in the `http://s3.amazonaws.com/doc/2006-03-01/` namespace.
An anonymous `GET` of any object key returns 200 with no signing.

Two practical traps, both hit during this phase:

- `max-keys` truncates at 1000 objects and paginates via `NextContinuationToken`.
  Judging a study from a truncated first page understates what it holds. OSD-480
  alone has 3208 objects.
- The `version-N` segment changes between releases. Pinning a URL without pinning
  the checksum would silently follow a re-release, so every file is recorded by
  byte length and SHA-256.

## Systematic sweep, not a list of familiar studies

Phase 8 candidates came from inspecting roughly 25 studies by hand. The brief
requires a sweep "not limited to the previously inspected 25 studies", so
`scripts/sweep_phase9_osdr.py` walks **every identifier from OSD-1 to OSD-900** and
classifies what each one publishes.

Result (`data/metadata/phase9_osdr_sweep.json`):

| Verdict | Studies |
| --- | --- |
| Usable processed matrix | **231** |
| No expression data | 209 |
| Raw sequencing only | 115 |
| Raw amplicon only | 32 |
| **Studies found in range** | **587** |

231 studies publish something a supervised model could use. That is the honest
headline: the repository is far richer than the Phase 8 candidate list implied.

## Narrowing: screening the 231

`scripts/screen_phase9_candidates.py` then asks the narrower question the brief's
Priority C needs: which studies publish a **processed taxonomic abundance table**?
Raw amplicon FASTQ does not count, because quantifying it would require a
QIIME/DADA2 pipeline this project does not run, and inventing one mid-phase would
put an unvalidated pipeline underneath a scientific claim.

Result (`data/metadata/phase9_candidate_screen.json`): of 231 usable studies,
**6 publish a processed taxonomy table**:

| Study | Tables | Content |
| --- | --- | --- |
| OSD-72 | `taxonomy-and-counts.tsv` | murine colon microbiota, radiation + iron diet |
| OSD-170 | `taxonomy-and-counts.tsv` | aircraft bioaerosol collector, altitude |
| **OSD-267** | `16S-taxonomy-and-counts.tsv` | **ISS lettuce VEG-01A** |
| **OSD-269** | `taxonomy-and-counts.tsv` | **ISS lettuce VEG-03A** |
| OSD-276 | `taxonomy-and-counts.tsv` | ISS surface swabs |
| OSD-487 | `taxonomy-and-counts.tsv` | human diabetic foot ulcer microbiome |

Filename screening alone reported **zero** crop-microbiome candidates, because no
object key contains the word "lettuce". Reading the ISA study descriptions — which
the brief requires and which is why they are read — showed that **OSD-267 and
OSD-269 are ISS-grown red romaine lettuce microbiome studies**. That is a real
correction to the earlier eligibility verdict, and it is recorded as such rather
than quietly dropped.

## What this changed

The Phase 8-era conclusion "no crop-microbiome data exists" was **wrong on the
facts**. The corrected statement, supported by
`ml/evaluation/phase9_veg_microbiome_feasibility.json`, is:

> Crop-microbiome data with processed taxonomy tables does exist (OSD-267,
> OSD-269), but its design cannot support a predictively validated model: VEG-01A
> has 2 flight versus 5 ground leaf plants, and each plant contributes both leaf
> and root samples, so tissues are repeated measures rather than independent units.

The discovery process is therefore the deliverable; the model decision is made in
`PHASE9_DATASET_ELIGIBILITY.md` on design grounds, not on data availability
grounds.

## Verification of every acquired file

`scripts/acquire_phase9.py` downloads each file and refuses it unless byte length
**and** SHA-256 match the pinned value. `data/metadata/phase9_nasa_datasets.json`
records 12 files: 9 small enough to commit, 3 fetched on demand.

| Study | File | Bytes | SHA-256 (prefix) |
| --- | --- | --- | --- |
| OSD-46 | array normalised expression | 23,794,742 | `f15c4179dbbe` |
| OSD-46 | array sample table | 4,139 | `0ae05ae09386` |
| OSD-782 | RSEM unnormalised counts | 4,527,540 | `dc98d786d797` |
| OSD-782 | VST counts | 14,679,817 | `6f1d41e0d2de` |
| OSD-782 | ISA metadata | 166,136 | `9564320f2449` |
| OSD-411 | RSEM unnormalised counts | 8,936,306 | `3a0d6c17473d` |
| OSD-411 | ISA metadata | 123,676 | `ab6687e01802` |
| OSD-267 | 16S taxonomy-and-counts | 15,821 | `2583de1db821` |
| OSD-267 | 16S sample table | 473 | `79613c01e747` |
| OSD-267 | ISA metadata | 101,415 | `daee85572f94` |
| OSD-269 | 16S taxonomy-and-counts | 24,144 | `22ebf8714037` |
| OSD-269 | ISA metadata | 62,785 | `ea1c96a51187` |

The raw downloads themselves are **not committed** (~92 MB). They are publicly
hosted, byte-stable, and re-acquirable exactly, so the checksums — not the blobs —
carry the provenance.
