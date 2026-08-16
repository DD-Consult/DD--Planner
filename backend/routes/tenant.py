"""
Tenant-side module endpoints (Step 6 of MULTITENANT_PLAN.md).

Exposes read-only module status to any authenticated tenant user so that the
frontend can conditionally render features based on what's enabled.

Endpoint:
    GET /api/tenant/modules   -> {module_key: enabled_bool, ...}

Used by the React `useEnabledModules()` hook after login.

Behaviour (both flag states):
  - Reads the actual tenant_modules collection state so platform-admin toggles
    are ALWAYS honored, even in backward-compat (flag=off) mode. This keeps
    the platform admin experience consistent — a toggle affects what tenant
    users see immediately.
  - Falls back to `true` for any module that has no row in tenant_modules
    (safe default for legacy tenants that predate module seeding).
  - When flag=off, backend gating (require_module) is still a no-op, so
    tenant users disabling a feature only impacts the UI (feature stays
    reachable via direct API call — this is intentional: the flag is the
    master enforcement switch).
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from auth.dependencies import get_current_user
from platform_db import (
    modules_catalog_collection,
    tenants_collection,
    tenant_modules_collection,
    MULTI_TENANT_ENABLED,
)

router = APIRouter(prefix="/api/tenant", tags=["tenant"])


async def _resolve_effective_tenant_slug(request: Request) -> str:
    """Determine which tenant to read modules for.
    
    Priority order:
      1. request.state.tenant (set by middleware in multi-tenant mode)
      2. The `is_default=True` tenant in platform_db (backward-compat mode)
      3. Fallback string 'ddconsult' (should never happen in practice)
    """
    tenant = getattr(request.state, "tenant", None)
    if tenant and tenant.get("slug"):
        return tenant.get("slug")
    # Backward-compat: no tenant on request.state -> use default tenant
    default_tenant = await tenants_collection.find_one({"is_default": True})
    if default_tenant:
        return default_tenant.get("slug", "ddconsult")
    return "ddconsult"


@router.get("/modules")
async def get_my_tenant_modules(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Return the enabled/disabled state of every module for the current tenant.
    
    Response shape:
        {
          "tenant_slug": "ddconsult",
          "multi_tenant_enabled": bool,
          "modules": {
            "projects": true,
            "wbs": true,
            "timesheets": false,
            ...
          }
        }
    
    Reads the actual tenant_modules collection in BOTH flag modes so
    platform-admin toggles are always honored by the frontend UI.
    """
    tenant_slug = await _resolve_effective_tenant_slug(request)

    # Look up the tenant to get its ID
    tenant_doc = await tenants_collection.find_one({"slug": tenant_slug})
    tenant_id = str(tenant_doc["_id"]) if tenant_doc else None

    # Load actual tenant_modules state
    stored: dict = {}
    if tenant_id:
        async for row in tenant_modules_collection.find({"tenant_id": tenant_id}):
            stored[row["module_key"]] = bool(row.get("enabled", False))

    # Load full catalog (so response always has all 17 keys, even for legacy tenants)
    all_keys = []
    async for m in modules_catalog_collection.find({}, {"key": 1}):
        all_keys.append(m["key"])

    # Combine: for each module in catalog, take stored value or default to TRUE
    # (safe default: legacy tenants without rows see everything enabled).
    modules = {k: bool(stored.get(k, True)) for k in all_keys}

    # Guard: if catalog itself is empty (should never happen post-seeding),
    # return the raw stored map as a defensive fallback.
    if not all_keys:
        modules = stored or {}

    return {
        "tenant_slug": tenant_slug,
        "multi_tenant_enabled": MULTI_TENANT_ENABLED,
        "modules": modules,
    }


# ============================================================================
# STEP 9 — Per-tenant branding & settings endpoints
# ============================================================================

# Default fallback branding + settings — used when no tenant record exists
# (edge case: legacy tenants pre-Step-1, or DB corruption). Matches the
# original DD Consulting palette so exports still look correct.
_DEFAULT_BRANDING = {
    "logo_url": None,
    "primary_color": "#1B2A47",
    "accent_color": "#C9A84C",
}
_DEFAULT_SETTINGS = {
    "work_week_hours": 40,
    "timezone": "UTC",
    "work_days": [0, 1, 2, 3, 4],  # Mon-Fri
}

