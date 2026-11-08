# Phase 13 — Security Review

Scope: the whole API surface, with emphasis on what this phase added (narration, pagination,
quotas, the provider endpoint) and the credential incident recorded in the Phase 13 brief.

Automated: `backend/tests/test_phase13_security.py` (26 tests),
`test_phase13_account_limits.py` (24), plus the existing Phase 8/12 authentication and isolation
suites. Nothing in this document is asserted without a test or a measurement behind it.

---

## 1. The exposed credential

The Phase 13 brief states that the Phase 12 GitHub token is exposed and must be treated as
compromised.

**What was done:** the token was never printed, logged, committed, echoed into a file or copied
into any artifact of this work. No credential was written to the workspace. No push was attempted
with it. A probe made at the very start of the engagement returned HTTP 200 for
`/api/github.com/user`, which establishes the token was **still valid and unrevoked** at that
moment; the result is recorded, the token itself is not.

**Secret scan, executed.** A pattern scan for credential-shaped strings was run over the working
tree and over **all 230 revisions** in the repository's history:

```bash
git grep -nIE "(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|gho_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----)" -- .
git grep -lIE "(ghp_|github_pat_|gho_|sk-|AKIA)[A-Za-z0-9_]{20,}" $(git rev-list --all)
```

Both returned only synthetic fixtures in `backend/tests/test_phase12_assistant.py` — dummy strings
(`ghp_` + 36 `a`s, `github_pat_` + 30 `b`s) used as inputs to the corpus secret screener. No real
credential is present in any tracked file or any commit. A scan for the literal token value would
require reading that value in this environment, so it was not attempted; the pattern scan is what
can be done without handling the secret.

**What was not done:** the token could not be revoked, because revoking it requires either the
token itself (an authenticated call, which would be another use of the exposed credential) or
account-level access to GitHub that this environment does not have.

**Consequence:** the Phase 13 merge is blocked at the push step. Everything up to and including a
verified local `--no-ff` merge is complete; the remote `main` HEAD remains
`4a09de3`. This is documented as a blocker in `docs/PHASE13_FINAL_REPORT.md` rather than worked
around.

**Required from the owner, through a secure channel and not in chat:**

1. Revoke the Phase 12 token at GitHub → Settings → Developer settings → Personal access tokens.
2. Create a fine-grained token limited to `meherabmehu/SpaceAgriSim`, with `Contents: read/write`
   only, the shortest practical expiry, and no workflow, package or admin scope.
3. Provide it through the host's secret mechanism (environment injection, credential helper or a
   GitHub App installation token) — never pasted into a conversation or a repository file.
4. Optionally run `git log -p --all -S '<token prefix>'` locally to confirm the history is clean;
   that check needs the value, so it belongs with the owner.

## 2. Authentication and session handling

| Control | Behaviour | Test |
|---|---|---|
| Token signing | HS256 with a server secret; `sub`, `jti`, `iat`, `exp` required to decode | `test_phase13_account_limits.py` |
| Secret provenance | Must be set in production; validated for length, entropy and known placeholders; ephemeral per-process fallback only in development | `test_production_requires_an_explicit_secret` and 4 more |
| Rotation | `auth_secret_previous` keeps old tokens valid during a rotation window; signing always uses the current secret | `test_rotation_window_accepts_the_previous_secret` |
| Expiry | Distinguished from a bad signature and reported as such | `test_expired_token_is_refused_with_an_expiry_message` |
| Revocation | `jti` recorded on logout; reused tokens rejected | `test_revoked_token_cannot_be_reused_after_logout` |
| Malformed input | Missing, empty, wrong-scheme, non-JWT, unsigned and tampered tokens all return 401 with `WWW-Authenticate`; **none is treated as anonymous** | `test_malformed_authorization_is_refused_*` |
| Algorithm confusion | `alg: none` and foreign-key tokens rejected | `test_algorithm_confusion_is_rejected` |
| Enumeration | Login failure is identical for a wrong password and a non-existent account | `test_failed_login_does_not_reveal_whether_an_account_exists` |

Passwords are hashed with Argon2. Email normalisation rejects malformed addresses and caps length
at 254 characters.

## 3. Authorisation and isolation

Every saved-analysis accessor takes `owner_id` from the token, never from the request. Another
account's analysis id returns **404, not 403**, so the API is not an existence oracle.

