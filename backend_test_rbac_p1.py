#!/usr/bin/env python3
"""
Test P1 read-access RBAC fixes on WBS and Baseline endpoints.

Tests the newly-added role-aware read access controls:
- admin/super_admin → can read ANY project
- resource → can read ANY project (owner decision: resources view all read-only)
- contractor → ONLY their allocated/led projects; 403 otherwise
- client → ONLY their allowed_project_ids; 403 otherwise

WRITE endpoints must remain admin/lead gated.
"""
import requests
import sys
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient
from passlib.context import CryptContext

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# Backend URL
BACKEND_URL = "https://ddplanner-fixes.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"

# MongoDB connection
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "resource_planner"

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

RESOURCE_EMAIL = "qa_resource@test.com"
RESOURCE_PASSWORD = "Test@2026"

# Will create these
CONTRACTOR_EMAIL = "qa_contractor@test.com"
CONTRACTOR_PASSWORD = "Test@2026"

CLIENT_EMAIL = "qa_client@test.com"
CLIENT_PASSWORD = "Test@2026"

# Test results
test_results = []
test_count = 0
pass_count = 0
fail_count = 0


def log_test(name, passed, details=""):
    """Log a test result"""
    global test_count, pass_count, fail_count
    test_count += 1
    if passed:
        pass_count += 1
        status = "✅ PASS"
    else:
        fail_count += 1
        status = "❌ FAIL"
    
    result = f"{status}: {name}"
    if details:
        result += f" - {details}"
    test_results.append(result)
    print(result)


