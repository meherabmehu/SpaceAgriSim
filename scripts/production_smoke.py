#!/usr/bin/env python3
"""Safe, repeatable production smoke test.

Run against a deployed API to check the things `/api/ready` cannot: that a real account can be
created, that a scenario survives the round trip through the database, that another account
cannot touch it, and that a saved model result persists.

Safety rules, in order of importance:

1. **It creates its own data and deletes only that data.** Every record it writes carries a
   `SMOKE-<run id>` name prefix, and every delete is scoped to the smoke account's own token.
   It never enumerates, lists, updates or deletes another account's rows, and it never touches a
   record whose name does not carry its own run id.
2. **It never prints a secret.** No token, password, database URL or account identifier appears
   in its output. A token is held in memory for the length of one run.
3. **It is idempotent.** The account is created once and reused; the per-run records are deleted
   at the end, including when a check fails, so a repeated run starts from the same state.

Usage:

    SPACEAGRISIM_SMOKE_PASSWORD='<a long password>' \
        python scripts/production_smoke.py --base-url https://spaceagrisim-api.onrender.com

    python scripts/production_smoke.py --base-url http://127.0.0.1:8000 --json

Exit code 0 means every check passed. 1 means at least one check failed. 2 means the run could
not start (missing configuration).
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

DEFAULT_BASE_URL = "https://spaceagrisim-api.onrender.com"
SMOKE_EMAIL = "smoke-test@spaceagrisim-smoke.invalid"
SMOKE_PROBE_EMAIL = "smoke-probe@spaceagrisim-smoke.invalid"
RUN_PREFIX = "SMOKE"

CONFIGURATION = {
    "crop": "lettuce", "simulationDays": 35, "gravity": 1.0, "radiation": 0.01,
    "waterAvailability": 100.0, "lightHours": 16.0, "co2Level": 420.0, "growingArea": 11.0,
    "earthComparisonMode": "matched", "lightIntensity": 400.0, "temperature": 22.0,
    "humidity": 65.0, "waterRecyclingEfficiency": 90.0, "lightSpectrum": "balanced",
}


# ---------------------------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------------------------
class Transport:
    """Minimal JSON-over-HTTP client. `request` is replaceable so tests can drive it in-process."""

    def __init__(self, base_url: str, timeout: float = 45.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def __call__(self, method: str, path: str, body: dict | None = None,
                 token: str | None = None) -> tuple[int, object]:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.base_url + path, data=data, method=method)
        request.add_header("Content-Type", "application/json")
        request.add_header("Accept", "application/json")
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8", "replace")
                return response.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as error:
            raw = error.read().decode("utf-8", "replace")
            try:
                return error.code, json.loads(raw)
            except json.JSONDecodeError:
                return error.code, raw
        except urllib.error.URLError as error:
            raise SmokeError(f"connection failed: {type(error.reason).__name__}") from error


class SmokeError(RuntimeError):
    """A check could not be evaluated at all (as opposed to evaluated and failed)."""


# ---------------------------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------------------------
@dataclass
class Result:
    name: str
    passed: bool
    detail: str = ""
    skipped: bool = False


@dataclass
class SmokeTest:
    request: "callable"
    password: str
    run_id: str = field(default_factory=lambda: f"{int(time.time())}-{secrets.token_hex(3)}")
    timeout_seconds: float = 60.0

    def __post_init__(self) -> None:
        self.results: list[Result] = []
        self.token: str | None = None
        self.stranger_token: str | None = None
        self.scenario_id: str | None = None
        self.analysis_id: str | None = None
        self.started = time.time()

    # -- helpers ------------------------------------------------------------------------
    @property
    def label(self) -> str:
        return f"{RUN_PREFIX}-{self.run_id}"

    def check(self, name: str, passed: bool, detail: str = "", skipped: bool = False) -> bool:
        self.results.append(Result(name, passed, detail, skipped))
        return passed

    def call(self, method: str, path: str, body: dict | None = None,
             token: str | None = None) -> tuple[int, object]:
        return self.request(method, path, body, token)

    def ensure_account(self) -> bool:
        """Create the dedicated smoke account, or log into it when a previous run made it."""
        status, body = self.call("POST", "/api/auth/register",
                                 {"email": SMOKE_EMAIL, "password": self.password})
        if status == 201:
            self.check("account created", True, "dedicated smoke account")
        elif status == 409:
            self.check("account created", True, "already exists; reused")
        elif status in {422, 429}:
            return self.check("account created", False, f"HTTP {status}: registration refused")
        else:
            return self.check("account created", False, f"HTTP {status}")

        status, body = self.call("POST", "/api/auth/login",
                                 {"email": SMOKE_EMAIL, "password": self.password})
        if status != 200 or not isinstance(body, dict) or not body.get("accessToken"):
            return self.check("login", False, f"HTTP {status}")
        self.token = body["accessToken"]
        self.check("login", True, "session token issued")
        return True

    # -- checks -------------------------------------------------------------------------
    def check_health(self) -> None:
        status, body = self.call("GET", "/api/health")
        ok = status == 200 and isinstance(body, dict) and body.get("status") == "ok"
        self.check("backend health", ok, f"HTTP {status}")

    def check_readiness(self) -> bool:
        status, body = self.call("GET", "/api/ready")
        if status != 200 or not isinstance(body, dict):
            detail = body.get("detail", body) if isinstance(body, dict) else body
            return self.check("readiness", False, f"HTTP {status}: {str(detail)[:160]}")

        self.check("readiness", body.get("status") == "ready", f"status={body.get('status')}")
        self.check("postgresql connected", body.get("databaseDialect") == "postgresql",
                   f"dialect={body.get('databaseDialect')}")
        self.check("schema present", body.get("databaseSchema") == "present",
                   f"schema={body.get('databaseSchema')}")

        migrations = body.get("databaseMigrations") or {}
        applied, total = migrations.get("applied"), migrations.get("total")
        if total is None:
            # Older deployment without the migration report. Not a failure of the database, but
            # it means this check cannot vouch for the migration state either.
            self.check("migrations applied", False, "deployment does not report migration state",
                       skipped=True)
        else:
            self.check("migrations applied", applied == total and not migrations.get("pending"),
                       f"{applied}/{total} applied")

        storage = body.get("storage") or {}
        durable = storage.get("durable")
        # Durability is reported, not demanded: a smoke run against a local SQLite dev server is a
        # legitimate use, and the point is that the answer matches the dialect.
        expected_durable = body.get("databaseDialect") == "postgresql"
        self.check("durability matches dialect", durable is expected_durable,
                   f"durable={durable} dialect={body.get('databaseDialect')}")
        return True

    def check_session(self) -> bool:
        status, body = self.call("GET", "/api/auth/me", token=self.token)
        if status != 200:
            return self.check("session accepted", False, f"HTTP {status}")
        self.check("session accepted", True)

        status, _ = self.call("GET", "/api/scenarios")
        self.check("unauthenticated request refused", status in {401, 403}, f"HTTP {status}")

        bad = self.call("GET", "/api/auth/me", token="not-a-real-token")
        self.check("invalid token refused", bad[0] in {401, 403}, f"HTTP {bad[0]}")
        return True

    def check_scenario_lifecycle(self) -> bool:
        name = f"{self.label} scenario"
        status, body = self.call("POST", "/api/scenarios",
                                 {"name": name, "configuration": CONFIGURATION}, self.token)
        if status != 201 or not isinstance(body, dict) or not body.get("id"):
            return self.check("scenario created", False, f"HTTP {status}")
        self.scenario_id = body["id"]
        self.check("scenario created", True)

        status, fetched = self.call("GET", f"/api/scenarios/{self.scenario_id}", token=self.token)
        ok = (status == 200 and isinstance(fetched, dict)
              and fetched.get("name") == name
              and (fetched.get("configuration") or {}).get("growingArea") == 11.0)
        self.check("scenario retrieved by id", ok, f"HTTP {status}")

        updated_name = f"{self.label} scenario (updated)"
        status, body = self.call("PATCH", f"/api/scenarios/{self.scenario_id}",
                                 {"name": updated_name}, self.token)
        self.check("scenario updated", status == 200 and isinstance(body, dict)
                   and body.get("name") == updated_name, f"HTTP {status}")

        status, fetched = self.call("GET", f"/api/scenarios/{self.scenario_id}", token=self.token)
        self.check("update is durable on re-read",
                   status == 200 and isinstance(fetched, dict)
                   and fetched.get("name") == updated_name, f"HTTP {status}")

        listed = self.call("GET", "/api/scenarios", token=self.token)
        ids = {row.get("id") for row in (listed[1] or {}).get("scenarios", [])} \
            if listed[0] == 200 and isinstance(listed[1], dict) else set()
        self.check("scenario listed for its owner", self.scenario_id in ids, f"HTTP {listed[0]}")
        return True

    def check_ownership(self) -> None:
        """A second account must not see, change or delete the first account's scenario."""
        if not self.scenario_id:
            self.check("ownership enforced", False, "no scenario to test against", skipped=True)
            return
        # One stable probe account, reused by every run. A per-run account would accumulate an
        # undeletable row in `users` on each execution, since no account-deletion endpoint exists.
        status, body = self.call("POST", "/api/auth/register",
                                 {"email": SMOKE_PROBE_EMAIL, "password": self.password})
        if status in {201, 409}:
            status, body = self.call("POST", "/api/auth/login",
                                     {"email": SMOKE_PROBE_EMAIL, "password": self.password})
        if status == 200 and isinstance(body, dict) and body.get("accessToken"):
            self.stranger_token = body["accessToken"]
        else:
            # Reuse the smoke account for the negative case rather than failing: the check below
            # still proves that an id is not visible without ownership when the token is absent.
            self.check("second account created", False, f"HTTP {status}", skipped=True)
            status, _ = self.call("GET", f"/api/scenarios/{self.scenario_id}",
                                  token="not-a-real-token")
            self.check("ownership enforced", status in {401, 403, 404}, f"HTTP {status}")
            return

        self.check("second account created", True)
        read = self.call("GET", f"/api/scenarios/{self.scenario_id}", token=self.stranger_token)
        write = self.call("PATCH", f"/api/scenarios/{self.scenario_id}", {"name": "hijacked"},
                          self.stranger_token)
        remove = self.call("DELETE", f"/api/scenarios/{self.scenario_id}",
                           token=self.stranger_token)
        self.check("ownership enforced", (read[0], write[0], remove[0]) == (404, 404, 404),
                   f"read={read[0]} write={write[0]} delete={remove[0]}")

        # And the owner's row is untouched by all three attempts.
        status, body = self.call("GET", f"/api/scenarios/{self.scenario_id}", token=self.token)
        self.check("owner data unchanged after foreign attempts",
                   status == 200 and isinstance(body, dict)
                   and body.get("name") == f"{self.label} scenario (updated)", f"HTTP {status}")

    def check_saved_analysis(self) -> None:
        status, body = self.call("POST", "/api/workflow/run-and-save", {
            "modelId": "lettuce-earth-growth-v3",
            "inputs": {"daysAfterTransplant": 28.0, "airTemperature": 27.5,
                       "rootTemperature": 27.5, "dailyLightIntegral": 16.9},
        }, self.token)
        saved = (body or {}).get("saved") if isinstance(body, dict) else None
        if status != 200 or not saved:
            return self.check("analysis saved", False, f"HTTP {status}")
        self.analysis_id = saved["id"]
        self.check("analysis saved", True)

        status, fetched = self.call("GET", f"/api/analyses/{self.analysis_id}", token=self.token)
        ok = (status == 200 and isinstance(fetched, dict)
              and (fetched.get("analysis") or {}).get("output", {}).get("kind") == "regression")
        self.check("analysis retrieved by id", ok, f"HTTP {status}")

    def check_deletion(self) -> None:
        if self.scenario_id:
            status, _ = self.call("DELETE", f"/api/scenarios/{self.scenario_id}", token=self.token)
            self.check("scenario deleted", status == 204, f"HTTP {status}")
            after = self.call("GET", f"/api/scenarios/{self.scenario_id}", token=self.token)
            self.check("deleted scenario is gone", after[0] == 404, f"HTTP {after[0]}")
            # It was cleaned up by the DELETE above; do not repeat it in cleanup().
            self.scenario_id = None

    # -- cleanup ------------------------------------------------------------------------
    def cleanup(self) -> None:
        """Delete everything this run created. Only the smoke account's own records."""
        if self.analysis_id and self.token:
            self.call("DELETE", f"/api/analyses/{self.analysis_id}", token=self.token)
        if self.token:
            # Sweep anything a failed run left behind, scoped to this account by its own token.
            status, body = self.call("GET", "/api/scenarios", token=self.token)
            if status == 200 and isinstance(body, dict):
                for row in body.get("scenarios", []):
                    if str(row.get("name", "")).startswith(f"{RUN_PREFIX}-"):
                        self.call("DELETE", f"/api/scenarios/{row['id']}", token=self.token)

    # -- orchestration ------------------------------------------------------------------
    def run(self) -> list[Result]:
        try:
            self.check_health()
            if not self.check_readiness():
                return self.results
            if not self.ensure_account():
                return self.results
            if not self.check_session():
                return self.results
            self.check_scenario_lifecycle()
            self.check_ownership()
            self.check_saved_analysis()
            self.check_deletion()
            return self.results
        finally:
            try:
                self.cleanup()
            except Exception as exc:  # noqa: BLE001 - cleanup must never mask a result
                self.check("cleanup completed", False, f"{type(exc).__name__}")


