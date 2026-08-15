"""
Platform-level endpoints for the multi-tenant transformation.

STEP 5 update: Now protected by `get_current_platform_admin` dependency.
When MULTI_TENANT_ENABLED=true, requires a JWT issued by /api/platform/auth/login.
When MULTI_TENANT_ENABLED=false (backward compat), also accepts super_admin JWTs.
"""
from fastapi import APIRouter, HTTPException, Depends, Request
import os

from platform_db import (
    tenants_collection,
    platform_users_collection,
    modules_catalog_collection,
    tenant_modules_collection,
    MULTI_TENANT_ENABLED,
)
from middleware.tenant_resolver import (
    resolve_tenant_from_request,
    get_tenant_enabled_modules,
    extract_subdomain,
)
from auth.dependencies import get_current_user, get_current_platform_admin

router = APIRouter(prefix="/api/platform", tags=["platform"])


def _serialize(doc):
    if not doc:
        return None
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    if "password_hash" in doc:
        del doc["password_hash"]
    return doc


@router.get("/status")
async def platform_status():
    """Public-ish observability endpoint: shows whether platform DB is seeded.
    
    Always available (regardless of MULTI_TENANT_ENABLED flag) so ops can verify
    the platform layer is healthy after Step 1 deployment.
    """
    try:
        tenants_count = await tenants_collection.count_documents({})
        modules_count = await modules_catalog_collection.count_documents({})
        platform_users_count = await platform_users_collection.count_documents({})
        tenant_modules_count = await tenant_modules_collection.count_documents({})
        return {
            "multi_tenant_enabled": MULTI_TENANT_ENABLED,
            "platform_db_ready": tenants_count > 0 and modules_count > 0,
            "counts": {
                "tenants": tenants_count,
                "modules_in_catalog": modules_count,
                "platform_users": platform_users_count,
                "tenant_module_entries": tenant_modules_count,
            }
        }
    except Exception as e:
        return {"error": str(e), "platform_db_ready": False}


@router.get("/tenants")
async def list_tenants(admin: dict = Depends(get_current_platform_admin)):
    """List all tenants. Platform admin only.
    
    In multi-tenant mode: requires JWT from /api/platform/auth/login.
    In backward-compat mode: also accepts super_admin JWTs (see get_current_platform_admin).
    """
    cursor = tenants_collection.find({}).sort("created_at", 1)
    docs = await cursor.to_list(length=1000)
    return [_serialize(d) for d in docs]


@router.get("/modules")
async def list_modules_catalog(admin: dict = Depends(get_current_platform_admin)):
    """List all modules in the catalog (17 modules). Platform admin only."""
    cursor = modules_catalog_collection.find({}).sort("category", 1)
    docs = await cursor.to_list(length=100)
    return [_serialize(d) for d in docs]


@router.get("/tenants/{slug}/modules")
async def get_tenant_modules(slug: str, admin: dict = Depends(get_current_platform_admin)):
    """Get the enabled/disabled status of all modules for a given tenant. Platform admin only."""
    tenant = await tenants_collection.find_one({"slug": slug})
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{slug}' not found")
    tenant_id = str(tenant["_id"])
    cursor = tenant_modules_collection.find({"tenant_id": tenant_id})
    docs = await cursor.to_list(length=100)
    # Enrich with catalog metadata
    catalog_map = {}
    async for m in modules_catalog_collection.find({}):
        catalog_map[m["key"]] = m
    enriched = []
    for d in docs:
        cat = catalog_map.get(d["module_key"], {})
        enriched.append({
            "module_key": d["module_key"],
            "name": cat.get("name", d["module_key"]),
            "category": cat.get("category", "other"),
            "depends_on": cat.get("depends_on", []),
            "is_core": cat.get("is_core", False),
            "enabled": d.get("enabled", False),
            "description": cat.get("description", ""),
        })
    return {
        "tenant_slug": slug,
        "tenant_name": tenant.get("name"),
        "modules": enriched
    }


# ============================================================================
# STEP 2: Tenant Resolution Endpoints
# ============================================================================

@router.get("/whoami-tenant")
async def whoami_tenant(request: Request):
    """Debug endpoint: shows how the tenant resolver interprets this request.

    Returns:
      - host: the raw Host header
      - subdomain: extracted subdomain (or null)
      - resolution_mode: 'flag_off' | 'subdomain' | 'default_fallback' | 'platform' | 'reserved'
      - is_platform: true if this is the admin.* subdomain
      - tenant: the resolved tenant record (redacted; no password hashes anywhere)
      - enabled_modules: {module_key: bool} for the resolved tenant (empty if platform)

    No auth required — this is a purely diagnostic endpoint for verifying that
    subdomain-based routing is working correctly. Safe to expose because it
    only reveals metadata about the current request's own tenant.
    """
    host = request.headers.get("host", "")
    result = await resolve_tenant_from_request(request)

    tenant = result.get("tenant")
    enabled_modules: dict = {}
    tenant_summary = None
    if tenant:
        tenant_summary = {
            "id": tenant.get("id"),
            "slug": tenant.get("slug"),
            "name": tenant.get("name"),
            "db_name": tenant.get("db_name"),
            "status": tenant.get("status"),
            "is_default": tenant.get("is_default", False),
            "branding": tenant.get("branding", {}),
            "settings": tenant.get("settings", {}),
        }
        enabled_modules = await get_tenant_enabled_modules(tenant["id"])

    return {
        "host": host,
        "subdomain": result.get("subdomain"),
        "resolution_mode": result.get("resolution_mode"),
        "is_platform": result.get("is_platform"),
        "multi_tenant_enabled": MULTI_TENANT_ENABLED,
        "tenant": tenant_summary,
        "enabled_modules": enabled_modules,
    }


@router.get("/resolve-subdomain")
async def resolve_subdomain_debug(host: str):
    """Standalone subdomain-parser test endpoint.

    Useful for verifying edge cases without actually sending requests with
    different Host headers:
        GET /api/platform/resolve-subdomain?host=ddconsult.ddplanner.io
        GET /api/platform/resolve-subdomain?host=admin.ddplanner.io
        GET /api/platform/resolve-subdomain?host=localhost:8001
    """
    sub = extract_subdomain(host)
    return {"host": host, "subdomain": sub}
