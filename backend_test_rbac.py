#!/usr/bin/env python3
"""
RBAC Backend Testing for DD Planner
Tests newly-implemented RBAC changes for projects and reports endpoints.
"""

import asyncio
import requests
import os
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import sys

# Backend URL from environment
BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
if not BACKEND_URL.startswith("http"):
    BACKEND_URL = f"http://{BACKEND_URL}"
BACKEND_URL = BACKEND_URL.rstrip("/")

# MongoDB connection
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "resource_planner")

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"
CLIENT_EMAIL = "client@test.com"
CLIENT_PASSWORD = "client123"  # We'll try this, may not work

# Test users we'll create
RESOURCE_EMAIL = "rbac_resource@test.com"
RESOURCE_PASSWORD = "Test@2026"
CONTRACTOR_EMAIL = "rbac_contractor@test.com"
CONTRACTOR_PASSWORD = "Test@2026"

# Resource IDs from seed data
BOB_SMITH_ID = "6ab25bc82be78e05e89230ef"  # Will be resource user
CAROL_WHITE_ID = "6ab25bc82be78e05e89230f0"  # Will be contractor user

# Project IDs from seed data
PROJECT_WEBSITE = "6ab25bc82be78e05e89230f3"  # Website Redesign
PROJECT_MOBILE = "6ab25bc82be78e05e89230f4"   # Mobile App
PROJECT_DATA = "6ab25bc82be78e05e89230f5"    # Data Migration
PROJECT_LEGACY = "6ab25bc82be78e05e89230f6"  # Legacy System

# Test results
test_results = []
created_user_ids = []