# Guard: reject huge base64 logos before they even hit the DB
_MAX_LOGO_BYTES = 500_000  # ~500KB after base64 encoding


class TenantBrandingUpdate(BaseModel):
    """Payload for PATCH /api/tenant/branding.

    All fields optional; only supplied fields are updated (partial updates).
    """
    name: Optional[str] = None
    logo_url: Optional[str] = None  # data:image/png;base64,... or https URL
    primary_color: Optional[str] = None  # 7-char hex (e.g. "#1B2A47")
    accent_color: Optional[str] = None


class TenantSettingsUpdate(BaseModel):
    """Payload for PATCH /api/tenant/settings.
    
    All fields optional; only supplied fields are updated.
    """
    work_week_hours: Optional[int] = None  # 1..168
    timezone: Optional[str] = None  # IANA tz string, e.g. 'Australia/Sydney'


def _valid_hex_color(v: str) -> bool:
    """Validate a #RRGGBB hex color."""
    if not v or not isinstance(v, str):
        return False
    if not v.startswith("#") or len(v) != 7:
        return False
    try:
        int(v[1:], 16)
        return True
    except ValueError:
        return False


async def _get_or_default_tenant(request: Request) -> dict:
    """Return the current tenant record with fallback to a synthesized default.

    Never raises: guarantees a dict with slug/name/branding/settings keys so
    downstream code (e.g. exports) can rely on the shape.
    """
    slug = await _resolve_effective_tenant_slug(request)
    doc = await tenants_collection.find_one({"slug": slug})
    if not doc:
        return {
            "slug": slug or "ddconsult",
            "name": "Workspace",
            "branding": dict(_DEFAULT_BRANDING),
            "settings": dict(_DEFAULT_SETTINGS),
        }
    # Merge with defaults so exports always have every key
    merged_branding = {**_DEFAULT_BRANDING, **(doc.get("branding") or {})}
    merged_settings = {**_DEFAULT_SETTINGS, **(doc.get("settings") or {})}
    return {
        "id": str(doc.get("_id")),
        "slug": doc.get("slug"),
        "name": doc.get("name") or "Workspace",
        "branding": merged_branding,
        "settings": merged_settings,
        "status": doc.get("status"),
    }


@router.get("/branding")
async def get_tenant_branding(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Return name + branding + settings for the current tenant.
    
    Any authenticated tenant user can read this. Used by:
      - Frontend header (logo, primary color styling)
      - Export services (cover slide branding — DD Navy default preserved)
    """
    return await _get_or_default_tenant(request)


@router.patch("/branding")
async def update_tenant_branding(
    request: Request,
    payload: TenantBrandingUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update tenant branding. Super-admin only.
    
    Validates hex colors (`#RRGGBB` only) and enforces logo size cap.
    Writes go to platform_db.tenants for the current tenant.
    """
    from fastapi import HTTPException, status
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin access required")

    slug = await _resolve_effective_tenant_slug(request)
    tenant = await tenants_collection.find_one({"slug": slug})
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{slug}' not found")

    update_ops: dict = {"updated_at": datetime.now(timezone.utc)}
    if payload.name is not None:
        name = payload.name.strip()
        if len(name) < 1 or len(name) > 100:
            raise HTTPException(status_code=400, detail="Name must be 1-100 characters")
        update_ops["name"] = name
    if payload.primary_color is not None:
        if not _valid_hex_color(payload.primary_color):
            raise HTTPException(status_code=400, detail="primary_color must be '#RRGGBB' hex")
        update_ops["branding.primary_color"] = payload.primary_color
    if payload.accent_color is not None:
        if not _valid_hex_color(payload.accent_color):
            raise HTTPException(status_code=400, detail="accent_color must be '#RRGGBB' hex")
        update_ops["branding.accent_color"] = payload.accent_color
    if payload.logo_url is not None:
        # Basic size guard for base64 data URLs
        if payload.logo_url and len(payload.logo_url) > _MAX_LOGO_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"logo_url exceeds max size ({_MAX_LOGO_BYTES} bytes). "
                       "Please upload a smaller image (recommended: <300KB)."
            )
        update_ops["branding.logo_url"] = payload.logo_url or None

    await tenants_collection.update_one({"slug": slug}, {"$set": update_ops})
    # Invalidate the tenant cache so the next read picks up the change
    from middleware.tenant_resolver import invalidate_tenant_cache
    invalidate_tenant_cache(slug)
    return await _get_or_default_tenant(request)


