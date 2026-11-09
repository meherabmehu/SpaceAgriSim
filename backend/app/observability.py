"""In-process, privacy-safe service counters for small hosted deployments."""
from collections import Counter
from datetime import datetime, timezone
from threading import Lock
from time import monotonic

_lock = Lock()
# When this process started. Exposed so a monitor can tell "up for 6 hours" from "restarted every
# two minutes", which is the failure mode a health probe cannot see: a crash-looping service keeps
# answering for the few seconds it is alive. Neither value identifies a client or a request.
_STARTED_MONOTONIC = monotonic()
_STARTED_AT = datetime.now(timezone.utc)
_requests = Counter()
_errors = Counter()
# Database diagnostics. These are deliberately aggregate: an operation verb, a duration bucket,
# and a failure class. No statement text, no parameters, no URL, no account identifier.
_db_failures = Counter()
_db_slow = Counter()
_db_slow_total = 0
_db_slow_ms = 0.0


def record(path: str, status: int) -> None:
    # Route path is intentionally all we retain; query strings, bodies, users,
    # bearer tokens and client addresses are never metrics labels.
    with _lock:
        _requests[path] += 1
        if status >= 500:
            _errors[path] += 1


def record_db_failure(kind: str) -> None:
    """Count a database failure class: connect, pool-timeout, integrity, other.

    The class is what an operator acts on: `pool-timeout` means capacity, `connect` means the
    server, `integrity` means the request. None of them needs the statement or its parameters.
    """
    with _lock:
        _db_failures[kind] += 1


def record_db_slow_query(operation: str, elapsed_ms: float) -> None:
    global _db_slow_total, _db_slow_ms
    with _lock:
        _db_slow[operation or "OTHER"] += 1
        _db_slow_total += 1
        _db_slow_ms += elapsed_ms


def database_snapshot() -> dict:
    with _lock:
        return {
            "slowQueries": dict(_db_slow),
            "slowQueryCount": _db_slow_total,
            "slowQueryMeanMs": round(_db_slow_ms / _db_slow_total, 1) if _db_slow_total else None,
            "failures": dict(_db_failures),
            "scope": "per-process; resets on restart",
        }


def reset_database_counters() -> None:
    """Test helper: counters are process-wide, so a test that asserts a count must start clean."""
    global _db_slow_total, _db_slow_ms
    with _lock:
        _db_failures.clear()
        _db_slow.clear()
        _db_slow_total = 0
        _db_slow_ms = 0.0


def uptime() -> dict:
    """Seconds since this process started, plus the UTC start time. No secrets, no clients."""
    return {"startedAt": _STARTED_AT.isoformat().replace("+00:00", "Z"),
            "uptimeSeconds": round(monotonic() - _STARTED_MONOTONIC, 1)}


def snapshot() -> dict:
    with _lock:
        return {"requests": dict(_requests), "serverErrors": dict(_errors),
                "database": {"slowQueries": dict(_db_slow), "slowQueryCount": _db_slow_total,
                             "failures": dict(_db_failures)},
                **uptime()}
