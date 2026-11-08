# Competition Package (General, Not a Verified Submission)

> **Status.** This is a general competition-ready package assembled from measured project results.
> No official rulebook, category definition or judging rubric was supplied, so nothing here is
> tailored to one, and this is **not** a submitted entry. Team name, contact details, submission
> deadline and category must be filled in by the owner before any official use.

Every number below is reproducible from this repository. Where something is not measured, it says
so.

---

## 1. One-paragraph overview

SpaceAgriSim is an open, auditable research platform for space-crop science. It combines a
transparent mechanistic simulator of crop growth and life support with an AI layer that is built
the other way round from most: instead of a language model producing plausible text about plants,
a retrieval system finds what 231 NASA OSDR studies actually record, quotes it, cites it — and
refuses to answer when the evidence is not there. Every model in the platform is accompanied by its
provenance, its validation scheme, its limitations and an honest statement of what it cannot do.
The result is a system that a plant scientist can check line by line, and that a judge can try to
break in a browser.

## 2. The problem

Space agriculture claims are easy to make and hard to verify. Three failures recur in this space:

1. **Numbers without provenance.** A yield figure presented as a prediction when it is an
   assumption, or a model score presented without the split it was measured on.
2. **Models without domains.** A classifier trained on Arabidopsis microarray data being read as a
   statement about crop productivity in lunar gravity.
3. **Assistants that always answer.** A language model asked "what crop yield will this classifier
   predict on the Moon?" will produce something confident and wrong, because nothing in its pipeline
   knows the capability does not exist.

## 3. The solution

**A simulation you can audit.** The mechanistic engine is parameterised by documented assumptions
with stated units and ranges, and every response carries `nasaValidated: false` and a null
confidence interval. Boundaries are tested at every parameter limit: physically coherent output, no
guaranteed yields, no planetary measurements.

**Models with their paperwork attached.** Eight registered models, each with a checksum-verified
artifact, recorded provenance, a validation scheme, a baseline it must beat, calibration status and
limitations. One is retired as an unsupported prediction and cannot be run from the interface; its
numbers (−0.55, −0.58 R², worse than the training mean) are published rather than removed.

**An assistant that refuses.** 47 curated evidence passages, per-sub-question retrieval, and a claim
that is only supported if its quote is a verbatim span of the cited evidence. Unsupported premises
are refused with the recorded statement that the capability does not exist.

**A workflow that ends in a file.** Evidence → model selection → validation → inference →
interpretation → saved analysis → export, with the exported CSV carrying a header stating that the
numbers are model output and not a measurement.

## 4. AI methodology

| Component | Approach | Why this and not the obvious alternative |
|---|---|---|
| Question planning | Rule-based decomposition: entity extraction, comparison split, conjunction split, pronoun-led follow-ups | Deterministic and inspectable; a planner that can hallucinate a sub-question could hallucinate a question |
| Retrieval | BM25 over 47 verified local passages, per sub-question, entity-scoped boosting | 1.24 ms median; a vector store would add infrastructure and reduce auditability at this corpus size |
| Composition | Extractive: each claim is a sentence from a retrieved passage with a citation index | The only way to guarantee no invented sentence is to not generate sentences |
| Refusal | False-premise detection + critical-phrasing guard | "Why can't it predict Mars yield?" is a real question and must stay answerable |
| Narration (optional) | Provider sees only numbered claims, never the corpus; output validated for untraceable accessions, quantities, uncited sentences and forbidden assertions | Structural boundary, not a prompt instruction; disabled by default |
| Verification | Benchmark of 32 items, exact substring support check | No semantic-similarity credit: a true paraphrase that is not in the document counts as unsupported |

## 5. Validation

| What | How | Result |
|---|---|---|
| Assistant | 32-item benchmark, 9 categories, re-scored against the Phase 12 commit under the same scorer | status accuracy **0.750 → 1.000**; citation hit **0.960 → 1.000**; 92 claims, **0 unsupported**; every item met its expectation |
| Refusals | Off-corpus, false-premise, and injection items | all refused correctly; no claim emitted |
| Models | Read-only artifact audit, checksums recomputed from disk | 8/8 audited, 114 checks, 0 failures, **17 documented gaps** |
| Dataset integrity | OSD-320 vs OSD-46 duplication finding | 44 arrays, 22,810 probesets, minimum correlation 1.000000, max absolute difference 0.0 — the accession is barred as independent evidence |
| Simulator | Invariants + boundary sweeps + language checks | 47 tests; mass balance, stoichiometry and area scaling hold; no guaranteed-yield phrasing anywhere |
| Security | 26 new tests + existing suites | cross-account isolation, malformed/tampered/expired tokens, quotas under concurrency, no secrets in responses or logs |
| Frontend | Playwright, 3 viewports | 69 tests: shell, assistant, radiation, workflow, accessibility |