Covered by: `test_saved_analysis_is_invisible_to_another_account`,
`test_export_of_another_account_analysis_is_not_found`,
`test_deleting_another_account_analysis_is_not_found_and_leaves_it_intact`,
`test_pagination_cannot_be_used_to_read_another_account_rows`,
`test_account_deletion_is_scoped_to_the_caller`.

## 4. Resource limits and abuse resistance

| Limit | Value (default) | Enforcement point |
|---|---|---|
| Request body | 64 KB | `RequestGuard` middleware |
| Request rate | 180/min general, 30/min auth, 12/min optimize | middleware, per address and bucket |
| Assistant question | 400 characters | request model + middleware |
| Assistant context | 2 previous questions, each length-checked | request model |
| Analysis payload | 200 KB (route) / `max_analysis_bytes` (storage) | route then transaction |
| Analyses per account | 200 | inside the write transaction |
| Analyses bytes per account | 20 MB | inside the write transaction |
| Page size | 50, server-capped | storage |

Unknown request fields are rejected (`extra="forbid"`) rather than ignored, so a client cannot
believe it set something that was silently dropped. Oversized and non-numeric inputs are 422;
over-limit payloads are 413; over-quota saves are 409 with the count and limit in the body.

Quota accounting is serialised per account: a no-op `UPDATE` on the owner row takes a row lock in
PostgreSQL and the database write lock in SQLite before the count is read, so two concurrent saves
cannot both pass the same check. `test_concurrent_saves_never_exceed_the_limit` runs six concurrent
saves against a limit of three and asserts three are stored.

## 5. Injection

**SQL** — all statements are SQLAlchemy constructs with bound parameters; no string interpolation
of user input reaches the database. Identifiers are validated as UUID-shaped or 404, exercised by
`test_sql_and_path_traversal_in_identifiers_return_not_found`.

**Prompt injection** — the assistant is not a prompt. Questions the corpus cannot ground return
`insufficient` with no claims. When optional narration is enabled, injection-shaped input is
detected before any provider call and the deterministic answer is returned
(`test_injection_question_is_refused_and_never_narrated`, and 6 tests in `test_phase13_llm.py`).
The model is never shown the corpus, only numbered claims, so there is nothing else for it to draw
from; its output is then validated for untraceable accessions, quantities, uncited sentences and
forbidden assertions.

**Content injection in evidence** — retrieved passages are treated as data. The narration prompt
delimits them and the system prompt states that text inside `<question>` is untrusted input.

## 6. Secrets and logging

* The auth secret and the optional LLM API key are read from the environment only. No value is
  hardcoded, and `Settings.auth_secret` is declared `repr=False` so it cannot appear in a
  traceback or a debug print of the settings object.
* `llm.redact()` strips bearer tokens, `api_key=` patterns and GitHub-shaped strings from any
  message that could reach a log or a response.
* `GET /api/assistant/provider` reports `apiKeyConfigured: true/false` and nothing else.
* Errors returned to clients are fixed strings or validated messages; no traceback, SQLAlchemy
  detail or internal identifier reaches them, asserted by
  `test_quota_errors_do_not_leak_internal_state`.
* `test_no_endpoint_echoes_a_configured_secret` plants a marker secret and checks six endpoints
  including the OpenAPI schema; `test_logs_contain_no_token_or_secret` inspects captured log
  records.

## 7. Dependencies and transport

* CORS origins must be explicit; wildcards are rejected at settings validation, and non-local
  origins must use HTTPS.
* No new runtime dependency was added in Phase 13. The optional LLM provider uses the standard
  library's `urllib`, deliberately, to avoid pulling a vendor SDK (and its supply chain) into a
  service that is fully functional without it.
* Security headers, compression and HTTPS termination remain a deployment concern; see
  `docs/PHASE13_PRODUCTION_READINESS.md`.

## 8. Residual risks

1. **The Phase 12 token may still be active.** Until the owner revokes it, the exposure stands.
   This is the highest-severity item in this document and it is outside this environment's control.
2. **Rate limiting is per process.** Two workers behind a shared edge each hold their own budget;
   a distributed limiter belongs at the deployment edge.
3. **Token revocation stores `jti` rows that are never pruned.** Correct but unbounded; a periodic
   delete of expired entries is the fix.
4. **No MFA and no password-complexity policy beyond length checks.** Acceptable for a research
   demonstration, not for a public service holding personal data.
5. **A stolen unexpired token is valid until expiry or logout.** Token lifetimes are 60 minutes by
   default; shortening them is an operator decision documented in production readiness.
