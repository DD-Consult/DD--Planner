"""
Migration 0006 — Re-sync modules catalog from code to DB.

Scope: platform

Re-runs the catalog upsert so display-name/description changes made in
MODULES_CATALOG (e.g. renaming "AI Copilot" -> "PM Assist") propagate to the
Platform Admin Portal. Non-destructive: upsert-by-key, preserves created_at.
"""
from datetime import datetime, timezone

version = 6
description = "Re-sync modules catalog (propagate display-name/description changes)"
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
        existing = await modules_catalog_collection.find_one({"key": key})
        if existing and existing.get("created_at"):
            doc["created_at"] = existing["created_at"]
        else:
            doc["created_at"] = now

        await modules_catalog_collection.replace_one({"key": key}, doc, upsert=True)
        upserted += 1

    return {"upserted": upserted}
