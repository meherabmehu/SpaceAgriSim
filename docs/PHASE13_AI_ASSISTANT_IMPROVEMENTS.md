# Phase 13 — Scientific Research Assistant: What Changed and Why

This document describes the changes to the in-app research assistant in Phase 13. Every claim
about quality here is backed by a number produced by `scripts/evaluate_assistant.py` against
the fixed benchmark in `backend/tests/data/assistant_benchmark.json`; the full metrics are in
`docs/PHASE13_ASSISTANT_EVALUATION.md` and `ml/evaluation/phase13_assistant_eval.json`.

The assistant is a **retrieval-grounded** system. It answers from a corpus of 47 curated
passages built from the project's own NASA OSDR manifests, dataset records, model cards, the
Phase 10–12 audits and the methodology notes. It does not call an external language model in
the default configuration. What changed in Phase 13 is *how it decides what to retrieve and what
it is allowed to say* — not the corpus, and not the scientific claims.

---

## 1. The failure Phase 12 left behind

Phase 12 issued **one retrieval query per user question**. The question text was scored against
every passage, the top handful were selected, and the best sentence from each was quoted.

That works for "What does the OSD-46 radiation classifier predict?" and fails for anything with
structure. Two failures were reproducible before any code changed:

**Comparison questions answered one side.** "Compare the findings of OSD-314 and OSD-346."
scored passages by how well they matched the *whole* sentence. A passage mentioning only
OSD-346 could outrank the OSD-314 record because the rest of the wording matched better. The
assistant then produced an answer that discussed one dataset and never said it had ignored the
other. The status still read `grounded`, because nothing in the pipeline knew that half the
question was unanswered.

**False premises were confirmed, not refused.** "What crop yield will the OSD-46 classifier
predict on the Moon?" matched the OSD-46 model card on every content word — radiation,
classifier, OSD-46, model — and returned `grounded` with the model's identity line as the
leading claim. A reader skimming the answer would come away believing the model predicts lunar
crop yield. It does not: no such capability exists anywhere in the study, and the model card
says so explicitly.

Both are integrity failures rather than fluency failures. The assistant was never wrong about
the corpus; it was wrong about *what it had been asked* and *what it was entitled to conclude*.

---

## 2. Planning before retrieval

`backend/app/reasoning.py` (new, 196 lines) turns a question into explicit retrieval targets
before any search runs. It returns a plan, not prose:

* **Entity extraction** — OSD/GLDS accessions and model slugs. An accession that appears only
  inside a model slug (`radiation-quality-osd46-v1`) is no longer counted as a second, separate
  entity, which previously made single-entity questions look multi-entity.
* **Comparison detection** — two or more distinct entities plus a comparison marker. `"both"`
  was removed from the marker list after it caused "does this apply to both models" to be
  planned as a comparison of two accessions.
* **Conjunction splitting** — "why did it fail replication **and** what would validate it"
  becomes two sub-questions. Splitting is refused where the halves do not stand alone: "the
  difference between OSD-314 and OSD-346" stays one question, because "the difference between
  OSD-314" is not a question.
* **Follow-up resolution** — a pronoun-led question inherits the previous turn's entity names
  and nothing else. "And what about its replicate design?" after an OSD-346 question becomes an
  OSD-346 question; it does not inherit the previous intent.
* `MAX_SUBQUESTIONS = 4`.

Retrieval then merges the per-target rankings. For a sub-question that is *about* a named
entity, the passage that *is* that entity's record gets a 2.5× boost, so an audit finding that
happens to share vocabulary cannot outrank the accession record itself.

## 3. Answering from more than one hop

Claims are selected **hop-first**: each planned sub-question gets at least one claim before any
sub-question gets a second. A two-part question therefore cannot be answered entirely from one
hop while the other half silently disappears.

A named entity that no *selected* passage mentions is recorded in `coverage_gaps` and blocks the
`grounded` label. The UI shows the gap. This is deliberately conservative: `partial` with a
stated gap is honest, `grounded` with a missing half is not.

## 4. Refusing unsupported premises

A small set of premise patterns (`FALSE_PREMISES`) describes capabilities that do not exist in
this project — most importantly, that a molecular or radiation classifier predicts crop yield,
biomass, survival or productivity on the Moon or Mars. When a question assumes one of these:

* the status is forced to `partial` (never `grounded`),
* `refusal` is set to `unsupported-premise`,
* the answer quotes the sentence that states the model does **not** do this, and
* the limitation list leads with the premise correction rather than burying it.

The statement quoted is not generated. It is an existing, recorded limitation on the cited
artifact, and the citation carries that limitation text so the reader can check it.

**Crucially, asking *why* a capability is absent is not treated as a false premise.**
"Why can the lettuce model not predict Mars crop yield?" is a question the corpus answers well,
and a `CRITICAL_PHRASING` guard keeps it answerable. Without that guard the false-premise
detector swallowed the project's most important limitation explanations.

## 5. Closing the vocabulary gap

Users ask in the register of the interface ("limitations", "explainability", "provenance",
"training suitability"); the corpus is written in the register of the audits ("not a predictive
model", "feature attribution", "checksum-verified"). `QUERY_EXPANSION` maps the former onto the
latter at retrieval time. It expands the *query*, never the claim: an expansion can change which
passages are found, and cannot add a sentence to an answer that the passage does not contain.

Two ranking defects were also fixed: the relative evidence floor discarded all corroborating
passages when one passage scored very high (now capped at 12×), and a single decisive passage
matching the question almost verbatim now counts as complete evidence instead of being padded
out with vocabulary-sharing records.

## 6. Citation integrity, before and after

Every claim carries `passageId`, a 1-based `citation` index, and the verbatim `quote` shown to
the reader. The benchmark's support check is exact:

> A claim is supported if and only if its quote is a verbatim substring of the cited passage's
> text, **or** of a limitation recorded on that cited artifact and included in its citation.

There is no fuzzy match and no semantic similarity credit. A paraphrase that is not in the
document counts as an unsupported claim even when it happens to be true. Measured on the final
build: **92 claims, 0 unsupported.**

The limitation branch exists because a refusal must be able to quote the statement that the
capability is absent, and that statement lives in the artifact's recorded limitations rather
than its description. Opening that branch without also opening the assertion hole requires the
citation to carry the exact text, which it now does — the quote the reader sees is always text
the reader can find in the citation block.

## 7. API surface

`POST /api/assistant/ask` accepts an optional `context` list of at most two prior questions,
used only for pronoun resolution. The request model now uses `extra="forbid"` and validates
per-item length, so an unknown field is a 400 rather than a silently ignored parameter, and an
oversized context entry is a 422. Nothing in the request can influence which claims are
permitted — request content changes retrieval, never evidence.

## 8. What was deliberately *not* done

* **No LLM in the measured path.** Every number in this document was produced by the
  deterministic pipeline. If an optional provider is enabled later, it may only explain
  retrieved evidence, and it is measured separately against the same benchmark — it does not
  inherit these scores.
* **No corpus edits to make questions answerable.** When a benchmark question had no grounding
  passage (OSD-320 is absent from the manifest and appears only through the duplicate audit),
  the *benchmark rule* was corrected and annotated, not the corpus.
* **No relaxation of the refusals.** The false-premise path makes the assistant answer *fewer*
  questions, and that is the point.
* **No change to any model metric, dataset classification or scientific limitation.** The
  assistant reports what the Phase 10–12 work established; it does not re-derive it.