## 6. Provenance

Every answer names its source: a NASA OSDR accession with a URL and a local artifact, an audit
finding with the numbers behind it, or a model card with its training scheme. Datasets are
distinguished as *registered* versus *downloaded* — 19 in the packaged manifest, 26 browsable in the
explorer — and the interface does not conflate them. The most important provenance finding is
negative: OSD-320 duplicates OSD-46 exactly, so a "replication" built on both would be an artefact.

## 7. Architecture

```
React 19 + Vite (existing design system preserved)
   │  hash-routed workspace, three viewports, no redesign
   ▼
FastAPI  ── RequestGuard (rate, body size) ── observability counters
   ├── simulation engine      mechanistic, assumptions-2.0, no fabricated physics
   ├── model platform         registry → checksums → validation → inference → interpretation
   ├── evidence layer         BM25 over 47 curated passages, no network at request time
   ├── assistant              planning → retrieval → extraction → citation gate → refusal
   ├── narration (optional)   provider + validator, deterministic fallback
   └── persistence            SQLite/PostgreSQL, owner-scoped, quota-enforced in-transaction
```

## 8. Features a judge can try

1. Ask *"Compare the findings of OSD-314 and OSD-346"* — two accessions cited, three retrievals.
2. Ask *"What crop yield will the OSD-46 classifier predict on the Moon?"* — a refusal, not an
   answer, quoting the recorded limitation.
3. Ask *"Why can the lettuce model not predict Mars crop yield?"* — answered, because it is a
   question about a limitation.
4. Open the workflow, select the retired mizuna model — it cannot be selected, and the reason is on
   the screen.
5. Run a lettuce prediction, save it, export the CSV, read the header.
6. Simulate the Moon, then look for a guaranteed yield — there is none, and the provenance block
   says so.

## 9. Limitations — stated, not hidden

* No model here is validated on an independent study. Every one is `trained-exploratory`.
* Neither radiation classifier states whether its probabilities are calibrated; no calibration
  analysis exists for either (high-severity gap in the audit).
* Per-artifact licences are not recorded for 5 of 8 models.
* The assistant's benchmark was written by the same author as the fixes; 32 items is small.
* The narration layer has never been run against a real provider. Its guards are tested; its
  quality is unknown.
* The simulator is uncalibrated. It is a transparent estimate, not a forecast.
* Nothing was deployed. Performance figures are in-process measurements.

## 10. Security posture

Bearer-token auth with Argon2 passwords, signed-token rotation, owner-scoped data access returning
404 rather than 403 for another account's id, quotas enforced inside the write transaction,
`extra="forbid"` request models, injection-shaped questions never reaching a provider, and no secret
in any response, error or log — each with a test. One open item outside this environment's control:
a previously exposed GitHub token must be revoked by the owner.

## 11. Roadmap

1. **Independent validation** of at least one model on a held-out study — the single change that
   would most improve the scientific claim.
2. **Calibration analysis** for both radiation classifiers, then a documented statement on their
   cards.
3. **Licence capture** per artifact from upstream data policies.
4. **Provider benchmarking** of the narration layer against the same 32-item set before it is ever
   enabled by default.
5. **Response-shape work** on `/api/datasets` (pagination or field selection) — the measured
   remaining performance cost.
6. **Distributed rate limiting and a pruned revocation table** ahead of any real deployment.

## 12. Three-minute script

> **[0:00]** "A model trained on Arabidopsis microarray data cannot tell you how much lettuce the
> Moon will grow. Ask a normal AI assistant and it will try anyway. This platform is built to
> refuse."
>
> **[0:20]** Open the research assistant. Type: *What crop yield will the OSD-46 classifier predict
> on the Moon?* The answer comes back *partial*, with `unsupported-premise`, quoting the model card:
> *"Never predicts yield, biomass, survival or crop productivity."* Not a disclaimer — the exact
> recorded sentence, with its citation.
>
> **[0:50]** Now: *Compare the findings of OSD-314 and OSD-346.* Two accessions, both cited, three
> retrievals, and the answer tells you the second one's gravity signal is confounded with flight
> run — because the audit found that, and the assistant can only quote what was found.
>
> **[1:20]** The measurement behind this: a 32-item benchmark, scored against the previous version
> of the same system under the same scorer. Status accuracy went from 0.750 to 1.000, and across 92
> claims, zero are unsupported — where "supported" means the sentence is a verbatim substring of the
> cited evidence. No similarity credit.
>
> **[2:00]** Open the scientific workflow. Try to select the retired mizuna model — you can't, and
> the reason is on the screen: R² of −0.55 against a training mean. Run a lettuce prediction, save
> it, export the CSV. Its first line says these are model outputs, not measurements.
>
> **[2:40]** That is the whole idea: not an AI that sounds like a scientist, but a system that shows
> its evidence, states its gaps — 17 of them, two high severity — and refuses the rest.

