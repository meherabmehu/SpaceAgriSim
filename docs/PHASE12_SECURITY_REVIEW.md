# Phase 12 — security review

Scope: everything Phase 12 added (assistant, workflow, analyses, explorer) plus the existing
surface those features now reach. No production deployment was performed, so this is a code
and API review, not a penetration test of a live host.

---

## 1. Threats considered

| # | Threat | Control | Verified by |
| --- | --- | --- | --- |
| 1 | Prompt injection inside a retrieved document | Index-time screening quarantines documents containing instruction patterns; retrieved text is treated as data (sentences are copied, never followed) | `test_phase12_assistant.py` injection cases (`ignore previous instructions`, role tags, `<system>`, `[/INST]`, shell commands), quarantine count in `/assistant/health` |
| 2 | Secret leakage through retrieval | Screening rejects key-like material (API keys, bearer tokens, private keys, `SECRET=`); the corpus indexes only committed artifacts — no `.env`, no settings object, no environment | Secret-pattern tests; corpus audit via `/assistant/corpus` |
| 3 | Unbounded context | 47 passages, ≤ 5 claims, ≤ 400 question characters, 400-character quote truncation, max 20 missing/unexpected feature names echoed | 422 on a 500-character question; `MAX_QUESTION_CHARS` test |
| 4 | Cross-account data access | `analyses.owner_id` is NOT NULL and every read/write helper takes it as its first argument; another account's id returns **404**, so the API is not an existence oracle | Owner-isolation tests for GET, LIST, DELETE and export |
| 5 | Anonymous write | `save: true` without a token → 401 **before** inference; `run-and-save` requires auth | `test_anonymous_caller_cannot_persist_an_analysis` |
| 6 | Input-validation bypass | Pydantic models with `extra="forbid"` and explicit lengths; `analyses` ids are opaque; export format is a closed `Literal` (`json`/`csv`/`md`) | 422 tests for extra fields, malformed bodies, unknown format |
| 7 | Resource exhaustion | Global request guard: 180 req/min/IP, 64 KiB body, 12/min on `/optimize`; analysis payload capped at 200 000 bytes; corpus cached so a request is ~4 ms | Guard tests (unchanged), payload cap |
| 8 | Data tampering through export | Exports serialise the **stored** payload unchanged — no recomputation, so an export cannot disagree with the API | CSV/JSON/MD fidelity tests |
| 9 | Injection into the database | All writes go through SQLAlchemy Core expressions with bound parameters; no string-built SQL | `storage.save_analysis` / `get_analysis` / `delete_analysis` |
| 10 | Rate-limit evasion by authenticated user | The guard buckets per client address, not per token; authenticated routes are additionally protected by token verification | `middleware.py` unchanged |
| 11 | Stale or forged model artifacts | Every artifact is pinned by SHA-256 in the registry; `/workflow/run` reports the digest and a mismatch raises 503 | `verify_model_registry.py` (40/40), workflow tests |
| 12 | Second-order prompt injection from an answer | Answers are rendered as text in the UI; no `dangerouslySetInnerHTML` anywhere in the new components | Code review of `ResearchAssistant.jsx` |

---

## 2. What the assistant will not do

* It will not answer a question it cannot ground — an off-corpus question returns
  `insufficient` with zero citations.
* It will not accept documents as input. The only input is a bounded question string; there
  is no upload path, so "answer from this PDF I attached" is not a request shape that exists.
* It will not reveal an internal prompt or configuration, because neither is in the corpus.
* It will not cite a passage it did not retrieve — the renderer raises `ValueError` on an
  unresolvable citation index.

---

## 3. Authentication and permissions

| Route class | Rule |
| --- | --- |
| Public read (`/models`, `/datasets`, `/science/*`, `/explorer/*`, `/assistant/*`, `/workflow/*` except saves) | No token required; nothing private is exposed |
| Owner-scoped (`/scenarios`, `/analyses`) | Bearer token required; every helper is filtered by `owner_id` |
| Write with side effects (`save: true`) | Requires a valid token; a malformed or expired token is **not** silently downgraded to anonymous |

That last point matters: silently treating a bad token as anonymous would let a caller believe
their analysis was saved. `optional_user` distinguishes "no credentials" from "bad
credentials".

---

## 4. Secrets

No secret is committed. The only key-shaped value in the backend is the JWT signing secret,
which is generated per process (`secrets.token_urlsafe(48)`) with an environment override, and
the documentation says an ephemeral fallback is unsuitable for multi-instance deployment.
Phase 12 added no new secret, no API key, and no paid dependency: there is no external LLM
provider in the answer path, so there is no credential to leak and no silent cost.

---

## 5. Rate limits during the test session

`backend/tests/conftest.py` raises the per-minute budgets for the test session, because one
TestClient address spends far more of the budget than a single user would and adding 49
Phase 12 tests began tripping the guard on unrelated assertions.

The guard itself is still asserted: `test_request_guard_rate_limit_is_retryable` builds a
fresh app with `max_per_minute=1` and checks the 429 with `Retry-After: 60`, and
`test_general_rate_limit_default_is_unchanged_and_operator_configurable` pins the shipped
defaults (180/min general, 30/min auth). Raising the budget in the test session is documented
in the conftest docstring so nobody later mistakes it for a weakened production default.

---

## 6. Residual risk, stated plainly

| Risk | Status |
| --- | --- |
| A retrieved passage could contain an instruction the screener misses | Accepted: the assistant never executes retrieved text, so the worst case is an odd-looking sentence in an answer, not an action |
| Sample-identifier overlap detection is not exhaustive | Accepted and documented: the audit canonicalises identifiers by stripping a trailing array suffix; a differently numbered duplicate would be missed and would be reported as `unverified-overlap`, not `independent` |
| Ephemeral JWT secret invalidates tokens at restart | Accepted for local use; documented as unsuitable for multi-instance deployment |
| No per-user quota on saved analyses | Accepted: payload is capped at 200 000 bytes and the request guard bounds write rate |
| The assistant's claim selection can pick a lower-ranked passage | Known and documented in `PHASE12_AI_RESEARCH_ASSISTANT.md` §5; it degrades answer quality, never integrity, because the claim is still a verbatim quote from a retrieved passage with its citation |
