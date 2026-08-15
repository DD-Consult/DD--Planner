"""
Platform admin authentication endpoints (Step 5 of MULTITENANT_PLAN.md).

These endpoints power the SEPARATE platform admin portal at
`admin.ddplanner.io`. They are:
  - Cross-tenant: not scoped to any tenant DB
  - Backed by `platform_db.platform_users`
  - Issue JWTs with `token_type: "platform"` which are only valid at
    /api/platform/* routes

Endpoints:
  POST /api/platform/auth/login   — email/password login
  GET  /api/platform/auth/me      — return current platform admin session
  POST /api/platform/auth/logout  — no-op for JWT (stateless), returns 204
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional

from platform_db import platform_users_collection
from auth.dependencies import (
    verify_password,
    create_access_token,
    get_current_platform_admin,
    TOKEN_TYPE_PLATFORM,
)

router = APIRouter(prefix="/api/platform/auth", tags=["platform-auth"])


class PlatformUserResponse(BaseModel):
    id: str
    email: str
    role: str
    name: Optional[str] = None
    must_change_password: bool = False
    linked_tenant_slug: Optional[str] = None


class PlatformTokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: PlatformUserResponse


def _serialize_platform_user(doc: dict) -> dict:
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    d.pop("password_hash", None)
    return d


@router.post("/login", response_model=PlatformTokenResponse)
async def platform_login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    """Platform admin login.
    
    Issues a JWT with `token_type: "platform"`. This JWT is valid ONLY for
    /api/platform/* routes and is rejected on tenant routes (see
    get_current_user in auth/dependencies.py).
    
    Note on Option B (dual-role accounts): the same email may exist as both
    a platform_admin (here) and a tenant super_admin (in a tenant DB). The
    passwords may differ. This endpoint checks ONLY the platform_users
    collection.
    """
    user = await platform_users_collection.find_one({"email": form_data.username})
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect platform admin credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.get("disabled"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform account is disabled.",
        )
    if user.get("role") != "platform_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not a platform admin.",
        )

    jwt_payload = {
        "sub": user["email"],
        "token_type": TOKEN_TYPE_PLATFORM,
        "role": "platform_admin",
        "platform_user_id": str(user["_id"]),
    }
    access_token = create_access_token(data=jwt_payload)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": _serialize_platform_user(user),
    }


@router.get("/me", response_model=PlatformUserResponse)
async def platform_me(current: dict = Depends(get_current_platform_admin)):
    """Return the current platform admin session (verifies JWT is valid)."""
    return current


@router.post("/logout", status_code=204)
async def platform_logout():
    """Stateless logout (JWT expires naturally). Clients should discard the token.
    
    Returns 204 No Content. In the future this could invalidate a session in
    a token blacklist if we need immediate revocation.
    """
    return None
