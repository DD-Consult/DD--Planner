"""
Tenant Resolution Middleware / Dependency (Step 2 of MULTITENANT_PLAN.md).

Given an incoming HTTP request, this module figures out which tenant it
belongs to based on the `Host` header (subdomain routing).

Examples:
    ddconsult.ddplanner.io      -> tenant "ddconsult"
    acme.ddplanner.io           -> tenant "acme"
    admin.ddplanner.io          -> platform portal (subdomain='admin', tenant=None)
    ddplanner.io                -> no subdomain, falls back to default tenant
    localhost:8001              -> dev fallback, uses default tenant
    ddconsult.localhost:8001    -> tenant "ddconsult" (dev)
    <uuid>.preview.emergentagent.com -> emergent preview URL, uses default tenant

Behaviour is gated by MULTI_TENANT_ENABLED:
    False (default)  -> always returns the "default" tenant (DD Consulting).
                        This preserves existing behaviour 100%.
    True             -> full subdomain-based resolution with 404 on unknown tenants.

The resolved tenant is cached in-memory for 60 seconds to keep hot-path lookups
fast. Cache is invalidated automatically when tenant records change (via the
`invalidate_tenant_cache` helper called from platform routes in Step 5+).
"""
from fastapi import Request, HTTPException, Depends
from typing import Optional, Dict, Any
import time
import logging

from platform_db import (
    tenants_collection,
    tenant_modules_collection,
    MULTI_TENANT_ENABLED,
)

logger = logging.getLogger(__name__)

# --- Reserved subdomains (never resolve to a tenant) ---
RESERVED_SUBDOMAINS = {
    "admin",       # Platform admin portal (Step 7)
    "www",         # Marketing site
    "api",         # API-only endpoint (future)
    "app",         # Marketing redirect
    "docs",        # Documentation site
    "status",      # Status page
    "help",        # Help/support
    "static",      # Static assets
    "cdn",         # CDN
    "mail",        # Email
    "smtp",        # Email
}

# --- Emergent / preview host suffixes to treat as "default tenant" in dev ---
# These are all treated as "no subdomain" so requests fall back to the default
# tenant. Extend this list when deploying to a new preview/dev environment.
_DEV_HOST_SUFFIXES = (
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    ".emergentagent.com",     # public preview URL
    ".emergent.host",          # legacy
    ".emergentcf.cloud",       # internal cluster/ingress-rewritten host
    ".cluster.local",          # k8s internal service DNS
    ".svc.cluster.local",      # k8s services
    ".preview.emergentcf.cloud",  # preview cluster ingress
)

# --- Simple in-memory cache: {slug: (tenant_doc, expires_at)} ---
_TENANT_CACHE: Dict[str, tuple] = {}
_CACHE_TTL_SECONDS = 60


def _now() -> float:
    return time.time()


def invalidate_tenant_cache(slug: Optional[str] = None):
    """Clear cache for one tenant, or the whole cache if slug is None."""
    global _TENANT_CACHE
    if slug is None:
        _TENANT_CACHE.clear()
    else:
        _TENANT_CACHE.pop(slug, None)
        _TENANT_CACHE.pop("__default__", None)  # Also drop default so it's re-fetched


async def _lookup_tenant_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """Fetch a tenant record by slug, with caching."""
    cached = _TENANT_CACHE.get(slug)
    if cached and cached[1] > _now():
        return cached[0]
    doc = await tenants_collection.find_one({"slug": slug, "status": "active"})
    if doc:
        # Normalize _id -> id
        doc = dict(doc)
        doc["id"] = str(doc.pop("_id"))
        _TENANT_CACHE[slug] = (doc, _now() + _CACHE_TTL_SECONDS)
    return doc


async def _lookup_default_tenant() -> Optional[Dict[str, Any]]:
    """Fetch the tenant marked as is_default=True (used when subdomain missing)."""
    cached = _TENANT_CACHE.get("__default__")
    if cached and cached[1] > _now():
        return cached[0]
    doc = await tenants_collection.find_one({"is_default": True, "status": "active"})
    if not doc:
        # Ultimate fallback: any active tenant
        doc = await tenants_collection.find_one({"status": "active"})
    if doc:
        doc = dict(doc)
        doc["id"] = str(doc.pop("_id"))
        _TENANT_CACHE["__default__"] = (doc, _now() + _CACHE_TTL_SECONDS)
    return doc