@router.patch("/settings")
async def update_tenant_settings(
    request: Request,
    payload: TenantSettingsUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update tenant work-policy settings. Super-admin only.
    
    - work_week_hours: 1..168 (168 = full week, 40 = standard)
    - timezone: any IANA tz string
    """
    from fastapi import HTTPException, status
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin access required")

    slug = await _resolve_effective_tenant_slug(request)
    tenant = await tenants_collection.find_one({"slug": slug})
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{slug}' not found")

    update_ops: dict = {"updated_at": datetime.now(timezone.utc)}
    if payload.work_week_hours is not None:
        if payload.work_week_hours < 1 or payload.work_week_hours > 168:
            raise HTTPException(status_code=400, detail="work_week_hours must be between 1 and 168")
        update_ops["settings.work_week_hours"] = payload.work_week_hours
    if payload.timezone is not None:
        tz = payload.timezone.strip()
        if not tz or len(tz) > 64:
            raise HTTPException(status_code=400, detail="timezone must be a non-empty IANA string")
        # Validate against pytz (already a dependency)
        try:
            import pytz
            pytz.timezone(tz)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Unknown timezone '{tz}'. Use an IANA tz like 'Australia/Sydney'.")
        update_ops["settings.timezone"] = tz

    await tenants_collection.update_one({"slug": slug}, {"$set": update_ops})
    from middleware.tenant_resolver import invalidate_tenant_cache
    invalidate_tenant_cache(slug)
    return await _get_or_default_tenant(request)


# ============================================================================
# STEP 10 — Integration Isolation
# ----------------------------------------------------------------------------
# integration_settings_collection is a LazyCollection → per-tenant DB routing
# is automatic. This endpoint simply exposes a redacted summary of what's
# configured for the current tenant so the frontend can render setup CTAs
# ("Connect HubSpot", "Rotate MCP Key", etc.) without exposing secrets.
# ============================================================================

@router.get("/integrations-summary")
async def get_integrations_summary(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Return a redacted view of which integrations the CURRENT TENANT has
    configured. Zero secrets in the response — safe for any authenticated
    tenant user.

    Response shape:
        {
          "tenant_slug": "ddconsult",
          "hubspot": {"enabled": bool, "connected": bool, "portal_id": str_or_null},
          "mcp": {"enabled": bool, "has_key": bool, "last_used_at": str_or_null},
          "resend_email": {"configured": bool},   // reads from env, not tenant DB
        }
    """
    from database import integration_settings_collection, RESEND_API_KEY
    tenant_slug = await _resolve_effective_tenant_slug(request)

    doc = await integration_settings_collection.find_one({"org_id": "default"})
    doc = doc or {}
    hs = doc.get("hubspot") or {}
    mcp = doc.get("agent_api") or {}

    return {
        "tenant_slug": tenant_slug,
        "hubspot": {
            "enabled": bool(hs.get("enabled", False)),
            # `connected` = enabled AND has a non-empty token (redacted from response)
            "connected": bool(hs.get("enabled") and hs.get("private_app_token")),
            "portal_id": hs.get("portal_id") or None,
            "trigger_stage": hs.get("trigger_stage") or None,
            "sync_status_updates": bool(hs.get("sync_status_updates", False)),
        },
        "mcp": {
            "enabled": bool(mcp.get("enabled", False)),
            "has_key": bool(mcp.get("api_key")),
            "last_used_at": mcp.get("last_used_at"),
        },
        "resend_email": {
            "configured": bool(RESEND_API_KEY),  # env-scoped, shared across tenants
        },
    }