## 13. Five-minute script

> **[0:00–0:40] The problem.** Space agriculture attracts confident numbers. Three are common:
> yields presented as predictions when they are assumptions; classifiers read as if they measured
> productivity; and assistants that always answer. Each is a failure of provenance, not of
> modelling.
>
> **[0:40–1:30] The evidence layer.** 231 OSDR studies were swept; 47 curated passages survived into
> the corpus, each with an accession, a URL, a local artifact and its limitations. Retrieval is BM25
> over those passages — 1.24 ms median — because at this size a vector store buys nothing and costs
> auditability.
>
> **[1:30–2:20] The assistant.** A question is planned before it is answered: entities extracted,
> comparisons split into one retrieval per accession, conjunctions split only where both halves
> stand alone, pronouns resolved against the previous turn. Claims are selected hop-first so a
> two-part question cannot be answered from one half. A named entity that no retrieved passage
> mentions becomes a visible coverage gap.
>
> **[2:20–3:00] The refusal.** False-premise detection catches questions that assume a capability
> the project does not have, and answers them with the recorded statement that it does not —
> partial, `unsupported-premise`, and the limitation leading. Critically, "why can't it?" is exempt:
> a question about a limitation is the question the corpus is best at answering.
>
> **[3:00–3:40] The measurement.** 32 items, 9 categories, scored against the previous release under
> one scorer: status accuracy 0.750 → 1.000, citation hit 0.960 → 1.000, 92 claims with zero
> unsupported. The benchmark also has a support check with no tolerance — a true paraphrase not
> present in the document counts as unsupported.
>
> **[3:40–4:20] The models.** Eight artifacts, checksummed and audited read-only: 114 checks, 0
> failures, and 17 documented gaps that are published rather than patched — including that neither
> radiation classifier states whether its probabilities are calibrated. One model is retired as an
> unsupported prediction and cannot be run.
>
> **[4:20–4:50] The workflow and the export.** Evidence, selection, validation, inference,
> interpretation, save, export — and the exported file says what it is.
>
> **[4:50–5:00] Close.** Everything here is reproducible: `scripts/evaluate_assistant.py`,
> `scripts/audit_models.py`, 535 backend tests, 69 browser tests across three viewports. The claim
> is not that this predicts crops on Mars. It is that every statement it makes can be traced — and
> the ones it cannot trace, it does not make.

## 14. Anticipated Q&A

**"Is this actually an AI system, or a search engine with a chat box?"**
Both, deliberately. Retrieval plus extraction is the AI layer; the refusal logic, question
decomposition and multi-hop composition are what make it more than search. The optional narration
layer exists and is disabled by default because it has not been measured — enabling an unmeasured
generator over a measured extractor would be a downgrade.

**"Your assistant just quotes documents. Where is the intelligence?"**
In deciding what to retrieve, in splitting a comparison into two retrievals so one side cannot
vanish, in knowing which questions are unanswerable, and in refusing them. A system that always
produces fluent text is not more intelligent; it is less honest.

**"What accuracy do your models have?"**
Reported per model, with the split they were measured on, and none of them is independent-study
validated. The lettuce v2 model has R² 0.87 under leave-one-experiment-out CV across 4 experiments;
the mizuna harvest model has R² −0.333, which is worse than a baseline, and that is published.

**"Can this predict crop yield on the Moon?"**
No. No dataset in the repository pairs partial gravity with a crop-production measurement, the
simulator is an uncalibrated estimate, and the classifiers measure experimental context. This is
enforced in code, in tests, and in the assistant's refusal path.

**"How do I know the assistant isn't making things up?"**
Every claim carries a citation index and a verbatim quote, and the benchmark rejects any claim whose
quote is not a literal substring of the cited evidence — including the limitations attached to the
cited artifact. 92 claims, zero unsupported.

**"What is your biggest weakness?"**
Two. The models are exploratory and none has independent-study validation; and two classifiers
document no calibration status. Both are in the audit artifact and both are on the roadmap rather
than in a footnote.

**"What did you build versus what did you reuse?"**
The evidence layer, the assistant, the model platform, the workflow and the audit tooling are this
project's. Standard open-source libraries (FastAPI, React, scikit-learn, SQLAlchemy, recharts) are
used as libraries; no model, dataset or benchmark score is borrowed or claimed as our own.

**"Why should this be trusted over a demo that shows higher numbers?"**
Because every number here can be regenerated by a command in the repository, against a fixed item
set, with the failing cases visible. A higher number that cannot be reproduced is not evidence.