def log_test(test_name, passed, details=""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    test_results.append({
        "name": test_name,
        "passed": passed,
        "details": details
    })
    print(f"{status}: {test_name}")
    if details:
        print(f"  Details: {details}")

def login(email, password):
    """Login and return token"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/auth/login",
            data={"username": email, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token"), data.get("user")
        else:
            print(f"Login failed for {email}: {response.status_code} - {response.text}")
            return None, None
    except Exception as e:
        print(f"Login error for {email}: {e}")
        return None, None

async def setup_test_users():
    """Create test users for resource and contractor roles"""
    print("\n=== SETTING UP TEST USERS ===")
    
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Import password hashing from backend
    sys.path.insert(0, '/app/backend')
    from auth.dependencies import get_password_hash
    
    # Create resource user
    existing_resource = await db.users.find_one({"email": RESOURCE_EMAIL})
    if existing_resource:
        print(f"Resource user {RESOURCE_EMAIL} already exists, deleting...")
        await db.users.delete_one({"email": RESOURCE_EMAIL})
    
    resource_user = {
        "email": RESOURCE_EMAIL,
        "password_hash": get_password_hash(RESOURCE_PASSWORD),
        "role": "resource",
        "resource_id": BOB_SMITH_ID,
        "allowed_project_ids": []
    }
    result = await db.users.insert_one(resource_user)
    created_user_ids.append(str(result.inserted_id))
    print(f"✅ Created resource user: {RESOURCE_EMAIL} (linked to Bob Smith)")
    
    # Create contractor user
    existing_contractor = await db.users.find_one({"email": CONTRACTOR_EMAIL})
    if existing_contractor:
        print(f"Contractor user {CONTRACTOR_EMAIL} already exists, deleting...")
        await db.users.delete_one({"email": CONTRACTOR_EMAIL})
    
    contractor_user = {
        "email": CONTRACTOR_EMAIL,
        "password_hash": get_password_hash(CONTRACTOR_PASSWORD),
        "role": "contractor",
        "resource_id": CAROL_WHITE_ID,
        "allowed_project_ids": []
    }
    result = await db.users.insert_one(contractor_user)
    created_user_ids.append(str(result.inserted_id))
    print(f"✅ Created contractor user: {CONTRACTOR_EMAIL} (linked to Carol White)")
    
    # Verify allocations
    print("\n=== VERIFYING ALLOCATIONS ===")
    bob_allocs = await db.allocations.find({"resource_id": BOB_SMITH_ID}).to_list(length=100)
    print(f"Bob Smith allocations: {[a['project_id'] for a in bob_allocs]}")
    
    carol_allocs = await db.allocations.find({"resource_id": CAROL_WHITE_ID}).to_list(length=100)
    print(f"Carol White allocations: {[a['project_id'] for a in carol_allocs]}")
    
    client.close()
    return True

async def cleanup_test_users():
    """Delete test users created during testing"""
    print("\n=== CLEANING UP TEST USERS ===")
    
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Delete by email
    result1 = await db.users.delete_one({"email": RESOURCE_EMAIL})
    if result1.deleted_count > 0:
        print(f"✅ Deleted resource user: {RESOURCE_EMAIL}")
    
    result2 = await db.users.delete_one({"email": CONTRACTOR_EMAIL})
    if result2.deleted_count > 0:
        print(f"✅ Deleted contractor user: {CONTRACTOR_EMAIL}")
    
    client.close()

def test_admin_baseline():
    """Test admin user has unrestricted access"""
    print("\n=== TESTING ADMIN (BASELINE) ===")
    
    token, user = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not token:
        log_test("Admin login", False, "Failed to login")
        return
    
    log_test("Admin login", True, f"Role: {user.get('role')}")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test 1: GET /api/projects
    response = requests.get(f"{BACKEND_URL}/api/projects", headers=headers)
    log_test("Admin GET /api/projects", response.status_code == 200, 
             f"Status: {response.status_code}, Projects: {len(response.json()) if response.status_code == 200 else 0}")
    
    # Test 2: GET /api/projects?scope=all
    response = requests.get(f"{BACKEND_URL}/api/projects?scope=all", headers=headers)
    log_test("Admin GET /api/projects?scope=all", response.status_code == 200,
             f"Status: {response.status_code}, Projects: {len(response.json()) if response.status_code == 200 else 0}")
    
    # Test 3: GET /api/reports/time-tracking/summary
    response = requests.get(f"{BACKEND_URL}/api/reports/time-tracking/summary", headers=headers)
    log_test("Admin GET /api/reports/time-tracking/summary", response.status_code == 200,
             f"Status: {response.status_code}")
    
    # Test 4: GET /api/reports/planned-vs-actual/project/{id}
    response = requests.get(f"{BACKEND_URL}/api/reports/planned-vs-actual/project/{PROJECT_WEBSITE}", headers=headers)
    log_test("Admin GET /api/reports/planned-vs-actual/project/{id}", response.status_code == 200,
             f"Status: {response.status_code}")

def test_resource_user():
    """Test resource user RBAC"""
    print("\n=== TESTING RESOURCE USER ===")
    
    token, user = login(RESOURCE_EMAIL, RESOURCE_PASSWORD)
    if not token:
        log_test("Resource login", False, "Failed to login")
        return
    
    log_test("Resource login", True, f"Role: {user.get('role')}")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test 1: GET /api/projects (default scope=mine)
    response = requests.get(f"{BACKEND_URL}/api/projects", headers=headers)
    if response.status_code == 200:
        mine_projects = response.json()
        mine_ids = [p['id'] for p in mine_projects]
        log_test("Resource GET /api/projects (default scope)", True,
                 f"Count: {len(mine_projects)}, IDs: {mine_ids}")
        
        # Verify Bob's allocations (should be Website f3 and Data Migration f5)
        expected_in_mine = [PROJECT_WEBSITE, PROJECT_DATA]
        has_expected = all(pid in mine_ids for pid in expected_in_mine)
        log_test("Resource scope=mine contains allocated projects", has_expected,
                 f"Expected {expected_in_mine}, Got {mine_ids}")
    else:
        log_test("Resource GET /api/projects (default scope)", False,
                 f"Status: {response.status_code}")
        mine_ids = []
    
    # Test 2: GET /api/projects?scope=all
    response = requests.get(f"{BACKEND_URL}/api/projects?scope=all", headers=headers)
    if response.status_code == 200:
        all_projects = response.json()
        all_ids = [p['id'] for p in all_projects]
        log_test("Resource GET /api/projects?scope=all", True,
                 f"Count: {len(all_projects)}, IDs: {all_ids}")
        
        # Verify scope=all returns MORE projects than scope=mine
        more_projects = len(all_ids) >= len(mine_ids)
        log_test("Resource scope=all shows more projects than scope=mine", more_projects,
                 f"scope=all: {len(all_ids)}, scope=mine: {len(mine_ids)}")
        
        # Verify scope=all includes projects NOT in mine
        out_of_scope_in_all = any(pid not in mine_ids for pid in all_ids)
        log_test("Resource scope=all includes out-of-scope projects", out_of_scope_in_all,
                 f"All IDs: {all_ids}, Mine IDs: {mine_ids}")
    else:
        log_test("Resource GET /api/projects?scope=all", False,
                 f"Status: {response.status_code}")
        all_ids = []
    
    # Test 3: GET /api/projects/{id} for project in SET_ALL but NOT in SET_MINE
    # Use PROJECT_MOBILE (f4) which Bob is NOT allocated to
    out_of_scope_project = PROJECT_MOBILE
    response = requests.get(f"{BACKEND_URL}/api/projects/{out_of_scope_project}", headers=headers)
    log_test("Resource GET /api/projects/{id} for out-of-scope project", response.status_code == 200,
             f"Status: {response.status_code} (should be 200 - resource can read any project detail)")
    
    # Test 4: GET /api/reports/planned-vs-actual/project/{id} for out-of-scope project
    response = requests.get(f"{BACKEND_URL}/api/reports/planned-vs-actual/project/{out_of_scope_project}", headers=headers)
    log_test("Resource GET /api/reports/planned-vs-actual for out-of-scope project", response.status_code == 403,
             f"Status: {response.status_code} (should be 403 - reports are scoped)")
    
    # Test 5: GET /api/reports/planned-vs-actual/project/{id} for in-scope project
    in_scope_project = PROJECT_WEBSITE
    response = requests.get(f"{BACKEND_URL}/api/reports/planned-vs-actual/project/{in_scope_project}", headers=headers)
    log_test("Resource GET /api/reports/planned-vs-actual for in-scope project", response.status_code == 200,
             f"Status: {response.status_code} (should be 200)")
    
    # Test 6: Write guard - attempt PUT /api/projects/{id}
    response = requests.put(
        f"{BACKEND_URL}/api/projects/{in_scope_project}",
        headers=headers,
        json={"name": "Test Update"}
    )
    log_test("Resource PUT /api/projects/{id} (write guard)", response.status_code == 403,
             f"Status: {response.status_code} (should be 403 - not admin/lead)")
    
    # Test 7: Write guard - attempt POST /api/allocations
    response = requests.post(
        f"{BACKEND_URL}/api/allocations",
        headers=headers,
        json={
            "project_id": in_scope_project,
            "resource_id": BOB_SMITH_ID,
            "allocation_percentage": 50,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31"
        }
    )
    log_test("Resource POST /api/allocations (write guard)", response.status_code == 403,
             f"Status: {response.status_code} (should be 403)")

def test_contractor_user():
    """Test contractor user RBAC"""
    print("\n=== TESTING CONTRACTOR USER ===")
    
    token, user = login(CONTRACTOR_EMAIL, CONTRACTOR_PASSWORD)
    if not token:
        log_test("Contractor login", False, "Failed to login")
        return
    
    log_test("Contractor login", True, f"Role: {user.get('role')}")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test 1: GET /api/projects (default)
    response = requests.get(f"{BACKEND_URL}/api/projects", headers=headers)
    if response.status_code == 200:
        mine_projects = response.json()
        mine_ids = [p['id'] for p in mine_projects]
        log_test("Contractor GET /api/projects (default)", True,
                 f"Count: {len(mine_projects)}, IDs: {mine_ids}")
        
        # Verify Carol's allocations (should be Mobile f4 and Data Migration f5)
        expected_in_mine = [PROJECT_MOBILE, PROJECT_DATA]
        has_expected = all(pid in mine_ids for pid in expected_in_mine)
        log_test("Contractor default scope contains allocated projects", has_expected,
                 f"Expected {expected_in_mine}, Got {mine_ids}")
    else:
        log_test("Contractor GET /api/projects (default)", False,
                 f"Status: {response.status_code}")
        mine_ids = []
    
    # Test 2: GET /api/projects?scope=all (should be IGNORED for contractor)
    response = requests.get(f"{BACKEND_URL}/api/projects?scope=all", headers=headers)
    if response.status_code == 200:
        all_projects = response.json()
        all_ids = [p['id'] for p in all_projects]
        log_test("Contractor GET /api/projects?scope=all", True,
                 f"Count: {len(all_projects)}, IDs: {all_ids}")
        
        # CRITICAL: Verify scope=all is IGNORED (returns same as default)
        same_as_mine = set(all_ids) == set(mine_ids)
        log_test("Contractor scope=all is IGNORED (same as default)", same_as_mine,
                 f"scope=all: {all_ids}, default: {mine_ids}")
    else:
        log_test("Contractor GET /api/projects?scope=all", False,
                 f"Status: {response.status_code}")
    
    # Test 3: GET /api/projects/{id} for out-of-scope project
    out_of_scope_project = PROJECT_WEBSITE  # Carol is NOT allocated to Website
    response = requests.get(f"{BACKEND_URL}/api/projects/{out_of_scope_project}", headers=headers)
    log_test("Contractor GET /api/projects/{id} for out-of-scope project", response.status_code == 403,
             f"Status: {response.status_code} (should be 403 - contractor restricted)")
    
    # Test 4: GET /api/reports/planned-vs-actual/project/{id} for out-of-scope project
    response = requests.get(f"{BACKEND_URL}/api/reports/planned-vs-actual/project/{out_of_scope_project}", headers=headers)
    log_test("Contractor GET /api/reports/planned-vs-actual for out-of-scope project", response.status_code == 403,
             f"Status: {response.status_code} (should be 403)")

def test_client_user():
    """Test client user RBAC (if login possible)"""
    print("\n=== TESTING CLIENT USER ===")
    
    token, user = login(CLIENT_EMAIL, CLIENT_PASSWORD)
    if not token:
        log_test("Client login", False, "Unable to login as client (password unknown) - SKIPPING client tests")
        return
    
    log_test("Client login", True, f"Role: {user.get('role')}")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test: GET /api/reports/planned-vs-actual/project/{id} for out-of-scope project
    # Assuming client doesn't have access to all projects
    response = requests.get(f"{BACKEND_URL}/api/reports/planned-vs-actual/project/{PROJECT_LEGACY}", headers=headers)
    log_test("Client GET /api/reports/planned-vs-actual for out-of-scope project", response.status_code == 403,
             f"Status: {response.status_code} (should be 403)")

def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("RBAC TESTING SUMMARY")
    print("="*80)
    
    passed = sum(1 for t in test_results if t['passed'])
    total = len(test_results)
    
    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success Rate: {passed/total*100:.1f}%")
    
    if total - passed > 0:
        print("\n❌ FAILED TESTS:")
        for t in test_results:
            if not t['passed']:
                print(f"  - {t['name']}")
                if t['details']:
                    print(f"    {t['details']}")
    
    print("\n✅ PASSED TESTS:")
    for t in test_results:
        if t['passed']:
            print(f"  - {t['name']}")

async def main():
    """Main test execution"""
    print("="*80)
    print("RBAC BACKEND TESTING FOR DD PLANNER")
    print("="*80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"MongoDB: {MONGO_URL}/{DB_NAME}")
    
    # Setup
    await setup_test_users()
    
    # Run tests
    test_admin_baseline()
    test_resource_user()
    test_contractor_user()
    test_client_user()
    
    # Cleanup
    await cleanup_test_users()
    
    # Summary
    print_summary()
    
    # Exit with appropriate code
    failed = sum(1 for t in test_results if not t['passed'])
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    asyncio.run(main())
