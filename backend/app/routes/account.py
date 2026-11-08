"""Account lifecycle: email verification, password reset and security activity.

Design notes that matter for a public deployment:

* **No account enumeration.** The request endpoints answer with the same 202 whether or not the
  address exists. A different status for an unknown address would turn them into a membership
  oracle.
* **Tokens are single-use and hashed at rest.** Only a SHA-256 digest is stored, so a database
  read cannot be replayed into a working reset link.
* **A reset invalidates existing sessions.** The new password stamps `password_changed_at`, and
  every token carries the stamp it was issued under.
* **Delivery failure is reported, not hidden.** Without SMTP in production the request endpoint
  returns 503 instead of pretending the mail went out.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app import mailer, storage
from app.auth import current_user, hash_password, normalize_email
from app.config.settings import settings

router = APIRouter(prefix="/auth", tags=["authentication"])


class EmailOnly(BaseModel):
    email: str = Field(max_length=254)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        return normalize_email(value)


class TokenOnly(BaseModel):
    token: str = Field(min_length=16, max_length=200)


class PasswordReset(BaseModel):
    token: str = Field(min_length=16, max_length=200)
    password: str = Field(min_length=12, max_length=256)


def _link(action: str, token: str) -> str:
    """Build a link the single-page app can act on without a server-side route.

    The app is served as static files and routes on the fragment, so `/#reset?token=…` always
    loads the app. A path link (`/reset?token=…`) would depend on a host rewrite that a static
    deployment does not have.
    """
    return f"{settings.public_app_url.rstrip('/')}/#{action}?token={token}"


def _send_or_503(address: str, subject: str, body: str) -> str:
    try:
        mailer.send(address, subject, body)
    except mailer.EmailDeliveryUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return mailer.delivery_mode()


def _dev_token(token: str) -> dict:
    """Development only: hand the token back so the flow is testable without a mail server.

    Production never takes this branch - `delivery_mode()` there is "smtp" or "unconfigured",
    and "unconfigured" fails with 503 before this is reached.
    """
    return {"debugToken": token} if settings.environment != "production" else {}


@router.post("/verify/request", status_code=status.HTTP_202_ACCEPTED)
def request_verification(request: EmailOnly):
    """Send a verification link. The answer does not reveal whether the address is registered."""
    user = storage.find_user_by_email(request.email)
    if not user or user["disabled"] or user.get("email_verified"):
        return {"status": "accepted", "delivery": mailer.delivery_mode()}
    token = storage.issue_account_token(user["id"], "verify",
                                        settings.email_verification_hours * 60)
    _send_or_503(
        user["email"],
        "Verify your SpaceAgriSim email address",
        "Confirm this address to attach it to your SpaceAgriSim account.\n\n"
        f"{_link('verify', token)}\n\n"
        f"This link works once and expires in {settings.email_verification_hours} hours. "
        "If you did not create an account, ignore this message.")
    storage.record_activity(user["id"], "verification-requested")
    return {"status": "accepted", "delivery": mailer.delivery_mode(), **_dev_token(token)}


@router.post("/verify/confirm")
def confirm_verification(request: TokenOnly):
    user_id = storage.consume_account_token(request.token, "verify")
    if not user_id:
        raise HTTPException(400, "This verification link is invalid, used or expired")
    storage.mark_email_verified(user_id)
    storage.record_activity(user_id, "email-verified")
    return {"status": "verified"}


@router.post("/password/forgot", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(request: EmailOnly):
    user = storage.find_user_by_email(request.email)
    if not user or user["disabled"]:
        return {"status": "accepted", "delivery": mailer.delivery_mode()}
    token = storage.issue_account_token(user["id"], "reset", settings.password_reset_minutes)
    _send_or_503(
        user["email"],
        "Reset your SpaceAgriSim password",
        "A password reset was requested for this address.\n\n"
        f"{_link('reset', token)}\n\n"
        f"This link works once and expires in {settings.password_reset_minutes} minutes. "
        "If this was not you, no action is needed and your password is unchanged.")
    storage.record_activity(user["id"], "password-reset-requested")
    return {"status": "accepted", "delivery": mailer.delivery_mode(), **_dev_token(token)}


@router.post("/password/reset")
def reset_password(request: PasswordReset):
    user_id = storage.consume_account_token(request.token, "reset")
    if not user_id:
        raise HTTPException(400, "This reset link is invalid, used or expired")
    storage.set_password(user_id, hash_password(request.password))
    storage.record_activity(user_id, "password-changed")
    return {"status": "password-changed",
            "note": "Every session issued before this change is now invalid; sign in again."}


@router.get("/activity")
def activity(user: dict = Depends(current_user), limit: int = 50):
    """This account's own security history, newest first. Never another account's."""
    return {"events": [{"kind": event["kind"], "detail": event["detail"],
                        "createdAt": event["created_at"]}
                       for event in storage.list_activity(user["id"], limit)]}
