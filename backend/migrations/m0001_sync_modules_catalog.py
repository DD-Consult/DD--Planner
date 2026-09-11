"""
Migration 0001 — Sync modules catalog from code to DB.

Scope: platform

Upserts every module from MODULES_CATALOG into modules_catalog_collection by key.
Adds/ensures a default_enabled field on each catalog doc (default True unless
the module dict has default_enabled=False; core modules always True).

Non-destructive: does not delete catalog entries absent from code.
"""
from datetime import datetime, timezone

version = 1
description = "Sync modules catalog from code to DB (non-destructive upsert)"
scope = "platform"


async def up(ctx) -> dict:
    from platform_db import modules_catalog_collection, MODULES_CATALOG
    
    now = datetime.now(timezone.utc)
    upserted = 0
    
    for module in MODULES_CATALOG:
        key = module["key"]
        default_enabled = module.get("default_enabled", True)
        if module.get("is_core"):
            default_enabled = True
        
        doc = {
            **module,
            "default_enabled": default_enabled,
            "updated_at": now,
        }
        # Ensure created_at only on insert, not update
        existing = await modules_catalog_collection.find_one({"key": key})
        if not existing:
            doc["created_at"] = now
        
        await modules_catalog_collection.replace_one({"key": key}, doc, upsert=True)
        upserted += 1
    
    return {"upserted": upserted}
