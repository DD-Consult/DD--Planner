#!/usr/bin/env python3
"""
Seed test data for My Allocations QA validation.
Creates a linked resource for admin@test.com and 3 test allocations spanning different periods.
Safe to run multiple times (idempotent).
"""
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

# Add backend to path for imports
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from dotenv import load_dotenv

# Load environment variables
env_path = backend_path / ".env"
load_dotenv(env_path)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "resource_planner")
SEED_TAG = "my_alloc_qa"


async def seed_data():
    """Main seeding function."""
    print(f"Connecting to MongoDB at {MONGO_URL}, database: {DB_NAME}")
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    users_col = db["users"]
    resources_col = db["resources"]
    projects_col = db["projects"]
    allocations_col = db["allocations"]
    
    # ===== STEP 1: Link admin@test.com to an existing resource =====
    print("\n=== STEP 1: Linking user to resource ===")
    user = await users_col.find_one({"email": "admin@test.com"})
    if not user:
        print("ERROR: User admin@test.com not found!")
        return
    
    print(f"Found user: {user['email']}, current resource_id: {user.get('resource_id')}")
    
    # Find Alice Johnson or any existing resource
    resource = await resources_col.find_one({"name": "Alice Johnson"})
    if not resource:
        # Fall back to any active resource
        resource = await resources_col.find_one({"active": True})
    
    if not resource:
        print("ERROR: No resources found in the database!")
        return
    
    resource_id_str = str(resource["_id"])
    print(f"Selected resource: {resource['name']} (ID: {resource_id_str})")
    
    # Link user to resource via resource_id field
    await users_col.update_one(
        {"email": "admin@test.com"},
        {"$set": {"resource_id": resource_id_str}}
    )
    print(f"✓ Linked admin@test.com to resource via resource_id field: {resource_id_str}")
    
    # ===== STEP 2: Find or create a project spanning August 2025 =====
    print("\n=== STEP 2: Ensuring project exists ===")
    
    # Look for existing project that spans August 2025
    aug_start = datetime(2025, 8, 1)
    aug_end = datetime(2025, 8, 31)
    
    project = await projects_col.find_one({
        "start_date": {"$lte": aug_end},
        "end_date": {"$gte": aug_start}
    })
    
    if not project:
        # Create a test project
        print("No suitable project found, creating test project...")
        project_doc = {
            "name": "QA Test Project - My Allocations",
            "client_name": "QA Client",
            "status": "active",
            "start_date": datetime(2025, 7, 1),
            "end_date": datetime(2025, 9, 30),
            "project_lead_id": resource_id_str,
            "created_at": datetime.utcnow(),
            "seed_tag": SEED_TAG
        }
        result = await projects_col.insert_one(project_doc)
        project = await projects_col.find_one({"_id": result.inserted_id})
        print(f"✓ Created project: {project['name']} (ID: {result.inserted_id})")
    else:
        print(f"✓ Using existing project: {project['name']} (ID: {project['_id']})")
    
    project_id_str = str(project["_id"])
    
    # ===== STEP 3: Create 3 test allocations (idempotent) =====
    print("\n=== STEP 3: Creating test allocations ===")
    
    allocations = [
        {
            "name": "Allocation A - July Only",
            "resource_id": resource_id_str,
            "project_id": project_id_str,
            "start_date": datetime(2025, 7, 13),
            "end_date": datetime(2025, 7, 31),
            "percentage": 60,
            "allocation_type": "percentage",
            "seed_tag": SEED_TAG,
            "marker": "alloc_a_july"
        },
        {
            "name": "Allocation B - Spans into August",
            "resource_id": resource_id_str,
            "project_id": project_id_str,
            "start_date": datetime(2025, 7, 20),
            "end_date": datetime(2025, 8, 28),
            "percentage": 18,
            "allocation_type": "percentage",
            "seed_tag": SEED_TAG,
            "marker": "alloc_b_span"
        },
        {
            "name": "Allocation C - August Only",
            "resource_id": resource_id_str,
            "project_id": project_id_str,
            "start_date": datetime(2025, 8, 1),
            "end_date": datetime(2025, 8, 15),
            "percentage": 30,
            "allocation_type": "percentage",
            "seed_tag": SEED_TAG,
            "marker": "alloc_c_august"
        }
    ]
    
    created_ids = []
    for alloc in allocations:
        marker = alloc["marker"]
        existing = await allocations_col.find_one({
            "seed_tag": SEED_TAG,
            "marker": marker
        })
        
        if existing:
            # Update existing
            await allocations_col.update_one(
                {"_id": existing["_id"]},
                {"$set": alloc}
            )
            created_ids.append(str(existing["_id"]))
            print(f"✓ Updated existing allocation: {alloc['name']} (ID: {existing['_id']})")
        else:
            # Insert new
            result = await allocations_col.insert_one(alloc)
            created_ids.append(str(result.inserted_id))
            print(f"✓ Created allocation: {alloc['name']} (ID: {result.inserted_id})")
    
    # ===== SUMMARY =====
    print("\n" + "="*70)
    print("SEED DATA SUMMARY")
    print("="*70)
    print(f"User: admin@test.com")
    print(f"Linked Resource: {resource['name']} (ID: {resource_id_str})")
    print(f"Link Field Used: resource_id = '{resource_id_str}'")
    print(f"Project: {project['name']} (ID: {project_id_str})")
    print(f"Allocations Created:")
    for i, alloc in enumerate(allocations):
        print(f"  {i+1}. {alloc['name']}")
        print(f"     - Period: {alloc['start_date'].date()} to {alloc['end_date'].date()}")
        print(f"     - Percentage: {alloc['percentage']}%")
        print(f"     - ID: {created_ids[i]}")
    print("="*70)
    print("\n✅ Seed script completed successfully!")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(seed_data())