def login(email, password):
    """Login and return token"""
    response = requests.post(
        f"{API_BASE}/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if response.status_code == 200:
        data = response.json()
        return data["access_token"], data["user"]
    return None, None


def get_headers(token):
    """Get auth headers"""
    return {"Authorization": f"Bearer {token}"}


def setup_test_users():
    """Create contractor and client test users"""
    print("\n" + "="*80)
    print("SETUP: Creating test users")
    print("="*80)
    
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    users_collection = db.users
    resources_collection = db.resources
    allocations_collection = db.allocations
    projects_collection = db.projects
    
    # Get admin token
    admin_token, admin_user = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        print("❌ Failed to login as admin")
        return None
    
    print(f"✅ Admin login successful: {admin_user['email']}")
    
    # Get all projects
    response = requests.get(f"{API_BASE}/projects", headers=get_headers(admin_token))
    all_projects = response.json() if response.status_code == 200 else []
    all_project_ids = [p["id"] for p in all_projects]
    print(f"✅ Found {len(all_project_ids)} total projects")
    
    # Get resource user info
    resource_token, resource_user = login(RESOURCE_EMAIL, RESOURCE_PASSWORD)
    if not resource_token:
        print(f"❌ Failed to login as resource: {RESOURCE_EMAIL}")
        return None
    
    print(f"✅ Resource login successful: {resource_user['email']}")
    
    # Get resource's allocated projects (scope=mine)
    response = requests.get(
        f"{API_BASE}/projects",
        params={"scope": "mine"},
        headers=get_headers(resource_token)
    )
    resource_projects = response.json() if response.status_code == 200 else []
    resource_project_ids = [p["id"] for p in resource_projects]
    print(f"✅ Resource has {len(resource_project_ids)} allocated projects")
    
    # Find a project NOT allocated to resource
    resource_out_project = None
    for pid in all_project_ids:
        if pid not in resource_project_ids:
            resource_out_project = pid
            break
    
    if resource_out_project:
        print(f"✅ Found project NOT allocated to resource: {resource_out_project}")
    else:
        print("⚠️  All projects are allocated to resource")
    
    # Create contractor user
    # Find a resource with allocations to use as contractor
    contractor_resource = None
    contractor_allocations = []
    
    # Look for Bob Smith or any resource with allocations
    bob = resources_collection.find_one({"name": {"$regex": "Bob", "$options": "i"}})
    if bob:
        contractor_resource = bob
        contractor_allocations = list(allocations_collection.find({"resource_id": str(bob["_id"])}))
    
    if not contractor_resource:
        # Find any resource with allocations
        all_resources = list(resources_collection.find())
        for res in all_resources:
            allocs = list(allocations_collection.find({"resource_id": str(res["_id"])}))
            if allocs:
                contractor_resource = res
                contractor_allocations = allocs
                break
    
    if not contractor_resource:
        print("❌ No resource with allocations found for contractor")
        return None
    
    contractor_project_ids = list(set(a["project_id"] for a in contractor_allocations))
    print(f"✅ Found resource '{contractor_resource['name']}' with {len(contractor_project_ids)} allocations")
    
    # Find a project NOT allocated to contractor
    contractor_out_project = None
    for pid in all_project_ids:
        if pid not in contractor_project_ids:
            contractor_out_project = pid
            break
    
    if contractor_out_project:
        print(f"✅ Found project NOT allocated to contractor: {contractor_out_project}")
    else:
        print("⚠️  All projects are allocated to contractor")
    
    # Delete existing contractor user if exists
    users_collection.delete_one({"email": CONTRACTOR_EMAIL})
    
    # Create contractor user
    contractor_user_doc = {
        "email": CONTRACTOR_EMAIL,
        "password_hash": get_password_hash(CONTRACTOR_PASSWORD),
        "role": "contractor",
        "resource_id": str(contractor_resource["_id"]),
        "must_change_password": False,
        "allowed_project_ids": []
    }
    result = users_collection.insert_one(contractor_user_doc)
    print(f"✅ Created contractor user: {CONTRACTOR_EMAIL}")
    
    # Login as contractor
    contractor_token, contractor_user = login(CONTRACTOR_EMAIL, CONTRACTOR_PASSWORD)
    if not contractor_token:
        print(f"❌ Failed to login as contractor")
        return None
    
    print(f"✅ Contractor login successful: {contractor_user['email']}")
    
    # Create client user
    # Pick one project for client
    client_allowed_project = all_project_ids[0] if all_project_ids else None
    client_not_allowed_project = all_project_ids[1] if len(all_project_ids) > 1 else None
    
    if not client_allowed_project:
        print("❌ No projects available for client")
        return None
    
    print(f"✅ Client will be allowed project: {client_allowed_project}")
    if client_not_allowed_project:
        print(f"✅ Client will NOT be allowed project: {client_not_allowed_project}")
    
    # Delete existing client user if exists
    users_collection.delete_one({"email": CLIENT_EMAIL})
    
    # Create client user
    client_user_doc = {
        "email": CLIENT_EMAIL,
        "password_hash": get_password_hash(CLIENT_PASSWORD),
        "role": "client",
        "must_change_password": False,
        "allowed_project_ids": [client_allowed_project]
    }
    result = users_collection.insert_one(client_user_doc)
    print(f"✅ Created client user: {CLIENT_EMAIL}")
    
    # Login as client
    client_token, client_user = login(CLIENT_EMAIL, CLIENT_PASSWORD)
    if not client_token:
        print(f"❌ Failed to login as client")
        return None
    
    print(f"✅ Client login successful: {client_user['email']}")
    
    # Create a baseline for testing if none exists
    if all_project_ids:
        test_project_id = all_project_ids[0]
        response = requests.get(
            f"{API_BASE}/projects/{test_project_id}/baselines",
            headers=get_headers(admin_token)
        )
        if response.status_code == 200:
            baselines = response.json().get("items", [])
            if not baselines:
                # Create a baseline
                response = requests.post(
                    f"{API_BASE}/projects/{test_project_id}/baselines",
                    json={"name": "Test Baseline", "description": "For RBAC testing", "set_current": True},
                    headers=get_headers(admin_token)
                )
                if response.status_code == 200:
                    print(f"✅ Created test baseline for project {test_project_id}")
                else:
                    print(f"⚠️  Could not create baseline: {response.status_code}")
    
    return {
        "admin": {"token": admin_token, "user": admin_user},
        "resource": {"token": resource_token, "user": resource_user, "out_project": resource_out_project},
        "contractor": {
            "token": contractor_token,
            "user": contractor_user,
            "in_projects": contractor_project_ids,
            "out_project": contractor_out_project
        },
        "client": {
            "token": client_token,
            "user": client_user,
            "in_project": client_allowed_project,
            "out_project": client_not_allowed_project
        },
        "all_projects": all_project_ids
    }


def test_wbs_endpoints(project_id, token, expected_status, scenario_name):
    """Test all WBS GET endpoints for a project"""
    endpoints = [
        f"/projects/{project_id}/wbs",
        f"/projects/{project_id}/wbs/budget-status",
        f"/projects/{project_id}/wbs/actuals",
        f"/projects/{project_id}/wbs/tasks-for-timesheet",
        f"/projects/{project_id}/wbs/summary"
    ]
    
    results = []
    for endpoint in endpoints:
        response = requests.get(f"{API_BASE}{endpoint}", headers=get_headers(token))
        passed = response.status_code == expected_status
        results.append({
            "endpoint": endpoint,
            "status": response.status_code,
            "expected": expected_status,
            "passed": passed
        })
        log_test(
            f"{scenario_name} - GET {endpoint}",
            passed,
            f"Got {response.status_code}, expected {expected_status}"
        )
    
    return results


def test_baseline_endpoints(project_id, token, expected_status, scenario_name):
    """Test all Baseline GET endpoints for a project"""
    # First, get a baseline_id if available
    baseline_id = None
    if expected_status == 200:
        response = requests.get(
            f"{API_BASE}/projects/{project_id}/baselines",
            headers=get_headers(token)
        )
        if response.status_code == 200:
            baselines = response.json().get("items", [])
            if baselines:
                baseline_id = baselines[0]["id"]
    
    endpoints = [
        f"/projects/{project_id}/baselines",
        f"/projects/{project_id}/baselines/current",
        f"/projects/{project_id}/variance",
        f"/projects/{project_id}/change-log"
    ]
    
    # Add baseline-specific endpoints if we have a baseline_id
    if baseline_id:
        endpoints.extend([
            f"/projects/{project_id}/baselines/{baseline_id}",
            f"/projects/{project_id}/variance/{baseline_id}"
        ])
    
    results = []
    for endpoint in endpoints:
        response = requests.get(f"{API_BASE}{endpoint}", headers=get_headers(token))
        # For baseline-specific endpoints, 404 is acceptable if no baseline exists
        # but 403 is NOT acceptable
        if expected_status == 200:
            passed = response.status_code in [200, 404]
            if response.status_code == 403:
                passed = False
        else:
            passed = response.status_code == expected_status
        
        results.append({
            "endpoint": endpoint,
            "status": response.status_code,
            "expected": expected_status,
            "passed": passed
        })
        
        expected_desc = f"{expected_status} (or 404 if no baseline)" if expected_status == 200 else str(expected_status)
        log_test(
            f"{scenario_name} - GET {endpoint}",
            passed,
            f"Got {response.status_code}, expected {expected_desc}"
        )
    
    return results


def test_write_endpoints(project_id, token, scenario_name):
    """Test that write endpoints are blocked for non-admin/non-lead"""
    results = []
    
    # Test POST WBS task
    response = requests.post(
        f"{API_BASE}/projects/{project_id}/wbs/tasks",
        json={"name": "Test Task", "description": "Should be blocked"},
        headers=get_headers(token)
    )
    passed = response.status_code == 403
    results.append({
        "endpoint": f"/projects/{project_id}/wbs/tasks",
        "method": "POST",
        "status": response.status_code,
        "expected": 403,
        "passed": passed
    })
    log_test(
        f"{scenario_name} - POST /projects/{project_id}/wbs/tasks",
        passed,
        f"Got {response.status_code}, expected 403"
    )
    
    # Test POST baseline
    response = requests.post(
        f"{API_BASE}/projects/{project_id}/baselines",
        json={"name": "Test Baseline", "description": "Should be blocked"},
        headers=get_headers(token)
    )
    passed = response.status_code == 403
    results.append({
        "endpoint": f"/projects/{project_id}/baselines",
        "method": "POST",
        "status": response.status_code,
        "expected": 403,
        "passed": passed
    })
    log_test(
        f"{scenario_name} - POST /projects/{project_id}/baselines",
        passed,
        f"Got {response.status_code}, expected 403"
    )
    
    return results


def run_tests():
    """Run all RBAC tests"""
    print("\n" + "="*80)
    print("DD PLANNER - P1 READ-ACCESS RBAC TESTING")
    print("="*80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test started: {datetime.now().isoformat()}")
    
    # Setup test users
    test_data = setup_test_users()
    if not test_data:
        print("\n❌ Setup failed, cannot continue")
        return False
    
    admin = test_data["admin"]
    resource = test_data["resource"]
    contractor = test_data["contractor"]
    client = test_data["client"]
    all_projects = test_data["all_projects"]
    
    if not all_projects:
        print("\n❌ No projects found, cannot test")
        return False
    
    # Pick test projects
    test_project = all_projects[0]
    
    print("\n" + "="*80)
    print("TEST SCENARIO 1: Admin (baseline)")
    print("="*80)
    print(f"Testing admin access to project: {test_project}")
    test_wbs_endpoints(test_project, admin["token"], 200, "Admin")
    test_baseline_endpoints(test_project, admin["token"], 200, "Admin")
    
    print("\n" + "="*80)
    print("TEST SCENARIO 2: Resource (can read ANY project)")
    print("="*80)
    if resource["out_project"]:
        print(f"Testing resource access to NON-allocated project: {resource['out_project']}")
        print("CRITICAL: Resource should get 200 (NOT 403) - owner requirement")
        test_wbs_endpoints(resource["out_project"], resource["token"], 200, "Resource (non-allocated)")
        test_baseline_endpoints(resource["out_project"], resource["token"], 200, "Resource (non-allocated)")
    else:
        print("⚠️  Skipping: All projects are allocated to resource")
    
    print("\n" + "="*80)
    print("TEST SCENARIO 3: Contractor (ONLY allocated projects)")
    print("="*80)
    if contractor["in_projects"]:
        contractor_in = contractor["in_projects"][0]
        print(f"Testing contractor access to ALLOCATED project: {contractor_in}")
        test_wbs_endpoints(contractor_in, contractor["token"], 200, "Contractor (allocated)")
        test_baseline_endpoints(contractor_in, contractor["token"], 200, "Contractor (allocated)")
    
    if contractor["out_project"]:
        print(f"\nTesting contractor access to NON-allocated project: {contractor['out_project']}")
        print("CRITICAL: Contractor should get 403 - this is the core leak-fix assertion")
        test_wbs_endpoints(contractor["out_project"], contractor["token"], 403, "Contractor (non-allocated)")
        test_baseline_endpoints(contractor["out_project"], contractor["token"], 403, "Contractor (non-allocated)")
    else:
        print("⚠️  Skipping: All projects are allocated to contractor")
    
    print("\n" + "="*80)
    print("TEST SCENARIO 4: Client (ONLY allowed projects)")
    print("="*80)
    if client["in_project"]:
        print(f"Testing client access to ALLOWED project: {client['in_project']}")
        test_wbs_endpoints(client["in_project"], client["token"], 200, "Client (allowed)")
        test_baseline_endpoints(client["in_project"], client["token"], 200, "Client (allowed)")
    
    if client["out_project"]:
        print(f"\nTesting client access to NOT-ALLOWED project: {client['out_project']}")
        print("CRITICAL: Client should get 403")
        test_wbs_endpoints(client["out_project"], client["token"], 403, "Client (not-allowed)")
        test_baseline_endpoints(client["out_project"], client["token"], 403, "Client (not-allowed)")
    else:
        print("⚠️  Skipping: Only one project available")
    
    print("\n" + "="*80)
    print("TEST SCENARIO 5: Write-guard regression")
    print("="*80)
    print("Testing that write endpoints are still blocked for non-admin/non-lead")
    
    if contractor["in_projects"]:
        contractor_in = contractor["in_projects"][0]
        print(f"\nTesting contractor write access to ALLOCATED project: {contractor_in}")
        test_write_endpoints(contractor_in, contractor["token"], "Contractor write")
    
    if resource["out_project"]:
        print(f"\nTesting resource write access to project: {resource['out_project']}")
        test_write_endpoints(resource["out_project"], resource["token"], "Resource write")
    
    # Cleanup
    print("\n" + "="*80)
    print("CLEANUP: Removing test users")
    print("="*80)
    client_conn = MongoClient(MONGO_URL)
    db = client_conn[DB_NAME]
    users_collection = db.users
    
    deleted_contractor = users_collection.delete_one({"email": CONTRACTOR_EMAIL})
    deleted_client = users_collection.delete_one({"email": CLIENT_EMAIL})
    
    print(f"✅ Deleted contractor user: {deleted_contractor.deleted_count}")
    print(f"✅ Deleted client user: {deleted_client.deleted_count}")
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total tests: {test_count}")
    print(f"Passed: {pass_count} ✅")
    print(f"Failed: {fail_count} ❌")
    print(f"Success rate: {(pass_count/test_count*100):.1f}%")
    
    print("\n" + "="*80)
    print("CRITICAL ASSERTIONS")
    print("="*80)
    
    # Check critical assertions
    critical_checks = []
    
    # 1. Resource gets 200 on non-allocated project
    resource_check = any("Resource (non-allocated)" in r and "✅ PASS" in r for r in test_results)
    critical_checks.append(("Resource gets 200 on non-allocated project", resource_check))
    
    # 2. Contractor gets 403 on non-allocated project
    contractor_check = any("Contractor (non-allocated)" in r and "✅ PASS" in r for r in test_results)
    critical_checks.append(("Contractor gets 403 on non-allocated project", contractor_check))
    
    # 3. Client gets 403 on not-allowed project
    client_check = any("Client (not-allowed)" in r and "✅ PASS" in r for r in test_results)
    critical_checks.append(("Client gets 403 on not-allowed project", client_check))
    
    # 4. Write endpoints still 403 for non-admins
    write_check = any("write" in r.lower() and "✅ PASS" in r for r in test_results)
    critical_checks.append(("Write endpoints still 403 for non-admins", write_check))
    
    for check_name, passed in critical_checks:
        status = "✅ VERIFIED" if passed else "❌ FAILED"
        print(f"{status}: {check_name}")
    
    all_critical_passed = all(passed for _, passed in critical_checks)
    
    print("\n" + "="*80)
    if fail_count == 0 and all_critical_passed:
        print("✅✅✅ ALL TESTS PASSED - RBAC FIX WORKING CORRECTLY ✅✅✅")
    else:
        print("❌ SOME TESTS FAILED - REVIEW REQUIRED")
    print("="*80)
    
    return fail_count == 0 and all_critical_passed


if __name__ == "__main__":
    try:
        success = run_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
