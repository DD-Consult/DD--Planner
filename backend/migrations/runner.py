"""
Migration runner for DD Planner — fan-out across all tenants.

Responsibilities:
  - Auto-discover migration modules (mNNNN_*.py) in migrations/ folder
  - Track applied migrations per tenant DB in _migrations collection
  - Provide get_status() to show pending migrations
  - Provide run_all(actor) to run all pending (platform first, then fan-out to tenants)
  - Provide run_for_tenant(slug, actor) for single-tenant runs
  - Concurrency guard with lock doc in platform_db._migration_locks
"""
import importlib
import importlib.util
import os
import re
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import asyncio

from motor.motor_asyncio import AsyncIOMotorDatabase

from migrations.base import MigrationContext

logger = logging.getLogger(__name__)


def _discover_migrations() -> List[Dict[str, Any]]:
    """Discover all migration modules in the migrations/ folder.
    
    Returns sorted list of dicts: [{module_name, filepath, version, description, scope, up_func}, ...]
    """
    migrations_dir = os.path.dirname(__file__)
    pattern = re.compile(r"^m(\d+)_.+\.py$")
    discovered = []
    
    for filename in os.listdir(migrations_dir):
        match = pattern.match(filename)
        if not match:
            continue
        
        module_name = filename[:-3]  # strip .py
        filepath = os.path.join(migrations_dir, filename)
        
        # Dynamically import
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        if not spec or not spec.loader:
            logger.warning(f"[MIGRATIONS] Could not load spec for {filename}")
            continue
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            logger.error(f"[MIGRATIONS] Error loading {filename}: {e}")
            continue
        
        # Validate contract
        if not hasattr(mod, "version") or not hasattr(mod, "description") or not hasattr(mod, "scope") or not hasattr(mod, "up"):
            logger.warning(f"[MIGRATIONS] {filename} missing required attributes (version, description, scope, up)")
            continue
        
        version = int(mod.version)
        description = str(mod.description)
        scope = str(mod.scope)
        up_func = mod.up
        
        if scope not in ("platform", "tenant"):
            logger.warning(f"[MIGRATIONS] {filename} has invalid scope '{scope}' (must be 'platform' or 'tenant')")
            continue
        
        discovered.append({
            "module_name": module_name,
            "filepath": filepath,
            "version": version,
            "description": description,
            "scope": scope,
            "up": up_func,
        })
    
    # Sort by version
    discovered.sort(key=lambda m: m["version"])
    logger.info(f"[MIGRATIONS] Discovered {len(discovered)} migrations: {[m['module_name'] for m in discovered]}")
    return discovered


async def _get_applied_versions(db: AsyncIOMotorDatabase) -> List[int]:
    """Return list of applied migration versions from _migrations collection."""
    cursor = db["_migrations"].find({"status": "success"}, {"version": 1})
    docs = await cursor.to_list(length=10000)
    return [int(doc["version"]) for doc in docs]


async def _mark_migration(db: AsyncIOMotorDatabase, version: int, description: str, status: str, summary: dict = None):
    """Insert or update a migration tracking record."""
    doc = {
        "_id": str(version),
        "version": version,
        "description": description,
        "applied_at": datetime.now(timezone.utc),
        "status": status,
        "summary": summary or {},
    }
    await db["_migrations"].replace_one({"_id": str(version)}, doc, upsert=True)


async def _acquire_lock(platform_db: AsyncIOMotorDatabase) -> bool:
    """Acquire a migration lock. Returns True if acquired, False if already running."""
    locks_coll = platform_db["_migration_locks"]
    now = datetime.now(timezone.utc)
    stale_threshold = now - timedelta(minutes=15)
    
    # Clean up stale locks
    await locks_coll.delete_many({"started_at": {"$lt": stale_threshold}})
    
    # Try to insert lock
    try:
        await locks_coll.insert_one({
            "_id": "global",
            "running": True,
            "started_at": now,
        })
        return True
    except Exception:
        # Lock already exists
        return False


async def _release_lock(platform_db: AsyncIOMotorDatabase):
    """Release the migration lock."""
    await platform_db["_migration_locks"].delete_one({"_id": "global"})


