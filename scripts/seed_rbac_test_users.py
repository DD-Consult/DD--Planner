#!/usr/bin/env python3
"""
Idempotent seeding script for RBAC QA test users.

Creates a resource-role user (qa_resource@test.com) linked to an existing
resource with allocations, allowing QA to test "My Projects" vs "All Projects".

Safe to run multiple times - uses upsert to avoid duplicates.
"""
import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

# Add backend to path so we can import the password hasher
sys.path.insert(0, '/app/backend')
from auth.dependencies import get_password_hash


def load_env():
    """Load environment variables from .env file."""
    env_path = '/app/backend/.env'
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value


async def seed_qa_resource_user():
    """Create/update the QA resource user and link to an existing resource."""
    load_env()
    
    # Get DB connection details from environment
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    db_name = os.environ.get('DB_NAME', 'resource_planner')
    
    print(f"📦 Connecting to MongoDB: {mongo_url}")
    print(f"📦 Database: {db_name}")
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    try:
        # === Step 1: Find a suitable resource with allocations ===
        print("\n🔍 Finding a resource with allocations...")
        
        # Get all allocations and count by resource
        allocations = await db.allocations.find({}).to_list(length=1000)
        resource_alloc_count = {}
        resource_project_ids = {}
        
        for alloc in allocations:
            if alloc.get('resource_id'):
                rid = str(alloc['resource_id'])
                resource_alloc_count[rid] = resource_alloc_count.get(rid, 0) + 1
                if rid not in resource_project_ids:
                    resource_project_ids[rid] = []
                if alloc.get('project_id'):
                    resource_project_ids[rid].append(str(alloc['project_id']))
        
        # Pick the first resource with allocations (or a specific one like Bob Smith)
        if not resource_alloc_count:
            print("❌ ERROR: No resources with allocations found!")
            print("   Please seed some projects and allocations first.")
            client.close()
            return False
        
        # Try to find "Bob Smith" first, otherwise use any resource with allocations
        target_resource = None
        for rid, count in resource_alloc_count.items():
            resource = await db.resources.find_one({"_id": ObjectId(rid)})
            if resource and resource.get('name') == 'Bob Smith':
                target_resource = resource
                break
        
        # If Bob Smith not found, use the first resource with allocations
        if not target_resource:
            rid = list(resource_alloc_count.keys())[0]
            target_resource = await db.resources.find_one({"_id": ObjectId(rid)})
        
        resource_id = str(target_resource['_id'])
        resource_name = target_resource.get('name')
        alloc_count = resource_alloc_count[resource_id]
        allocated_project_ids = resource_project_ids[resource_id]
        
        print(f"✅ Selected resource: {resource_name} (id: {resource_id})")
        print(f"   This resource has {alloc_count} allocation(s)")
        
        # === Step 2: Create/update the QA user ===
        print("\n👤 Creating/updating QA resource user...")
        
        qa_email = "qa_resource@test.com"
        qa_password = "Test@2026"
        qa_role = "resource"
        
        # Hash the password using the app's bcrypt hasher
        password_hash = get_password_hash(qa_password)
        
        # Build the user document matching the app's schema
        user_doc = {
            "email": qa_email,
            "password_hash": password_hash,  # Note: password_hash, not password
            "role": qa_role,
            "resource_id": resource_id,  # Link to the resource
            "allowed_project_ids": [],  # Empty for resource role
            "disabled": False,
            "must_change_password": False,
            "name": "QA Resource User",  # Optional but helpful
        }
        
        # Upsert the user (idempotent - safe to re-run)
        result = await db.users.update_one(
            {"email": qa_email},
            {"$set": user_doc},
            upsert=True
        )
        
        if result.upserted_id:
            print(f"✅ Created new user: {qa_email}")
        else:
            print(f"✅ Updated existing user: {qa_email}")
        
        print(f"   Role: {qa_role}")
        print(f"   Password: {qa_password}")
        print(f"   Linked to resource: {resource_name} (id: {resource_id})")
        
        # === Step 3: Verify and report project counts ===
        print("\n📊 Project visibility for this user:")
        
        # Count "My Projects" (projects where this resource has allocations)
        my_project_ids = set(allocated_project_ids)
        my_projects_count = len(my_project_ids)
        
        # Count "All Projects" (total projects in DB)
        total_projects = await db.projects.count_documents({})
        
        print(f"   'My Projects' (allocated): {my_projects_count}")
        print(f"   'All Projects' (total):    {total_projects}")
        
        if my_projects_count < total_projects:
            print(f"   ✅ Difference: {total_projects - my_projects_count} projects not allocated to this resource")
        else:
            print(f"   ⚠️  This resource is allocated to all projects")
        
        # === Step 4: Show allocated project details ===
        if my_project_ids:
            print(f"\n📋 Projects allocated to {resource_name}:")
            for pid in my_project_ids:
                project = await db.projects.find_one({"_id": ObjectId(pid)})
                if project:
                    print(f"   - {project.get('name', 'Unnamed')} (id: {pid})")
        
        print("\n" + "="*70)
        print("✅ SEED COMPLETE")
        print("="*70)
        print(f"\n🔐 Login credentials for QA testing:")
        print(f"   Email:    {qa_email}")
        print(f"   Password: {qa_password}")
        print(f"   Role:     {qa_role}")
        print(f"\n📝 Test scenarios:")
        print(f"   1. Login as {qa_email}")
        print(f"   2. Check 'My Projects' - should show {my_projects_count} project(s)")
        print(f"   3. Check 'All Projects' - should show {total_projects} project(s)")
        print(f"   4. Verify resource dashboard shows {resource_name}'s allocations")
        print("="*70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        client.close()


if __name__ == "__main__":
    print("=" * 70)
    print("RBAC QA Test User Seeding Script")
    print("=" * 70)
    success = asyncio.run(seed_qa_resource_user())
    sys.exit(0 if success else 1)
