"""
Migration 0005 — Backfill ai_voice module for existing tenants.

Scope: tenant

Ensures a tenant_modules row exists for the ai_voice module for this tenant.
Inserts with enabled = default_enabled (True) if missing.
"""
from datetime import datetime, timezone

version = 5
description = "Backfill ai_voice module enablement for existing tenants"
scope = "tenant"


async def up(ctx) -> dict:
    from platform_db import modules_catalog_collection, tenant_modules_collection
    
    tenant_id = ctx.tenant_doc["_id"]
    tenant_slug = ctx.tenant_doc.get("slug")
    now = datetime.now(timezone.utc)
    
    # Get ai_voice from catalog
    ai_voice_catalog = await modules_catalog_collection.find_one({"key": "ai_voice"})
    if not ai_voice_catalog:
        return {"skipped": "ai_voice module not in catalog yet"}
    
    # Check if this tenant already has ai_voice enabled
    existing = await tenant_modules_collection.find_one({
        "tenant_id": tenant_id,
        "module_key": "ai_voice"
    })
    
    if existing:
        return {"already_exists": True}
    
    # Insert the tenant_modules row
    default_enabled = ai_voice_catalog.get("default_enabled", True)
    
    doc = {
        "tenant_id": tenant_id,
        "tenant_slug": tenant_slug,
        "module_key": "ai_voice",
        "enabled": default_enabled,
        "enabled_at": now,
        "enabled_by": "migration_0005",
        "updated_at": now,
    }
    await tenant_modules_collection.insert_one(doc)
    
    return {"added": "ai_voice", "enabled": default_enabled}