async def get_status() -> dict:
    """Return migration status for platform and all tenants.
    
    Shape:
    {
      "latest_version": int,
      "platform": {"applied": int, "pending": [ints]},
      "tenants": [{"slug", "name", "applied": int, "pending": [ints], "status": "up_to_date"|"pending"|"error"}]
    }
    """
    from platform_db import platform_db, tenants_collection
    from database import get_db_for_tenant_slug
    
    all_migrations = _discover_migrations()
    latest_version = max([m["version"] for m in all_migrations], default=0)
    
    # Platform migrations
    platform_migrations = [m for m in all_migrations if m["scope"] == "platform"]
    platform_applied = await _get_applied_versions(platform_db)
    platform_applied_max = max(platform_applied, default=0)
    platform_pending = [m["version"] for m in platform_migrations if m["version"] not in platform_applied]
    
    # Tenant migrations
    tenant_migrations = [m for m in all_migrations if m["scope"] == "tenant"]
    tenants_status = []
    
    async for tenant in tenants_collection.find({"status": {"$in": ["active", "suspended"]}}):
        slug = tenant.get("slug")
        name = tenant.get("name", slug)
        tenant_db = get_db_for_tenant_slug(slug)
        
        try:
            applied = await _get_applied_versions(tenant_db)
            applied_max = max(applied, default=0)
            pending = [m["version"] for m in tenant_migrations if m["version"] not in applied]
            
            if pending:
                status_str = "pending"
            else:
                status_str = "up_to_date"
        except Exception as e:
            logger.error(f"[MIGRATIONS] Error getting status for tenant {slug}: {e}")
            applied_max = 0
            pending = [m["version"] for m in tenant_migrations]
            status_str = "error"
        
        tenants_status.append({
            "slug": slug,
            "name": name,
            "applied": applied_max,
            "pending": pending,
            "status": status_str,
        })
    
    return {
        "latest_version": latest_version,
        "platform": {
            "applied": platform_applied_max,
            "pending": platform_pending,
        },
        "tenants": tenants_status,
    }


async def run_all(actor: str = "system") -> dict:
    """Run all pending migrations (platform first, then fan-out to all tenants).
    
    Returns a detailed report dict.
    """
    from platform_db import platform_db, tenants_collection, platform_audit_log_collection
    from database import get_db_for_tenant_slug
    import uuid
    
    started_at = datetime.now(timezone.utc)
    
    # Acquire lock
    if not await _acquire_lock(platform_db):
        logger.info("[MIGRATIONS] Another migration run is already in progress")
        return {"skipped": True, "reason": "already_running"}
    
    try:
        all_migrations = _discover_migrations()
        report = {
            "started_at": started_at.isoformat(),
            "actor": actor,
            "platform": {"applied": [], "errors": []},
            "tenants": [],
        }
        
        # 1. Run platform migrations
        platform_migrations = [m for m in all_migrations if m["scope"] == "platform"]
        platform_applied = await _get_applied_versions(platform_db)
        
        for mig in platform_migrations:
            if mig["version"] in platform_applied:
                continue
            
            logger.info(f"[MIGRATIONS] Running platform migration v{mig['version']}: {mig['description']}")
            ctx = MigrationContext(platform_db=platform_db)
            try:
                summary = await mig["up"](ctx)
                await _mark_migration(platform_db, mig["version"], mig["description"], "success", summary)
                report["platform"]["applied"].append(mig["version"])
                logger.info(f"[MIGRATIONS] Platform v{mig['version']} SUCCESS: {summary}")
            except Exception as e:
                logger.error(f"[MIGRATIONS] Platform v{mig['version']} FAILED: {e}", exc_info=True)
                await _mark_migration(platform_db, mig["version"], mig["description"], "failed", {"error": str(e)})
                report["platform"]["errors"].append({"version": mig["version"], "error": str(e)})
        
        # 2. Run tenant migrations (fan-out)
        tenant_migrations = [m for m in all_migrations if m["scope"] == "tenant"]
        
        async for tenant in tenants_collection.find({"status": {"$in": ["active", "suspended"]}}):
            slug = tenant.get("slug")
            tenant_db = get_db_for_tenant_slug(slug)
            tenant_applied = await _get_applied_versions(tenant_db)
            
            tenant_report = {
                "slug": slug,
                "name": tenant.get("name", slug),
                "applied": [],
                "errors": [],
            }
            
            for mig in tenant_migrations:
                if mig["version"] in tenant_applied:
                    continue
                
                logger.info(f"[MIGRATIONS] Running tenant {slug} v{mig['version']}: {mig['description']}")
                ctx = MigrationContext(platform_db=platform_db, tenant_db=tenant_db, tenant_doc=tenant)
                try:
                    summary = await mig["up"](ctx)
                    await _mark_migration(tenant_db, mig["version"], mig["description"], "success", summary)
                    tenant_report["applied"].append(mig["version"])
                    logger.info(f"[MIGRATIONS] Tenant {slug} v{mig['version']} SUCCESS: {summary}")
                except Exception as e:
                    logger.error(f"[MIGRATIONS] Tenant {slug} v{mig['version']} FAILED: {e}", exc_info=True)
                    await _mark_migration(tenant_db, mig["version"], mig["description"], "failed", {"error": str(e)})
                    tenant_report["errors"].append({"version": mig["version"], "error": str(e)})
            
            report["tenants"].append(tenant_report)
        
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        
        # Audit log
        try:
            await platform_audit_log_collection.insert_one({
                "_id": str(uuid.uuid4()),
                "actor_email": actor,
                "action": "migrations.run",
                "tenant_slug": None,
                "target": "all",
                "details": {
                    "platform_applied": report["platform"]["applied"],
                    "tenants_count": len(report["tenants"]),
                },
                "created_at": datetime.now(timezone.utc),
            })
        except Exception:
            pass
        
        return report
    
    finally:
        await _release_lock(platform_db)


