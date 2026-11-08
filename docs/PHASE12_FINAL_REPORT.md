# Phase 12 — final report

Evidence-grounded AI, a complete scientific workflow, and four refusals that are enforced in
code rather than promised in prose.

---

## 1. Merge verification

| Item | Value |
| --- | --- |
| Base | remote `main` = `7957a05` (Phase 11 merge), verified with `git ls-remote` before any work |
| Branch | `feat/phase12-ai-platform-completion` |
| Feature branch HEAD | `c78e7a2` (`docs/phase12-ai-platform-completion`) |
| Feature commits | 7 (`d2e7f4b` baseline doc … `c78e7a2` docs) |
| Merge commit | **`5ccdf08`** — `Merge Phase 12: evidence-grounded AI, scientific workflows, and dataset independence` |
| Remote `main` HEAD | **`5ccdf08e318bf67c8b7f433b9b02f05d05c3cb65`** (`git ls-remote`, and re-verified from a fresh clone) |
| Push type | fast-forward `7957a05..5ccdf08`; **no force-push** |
| Branch-protection bypass | none |
| Remote tree equals local tree | yes (`HEAD^{tree}` identical in a fresh `--depth 1` clone) |

The push required a credential, which the sandbox did not have after an environment reset;
once a token was supplied the branch was pushed first (so the work survived the sandbox
resetting its own `.git` directory mid-session), then merged into `main` and pushed. The
history was rebuilt after that reset, so the commit ids above are the ones that actually
exist on the remote — they were read back with `git ls-remote` and confirmed by cloning the
repository fresh rather than trusted from the local log.

---

## 2. What was built

| Component | Where | Tests |
| --- | --- | --- |
| Evidence corpus + research assistant | `backend/app/evidence.py`, `assistant.py`, `routes/assistant.py` | 38 |
| Registry enrichment (classification, calibration, explanations, supersedes) | `backend/app/research.py` | (in the 38) |
| Scientific workflow + saved analyses + export | `backend/app/workflow.py`, `routes/workflow.py`, `storage.py`, `auth.py` | 32 |
| Dataset explorer and duplicate safeguards | `backend/app/explorer.py`, `routes/explorer.py` | 17 |
| UI: assistant module, scientific status panel, independence panel | `frontend/src/pages/modules/{ResearchAssistant,sciencePanels}.jsx` + 2 pages | 12 browser |
| Demo step | `scripts/demo_phase12.py`, wired into `scripts/demo_phase9.sh` step 7/8 | — |
| Documentation | 11 `docs/PHASE12_*.md` | — |

---

## 3. Acceptance criteria, one by one

