"""
Platform admin operational endpoints (Step 7 of MULTITENANT_PLAN.md).

Provides tenant lifecycle management, support impersonation, and audit log
for the platform admin portal at `admin.ddplanner.io`.

Endpoints (all require `get_current_platform_admin`):
    GET    /api/platform/dashboard/stats           — high-level portfolio metrics
    POST   /api/platform/tenants                   — create a new tenant + DB + seed
    PATCH  /api/platform/tenants/{slug}            — update tenant (status, branding, settings)
    DELETE /api/platform/tenants/{slug}            — soft-delete tenant
    POST   /api/platform/tenants/{slug}/impersonate — issue short-lived scoped tenant JWT
    GET    /api/platform/audit-log                 — cross-tenant audit trail
    GET    /api/platform/tenants/{slug}/users      — list tenant users (redacted)

Audit log:
    Every mutating platform endpoint calls `_record_audit(...)` which writes
    a doc to `platform_audit_log`. Includes: actor, action, target, before/after
    snapshot (for updates), and timestamp.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
import uuid

from platform_db import (
    tenants_collection,
    platform_users_collection,
    modules_catalog_collection,
    tenant_modules_collection,
    memberships_collection,
    platform_audit_log_collection,
    tenant_db_name,
    MODULES_CATALOG,
)
from auth.dependencies import (
    get_current_platform_admin,
    get_password_hash,
    create_access_token,
    TOKEN_TYPE_TENANT,
)
from middleware.tenant_resolver import invalidate_tenant_cache

router = APIRouter(prefix="/api/platform", tags=["platform-ops"])


# --- Serializers ---
def _serialize(doc):
    if not doc:
        return None
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    doc.pop("password_hash", None)
    return doc


# --- Audit log helper ---
async def _record_audit(
    actor_email: str,
    action: str,
    tenant_slug: Optional[str] = None,
    target: Optional[str] = None,
    details: Optional[dict] = None,
):
    """Write a single audit-log entry. Non-blocking-friendly."""
    doc = {
        "_id": str(uuid.uuid4()),
        "actor_email": actor_email,
        "action": action,
        "tenant_slug": tenant_slug,
        "target": target,
        "details": details or {},
        "created_at": datetime.now(timezone.utc),
    }
    try:
        await platform_audit_log_collection.insert_one(doc)
    except Exception:
        # Never let audit failures break the actual operation
        pass


# ============================================================================
# Dashboard stats
# ============================================================================

@router.get("/dashboard/stats")
async def dashboard_stats(admin: dict = Depends(get_current_platform_admin)):
    """High-level metrics for the platform admin dashboard landing page."""
    tenant_count = await tenants_collection.count_documents({})
    active_tenant_count = await tenants_collection.count_documents({"status": "active"})
    suspended_tenant_count = await tenants_collection.count_documents({"status": "suspended"})
    platform_user_count = await platform_users_collection.count_documents({"disabled": {"$ne": True}})
    membership_count = await memberships_collection.count_documents({})

    # Modules enabled across tenants
    module_stats = {}
    async for row in tenant_modules_collection.find({}):
        key = row["module_key"]
        if key not in module_stats:
            module_stats[key] = {"enabled": 0, "disabled": 0}
        if row.get("enabled"):
            module_stats[key]["enabled"] += 1
        else:
            module_stats[key]["disabled"] += 1

    # Recent audit entries
    recent_audit = await platform_audit_log_collection.find({}).sort("created_at", -1).limit(10).to_list(length=10)

    return {
        "tenants": {
            "total": tenant_count,
            "active": active_tenant_count,
            "suspended": suspended_tenant_count,
        },
        "platform_users": platform_user_count,
        "memberships": membership_count,
        "modules": module_stats,
        "recent_audit": [_serialize(a) for a in recent_audit],
    }


# ============================================================================
# Tenant CRUD
# ============================================================================

class TenantCreate(BaseModel):
    slug: str = Field(..., min_length=2, max_length=32, pattern=r"^[a-z0-9][a-z0-9_-]*[a-z0-9]$")
    name: str = Field(..., min_length=1, max_length=100)
    owner_email: EmailStr
    owner_password: str = Field(..., min_length=8, max_length=100)
    primary_color: Optional[str] = "#1B2A47"
    accent_color: Optional[str] = "#C9A84C"
    work_week_hours: Optional[int] = 40
    timezone: Optional[str] = "UTC"
    enabled_modules: Optional[List[str]] = None  # If None, all catalog modules enabled


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None  # 'active' | 'suspended'
    primary_color: Optional[str] = None
    accent_color: Optional[str] = None
    logo_url: Optional[str] = None
    work_week_hours: Optional[int] = None
    timezone: Optional[str] = None


@router.post("/tenants", status_code=201)
async def create_tenant(
    payload: TenantCreate,
    admin: dict = Depends(get_current_platform_admin),
):
    """Create a new tenant with its own database and an initial admin user.
    
    Actions:
      1. Insert row in `platform_db.tenants` (slug uniqueness enforced by index)
      2. Enable requested modules (or all) in `platform_db.tenant_modules`
      3. Insert admin user in the new `tenant_{slug}` DB
      4. Create matching membership row
      5. Write audit log
    """
    from database import get_db_for_tenant_slug

    slug = payload.slug.lower()

    # Slug uniqueness
    existing = await tenants_collection.find_one({"slug": slug})
    if existing:
        raise HTTPException(status_code=409, detail=f"Tenant slug '{slug}' already exists")

    now = datetime.now(timezone.utc)
    tenant_id = str(uuid.uuid4())
    tenant_doc = {
        "_id": tenant_id,
        "slug": slug,
        "name": payload.name,
        "db_name": tenant_db_name(slug),
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "owner_email": payload.owner_email,
        "is_default": False,
        "branding": {
            "logo_url": None,
            "primary_color": payload.primary_color or "#1B2A47",
            "accent_color": payload.accent_color or "#C9A84C",
        },
        "settings": {
            "work_week_hours": payload.work_week_hours or 40,
            "timezone": payload.timezone or "UTC",
            "work_days": [0, 1, 2, 3, 4],
        },
    }
    await tenants_collection.insert_one(tenant_doc)

    # Determine which modules to enable
    requested_keys = payload.enabled_modules
    if requested_keys is None:
        requested_keys = [m["key"] for m in MODULES_CATALOG]

    tm_docs = []
    for m in MODULES_CATALOG:
        tm_docs.append({
            "tenant_id": tenant_id,
            "tenant_slug": slug,
            "module_key": m["key"],
            "enabled": (m["key"] in requested_keys),
            "enabled_at": now,
            "enabled_by": admin.get("email", "platform_admin"),
            "updated_at": now,
        })
    if tm_docs:
        await tenant_modules_collection.insert_many(tm_docs)

    # Insert admin user into the new tenant DB
    tenant_db = get_db_for_tenant_slug(slug)
    admin_user_doc = {
        "email": payload.owner_email,
        "password_hash": get_password_hash(payload.owner_password),
        "role": "super_admin",
        "allowed_project_ids": [],
        "must_change_password": True,
        "created_at": now,
    }
    result = await tenant_db.users.insert_one(admin_user_doc)
    admin_user_id = str(result.inserted_id)

    # Create membership
    membership_doc = {
        "_id": str(uuid.uuid4()),
        "user_id": admin_user_id,
        "user_email": payload.owner_email,
        "tenant_id": tenant_id,
        "tenant_slug": slug,
        "role": "super_admin",
        "created_at": now,
        "source": "platform_create_tenant",
    }
    await memberships_collection.insert_one(membership_doc)

    # Audit
    await _record_audit(
        actor_email=admin.get("email", "unknown"),
        action="tenant.create",
        tenant_slug=slug,
        details={"name": payload.name, "owner_email": payload.owner_email},
    )

    invalidate_tenant_cache()
    return _serialize(tenant_doc)


@router.patch("/tenants/{slug}")
async def update_tenant(
    slug: str,
    payload: TenantUpdate,
    admin: dict = Depends(get_current_platform_admin),
):
    """Update tenant metadata (status, branding, settings)."""
    tenant = await tenants_collection.find_one({"slug": slug})
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{slug}' not found")

    # Prevent status downgrade of the default (DD) tenant
    if payload.status and payload.status != "active" and tenant.get("is_default"):
        raise HTTPException(status_code=400, detail="Cannot change status of the default tenant.")

    if payload.status and payload.status not in ("active", "suspended"):
        raise HTTPException(status_code=400, detail="status must be 'active' or 'suspended'")

    update_doc: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
    if payload.name is not None:
        update_doc["name"] = payload.name
    if payload.status is not None:
        update_doc["status"] = payload.status
    if payload.primary_color is not None:
        update_doc["branding.primary_color"] = payload.primary_color
    if payload.accent_color is not None:
        update_doc["branding.accent_color"] = payload.accent_color
    if payload.logo_url is not None:
        update_doc["branding.logo_url"] = payload.logo_url
    if payload.work_week_hours is not None:
        update_doc["settings.work_week_hours"] = payload.work_week_hours
    if payload.timezone is not None:
        update_doc["settings.timezone"] = payload.timezone

    await tenants_collection.update_one({"slug": slug}, {"$set": update_doc})
    updated = await tenants_collection.find_one({"slug": slug})

    await _record_audit(
        actor_email=admin.get("email", "unknown"),
        action="tenant.update",
        tenant_slug=slug,
        details={"changes": {k: v for k, v in update_doc.items() if k != "updated_at"}},
    )
    invalidate_tenant_cache(slug)
    return _serialize(updated)


@router.delete("/tenants/{slug}")
async def delete_tenant(
    slug: str,
    admin: dict = Depends(get_current_platform_admin),
):
    """Soft-delete a tenant by setting status='deleted'. The tenant DB is NOT dropped
    (data preservation). To permanently delete, use `mongosh` on the tenant DB
    manually — this endpoint intentionally does not offer a hard-delete for safety.
    """
    tenant = await tenants_collection.find_one({"slug": slug})
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{slug}' not found")
    if tenant.get("is_default"):
        raise HTTPException(status_code=400, detail="Cannot delete the default tenant.")

    await tenants_collection.update_one(
        {"slug": slug},
        {"$set": {"status": "deleted", "updated_at": datetime.now(timezone.utc)}},
    )
    await _record_audit(
        actor_email=admin.get("email", "unknown"),
        action="tenant.delete",
        tenant_slug=slug,
        details={"note": "soft-delete; DB preserved"},
    )
    invalidate_tenant_cache(slug)
    return {"status": "deleted", "slug": slug}


# ============================================================================
# Impersonation
# ============================================================================

class ImpersonateResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_slug: str
    expires_in_seconds: int


@router.post("/tenants/{slug}/impersonate", response_model=ImpersonateResponse)
async def impersonate_tenant(
    slug: str,
    admin: dict = Depends(get_current_platform_admin),
):
    """Issue a short-lived (15-min) tenant-type JWT for support purposes.
    
    The token has `token_type=tenant` so it's accepted by the tenant-side
    `get_current_user`. Use case: platform admin opens the tenant workspace in a
    new tab to diagnose a customer issue.
    
    Audit-logged for every use so support activity is traceable.
    """
    tenant = await tenants_collection.find_one({"slug": slug})
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{slug}' not found")
    if tenant.get("status") == "deleted":
        raise HTTPException(status_code=410, detail="Tenant is deleted")

    # Short-lived override — override ACCESS_TOKEN_EXPIRE_MINUTES via custom exp
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=15)
    payload = {
        "sub": admin.get("email", "platform_admin"),
        "tenant_id": str(tenant["_id"]),
        "tenant_slug": slug,
        "token_type": TOKEN_TYPE_TENANT,
        "role": "super_admin",  # Impersonation always gets super_admin in target tenant
        "impersonator": admin.get("email"),
        "exp": exp,
    }
    from jose import jwt
    from database import SECRET_KEY, ALGORITHM
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    await _record_audit(
        actor_email=admin.get("email", "unknown"),
        action="tenant.impersonate",
        tenant_slug=slug,
        details={"exp_minutes": 15},
    )
    return ImpersonateResponse(
        access_token=token,
        token_type="bearer",
        tenant_slug=slug,
        expires_in_seconds=15 * 60,
    )


# ============================================================================
# Audit log
# ============================================================================

@router.get("/audit-log")
async def audit_log(
    admin: dict = Depends(get_current_platform_admin),
    limit: int = 100,
    tenant_slug: Optional[str] = None,
    action: Optional[str] = None,
):
    """Return cross-tenant audit entries, filtered optionally by tenant or action.
    
    Ordered newest-first. Max limit=500.
    """
    limit = max(1, min(limit, 500))
    query: Dict[str, Any] = {}
    if tenant_slug:
        query["tenant_slug"] = tenant_slug
    if action:
        query["action"] = action
    cursor = platform_audit_log_collection.find(query).sort("created_at", -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_serialize(d) for d in docs]


# ============================================================================
# Tenant users introspection
# ============================================================================

@router.get("/tenants/{slug}/users")
async def list_tenant_users(
    slug: str,
    admin: dict = Depends(get_current_platform_admin),
):
    """Return the users of a specific tenant (redacted; no password hashes)."""
    tenant = await tenants_collection.find_one({"slug": slug})
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{slug}' not found")

    from database import get_db_for_tenant_slug
    tenant_db = get_db_for_tenant_slug(slug)
    users_cursor = tenant_db.users.find({}, {"password_hash": 0})
    users = await users_cursor.to_list(length=1000)
    return [_serialize(u) for u in users]
