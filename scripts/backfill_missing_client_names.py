#!/usr/bin/env python3
"""
Backfill script to set client_name = "" on any project documents missing that field.
This prevents ResponseValidationError on GET /api/projects endpoints.
Safe to run multiple times (idempotent).
"""
import asyncio
import os
import sys
from pathlib import Path

# Add backend to path for imports
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load environment variables
env_path = backend_path / ".env"
load_dotenv(env_path)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "resource_planner")


async def backfill_client_names():
    """Set client_name = '' on any project documents that lack it."""
    print(f"Connecting to MongoDB at {MONGO_URL}, database: {DB_NAME}")
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    projects_col = db["projects"]
    
    # Find all projects without client_name field
    print("\nSearching for projects missing client_name field...")
    missing_client_name = await projects_col.count_documents({
        "client_name": {"$exists": False}
    })
    
    print(f"Found {missing_client_name} project(s) without client_name field")
    
    if missing_client_name == 0:
        print("✅ No projects need backfilling. All projects have client_name field.")
        client.close()
        return
    
    # Update all projects missing client_name, set to empty string
    result = await projects_col.update_many(
        {"client_name": {"$exists": False}},
        {"$set": {"client_name": ""}}
    )
    
    print(f"✅ Backfilled {result.modified_count} project document(s) with client_name = ''")
    
    # Verify fix
    remaining = await projects_col.count_documents({
        "client_name": {"$exists": False}
    })
    
    if remaining == 0:
        print("✅ Verification passed: All projects now have client_name field")
    else:
        print(f"⚠️  Warning: {remaining} project(s) still missing client_name")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(backfill_client_names())