| Criterion | Status | Evidence |
| --- | --- | --- |
| Preserve frontend design; no redesign | **Met** | Existing card, pill, badge-row and module-intro components; palette and typography unchanged; one sidebar entry added because the feature needs an entry point |
| No deployment / no production infra | **Met** | Nothing deployed; no host configured; demo runs in-process |
| No fabricated measurements, citations or predictions | **Met** | Every answer sentence is a verbatim quote from a retrieved artifact; 0 of 47 passages fabricated; the renderer refuses an uncited claim |
| Assistant cites title, accession, URL or local reference, model/experiment, limitations | **Met** | `citations[]` carries all of them; `PHASE12_AI_RESEARCH_ASSISTANT.md` §3 |
| Assistant distinguishes measured data from model interpretation | **Met** | `measuredVersusInterpreted` + per-citation `evidenceClass` |
| Assistant refuses evidence it did not retrieve | **Met** | `insufficient` with zero citations; `test_insufficient_evidence_is_reported_rather_than_guessed` |
| Assistant says when evidence is insufficient | **Met** | Same test, plus the "partial" limitation text |
| Prompt-injection defence on retrieved documents | **Met** | Index-time quarantine; retrieval treated as data; 7 injection cases tested |
| No retrieval of secrets | **Met** | Key-pattern screening; corpus is committed artifacts only |
| Permissions enforced | **Met** | Owner-scoped analyses; 404 for another account; 401 before inference on an anonymous save |
| Context size limited / input validation / request limits | **Met** | 400-char question, 5 claims, 47 passages, 64 KiB body, 180 req/min |
| Graceful LLM-provider failure | **Met by construction** | No external provider in the answer path; documented as a deliberate choice rather than an untested fallback |
| No invented OOD threshold | **Met** | `thresholdValidated: false` respected; only schema + physical plausibility checks; stated in the response and in `PHASE12_SIMULATOR_VALIDATION.md` |
| Never present uncalibrated probabilities as calibrated | **Met** | `calibrated: false` on all 8 models; asserted by test |
| OSD-320 and OSD-46 never independent | **Met** | Relation `duplicate-measurement`, excluded from independent counts, 26 → 25 |
| Four-way overlap distinction | **Met** | Closed vocabulary: duplicate-measurement / shared-sample-different-assay / independent / unverified-overlap |
| Not all 8 models presented as NASA-trained | **Met** | Catalogue carries `sourceType`; the UI says "4 of 8" |
| Retired models never offered as inference | **Met** | `runStatus: retired`, `410 retired-model`, marked in the UI |
| Gene models require the real feature schema | **Met** | Family inference; both directions tested |
| Reports/exports match API and artifacts exactly | **Met** | Exports serialise the stored payload; float equality asserted |
| 11 required documents | **Met** | All present, see §5 |
| Final report includes merge commit and verified remote HEAD | **Met for local; remote pending credential** | §1 |
| No force-push, no protection bypass | **Met** | Fast-forward-free history, `--no-ff` merge, single push attempt |
| No regression below the Phase 11 baseline | **Met** | 377 backend (was 291), 40/40 registry, 39 browser (was 27), clean lint and typecheck |

---

## 4. Gates

| Gate | Phase 11 baseline | Phase 12 | Result |
| --- | --- | --- | --- |
| Backend tests | 291 | **377 passed, 1 skipped** (+86) | pass |
| Registry verification | 40/40 | **40/40** | pass |
| Browser tests | 27 | **39 passed** (desktop, tablet, mobile) | pass |
| Lint / typecheck / build | clean | **clean**, build 11.2 s | pass |
| Full demo with deterministic refit | pass | **pass, EXIT=0, 678 s** | pass |
| Fast demo | — | pass, 2.3 s (3.8 s with live API) | pass |
| UI layout change | none | none (panels only + one nav entry) | pass |

The full demo was run end to end in this session, including the refit of both radiation models
from the pinned NASA matrices. As documented in Phase 11, the refit changes only timestamps and
checksums; the regenerated artifacts were reverted and the runtime bundle repackaged, which is
the documented path and which the test suite enforces
(`test_lettuce_v2_is_registered_beside_v1_not_over_it` fails on a stale bundle).

---

## 5. Documents

`PHASE12_BASELINE`, `FEATURE_AUDIT`, `AI_RESEARCH_ASSISTANT`, `AI_WORKFLOWS`,
`SCIENTIFIC_DASHBOARD`, `DATASET_EXPLORER`, `SIMULATOR_VALIDATION`, `SECURITY_REVIEW`,
`PERFORMANCE`, `COMPETITION_DEMO`, `FINAL_REPORT`.

---

## 6. Honest limits of this phase

* **The assistant's claim selection is not always optimal.** For "what future AI training is
  the data ready for?", retrieval correctly puts the training-eligibility audit first, but
  claim composition reaches a different passage and the answer is `partial`. Integrity holds
  (every sentence is quoted and cited); usefulness in that one case does not.
* **Sample-overlap detection is not exhaustive.** OSD-320/OSD-46 has numeric proof; the
  others rest on identifier canonicalisation. A differently numbered duplicate would show as
  `unverified-overlap`, not `independent`, which is the safe direction but not detection.
* **No per-user quota on saved analyses**, only a 200 000-byte payload cap and the global
  request guard.
* **The JWT secret is per-process**, so tokens do not survive a restart; fine locally, stated
  as unsuitable for multi-instance deployment.
* **No external language model**, so there is no paraphrasing and no multi-hop reasoning over
  the corpus; that was a deliberate trade for determinism and auditability.

---

## 7. Bengali summary (সারসংক্ষেপ)

