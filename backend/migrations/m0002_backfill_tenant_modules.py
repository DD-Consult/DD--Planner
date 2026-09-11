"""
Migration 0002 — Backfill tenant_modules for the given tenant.

Scope: tenant

Ensures a tenant_modules row exists for EVERY module in the catalog.
For any module missing a row for this tenant, inserts one with:
  enabled = catalog.default_enabled (core → always True)

This is what makes NEW modules auto-propagate to existing tenants on deploy.
"""
from datetime import datetime, timezone

version = 2
description = "Backfill tenant_modules for all catalog modules (auto-propagate new modules)"
scope = "tenant"


async def up(ctx) -> dict:
    from platform_db import modules_catalog_collection, tenant_modules_collection
    
    tenant_id = ctx.tenant_doc["_id"]
    tenant_slug = ctx.tenant_doc.get("slug")
    now = datetime.now(timezone.utc)
    
    # Get all catalog modules
    catalog_modules = await modules_catalog_collection.find({}).to_list(length=1000)
    
    # Get existing tenant_modules for this tenant
    existing_keys = set()
    async for row in tenant_modules_collection.find({"tenant_id": tenant_id}):
        existing_keys.add(row["module_key"])
    
    # Insert missing rows
    added = 0
    for module in catalog_modules:
        key = module["key"]
        if key in existing_keys:
            continue
        
        # Determine enabled: use catalog default_enabled (core → always True)
        default_enabled = module.get("default_enabled", True)
        if module.get("is_core"):
            default_enabled = True
        
        doc = {
            "tenant_id": tenant_id,
            "tenant_slug": tenant_slug,
            "module_key": key,
            "enabled": default_enabled,
            "enabled_at": now,
            "enabled_by": "migration_0002",
            "updated_at": now,
        }
        await tenant_modules_collection.insert_one(doc)
        added += 1
    
    return {"added": added}
