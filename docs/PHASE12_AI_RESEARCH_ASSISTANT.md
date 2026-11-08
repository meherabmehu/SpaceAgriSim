# Phase 12 — AI research assistant

An assistant that answers questions about this repository's evidence, cites the passage
behind every sentence, and refuses when the evidence does not cover the question.

It is **extractive and deterministic**: it composes sentences out of retrieved passages. It
does not paraphrase, does not use an external model, and cannot state anything that is not
in a passage it retrieved. That is a deliberate limitation — an answer about NASA data that
cannot be traced to a file is indistinguishable from an invented one.

---

## 1. What it can see

`backend/app/evidence.py` builds the corpus at import from committed artifacts only.

| Kind | Passages | Source |
| --- | --- | --- |
| `dataset` | 20 | `data/metadata/dataset_manifest.json` + candidates |
| `model` | 8 | `ml/artifacts/registry.json` |
| `evaluation` | 10 | `ml/evaluation/phase10_*.json`, `phase11_*.json` |
| `methodology` | 6 | simulator, split, eligibility and coverage records |
| `classification` | 3 | `app/science_classification.py` |

**47 passages, 0 quarantined.** `GET /api/assistant/corpus` serves the counts, and
`GET /api/assistant/evidence/{passage_id}` serves the full text and citation record of any
passage a claim points at, so every answer can be audited down to the file.

Each passage carries: `sourceId`, `kind`, `title`, `accession`, `url`, `localReference`,
`evidenceClass` (`measured data` / `model or estimate, not a measurement` / `methodology`),
and its own `limitations`.

---

## 2. How retrieval works, and why it stopped being plain BM25

The first implementation was BM25. It failed in a way that looks fine: a single rare word
("future", appearing twice in a short methodology passage) outranked every dataset record
for "which datasets exist". Three changes fixed it.

1. **Distinct-term coverage scaling.** The BM25 score is multiplied by
   `matched distinct query terms / distinct query terms`. A passage now earns rank by
   covering the question, not by containing one unusual word.
2. **A joint-match rule.** When the question has more than two distinct terms, at least two
   must match. One matching word is not evidence that a passage is about the question.
3. **A specificity rule.** A match must include at least one term that is specific to the
   question. Subject-matter words — space, NASA, dataset, model, plant, growth — can support
   a match but cannot be the whole of it. Without this rule, "What is the best restaurant
   near the Johnson Space Center?" was answered as `partial` because "space" and "center"
   both matched.

Stemming (`_stem`), hyphenated-term dual indexing (`COMPOUND_SPLIT`) and an accession-in-text
bonus are also in place; the last one is why "OSD-346 confound" reaches the Phase 11 gravity
finding rather than a generic dataset row.

Two floors decide whether anything is strong enough to ground an answer: an absolute floor
(`MIN_EVIDENCE_SCORE` 2.5) and a relative floor of 30 % of the top score. Both had to exist:
the absolute one alone let stem-sharing passages pad an answer, and the relative one alone
let a weak corpus answer a question it only half-matched.

---

## 3. What an answer looks like

`POST /api/assistant/ask` with `{"question": "..."}` (≤ 400 characters) returns:

| Field | Meaning |
| --- | --- |
| `status` | `grounded` (≥ 2 cited claims and a recognised intent), `partial` (relevant but incomplete), `insufficient` (nothing above the floor) |
| `summary` | The intent frame, or an explicit statement that the evidence is incomplete |
| `claims[]` | One sentence each, with `citation` = the 1-based index into `citations` |
| `citations[]` | Title, accession, URL, local reference, evidence class, and that passage's limitations |
| `limitations[]` | Union of the cited passages' limitations; partial answers additionally say the passages are a pointer, not an answer |
| `measuredVersusInterpreted` | Which cited sources are measured data and which are model or estimate |
| `refusal` | `insufficient-evidence`, `empty-question` or `greeting` |

Eight intents (`model_scope`, `model_selection`, `exclusion`, `evidence_for_assumption`,
`earth_only`, `uncertainty`, `dataset_suitability`, `comparison`) re-weight which *kind* of
passage may ground which question: a question about uncertainty prefers evaluation records,
a question about scope prefers model records.

**The renderer refuses an uncited claim.** `EvidenceAnswer.render()` raises `ValueError` if any
claim's citation index does not resolve to a retrieved citation. The guarantee is structural,
not a convention the next developer has to remember.

### Refusal, demonstrated

```
POST /api/assistant/ask  {"question": "How do I bake sourdough bread?"}
-> status: insufficient, refusal: insufficient-evidence, claims: [], citations: []
```

The refusal never carries citations, because a refusal that cites something looks like an
answer.

---

## 4. Security

| Risk | Control |
| --- | --- |
| Prompt injection inside a retrieved document | Passages are screened as they are indexed; a document containing instruction patterns ("ignore previous instructions", role tags, `<system>`, `[/INST]`, shell commands, credential requests) is **quarantined** and never retrievable. The assistant also treats retrieved text as data, never as instructions — it copies sentences and does not execute or follow them. |
| Secret leakage | Screening rejects passages containing key-like patterns (API keys, tokens, private keys); the corpus is built only from artifacts that are already committed, and no environment or configuration file is indexed. |
| Context size | 47 passages, ≤ 5 claims per answer, ≤ 400 question characters, and each quote truncated to 400 characters. There is no path by which a caller can inject documents. |
| Permission bypass | The assistant reads public scientific artifacts only. Saved analyses are **not** in the corpus, so one account's saved work can never appear in another account's answer. |
| Denial of service | The global request guard (180/min, 64 KiB body) applies unchanged; a question over 400 characters is rejected with 422 before retrieval. |
| Provider failure | There is no external provider in the answer path, so there is no failure mode to handle. This was chosen over an unexercised fallback path. |

---

## 5. Quality evidence

A 12-question sweep (also asserted in `backend/tests/test_phase12_assistant.py`, 38 tests):

| Question | Status | Leads with |
| --- | --- | --- |
| Which NASA studies investigated microgravity? | grounded | OSD-120 |
| What does the OSD-46 classifier predict? | grounded | `radiation-quality-osd46-v1` |
| Why did the OSD-346 gravity result fail? | grounded | `phase11-gravity-osd346` |
| Which model can analyse a gene expression input? | grounded | `tomato-flight-response-v1` |
| Is OSD-320 an independent replication of OSD-46? | grounded | `phase11-duplicate-osd320` + OSD-46 |
| Which models were excluded and why? | grounded | `method-classification` |
| Compare the OSD-267 and OSD-269 experiments | grounded | OSD-269 |
| What future AI training is the data ready for? | partial (training-eligibility is the top retrieved passage) | `phase11-ood-rejected` |
| Uncertainty interval on the lettuce model | partial | `phase10-coverage` |
| How much water does lettuce need on Mars? | partial | `method-simulator` |
| Restaurant near Johnson Space Center | partial — weak match, flagged as a pointer | OSD-766 |
| How do I bake sourdough bread? | **insufficient** | — |

The three `partial` rows are reported as partial rather than promoted: the corpus contains
related material and the answer says so, which is more useful than a refusal and more honest
than a confident answer. The "future AI training" row is the known weak spot: retrieval puts
the eligibility audit first, and claim composition reaches a different passage.
