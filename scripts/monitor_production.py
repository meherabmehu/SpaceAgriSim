#!/usr/bin/env python3
"""Lightweight production monitor for the deployed SpaceAgriSim API.

Three public endpoints already exist and are cheap to poll:

  * ``/api/health``  - liveness only; green even when the database is unreachable.
  * ``/api/ready``   - the one that matters: database dialect, schema, migrations, pool, storage.
  * ``/api/metrics`` - per-process counters (requests, 5xx, database failure classes).

This script turns them into an opinion rather than a wall of JSON. Each failed check prints what
is wrong *and* what to do about it, because "status != ready" on its own sends an operator to the
dashboard to guess.

Privacy rules: it prints only what the endpoints already expose publicly - no request bodies, no
user identifiers, no database host, no credentials. It never authenticates, so it cannot read
anyone's data, and it writes no records.

Usage:
    python3 scripts/monitor_production.py                       # hosted API, human output
    python3 scripts/monitor_production.py --json                # machine-readable
    python3 scripts/monitor_production.py --base-url http://127.0.0.1:8011 --allow-degraded

Exit codes:
    0  every check passed
    1  at least one check failed (the service needs attention)
    2  the monitor could not run (unreachable, or the endpoint answered with something unusable)
    3  every check passed but a warning was raised (spindown, email unconfigured, ...)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

DEFAULT_BASE_URL = "https://spaceagrisim-api.onrender.com"
DEFAULT_TIMEOUT = 45.0  # a spun-down free instance takes about a minute to wake

# Failure-class text from backend/app/observability.py; only these four labels exist.
DB_FAILURE_HINTS = {
    "connect": "the API could not reach PostgreSQL at all (host, port, suspended or deleted "
               "instance). Check Render -> database status first, then SPACEAGRISIM_DATABASE_URL.",
    "pool-timeout": "the connection pool is exhausted: requests waited longer than the timeout. "
                    "Look for a slow query or a stuck transaction before raising pool size.",
    "integrity": "the database rejected a write (constraint or type). That is a request bug, not "
                 "capacity; check the API logs for the request id.",
    "configuration": "SPACEAGRISIM_DATABASE_URL is not a URL the driver accepts. Fix the variable "
                     "on the service and redeploy.",
}


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    remedy: str = ""
    warning: bool = False

    def as_dict(self) -> dict:
        payload = {"check": self.name, "ok": self.ok, "detail": self.detail}
        if self.remedy:
            payload["remedy"] = self.remedy
        if self.warning:
            payload["warning"] = True
        return payload


@dataclass
class Result:
    base_url: str
    checks: list[Check] = field(default_factory=list)
    payloads: dict[str, dict] = field(default_factory=dict)

    def add(self, *args, **kwargs) -> Check:
        check = Check(*args, **kwargs)
        self.checks.append(check)
        return check

    @property
    def failures(self) -> list[Check]:
        return [check for check in self.checks if not check.ok]

    @property
    def warnings(self) -> list[Check]:
        return [check for check in self.checks if check.ok and check.warning]

    def as_dict(self) -> dict:
        return {
            "baseUrl": self.base_url,
            "ok": not self.failures,
            "summary": f"{len(self.checks) - len(self.failures)}/{len(self.checks)} checks passed",
            "checks": [check.as_dict() for check in self.checks],
        }


def get(url: str, timeout: float) -> tuple[int, dict | str, float]:
    started = time.monotonic()
    request = urllib.request.Request(url, headers={"accept": "application/json",
                                                   "user-agent": "spaceagrisim-monitor/1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(200_000).decode("utf-8", "replace")
            elapsed = (time.monotonic() - started) * 1000
            try:
                return response.status, json.loads(body), elapsed
            except json.JSONDecodeError:
                return response.status, body[:200], elapsed
    except urllib.error.HTTPError as exc:
        body = exc.read(200_000).decode("utf-8", "replace")
        elapsed = (time.monotonic() - started) * 1000
        try:
            return exc.code, json.loads(body), elapsed
        except json.JSONDecodeError:
            return exc.code, body[:200], elapsed
    except Exception as exc:  # noqa: BLE001 - a monitor reports, it does not raise
        elapsed = (time.monotonic() - started) * 1000
        return 0, f"{type(exc).__name__}", elapsed


def check_health(result: Result, base: str, timeout: float) -> None:
    status, body, elapsed = get(f"{base}/api/health", timeout)
    if status == 0:
        result.add("health:reachable", False,
                   f"no HTTP response ({body}) after {elapsed/1000:.1f}s",
                   "the service did not answer at all: check Render -> service status and the "
                   "deploy log. A free instance wakes in ~50s, so retry once before escalating.")
        return
    if not isinstance(body, dict):
        result.add("health:reachable", False, f"HTTP {status} with a non-JSON body",
                   "an edge proxy answered instead of the app; check the service is deployed.")
        return
    result.payloads["health"] = body
    result.add("health:reachable", status == 200, f"HTTP {status} in {elapsed:.0f} ms",
               "" if status == 200 else "restart the service from the Render dashboard and "
                                        "check the deploy log for a startup failure.")
    result.add("health:status-ok", body.get("status") == "ok",
               f"status={body.get('status')!r}",
               "" if body.get("status") == "ok" else "/api/health is not reporting ok; the "
                                                    "process is up but unhealthy.")


def check_ready(result: Result, base: str, timeout: float, allow_degraded: bool) -> None:
    status, body, elapsed = get(f"{base}/api/ready", timeout)
    if not isinstance(body, dict):
        result.add("ready:reachable", False, f"HTTP {status}: {str(body)[:120]}",
                   "readiness did not return JSON; treat it as down and check the deploy log.")
        return
    result.payloads["ready"] = body
    ready = status == 200 and body.get("status") == "ready"
    if ready:
        result.add("ready:status", True, f"ready in {elapsed:.0f} ms")
    else:
        reason = body.get("reason") or body.get("error") or "unknown"
        remedy = body.get("remedy") or (
            "read /api/ready's own `remedy` field: the endpoint classifies its own failure "
            "(database_misconfigured, database_unavailable, database_schema_incomplete, "
            "database_migration_pending).")
        result.add("ready:status", allow_degraded,
                   f"HTTP {status}, reason={reason}", remedy,
                   warning=allow_degraded)
        return

    result.add("ready:database", body.get("database") == "available",
               f"database={body.get('database')!r}, dialect={body.get('databaseDialect')!r}",
               "the schema or the connection is missing; /api/ready will name which.")

    migrations = body.get("databaseMigrations") or {}
    pending = migrations.get("pending")
    result.add("ready:migrations", pending == 0,
               f"{migrations.get('applied')}/{migrations.get('total')} applied, {pending} pending",
               "" if pending == 0 else
               "an additive migration has not run: restart the service once so it applies, then "
               "re-check. The migration never drops or rewrites rows.")

    pool = body.get("databasePool") or {}
    exhausted = pool.get("exhausted")
    result.add("ready:pool", exhausted is False,
               f"size={pool.get('size')}, checkedOut={pool.get('checkedOut')}, "
               f"capacity={pool.get('capacity')}, exhausted={exhausted}",
               "" if exhausted is False else
               "the pool is exhausted: find the slow query (see /api/metrics database.slowQueries) "
               "before changing pool_size; worker count must stay 1.")

    storage = body.get("storage") or {}
    durable = storage.get("durable")
    result.add("ready:storage-durable", durable is True,
               f"durable={durable}, dialect={storage.get('dialect')!r}",
               "" if durable is True else
               (storage.get("remedy") or
                "saved data would not survive a restart: set SPACEAGRISIM_DATABASE_URL to the "
                "PostgreSQL instance's Internal URL, not a SQLite path."))

    identity = body.get("rateLimitIdentity")
    result.add("ready:rate-limit-identity", True,
               f"rateLimitIdentity={identity!r}",
               "", warning=(identity == "socket"))

    if body.get("emailDelivery") == "unconfigured":
        result.add("ready:email-delivery", True,
                   "emailDelivery=unconfigured (verification and reset mail is not sent)",
                   "expected until SMTP is configured; accounts still work, the UI prompts "
                   "instead of emailing.", warning=True)


def check_metrics(result: Result, base: str, timeout: float) -> None:
    status, body, _ = get(f"{base}/api/metrics", timeout)
    if not isinstance(body, dict):
        result.add("metrics:reachable", False, f"HTTP {status}",
                   "/api/metrics should always answer; a failure here suggests the process is "
                   "partially wedged. Restart it.")
        return
    metrics = body.get("metrics") or {}
    errors = metrics.get("serverErrors") or {}
    total_errors = sum(int(value) for value in errors.values() if isinstance(value, int))
    total_requests = sum(int(value) for value in (metrics.get("requests") or {}).values()
                         if isinstance(value, int))
    database = metrics.get("database") or {}
    failures = database.get("failures") or {}
    result.payloads["metrics"] = body

    # Counters reset on every deploy and on every wake from the 15-minute spindown, so a non-zero
    # number is information, not a threshold: the remedy is the failure class, not the count.
    if total_errors:
        result.add("metrics:server-errors", True,
                   f"{total_errors} 5xx of {total_requests} requests (per process since start)",
                   "5xx responses have happened since this process started: pull the request ids "
                   "from the logs for the paths in serverErrors.", warning=True)
    else:
        result.add("metrics:server-errors", True, f"0 5xx of {total_requests} requests")

    if failures:
        detail = ", ".join(f"{kind}={count}" for kind, count in sorted(failures.items()))
        remedy = " ".join(DB_FAILURE_HINTS.get(kind, f"{kind}: unknown failure class.")
                          for kind in sorted(failures))
        result.add("metrics:database-failures", True,
                   f"database failure classes since start: {detail}", remedy, warning=True)
    else:
        result.add("metrics:database-failures", True, "no database failure classes recorded")


def check_uptime(result: Result) -> None:
    """A process that restarts constantly is down without ever returning an error."""
    metrics = (result.payloads.get("metrics") or {}).get("metrics") or {}
    uptime = metrics.get("uptimeSeconds")
    if uptime is None:
        result.add("metrics:uptime", True,
                   "uptimeSeconds not reported by this deployment (older build)",
                   "", warning=True)
        return
    result.add("metrics:uptime", True, f"process uptime {uptime}s",
               "" if uptime > 120 else
               "the process restarted recently: if this repeats on consecutive runs the service is "
               "crash-looping or being OOM-killed (free instances have 512 MB).",
               warning=uptime <= 120)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Monitor the deployed SpaceAgriSim API.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--allow-degraded", action="store_true",
                        help="report a not-ready service as a warning instead of a failure "
                             "(for a maintenance window, not for CI)")
    args = parser.parse_args(argv)
    base = args.base_url.rstrip("/")

    result = Result(base_url=base)
    check_health(result, base, args.timeout)
    check_ready(result, base, args.timeout, args.allow_degraded)
    check_metrics(result, base, args.timeout)
    check_uptime(result)

    payload = result.as_dict()
    payload["warnings"] = [check.name for check in result.warnings]
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"SpaceAgriSim production monitor: {base}")
        for check in result.checks:
            label = "ok" if check.ok and not check.warning else ("warn" if check.ok else "FAIL")
            print(f"  [{label:4}] {check.name}: {check.detail}")
            if check.remedy and (not check.ok or check.warning):
                print(f"         -> {check.remedy}")
        print(f"  {payload['summary']}")
        if not result.failures:
            print("  service healthy" if not result.warnings else
                  f"  service healthy with {len(result.warnings)} warning(s)")

    if result.failures:
        return 1
    return 3 if result.warnings else 0


if __name__ == "__main__":
    sys.exit(main())
