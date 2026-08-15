"""
Module toggle guard (Step 6 of MULTITENANT_PLAN.md).

Provides a FastAPI dependency `require_module(key)` that returns a dependency
callable which, when injected into a route, verifies the current tenant has
the given module enabled. Otherwise raises 403.

Usage:
    from middleware.module_guard import require_module

    @router.get("/timesheets", dependencies=[Depends(require_module("timesheets"))])
    async def list_timesheets(...):
        ...

Or on an entire router:
    router = APIRouter(prefix="/api/timesheets", dependencies=[Depends(require_module("timesheets"))])

Behaviour:
  - Multi-tenant flag OFF: always passes (backward compat).
  - Multi-tenant flag ON: reads enabled modules from platform_db.tenant_modules
    for the current request's resolved tenant. Cached in request.state to
    avoid duplicate DB roundtrips per request.
  - If the tenant has NO tenant_modules rows at all (legacy tenant), defaults
    to "all enabled" — safer failure mode.
"""
from fastapi import Depends, HTTPException, status, Request
from typing import Dict, Optional
import os

from platform_db import tenant_modules_collection


def _multi_tenant_enabled() -> bool:
    return os.environ.get('MULTI_TENANT_ENABLED', 'false').lower() == 'true'


async def _load_tenant_modules(tenant_id: str) -> Dict[str, bool]:
    """Load {module_key: enabled} for a tenant from platform_db."""
    result: Dict[str, bool] = {}
    async for doc in tenant_modules_collection.find({"tenant_id": tenant_id}):
        result[doc["module_key"]] = bool(doc.get("enabled", False))
    return result


async def get_current_tenant_modules(request: Request) -> Dict[str, bool]:
    """Return the enabled-modules map for the current request's tenant.
    
    Cached on request.state for the duration of the request.
    Returns empty dict when flag=OFF or no tenant resolved (interpreted as
    "no gating; all modules effectively enabled").
    """
    # Fast-path: cache on request.state
    cached = getattr(request.state, "tenant_modules_cache", None)
    if cached is not None:
        return cached

    if not _multi_tenant_enabled():
        request.state.tenant_modules_cache = {}
        return {}

    tenant = getattr(request.state, "tenant", None)
    if not tenant:
        request.state.tenant_modules_cache = {}
        return {}

    modules = await _load_tenant_modules(tenant.get("id") or tenant.get("_id"))
    request.state.tenant_modules_cache = modules
    return modules


def require_module(module_key: str):
    """Return a FastAPI dependency that ensures `module_key` is enabled for tenant.
    
    Raises 403 with a descriptive detail when the module is disabled.
    
    Example:
        @router.get("/timesheets", dependencies=[Depends(require_module("timesheets"))])
    """
    async def _check(request: Request) -> None:
        # Flag OFF: never gate.
        if not _multi_tenant_enabled():
            return None

        modules = await get_current_tenant_modules(request)

        # If tenant has no tenant_modules rows at all, treat as "all enabled".
        # This is defensive: prevents brand-new or legacy tenants from being
        # locked out of everything before a platform admin assigns modules.
        if not modules:
            return None

        if not modules.get(module_key, False):
            tenant = getattr(request.state, "tenant", {}) or {}
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "module_disabled",
                    "module": module_key,
                    "tenant_slug": tenant.get("slug"),
                    "message": f"The '{module_key}' module is not enabled for this workspace."
                },
            )
        return None

    return _check
