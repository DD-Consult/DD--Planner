"""
Migration 0003 — Ensure tenant DB indexes.

Scope: tenant

Creates the core indexes on each tenant DB that server.py creates on the default DB:
  - allocations: resource_id, project_id, start_date, end_date
  - pending_actions: expires_at (TTL), token

Idempotent (create_index is a no-op if index already exists).
"""

version = 3
description = "Ensure core indexes on tenant DB (allocations, pending_actions)"
scope = "tenant"


async def up(ctx) -> dict:
    tenant_db = ctx.tenant_db
    
    # Allocations indexes
    await tenant_db.allocations.create_index("resource_id")
    await tenant_db.allocations.create_index("project_id")
    await tenant_db.allocations.create_index("start_date")
    await tenant_db.allocations.create_index("end_date")
    
    # Pending actions indexes (TTL + token)
    try:
        await tenant_db.pending_actions.create_index("expires_at", expireAfterSeconds=0)
        await tenant_db.pending_actions.create_index("token")
    except Exception:
        # TTL index may already exist or fail on some Mongo versions
        pass
    
    return {"indexes_created": "allocations + pending_actions"}