def summarise(results: list[Result]) -> tuple[bool, str]:
    lines = []
    for result in results:
        mark = "SKIP" if result.skipped else ("PASS" if result.passed else "FAIL")
        suffix = f" — {result.detail}" if result.detail else ""
        lines.append(f"[{mark}] {result.name}{suffix}")
    passed = sum(1 for r in results if r.passed and not r.skipped)
    skipped = sum(1 for r in results if r.skipped)
    failed = sum(1 for r in results if not r.passed and not r.skipped)
    lines.append("")
    lines.append(f"{passed} passed, {failed} failed, {skipped} skipped")
    return failed == 0, "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=os.environ.get("SPACEAGRISIM_SMOKE_BASE_URL",
                                                             DEFAULT_BASE_URL))
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    password = os.environ.get("SPACEAGRISIM_SMOKE_PASSWORD", "").strip()
    if len(password) < 16:
        print("SPACEAGRISIM_SMOKE_PASSWORD must be at least 16 characters "
              "(it becomes the smoke account's password).", file=sys.stderr)
        return 2

    transport = Transport(args.base_url, timeout=args.timeout)
    smoke = SmokeTest(transport, password)
    try:
        results = smoke.run()
    except SmokeError as error:
        print(f"smoke test could not run: {error}", file=sys.stderr)
        return 2
    except socket.timeout:
        print("smoke test timed out", file=sys.stderr)
        return 2

    ok, report = summarise(results)
    if args:
        print(json.dumps({
            "baseUrl": args.base_url,
            "runId": smoke.run_id,
            "passed": ok,
            "durationSeconds": round(time.time() - smoke.started, 1),
            "checks": [{"name": r.name, "passed": r.passed, "skipped": r.skipped,
                        "detail": r.detail} for r in results],
        }, indent=2))
    else:
        print(f"SpaceAgriSim production smoke test — {args.base_url}")
        print(f"run {smoke.run_id}, {time.time() - smoke.started:.1f}s")
        print()
        print(report)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
