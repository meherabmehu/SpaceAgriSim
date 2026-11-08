"""Account endpoints. Public science routes deliberately live elsewhere."""
from pydantic import BaseModel, Field, field_validator
from fastapi import APIRouter, Depends, HTTPException, status

from app import storage
from app.auth import current_user, hash_password, issue_token, normalize_email, verify_password

router = APIRouter(prefix="/auth", tags=["authentication"])


class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=12, max_length=256)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        return normalize_email(value)


def public_user(user: dict) -> dict:
    return {"id": user["id"], "email": user["email"], "createdAt": user["created_at"],
            # Phase 19: verification is recorded and surfaced. It is not yet a login requirement,
            # so an existing account keeps working and the UI can prompt instead of blocking.
            "emailVerified": bool(user.get("email_verified"))}


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(request: Credentials):
    if storage.find_user_by_email(request.email):
        raise HTTPException(409, "An account with this email already exists")
    user = storage.create_user(request.email, hash_password(request.password))
    storage.record_activity(user["id"], "account-created")
    return {"user": public_user(user), **issue_token(user),
            # The client can call POST /auth/verify/request; the account is usable either way.
            "nextStep": "verify-email"}


@router.post("/login")
def login(request: Credentials):
    user = storage.find_user_by_email(request.email)
    if not user or user["disabled"] or not verify_password(user["password_hash"], request.password):
        # Log the failed attempt against the account when it exists, without telling the caller
        # which half of the credential was wrong.
        if user:
            storage.record_activity(user["id"], "login-failed")
        raise HTTPException(401, "Invalid email or password", headers={"WWW-Authenticate": "Bearer"})
    storage.record_activity(user["id"], "login")
    return {"user": public_user(user), **issue_token(user)}


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return {"user": public_user(user)}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(user: dict = Depends(current_user)):
    storage.revoke_token(user["token_jti"], user["token_expires_at"])
    storage.record_activity(user["id"], "logout")
