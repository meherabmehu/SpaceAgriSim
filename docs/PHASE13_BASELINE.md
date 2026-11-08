# Phase 13 — baseline

Recorded from the repository itself on branch `feat/phase13-final-ai-and-competition-readiness`.
Every number below was produced by running a command, not by reading the Phase 12 report.

---

## 1. Remote state at the start of Phase 13

```
git ls-remote origin refs/heads/main
  4a09de38bfce666d17e3c4f33821f0dc60b7837c   refs/heads/main
```

The two commits cited in the Phase 12 report are both present in history and are ancestors of
remote `main`:

| Reported | Present | Role |
| --- | --- | --- |
| `5ccdf08` | yes | `Merge Phase 12: evidence-grounded AI, scientific workflows, and dataset independence` |
| `1b07d12` | yes | documentation commit that followed the merge |
| `4a09de3` | yes | actual remote HEAD (one further report commit) |

Remote HEAD was therefore **not** assumed from the report: it was read with `git ls-remote` and
the two quoted commits were confirmed as reachable objects (`git cat-file -t`).

## 2. Credential state (first priority)

Phase 12 disclosed a GitHub personal access token in chat and it was used for that phase's
pushes. Phase 13 begins by checking whether it was revoked:

```
curl -H "Authorization: Bearer <phase 12 token>" https://api.github.com/user
  -> HTTP 200      (authenticated as the repository owner)
```

**The token is still live.** It was never revoked. Consequences, applied for the whole phase:

* it is **not used** for any Phase 13 operation, including the merge;
* it is not printed, logged, written to any file, or committed;
* every Phase 13 result below is produced and verified **locally**;
* the merge and push are prepared exactly as specified and blocked on a credential supplied
  through a secure mechanism — see `PHASE13_SECURITY.md` §1 and `PHASE13_FINAL_REPORT.md` §8.

A history scan for accidentally committed secrets is reported in `PHASE13_SECURITY.md`.

## 3. Working-tree restoration

The sandbox had again reset its `.git` directory to the Phase 8 merge (`9669553`) with ~177
modified files, while the tracked content of remote `main` already contained every Phase 12
file. Rather than replay stale copies, the tree was reset to the verified remote commit:

```
git fetch origin
git checkout -f -B main origin/main      -> 4a09de3, 0 dirty files
git switch -c feat/phase13-final-ai-and-competition-readiness
```

## 4. Reproduced baseline gates

| Gate | Phase 12 report | Reproduced in Phase 13 | Match |
| --- | --- | --- | --- |
| Backend tests | 377 passed, 1 skipped | **377 passed, 1 skipped** (18.2 s) | yes |
| Registry checks | 40/40 | **40/40** | yes |
| Models registered | 8 | **8** | yes |
| Datasets | 19 in manifest, 26 in explorer universe | **19 / 26** | yes |
| Corpus passages | 47 | **47** (20 datasets, 8 models, 10 findings, 6 methodology, 3 classification) | yes |
| Playwright | 39 | 39 (re-run in §6 of the final report) | yes |
| Lint / typecheck / build | clean | clean | yes |
| Production deployment | none | none | yes |

Runtime bundle regenerated before the run (`scripts/package_runtime_data.py` → 41 assets), because
a stale bundle produces two spurious failures that are not code defects.

## 5. What was actually in the tree at baseline

| Area | State at Phase 13 start |
| --- | --- |
| Evidence corpus | 47 passages, 0 quarantined, BM25 with coverage scaling, joint-match and specificity rules |
| Assistant | extractive, single retrieval pass, 8 intents, two evidence floors, `grounded`/`partial`/`insufficient` |
| Workflow | `/workflow/{models,compatible,validate,run,run-and-save}`, input-family inference, physical limits, 410 for retired models |
| Analyses | owner-scoped table, `json`/`csv`/`md` export from the stored payload |
| Explorer | four-way relation vocabulary, 26 accessions → 25 independent studies |
| Auth | JWT, per-process `secrets.token_urlsafe(48)` secret, `optional_user` |
| Simulator | deterministic, Phase 7 calibrated, unchanged since |
| Frontend | 11 workspace modules, 39 browser tests, three viewports |

## 6. Baseline weaknesses carried into Phase 13

These are the gaps Phase 13 exists to close. Each is stated as observed behaviour, not opinion:

1. **Single-pass retrieval.** A comparison question retrieves one side. `"Compare the findings of
   OSD-314 and OSD-346"` returns OSD-314 material only; the second accession is never fetched
   because the BM25 query is issued once.
2. **No decomposition.** Conjunctive questions ("why did X fail **and** what would validate it")
   are scored as one bag of words, so one half of the question dominates the ranking.
3. **No coverage check.** Nothing verifies that every entity named in the question was actually
   answered, so a one-sided answer could still be labelled `grounded`.
4. **Claim selection can pick a lower-ranked passage.** Observed on
   "What future AI training is the data ready for?" in Phase 12 (retrieval correct, claim
   different).
5. **No assistant evaluation harness.** Answer quality was checked by an ad-hoc 12-question
   sweep, not by a repeatable benchmark with recorded metrics.
6. **No follow-up support.** A pronoun in a second question is treated as a stopword.
7. **Per-process JWT secret.** Tokens die on restart; suitable for one process only.
8. **No per-user storage quota.** A saved analysis is capped at 200 000 bytes, but nothing limits
   how many a single account can create.
9. **No pagination** on `GET /api/analyses`.
10. **No optional-LLM abstraction**, and therefore no way to evaluate whether one would help.

## 7. Constraints carried forward

* No production deployment of any kind.
* UI design preserved: same palette, type scale, card and pill components, navigation order.
* No new scientific claim: nothing below changes a model metric, a calibration number, or a
  classification. `verify_model_registry.py` remains the gate at 40/40.
* OSD-320 is never counted as an independent study.
* No retired or excluded model is re-enabled.