Phase 12-এ প্ল্যাটফর্মে চারটি নতুন স্তর যোগ করা হয়েছে, এবং প্রতিটির মূল্য হলো এটি যা করতে
**অস্বীকার** করে তা-ই:

1. **গবেষণা সহকারী (Research Assistant)** — ৪৭টি যাচাইকৃত অনুচ্ছেদ থেকে উত্তর তৈরি করে, প্রতিটি
   বাক্যের সাথে উৎস (অ্যাক্সেসন, ফাইল রেফারেন্স বা URL), সীমাবদ্ধতা এবং "মাপা তথ্য বনাম মডেলের
   অনুমান" আলাদা করে দেখায়। করপাসে না থাকলে উত্তর দেয় না — স্পষ্টভাবে "প্রমাণ অপর্যাপ্ত" বলে
   অস্বীকার করে, কোনো উদ্ধৃতি ছাড়াই।
2. **বৈজ্ঞানিক কর্মপ্রবাহ (Scientific workflow)** — মডেল বেছে নেওয়া, ইনপুট যাচাই, অনুমান, ব্যাখ্যা,
   সীমাবদ্ধতা ও উৎস একসাথে দেয়। চারটি প্রত্যাখ্যান কাঠামোগতভাবে প্রয়োগ করা: করপাসের বাইরের প্রশ্ন,
   আণবিক মডেলে পরিবেশগত ইনপুট (HTTP 422), শারীরিকভাবে অসম্ভব মান যেমন ৯০০ °C (422), এবং অবসরপ্রাপ্ত
   মডেল (410)।
3. **সংরক্ষিত বিশ্লেষণ (Saved analyses)** — প্রতিটি হিসাব কেবল তার মালিকের; অন্য অ্যাকাউন্টের আইডি
   404 দেয় (403 নয়, যাতে আইডির অস্তিত্ব ফাঁস না হয়)। এক্সপোর্ট করা সংখ্যা API-র সংখ্যার সাথে
   হুবহু মেলে, এবং "এটি মাপা মান নয়" — এই ঘোষণাটি ফাইলের ভেতরেও থাকে।
4. **ডেটাসেট এক্সপ্লোরার** — ২৬টি অ্যাক্সেসন আসলে ২৫টি স্বাধীন গবেষণা, কারণ OSD-320 হলো OSD-46-এর
   দ্বিতীয় ডিপোজিট (৪৪টি অ্যারেকে ২২,৮১০টি প্রোবসেটে সর্বোচ্চ পার্থক্য ০.০)। কোনো অ-যাচাইকৃত জোড়াকে
   "স্বাধীন" বলা হয় না।

সব মিলিয়ে: **377 ব্যাকএন্ড টেস্ট**, **39 ব্রাউজার টেস্ট**, রেজিস্ট্রি **40/40**, পূর্ণ ডেমো সফল।
Phase 12 কখনো ক্যালিব্রেটেড সম্ভাবনা, বৈধ OOD থ্রেশহোল্ড, কিংবা চাঁদ/মঙ্গলে ফসলের ফলন দাবি করে না।

---

## 8. Push and independent verification

```
git push origin feat/phase12-ai-platform-completion   ->  6e31b70..c78e7a2
git merge --no-ff feat/phase12-ai-platform-completion ->  5ccdf08
git push origin main                                  ->  7957a05..5ccdf08
git ls-remote origin refs/heads/main                  ->  5ccdf08e318bf67c8b7f433b9b02f05d05c3cb65
```

Then verified from a **fresh clone**, not from the local repository:

```
git clone --depth 1 https://github.com/meherabmehu/SpaceAgriSim.git
HEAD                       = 5ccdf08e318bf67c8b7f433b9b02f05d05c3cb65
git rev-parse HEAD^{tree}  = identical to the local tree
docs/PHASE12_*.md          = 11 files present
workflow.py, assistant.py, explorer.py, ResearchAssistant.jsx, demo_phase12.py = all present
```

Nothing in Phase 12 is waiting on further work.

> **Credential note.** The token used for this push was supplied in chat, so it should be
> treated as exposed: revoke it in GitHub settings. It was used only for these two pushes, was
> passed through a temporary `GIT_ASKPASS` script rather than written into `.git/config` or any
> committed file, and never appears in the repository.
