"""Operator-only surface: what the deployment is doing, without looking at anybody's account.

The per-account activity log answers "what happened to my account?". An operator needs the other
question — "is this deployment healthy, and is anyone behaving badly?" — and the safe way to answer
it is with aggregates and pseudonymous ids, never addresses.

Access is a dedicated bearer token, not an account: an operator credential that also worked as a
login would make every operator an account holder, with their own scenarios and share links.
Without `SPACEAGRISIM_ADMIN_TOKEN` the whole surface answers 404, so a public deployment does not
advertise a panel nobody configured.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import mailer, storage
from app.config.settings import settings

router = APIRouter(prefix="/admin", tags=["operator"])
_bearer = HTTPBearer(auto_error=False)

# Event kinds the operator summary breaks down. Anything else is reported as "other" so a new
# event type cannot silently vanish from the totals.
KNOWN_KINDS = ("account-created", "login", "login-failed", "logout", "email-verified",
               "verification-requested", "password-changed", "password-reset-requested",
               "share-link-created", "share-link-revoked")


def require_operator(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> None:
    configured = settings.admin_token or ""
    if not configured:
        # Not configured means not offered. A 403 here would confirm the endpoint exists.
        raise HTTPException(404, "Not found")
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Operator token required", headers={"WWW-Authenticate": "Bearer"})
    # Constant-time compare: a byte-by-byte early exit leaks the token prefix to a patient caller.
    if not secrets.compare_digest(credentials.credentials, configured):
        raise HTTPException(401, "Operator token rejected", headers={"WWW-Authenticate": "Bearer"})


def _pseudonym(user_id: str) -> str:
    """A stable, non-reversible handle so events can be correlated but not attributed."""
    return hashlib.sha256(f"spaceagrisim-operator:{user_id}".encode()).hexdigest()[:12]


@router.get("/audit")
def audit(
    _: None = Depends(require_operator),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    """Recent account events, pseudonymised, plus the counts that make them interpretable."""
    events = storage.list_recent_activity(limit)
    counts: dict[str, int] = {kind: 0 for kind in KNOWN_KINDS}
    for event in events:
        counts[event["kind"]] = counts.get(event["kind"], 0) + 1
    rows = [{"kind": event["kind"], "at": event["created_at"],
             "account": _pseudonym(event["user_id"]),
             "detail": event["detail"]} for event in events]
    return {
        "scope": "operator audit: pseudonymous account events, no addresses, no payloads",
        "retention": f"each account keeps its newest {settings.max_activity_events} events",
        "window": f"{len(events)} most recent events across all accounts",
        "counts": counts,
        "failedLogins": counts.get("login-failed", 0),
        "events": rows,
    }


@router.get("/summary")
def summary(_: None = Depends(require_operator)) -> dict:
    """One screen for an operator: is the service healthy and are the claims still true?"""
    try:
        health = storage.database_health()
    except Exception as exc:  # noqa: BLE001 - the operator needs the failure, not a traceback
        health = {"status": f"unavailable: {type(exc).__name__}", "dialect": "unknown"}
    snapshot = storage.activity_summary()
    resync = storage.read_json_artifact("osdr_live_status.json")
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "database": health,
        "storage": storage.storage_durability(),
        "emailDelivery": mailer.delivery_mode(),
        "accounts": snapshot["accounts"],
        "liveShareLinks": snapshot["liveShareLinks"],
        "activityByKind": snapshot["byKind"],
        "rateLimitIdentity": "forwarded" if settings.trusted_proxy_hops else "socket",
        "provenanceResync": None if resync is None else {
            "checkedAt": resync.get("checkedAt"),
            "studiesChecked": resync.get("studiesChecked"),
            "verdicts": resync.get("verdictCounts"),
        },
        "scientificValidation": "uncalibrated mathematical estimates",
    }
