#!/usr/bin/env python3
"""
DD Planner — Production Database Migration Script

Exports FULL production data from the Emergent deployment and imports it
into any target MongoDB (Atlas, local, Cloud Run, etc.).

Usage:
  # Step 1: Export from production (already done — uses /api/export ZIP endpoint)
  python3 migrate_production_db.py export

  # Step 2: Import into target MongoDB
  python3 migrate_production_db.py import --target-mongo "mongodb+srv://user:pass@cluster/db"

  # Step 3: Verify
  python3 migrate_production_db.py verify --target-mongo "mongodb+srv://user:pass@cluster/db"
"""

import asyncio
import json
import os
import sys
import zipfile
import requests
from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

PROD_URL = "https://smartplanning-r-1770818389.emergent.host"
PROD_EMAIL = "don@ddconsult.tech"
PROD_PASSWORD = "@Ddplanner2026"
EXPORT_API_KEY = "0ulG5kuzP1NRFKk8kH4D1GM0jd7IgMfZECLnAFIO_zvHNDA8hk8QI5pB9NVPaHlB"
EXPORT_DIR = "/tmp/prod_migration"


def export_from_production():
    """Download the full database export ZIP from production."""
    print(f"[EXPORT] Downloading from {PROD_URL}/api/export ...")
    os.makedirs(EXPORT_DIR, exist_ok=True)

    resp = requests.get(
        f"{PROD_URL}/api/export",
        params={"key": EXPORT_API_KEY},
        timeout=60,
    )
    if resp.status_code != 200:
        print(f"[EXPORT] FAILED: HTTP {resp.status_code} — {resp.text[:200]}")
        sys.exit(1)

    zip_path = os.path.join(EXPORT_DIR, "production_export.zip")
    with open(zip_path, "wb") as f:
        f.write(resp.content)
    print(f"[EXPORT] Saved {len(resp.content)} bytes → {zip_path}")

    # Extract
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(EXPORT_DIR)
        for name in z.namelist():
            filepath = os.path.join(EXPORT_DIR, name)
            with open(filepath) as f:
                data = json.load(f)
            count = len(data) if isinstance(data, list) else "metadata"
            print(f"  {name}: {count}")

    print("[EXPORT] Done.")
    return EXPORT_DIR


def parse_date(val):
    """Try to parse a date string back to datetime for MongoDB storage."""
    if val is None or val == "" or val == "null":
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d"):
            try:
                return datetime.strptime(val.rstrip("Z"), fmt)
            except ValueError:
                continue
    return val  # return as-is if unparseable


def restore_objectids(doc):
    """Convert 'id' fields back to '_id' ObjectId for MongoDB insertion."""
    if isinstance(doc, list):
        return [restore_objectids(d) for d in doc]
    if not isinstance(doc, dict):
        return doc

    result = {}
    for key, value in doc.items():
        if key == "id":
            # Restore as _id ObjectId
            try:
                result["_id"] = ObjectId(value)
            except Exception:
                result["_id"] = value
        elif key == "_id":
            try:
                result["_id"] = ObjectId(value) if isinstance(value, str) else value
            except Exception:
                result["_id"] = value
        elif key in ("start_date", "end_date", "created_at", "updated_at",
                      "week_start_date", "week_end_date", "submitted_at",
                      "last_status_update", "date"):
            result[key] = parse_date(value)
        elif isinstance(value, list):
            result[key] = [restore_objectids(v) if isinstance(v, dict) else v for v in value]
        elif isinstance(value, dict):
            result[key] = restore_objectids(value)
        else:
            result[key] = value
    return result


