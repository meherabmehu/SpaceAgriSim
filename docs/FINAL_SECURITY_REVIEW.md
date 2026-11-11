# Final security review

Two things were done here that had not been done before in this repository: the application code was
scanned with a static analyser as part of the build, and the LLM client's outbound URL was validated.
Everything else in this document is a re-verification of controls established in earlier phases, with
the evidence named. Nothing was weakened.

## 1. Result summary

| Check | Command | Result |
|---|---|---|
| Static analysis, application code | `bandit -q -r backend/app` | **0 unsuppressed findings** — 6 raw findings: 1 fixed in code, 5 reviewed and marked on the line that raised them (§3) |
| Python dependency audit | `pip-audit -r backend/requirements.txt -r backend/requirements-dev.txt` | no known vulnerabilities |
| JavaScript dependency audit | `npm audit --audit-level=high` | 0 vulnerabilities (312 dependencies: 45 prod, 267 dev) |
| Secret handling | code read + `/api/assistant/provider` test | API key never echoed; asserted by `test_provider_endpoint_describes_guards_without_secrets` |
| Tests | SQLite 1 242 passed / 23 skipped; PostgreSQL 17.11 1 265 passed / 0 skipped | green |

`bandit` is now a CI step that fails on **any** finding, not on a severity floor. The floor was
deliberately not used: five of the six raw findings are false positives that are individually marked,
so a sixth appearing is a signal instead of noise.

## 2. Fixed: the LLM endpoint was passed to `urlopen` unvalidated

**Finding** `backend/app/llm.py`, `HttpProvider._post`: `urllib.request.Request(self._config.endpoint)`
with no scheme check (bandit B310, medium).

**Consequence** The endpoint is operator configuration, not user input, so this is not a remote attack
path. It is still a real defect: `urlopen` opens `file:`, `ftp:` and anything else its handler table
knows. A deployment whose `SPACEAGRISIM_LLM_ENDPOINT` lost its `https://` — or was set to a path — would
read a file from the container and feed its contents back as a "model completion", and that text is
then subject to the citation validator rather than to a filesystem check.

**Fix**

```python
ALLOWED_SCHEMES = ("http", "https")

def _validated_endpoint(self) -> str:
    endpoint = (self._config.endpoint or "").strip()
    scheme = urllib.parse.urlsplit(endpoint).scheme.lower()
    if scheme not in self.ALLOWED_SCHEMES:
        raise LLMUnavailable(...)
    return endpoint
```

called from `complete()` **and** from `_post()`. `complete()` is the important one: a host or a test can
inject a transport and never reach `_post`, so the refusal has to belong to the public entry point.

**Verification** `backend/tests/test_phase13_llm.py`:
* `test_http_provider_refuses_a_non_http_endpoint` — four endpoints (`/etc/passwd`,
  `file:///etc/passwd`, `ftp://…`, empty) each raise `LLMUnavailable`, and the injected transport
  records zero calls;
* `test_http_provider_accepts_https_and_http` — both allowed schemes still work, so the guard is not
  simply blocking everything.

Both were written first against the old code path and failed for the right reason (the injected
transport bypassed the in-`_post` check), which is why the check lives in `complete()` too.

## 3. Reviewed, not defects — the five marked findings

Each carries a `# nosec <id>` on the line that raised it plus an explanatory comment; the reason is
repeated here so the marker is not the only record.

| File:line | Rule | Finding | Why it is not a defect |
|---|---|---|---|
| `app/llm.py:250` | B310 (`urlopen`) | see §2 | The scheme is validated two lines above, in a function with its own test. The marker records that the review happened at exactly that call. |
| `app/storage.py:482` | B108 (temp directory) | `path.startswith("/tmp")` | A **string comparison** against the configured SQLite URL used to tell the operator whether their data survives a redeploy. No file is created under `/tmp` here. |
| `app/storage.py:725` | B105 (hardcoded password) | `"password_hash": password_hash` | Bandit matches the column *name*. The value is the Argon2 hash the caller produced; it is never a literal. |
| `app/workflows/light_stress.py:253` | B311 (PRNG) | `random.Random(BOOTSTRAP_SEED + len(values))` | A percentile bootstrap whose intervals must be a function of the data and not of when it ran. Determinism is the requirement; nothing secret is drawn. |
| `app/workflows/light_stress.py:264` | B311 (PRNG) | same, for the paired difference bootstrap | same |

Bandit prints a `nosec encountered … but no failed test` warning for the three multi-line nodes
(storage.py ×2, light_stress.py ×1). That is bandit's own bookkeeping for markers that sit inside a
multi-line expression; it is visible in the log rather than suppressed, and the gate's exit code is
driven by findings, not by these lines.

## 4. Re-verified controls (unchanged this pass)

| Area | Implementation | Evidence |
|---|---|---|
| Password storage | Argon2 via `argon2.PasswordHasher` | `test_auth.py`, `test_phase13_security.py` |
| Token authentication | signed JWT; `jti` checked against a revocation table on every request | revocation and expiry tests |
| Token revocation | `storage.token_is_revoked` + admin revocation list | auth tests |
| Share links | per-scenario cap, expiry, wholesale revoke | `test_phase12_*`, PostgreSQL persistence suite |
| Ownership / authorisation | every scenario and analysis read, write and delete is scoped to the caller | both suites, including `test_ownership_is_enforced_on_read_update_and_delete` |
| Rate limiting | per-address per-minute budgets, separate auth and general buckets | security tests; budget raised **only** in the Playwright web server, so the guard stays live in production |
| Proxy handling | `trusted_proxy_hops` defaults to 0; `X-Forwarded-For` ignored unless an operator opts in | middleware default and docstring |
| Secret handling | ephemeral per-process secret when `SPACEAGRISIM_AUTH_SECRET` is unset, with a startup warning; placeholder and low-entropy values rejected | `_validate_auth_secret` |
| CORS | explicit `allow_origins` from settings, never `*` | `main.py` |
| Security headers | `nosniff`, `x-frame-options: DENY`, `referrer-policy: no-referrer`, `permissions-policy` denying geolocation/microphone/camera, `x-request-id` on every response, `cache-control: no-store` on auth and scenario responses | `middleware.py` |
| SQL injection | SQLAlchemy Core/ORM with bound parameters; no string-built SQL | code read; the same statements pass on PostgreSQL |
| Error disclosure | database exceptions classified and logged with a request id, re-raised without the DSN | `test_connection_failure_is_reported_without_leaking_credentials` |
| Request validation | Pydantic models with bounded fields on every write; unknown transcriptomic features rejected with 422 | auth and radiation 422 tests |
| Workers | `--workers 1` in `render.yaml` and the `Dockerfile`, because the rate limiter and the SQLite path are in-process | configuration read, not changed |

## 5. What this review does not cover

* **No penetration test was run.** These are code-level controls with test evidence, not an
  adversarial assessment.
* **No dependency is pinned to a hash.** `pip-audit` matches version numbers against the advisory
  database; it cannot detect a compromised release that has no advisory yet.
* **The rate limiter is in-process**, so it is correct only at `--workers 1`. That is why the worker
  count is configuration and not a tuning knob: raising it without shared rate-limit storage would
  multiply every budget by the worker count. This constraint is unchanged and documented in
  `docs/POSTGRESQL_OPERATIONS.md`.
* **Secrets in the repository** were searched for by pattern and by the test that asserts the API key
  is not echoed; no credential, token or private key is present in any tracked file. The delivery used
  a PAT supplied inline for push and never written to disk.
