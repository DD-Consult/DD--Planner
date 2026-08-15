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
