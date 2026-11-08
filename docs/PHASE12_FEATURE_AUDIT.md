# Phase 12 — feature audit

An audit of every feature the platform already had, what state it was in at the Phase 11
merge (`7957a05`), and what Phase 12 changed. The audit was done by exercising the code,
not by reading the earlier reports.

---

## 1. What exists

The API exposes **56 paths**. Grouped by first path segment:

| Group | Paths | State at audit | Phase 12 change |
| --- | --- | --- | --- |
| `predict` | 8 | working, one per served model, each with its own request schema | unchanged; now also reachable through `/workflow/run` |
| `models` | 4 | registry, explanation, reference profiles, example | unchanged |
| `datasets` | 3 | manifest list, detail, preview | **additive** `countsAsIndependentStudy`, `redundantWith` |
| `science` | 5 | measurements, checksums, classification, summary | unchanged |
| `simulate`, `compare`, `optimize`, `advisor`, `reports` | 5 | deterministic simulator and its exports | unchanged |
| `scenarios` | 1 | owner-scoped saved scenarios | unchanged; mirrors the new analyses store |
| `auth` | 4 | register, login, me, logout | unchanged |
| `health`, `ready`, `metrics`, `config`, `assumptions`, `crops`, `provenance`, `external-datasets`, `scientific-summary` | 9 | operational and read-only | unchanged |
| **`assistant`** | 5 | did not exist | **new**: evidence-grounded Q&A |
| **`workflow`** | 5 | did not exist | **new**: validate → run → interpret → limitations → provenance |
| **`analyses`** | 3 | did not exist | **new**: owner-scoped saved analyses and export |
| **`explorer`** | 4 | did not exist | **new**: dataset independence and overlap relations |

The frontend had 10 workspace modules. Phase 12 adds one (`Research assistant`) and extends
two existing pages (`AI prediction center`, `NASA data explorer`) with panels — no
navigation redesign, no layout change, no new visual language.

---

## 2. Gaps the audit found, and what was done about each

### 2.1 Evidence was documented but not queryable

Nineteen datasets, eight models and the Phase 9–11 evaluation records were all in the
repository, but finding the sentence behind a number meant grepping Markdown. The Phase 11
snapshot report makes fourteen separate scientific claims in prose with no way to check
which file supports which line.

**Done:** `backend/app/evidence.py` builds a 47-passage corpus from the committed artifacts
(20 datasets, 8 models, 10 findings, 6 methodology, 3 classification), and
`/assistant/ask` answers from it with a citation per claim, or refuses. See
`PHASE12_AI_RESEARCH_ASSISTANT.md`.

### 2.2 Eight models, no single place to see what each may be used for

`/api/models` already carried metrics and limitations, but the classification, the
calibration status and the explanation availability were spread across three artifacts and
the registry did not join them.

**Done:** `research.model_registry()` now carries `scientificClassification`,
`calibration`, `explanationAvailable` and `supersedes` on every row, and `/workflow/models`
projects them into one catalogue with the input family each model consumes.

### 2.3 Running a model required knowing its bespoke endpoint

Each `POST /predict/...` has its own schema. Nothing answered "which model accepts this
input", nothing validated against the model's recorded training domain before inference,
and nothing attached the interpretation, limitations and provenance to the number in one
response.

**Done:** `backend/app/workflow.py` plus `/workflow/*`. It is additive: every dedicated
endpoint still works, and the workflow calls the same evaluators, so a number from the
workflow is the same number from the model.

### 2.4 A prediction could not be saved

`scenarios` stores simulator configurations. There was no way to keep a model output, and
therefore no way to export a report that matched what a model actually returned.

**Done:** an `analyses` table with a non-null `owner_id`, four owner-scoped helpers, and
`/analyses` with `json`/`csv`/`md` export that serialises the stored payload unchanged.

### 2.5 "19 datasets" was the wrong headline

The Phase 11 duplicate audit had established that OSD-320 is a bit-identical second deposit
of OSD-46. The dataset list still presented every accession as a study, so any client
counting them would over-count.

**Done:** `/explorer/*` classifies every pair into a closed relation vocabulary and refuses
to call an unaudited pair independent. `/datasets` gains the safeguard fields additively.

### 2.6 Retired models were still listed as available

`mizuna-microbial-load-v1` is category 6 and returns 410 from its endpoint, but the
registry and any list built from it did not distinguish "registered for reproducibility"
from "available for inference".

**Done:** the catalogue reports `runStatus: retired` with the evidence that retired it, and
`/workflow/run` returns 410 rather than running it. The UI marks it retired.

---

## 3. Features deliberately left alone

| Feature | Why untouched |
| --- | --- |
| Simulator (`/simulate`, `/compare`, `/optimize`) | Deterministic and already calibrated in Phase 7; it is a scenario tool, and Phase 12 adds no new physics. |
| Reports (`/reports/{json,csv,pdf}`) | Already produce numbers from the same call as the API; the new analysis export reuses the same discipline. |
| 3D greenhouse, charts, mission shell | Design preservation is a standing constraint; no Phase 12 feature needed them to change. |
| `/predict/*` request schemas | Each model's schema is its scientific contract; loosening them for a uniform UI would have been a regression. |

---

## 4. What is still not done, stated plainly

* **No validated out-of-distribution threshold.** Phase 11 tested two novelty scores against
  three controls and both failed; Phase 12 therefore does schema-based and
  physical-plausibility domain checks only, and reports `insideTrainingDomain` from the
  model's recorded range. It does not claim a novelty detector.
* **No calibrated probabilities anywhere.** Eight of eight models report
  `calibrated: false`. The workflow prints that in the response instead of hiding it.
* **No cross-owner sharing of analyses.** There is no sharing endpoint, so there is no
  sharing permission to get wrong.
* **No external language model.** The assistant is extractive and deterministic; an optional
  provider integration was deliberately not built, because a provider failure path that has
  never been exercised is worse than no provider.
