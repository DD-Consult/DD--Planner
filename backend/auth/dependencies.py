"""
Auth dependencies (Step 5 of MULTITENANT_PLAN.md — tenant-aware).

Backward compatible with the pre-Step-5 JWT format. When
MULTI_TENANT_ENABLED=false (default), behaves exactly as before.

When MULTI_TENANT_ENABLED=true:
  - Tenant login (POST /api/auth/login) issues a JWT with:
        {sub, tenant_id, tenant_slug, token_type: "tenant", role, exp}
  - Platform admin login (POST /api/platform/auth/login) issues a JWT with:
        {sub, token_type: "platform", role: "platform_admin", exp}
  - get_current_user validates:
      * token_type must be "tenant" (platform tokens rejected here)
      * tenant_slug in JWT must match the current request's resolved tenant
        (prevents JWT replay across tenants)
      * user must exist in the current tenant's DB
  - get_current_platform_admin validates:
      * token_type must be "platform"
      * user must exist in platform_users collection
      * role must be "platform_admin"
"""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import bcrypt
import os

from database import users_collection, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from utils import serialize_doc

# Feature flag (evaluated per-request via ContextVar-free helper)
def _multi_tenant_enabled() -> bool:
    return os.environ.get('MULTI_TENANT_ENABLED', 'false').lower() == 'true'

# JWT token types
TOKEN_TYPE_TENANT = "tenant"
TOKEN_TYPE_PLATFORM = "platform"
TOKEN_TYPE_LEGACY = "legacy"  # Pre-Step-5 tokens (no token_type claim)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')


def create_access_token(data: dict):
    """Create a JWT. Backward compatible: any dict is accepted.
    
    For tenant tokens (Step 5+), callers should include:
        {sub, tenant_id, tenant_slug, token_type: "tenant", role}
    
    For platform tokens (Step 5+):
        {sub, token_type: "platform", role: "platform_admin"}
    
    Legacy tokens have only {sub} and are still accepted by get_current_user
    when MULTI_TENANT_ENABLED=false or in transitional mode.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode a JWT. Returns None if invalid."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


async def get_current_user(request: Request, token: str = Depends(oauth2_scheme)):
    """Resolve the current tenant user from the JWT.
    
    Behaviour matrix:
    
    | flag=OFF     | any JWT with sub -> look up in default DB. Legacy behavior.
    | flag=ON      | JWT type=tenant  -> validate tenant_slug matches request, look up in tenant DB
    | flag=ON      | JWT type=platform -> REJECT (403). Platform tokens are only for /api/platform/auth
    | flag=ON      | JWT type=legacy   -> look up in current-tenant DB (tolerant migration)
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if not payload:
        raise credentials_exception

    email: Optional[str] = payload.get("sub")
    if not email:
        raise credentials_exception

    token_type = payload.get("token_type", TOKEN_TYPE_LEGACY)

    # --- Multi-tenant validation ---
    if _multi_tenant_enabled():
        # 1. Platform tokens must NEVER be used on tenant routes.
        if token_type == TOKEN_TYPE_PLATFORM:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Platform tokens cannot be used on tenant endpoints. Use /api/platform/* instead."
            )
        # 2. Tenant tokens must match the resolved tenant.
        current_tenant = getattr(request.state, "tenant", None)
        if token_type == TOKEN_TYPE_TENANT:
            jwt_slug = payload.get("tenant_slug")
            current_slug = current_tenant.get("slug") if current_tenant else None
            if jwt_slug and current_slug and jwt_slug != current_slug:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Token issued for tenant '{jwt_slug}' cannot be used on tenant '{current_slug}'.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        # Legacy tokens fall through (best-effort, no tenant validation).

    # --- User lookup (via LazyCollection, respects tenant DB routing) ---
    user = await users_collection.find_one({"email": email})
    if user is None:
        raise credentials_exception
    if user.get("disabled"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled. Contact an administrator.")
    return serialize_doc(user)


async def get_current_platform_admin(request: Request, token: str = Depends(oauth2_scheme)):
    """Resolve the current platform_admin from a platform-type JWT.
    
    Used by:
      - /api/platform/tenants (list, CRUD)
      - /api/platform/modules (management)
      - /api/platform/tenants/{slug}/modules (toggle)
      - Any future platform-portal-only endpoints
    
    Requires:
      - JWT token_type == "platform"
      - User exists in platform_db.platform_users
      - Role == "platform_admin"
      - Account not disabled
    
    Backward compatibility (Option B — dual-role account):
      - When MULTI_TENANT_ENABLED=false, this dependency ACCEPTS any super_admin JWT.
        This lets existing tests and the DD Consulting super_admin manage the
        platform before Step 7's proper portal login exists.
      - When MULTI_TENANT_ENABLED=true, only platform-type JWTs are accepted.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Platform admin credentials required",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if not payload:
        raise credentials_exception

    email: Optional[str] = payload.get("sub")
    if not email:
        raise credentials_exception

    token_type = payload.get("token_type", TOKEN_TYPE_LEGACY)

    # --- Multi-tenant mode: strict platform-token requirement ---
    if _multi_tenant_enabled():
        if token_type != TOKEN_TYPE_PLATFORM:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Platform admin access requires a platform token. Log in at /api/platform/auth/login."
            )
        # Look up in platform_users
        from platform_db import platform_users_collection
        pu = await platform_users_collection.find_one({"email": email})
        if not pu or pu.get("disabled"):
            raise credentials_exception
        if pu.get("role") != "platform_admin":
            raise HTTPException(status_code=403, detail="Not a platform admin")
        pu = dict(pu)
        pu["id"] = str(pu.pop("_id"))
        pu.pop("password_hash", None)
        return pu

    # --- Backward-compat mode (flag OFF): accept super_admin JWTs too ---
    # This allows testing/introspection before Step 7 lands the platform portal.
    from platform_db import platform_users_collection
    pu = await platform_users_collection.find_one({"email": email})
    if pu and not pu.get("disabled") and pu.get("role") == "platform_admin":
        pu = dict(pu)
        pu["id"] = str(pu.pop("_id"))
        pu.pop("password_hash", None)
        return pu
    # Fallback: check if user is a super_admin in the default DB
    user = await users_collection.find_one({"email": email})
    if not user:
        raise credentials_exception
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Platform admin access required")
    if user.get("disabled"):
        raise HTTPException(status_code=403, detail="Account disabled")
    user = serialize_doc(user)
    user["role"] = "platform_admin"  # Normalize for downstream code
    return user


def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def require_super_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super Admin access required"
        )
    return current_user


def require_admin_or_above(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def require_resource_or_above(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ["resource", "admin", "super_admin", "contractor"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Resource access required"
        )
    return current_user
