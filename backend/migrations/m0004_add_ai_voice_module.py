"""
Migration 0004 — Add ai_voice module to platform catalog.

Scope: platform

Upserts the ai_voice module into modules_catalog_collection.
Idempotent — safe to run multiple times.
"""
from datetime import datetime, timezone

version = 4
description = "Add ai_voice module to platform catalog"
scope = "platform"


async def up(ctx) -> dict:
    from platform_db import modules_catalog_collection
    
    now = datetime.now(timezone.utc)
    
    ai_voice_module = {
        "key": "ai_voice",
        "name": "AI Voice (Speech)",
        "category": "ai",
        "depends_on": ["ai_copilot"],
        "is_core": False,
        "description": "Speak to the AI Copilot and hear replies (Gemini speech-to-text + text-to-speech).",
        "default_enabled": True,
        "updated_at": now,
    }
    
    # Only set created_at if this is a new insert
    existing = await modules_catalog_collection.find_one({"key": "ai_voice"})
    if not existing:
        ai_voice_module["created_at"] = now
    
    await modules_catalog_collection.replace_one(
        {"key": "ai_voice"},
        ai_voice_module,
        upsert=True
    )
    
    return {"upserted": "ai_voice", "was_new": not bool(existing)}