def extract_subdomain(host_header: str) -> Optional[str]:
    """Extract the subdomain portion of a Host header.

    Returns None if no subdomain (root domain, IP, localhost, or preview URL).
    Returns the subdomain string otherwise (e.g. 'ddconsult', 'admin', 'acme').

    Examples:
        'ddconsult.ddplanner.io'          -> 'ddconsult'
        'admin.ddplanner.io'              -> 'admin'
        'ddplanner.io'                    -> None
        'localhost:8001'                  -> None
        'ddconsult.localhost:8001'        -> 'ddconsult'
        'foo.preview.emergentagent.com'   -> None (treated as dev/preview)
        '192.168.1.5'                     -> None
    """
    if not host_header:
        return None
    # Strip port
    host = host_header.split(":")[0].strip().lower()
    if not host:
        return None
    # Reject bare IPs (rough check)
    if all(part.isdigit() for part in host.split(".")):
        return None
    # Preview / dev hosts: check suffix match, treat as "no subdomain" so we
    # fall back to the default tenant automatically in these environments.
    for suffix in _DEV_HOST_SUFFIXES:
        if host == suffix.lstrip("."):
            return None
        if suffix.startswith(".") and host.endswith(suffix):
            return None
    # localhost variants (dev): host = 'ddconsult.localhost' etc.
    parts = host.split(".")
    if len(parts) >= 2 and parts[-1] == "localhost":
        # ddconsult.localhost -> subdomain = 'ddconsult'
        return parts[0] if len(parts) >= 2 else None
    # Normal domain rules: need at least 3 parts (sub.domain.tld) to have a subdomain
    if len(parts) < 3:
        return None
    # First part is the subdomain (ignore www)
    sub = parts[0]
    if sub == "www":
        return None
    return sub


async def resolve_tenant_from_request(request: Request) -> Dict[str, Any]:
    """Resolve the tenant for an incoming request.

    Returns a dict:
        {
          "tenant": <tenant doc or None>,   # None only for platform portal (admin.*)
          "subdomain": <str or None>,       # Raw subdomain extracted
          "is_platform": <bool>,            # True if admin.* subdomain
          "resolution_mode": <str>,          # 'flag_off' | 'subdomain' | 'default_fallback' | 'platform'
        }

    Behaviour:
      - If MULTI_TENANT_ENABLED=false: always returns the default tenant.
        This is the safe backward-compat mode.
      - If MULTI_TENANT_ENABLED=true:
          * subdomain == 'admin' -> is_platform=True, tenant=None
          * subdomain matches a tenant slug -> that tenant
          * no subdomain -> default tenant (marketing / dev)
          * subdomain doesn't match -> 404
    """
    host = request.headers.get("host", "")
    subdomain = extract_subdomain(host)

    # --- Backward-compat mode (feature flag OFF) ---
    if not MULTI_TENANT_ENABLED:
        tenant = await _lookup_default_tenant()
        return {
            "tenant": tenant,
            "subdomain": subdomain,
            "is_platform": False,
            "resolution_mode": "flag_off",
        }

    # --- Multi-tenant mode (feature flag ON) ---
    # Platform portal (admin subdomain reserved)
    if subdomain == "admin":
        return {
            "tenant": None,
            "subdomain": subdomain,
            "is_platform": True,
            "resolution_mode": "platform",
        }

    # Other reserved subdomains -> no tenant (marketing routes)
    if subdomain in RESERVED_SUBDOMAINS:
        return {
            "tenant": None,
            "subdomain": subdomain,
            "is_platform": False,
            "resolution_mode": "reserved",
        }

    # No subdomain -> use default tenant (marketing site, or dev environment)
    if not subdomain:
        tenant = await _lookup_default_tenant()
        return {
            "tenant": tenant,
            "subdomain": None,
            "is_platform": False,
            "resolution_mode": "default_fallback",
        }

    # Real subdomain -> look up tenant by slug
    tenant = await _lookup_tenant_by_slug(subdomain)
    if not tenant:
        raise HTTPException(
            status_code=404,
            detail=f"Tenant '{subdomain}' not found or inactive"
        )
    return {
        "tenant": tenant,
        "subdomain": subdomain,
        "is_platform": False,
        "resolution_mode": "subdomain",
    }


# --- FastAPI dependency helpers ---


async def get_current_tenant(request: Request) -> Dict[str, Any]:
    """Dependency: returns the resolved tenant record for this request.

    Raises 404 if no tenant is resolvable (only happens in multi-tenant mode
    with unknown subdomain). Raises 400 if this is a platform-portal request
    (admin.*) — those requests should not use this dependency.
    """
    result = await resolve_tenant_from_request(request)
    if result["is_platform"]:
        raise HTTPException(
            status_code=400,
            detail="This endpoint is not available on the platform admin portal"
        )
    tenant = result["tenant"]
    if not tenant:
        raise HTTPException(status_code=404, detail="No tenant resolved for this request")
    # Stash on request state so downstream code (Step 4+) can access without
    # re-running the dependency.
    request.state.tenant = tenant
    return tenant


async def get_tenant_context(request: Request) -> Dict[str, Any]:
    """Dependency: returns the full resolution context (may include is_platform=True).

    Use this for endpoints that should work on BOTH tenant subdomains AND the
    platform portal (very rare — mostly used by /api/whoami-tenant debug endpoint).
    """
    result = await resolve_tenant_from_request(request)
    if result.get("tenant"):
        request.state.tenant = result["tenant"]
    return result


async def get_tenant_enabled_modules(tenant_id: str) -> Dict[str, bool]:
    """Return {module_key: enabled_bool} for a given tenant.

    Used by Step 6 (module gates). In Step 2 we expose it via the whoami endpoint
    so the frontend can start reading it (safely defaults to all-enabled if the
    tenant has no tenant_modules rows, e.g. legacy DD data).
    """
    result: Dict[str, bool] = {}
    async for doc in tenant_modules_collection.find({"tenant_id": tenant_id}):
        result[doc["module_key"]] = bool(doc.get("enabled", False))
    return result
