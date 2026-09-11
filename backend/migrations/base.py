"""
Migration contract for DD Planner.

Every migration module must expose:
  - version: int (monotonic, e.g. 1, 2, 3)
  - description: str
  - scope: str ("tenant" or "platform")
  - async def up(ctx) -> dict

The ctx object provides:
  - For scope="tenant": ctx.tenant_db (AsyncIOMotorDatabase), ctx.tenant_doc (dict), ctx.platform_db
  - For scope="platform": ctx.platform_db

Return a small summary dict from up(), e.g. {"backfilled": 3}.
"""
from typing import Any, Dict
from dataclasses import dataclass
from motor.motor_asyncio import AsyncIOMotorDatabase


@dataclass
class MigrationContext:
    """Context passed to migration up() functions."""
    platform_db: AsyncIOMotorDatabase
    tenant_db: AsyncIOMotorDatabase = None
    tenant_doc: Dict[str, Any] = None
