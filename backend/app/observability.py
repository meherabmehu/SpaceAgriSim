"""In-process, privacy-safe service counters for small hosted deployments."""
from collections import Counter
from threading import Lock

_lock = Lock()
_requests = Counter()
_errors = Counter()


def record(path: str, status: int) -> None:
    # Route path is intentionally all we retain; query strings, bodies, users,
    # bearer tokens and client addresses are never metrics labels.
    with _lock:
        _requests[path] += 1
        if status >= 500:
            _errors[path] += 1


def snapshot() -> dict:
    with _lock:
        return {"requests": dict(_requests), "serverErrors": dict(_errors)}