async def import_to_target(target_mongo_url: str):
    """Import exported JSON files into the target MongoDB."""
    print(f"[IMPORT] Connecting to target: {target_mongo_url[:60]}...")

    client = AsyncIOMotorClient(target_mongo_url, serverSelectionTimeoutMS=10000)
    # Extract DB name from URL or default
    db_name = target_mongo_url.split("/")[-1].split("?")[0] or "resource_planner"
    db = client[db_name]

    # Test connection
    await db.command("ping")
    print(f"[IMPORT] Connected to database '{db_name}'")

    # Collection mapping: filename → MongoDB collection name
    collection_map = {
        "users.json": "users",
        "resources.json": "resources",
        "projects.json": "projects",
        "allocations.json": "allocations",
        "timesheets.json": "timesheets",
        "status_updates.json": "status_updates",
        "risks.json": "risks",
        "holidays.json": "holidays",
        "leaves.json": "leaves",
        "settings.json": "settings",
        "chat_sessions.json": "chat_sessions",
    }

    for filename, coll_name in collection_map.items():
        filepath = os.path.join(EXPORT_DIR, filename)
        if not os.path.exists(filepath):
            print(f"  SKIP {filename} (file not found)")
            continue

        with open(filepath) as f:
            raw_docs = json.load(f)

        if not isinstance(raw_docs, list) or len(raw_docs) == 0:
            print(f"  SKIP {filename} (empty)")
            continue

        # Restore ObjectIds and dates
        docs = [restore_objectids(d) for d in raw_docs]

        # Drop existing collection and insert fresh
        coll = db[coll_name]
        existing = await coll.count_documents({})
        if existing > 0:
            print(f"  {coll_name}: dropping {existing} existing docs...")
            await coll.drop()

        await coll.insert_many(docs)
        print(f"  {coll_name}: imported {len(docs)} docs")

    # Create indexes
    await db.allocations.create_index("resource_id")
    await db.allocations.create_index("project_id")
    await db.allocations.create_index("start_date")
    await db.allocations.create_index("end_date")
    await db.timesheets.create_index([("resource_id", 1), ("week_start_date", 1)])
    await db.status_updates.create_index([("project_id", 1), ("created_at", -1)])
    await db.risks.create_index("project_id")
    await db.chat_sessions.create_index("user_email")
    print("[IMPORT] Indexes created.")
    print("[IMPORT] Done.")


async def verify_target(target_mongo_url: str):
    """Verify the imported data matches production counts."""
    client = AsyncIOMotorClient(target_mongo_url, serverSelectionTimeoutMS=10000)
    db_name = target_mongo_url.split("/")[-1].split("?")[0] or "resource_planner"
    db = client[db_name]
    await db.command("ping")

    print(f"[VERIFY] Database '{db_name}':")
    collections = await db.list_collection_names()
    for c in sorted(collections):
        count = await db[c].count_documents({})
        print(f"  {c}: {count} docs")

    # Spot-check: verify admin user exists
    admin = await db.users.find_one({"email": "don@ddconsult.tech"})
    if admin:
        print(f"\n  Admin user verified: {admin.get('email')} ({admin.get('role')})")
    else:
        print("\n  WARNING: Admin user don@ddconsult.tech NOT FOUND!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 migrate_production_db.py [export|import|verify] [--target-mongo URL]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "export":
        export_from_production()

    elif command == "import":
        target = None
        for i, arg in enumerate(sys.argv):
            if arg == "--target-mongo" and i + 1 < len(sys.argv):
                target = sys.argv[i + 1]
        if not target:
            target = os.environ.get("TARGET_MONGO_URL")
        if not target:
            print("ERROR: --target-mongo URL or TARGET_MONGO_URL env var required")
            sys.exit(1)
        export_from_production()  # Always re-export fresh
        asyncio.run(import_to_target(target))

    elif command == "verify":
        target = None
        for i, arg in enumerate(sys.argv):
            if arg == "--target-mongo" and i + 1 < len(sys.argv):
                target = sys.argv[i + 1]
        if not target:
            target = os.environ.get("TARGET_MONGO_URL")
        if not target:
            print("ERROR: --target-mongo URL required")
            sys.exit(1)
        asyncio.run(verify_target(target))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