async def run_for_tenant(slug: str, actor: str = "system") -> dict:
    """Run pending tenant migrations for a single tenant."""
    from platform_db import platform_db, tenants_collection, platform_audit_log_collection
    from database import get_db_for_tenant_slug
    import uuid
    
    started_at = datetime.now(timezone.utc)
    
    tenant = await tenants_collection.find_one({"slug": slug})
    if not tenant:
        return {"error": f"Tenant '{slug}' not found"}
    
    tenant_db = get_db_for_tenant_slug(slug)
    all_migrations = _discover_migrations()
    tenant_migrations = [m for m in all_migrations if m["scope"] == "tenant"]
    tenant_applied = await _get_applied_versions(tenant_db)
    
    report = {
        "started_at": started_at.isoformat(),
        "actor": actor,
        "tenant_slug": slug,
        "applied": [],
        "errors": [],
    }
    
    for mig in tenant_migrations:
        if mig["version"] in tenant_applied:
            continue
        
        logger.info(f"[MIGRATIONS] Running tenant {slug} v{mig['version']}: {mig['description']}")
        ctx = MigrationContext(platform_db=platform_db, tenant_db=tenant_db, tenant_doc=tenant)
        try:
            summary = await mig["up"](ctx)
            await _mark_migration(tenant_db, mig["version"], mig["description"], "success", summary)
            report["applied"].append(mig["version"])
            logger.info(f"[MIGRATIONS] Tenant {slug} v{mig['version']} SUCCESS: {summary}")
        except Exception as e:
            logger.error(f"[MIGRATIONS] Tenant {slug} v{mig['version']} FAILED: {e}", exc_info=True)
            await _mark_migration(tenant_db, mig["version"], mig["description"], "failed", {"error": str(e)})
            report["errors"].append({"version": mig["version"], "error": str(e)})
    
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    
    # Audit log
    try:
        await platform_audit_log_collection.insert_one({
            "_id": str(uuid.uuid4()),
            "actor_email": actor,
            "action": "migrations.run",
            "tenant_slug": slug,
            "target": slug,
            "details": {"applied": report["applied"]},
            "created_at": datetime.now(timezone.utc),
        })
    except Exception:
        pass
    
    return report
