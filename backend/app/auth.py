"""Small, explicit bearer-token authentication boundary for account data."""
from datetime import datetime, timedelta, timezone
import re
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import storage
from app.config.settings import settings

password_hasher = PasswordHasher()
bearer = HTTPBearer(auto_error=False)
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 254 or not EMAIL_RE.fullmatch(email):
        raise ValueError("Enter a valid email address")
    return email


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def issue_token(user: dict) -> dict[str, str | int]:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=settings.auth_token_minutes)
    jti = uuid4().hex
    token = jwt.encode({"sub": user["id"], "email": user["email"], "jti": jti,
                        "iat": now, "exp": expires}, settings.resolved_auth_secret,
                       algorithm="HS256")
    return {"accessToken": token, "tokenType": "bearer", "expiresIn": settings.auth_token_minutes * 60,
            "expiresAt": expires.isoformat()}


def optional_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict | None:
    """Identify a caller if a valid token is presented, without requiring one.

    Used by the workflow run endpoint, which serves an anonymous visitor exactly as the
    existing prediction endpoints do, but must refuse to persist anything without an
    account. A malformed token is *not* silently treated as anonymous: that would let a
    caller with an expired session believe their analysis was saved.
    """
    if credentials is None:
        return None
    return current_user(credentials)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Authentication is required", headers={"WWW-Authenticate": "Bearer"})
    payload = None
    for secret in settings.auth_secrets_for_verification:
        try:
            payload = jwt.decode(credentials.credentials, secret, algorithms=["HS256"],
                                 options={"require": ["sub", "jti", "exp"]})
            break
        except jwt.ExpiredSignatureError as exc:
            # Expiry is not a secret mismatch: retrying with the previous secret would only
            # delay the same answer.
            raise HTTPException(401, "Authentication token has expired",
                                headers={"WWW-Authenticate": "Bearer"}) from exc
        except jwt.PyJWTError:
            continue
    if payload is None:
        raise HTTPException(401, "Invalid or expired authentication token",
                            headers={"WWW-Authenticate": "Bearer"})
    if storage.token_is_revoked(payload["jti"]):
        raise HTTPException(401, "Authentication token has been revoked", headers={"WWW-Authenticate": "Bearer"})
    user = storage.find_user_by_email(str(payload.get("email", "")))
    if not user or user["id"] != payload["sub"] or user["disabled"]:
        raise HTTPException(401, "Authentication is no longer valid", headers={"WWW-Authenticate": "Bearer"})
    user["token_jti"] = payload["jti"]
    user["token_expires_at"] = datetime.fromtimestamp(payload["exp"], timezone.utc).isoformat()
    return user
