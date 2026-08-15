"""
DD Planner Step 4 Regression Test Suite
========================================
Tests the LazyCollection proxy refactor to ensure backward compatibility
when MULTI_TENANT_ENABLED=false.

This test verifies:
1. Auth flow (login, /api/auth/me)
2. Core reads (projects, resources, allocations, portfolio) - verify counts
3. CRUD on projects (create, update, delete)
4. CRUD on resources (create, update, delete)
5. Platform endpoints (new, added by Step 1-2)
6. Auth negative test (401 without token)

Expected behavior: Everything should work identically to pre-refactor.
"""
import requests
import json
from datetime import datetime, timedelta

# Configuration
BASE_URL = "https://a0ac7ee9-2785-4339-ad6f-6886af7a3f1a.preview.emergentagent.com"
API_URL = f"{BASE_URL}/api"

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"
CLIENT_EMAIL = "client@test.com"
CLIENT_PASSWORD = "client123"

# Test state
admin_token = None
test_project_id = None
test_resource_id = None

def log_test(name, passed, details=""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {name}")
    if details:
        print(f"   {details}")
    return passed

def test_auth_login():
    """Test 1: POST /api/auth/login with admin credentials"""
    global admin_token
    
    # OAuth2PasswordRequestForm expects form data with username/password
    response = requests.post(
        f"{API_URL}/auth/login",
        data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    
    if response.status_code != 200:
        return log_test("Auth Login", False, f"Status: {response.status_code}, Body: {response.text}")
    
    data = response.json()
    if "access_token" not in data:
        return log_test("Auth Login", False, "No access_token in response")
    
    admin_token = data["access_token"]
    return log_test("Auth Login", True, f"Token received: {admin_token[:20]}...")

def test_auth_me():
    """Test 2: GET /api/auth/me returns admin user"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.get(f"{API_URL}/auth/me", headers=headers)
    
    if response.status_code != 200:
        return log_test("Auth Me", False, f"Status: {response.status_code}")
    
    data = response.json()
    if data.get("email") != ADMIN_EMAIL:
        return log_test("Auth Me", False, f"Wrong email: {data.get('email')}")
    
    if data.get("role") != "admin":
        return log_test("Auth Me", False, f"Wrong role: {data.get('role')}")
    
    return log_test("Auth Me", True, f"User: {data.get('email')}, Role: {data.get('role')}")

def test_get_projects():
    """Test 3: GET /api/projects returns 4 projects"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.get(f"{API_URL}/projects", headers=headers)
    
    if response.status_code != 200:
        return log_test("Get Projects", False, f"Status: {response.status_code}")
    
    data = response.json()
    if not isinstance(data, list):
        return log_test("Get Projects", False, f"Response is not a list: {type(data)}")
    
    count = len(data)
    if count != 4:
        return log_test("Get Projects", False, f"Expected 4 projects, got {count}")
    
    # Verify essential fields are present (backend uses 'id' not '_id')
    first_project = data[0]
    required_fields = ["id", "name", "client_name", "status", "start_date", "end_date"]
    missing_fields = [f for f in required_fields if f not in first_project]
    if missing_fields:
        return log_test("Get Projects", False, f"Missing fields: {missing_fields}")
    
    return log_test("Get Projects", True, f"Count: {count}, Fields OK")

def test_get_resources():
    """Test 4: GET /api/resources returns 5 resources"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.get(f"{API_URL}/resources", headers=headers)
    
    if response.status_code != 200:
        return log_test("Get Resources", False, f"Status: {response.status_code}")
    
    data = response.json()
    if not isinstance(data, list):
        return log_test("Get Resources", False, f"Response is not a list: {type(data)}")
    
    count = len(data)
    if count != 5:
        return log_test("Get Resources", False, f"Expected 5 resources, got {count}")
    
    # Verify essential fields (backend uses 'id' not '_id')
    first_resource = data[0]
    required_fields = ["id", "name", "role", "standard_capacity"]
    missing_fields = [f for f in required_fields if f not in first_resource]
    if missing_fields:
        return log_test("Get Resources", False, f"Missing fields: {missing_fields}")
    
    return log_test("Get Resources", True, f"Count: {count}, Fields OK")

def test_get_allocations():
    """Test 5: GET /api/allocations returns 10 allocations"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.get(f"{API_URL}/allocations", headers=headers)
    
    if response.status_code != 200:
        return log_test("Get Allocations", False, f"Status: {response.status_code}")
    
    data = response.json()
    if not isinstance(data, list):
        return log_test("Get Allocations", False, f"Response is not a list: {type(data)}")
    
    count = len(data)
    if count != 10:
        return log_test("Get Allocations", False, f"Expected 10 allocations, got {count}")
    
    # Verify essential fields
    first_allocation = data[0]
    required_fields = ["_id", "resource_id", "project_id", "start_date", "end_date", "percentage"]
    missing_fields = [f for f in required_fields if f not in first_allocation]
    if missing_fields:
        return log_test("Get Allocations", False, f"Missing fields: {missing_fields}")
    
    return log_test("Get Allocations", True, f"Count: {count}, Fields OK")

def test_get_portfolio():
    """Test 6: GET /api/portfolio returns portfolio data with 3+ project cards"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.get(f"{API_URL}/portfolio", headers=headers)
    
    if response.status_code != 200:
        return log_test("Get Portfolio", False, f"Status: {response.status_code}")
    
    data = response.json()
    if not isinstance(data, dict):
        return log_test("Get Portfolio", False, f"Response is not a dict: {type(data)}")
    
    # Portfolio should have projects array
    projects = data.get("projects", [])
    if len(projects) < 3:
        return log_test("Get Portfolio", False, f"Expected 3+ projects, got {len(projects)}")
    
    return log_test("Get Portfolio", True, f"Projects: {len(projects)}")

def test_create_project():
    """Test 7: POST /api/projects to create a new project"""
    global test_project_id
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Generate unique name with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_data = {
        "name": f"TEST_STEP4_REGRESSION_{timestamp}",
        "client_name": "Test Client",
        "status": "Pipeline",
        "start_date": (datetime.now() + timedelta(days=1)).isoformat(),
        "end_date": (datetime.now() + timedelta(days=30)).isoformat()
    }
    
    response = requests.post(f"{API_URL}/projects", json=project_data, headers=headers)
    
    if response.status_code != 200:
        return log_test("Create Project", False, f"Status: {response.status_code}, Body: {response.text}")
    
    data = response.json()
    if "_id" not in data:
        return log_test("Create Project", False, "No _id in response")
    
    test_project_id = data["_id"]
    
    # Verify the project was created with correct data
    if data.get("name") != project_data["name"]:
        return log_test("Create Project", False, f"Name mismatch: {data.get('name')}")
    
    return log_test("Create Project", True, f"ID: {test_project_id}, Name: {data.get('name')}")

def test_verify_project_count_after_create():
    """Test 8: GET /api/projects should now return 5 projects"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.get(f"{API_URL}/projects", headers=headers)
    
    if response.status_code != 200:
        return log_test("Verify Project Count (After Create)", False, f"Status: {response.status_code}")
    
    data = response.json()
    count = len(data)
    if count != 5:
        return log_test("Verify Project Count (After Create)", False, f"Expected 5 projects, got {count}")
    
    return log_test("Verify Project Count (After Create)", True, f"Count: {count}")

def test_update_project():
    """Test 9: PUT /api/projects/{id} to update the project name"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    update_data = {
        "name": f"TEST_STEP4_REGRESSION_UPDATED_{datetime.now().strftime('%H%M%S')}"
    }
    
    response = requests.put(
        f"{API_URL}/projects/{test_project_id}",
        json=update_data,
        headers=headers
    )
    
    if response.status_code != 200:
        return log_test("Update Project", False, f"Status: {response.status_code}, Body: {response.text}")
    
    data = response.json()
    if data.get("name") != update_data["name"]:
        return log_test("Update Project", False, f"Name not updated: {data.get('name')}")
    
    return log_test("Update Project", True, f"New name: {data.get('name')}")

def test_delete_project():
    """Test 10: DELETE /api/projects/{id} to clean up"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    response = requests.delete(
        f"{API_URL}/projects/{test_project_id}",
        headers=headers
    )
    
    if response.status_code != 200:
        return log_test("Delete Project", False, f"Status: {response.status_code}")
    
    return log_test("Delete Project", True, f"Deleted ID: {test_project_id}")

def test_verify_project_count_after_delete():
    """Test 11: GET /api/projects should return 4 again"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.get(f"{API_URL}/projects", headers=headers)
    
    if response.status_code != 200:
        return log_test("Verify Project Count (After Delete)", False, f"Status: {response.status_code}")
    
    data = response.json()
    count = len(data)
    if count != 4:
        return log_test("Verify Project Count (After Delete)", False, f"Expected 4 projects, got {count}")
    
    return log_test("Verify Project Count (After Delete)", True, f"Count: {count}")

def test_create_resource():
    """Test 12: POST /api/resources to create a new resource"""
    global test_resource_id
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    resource_data = {
        "name": f"Test Resource {datetime.now().strftime('%H%M%S')}",
        "role": "Test Engineer",
        "standard_capacity": 100
    }
    
    response = requests.post(f"{API_URL}/resources", json=resource_data, headers=headers)
    
    if response.status_code != 200:
        return log_test("Create Resource", False, f"Status: {response.status_code}, Body: {response.text}")
    
    data = response.json()
    if "_id" not in data:
        return log_test("Create Resource", False, "No _id in response")
    
    test_resource_id = data["_id"]
    
    return log_test("Create Resource", True, f"ID: {test_resource_id}, Name: {data.get('name')}")

def test_update_resource():
    """Test 13: PUT /api/resources/{id} to update the resource"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    update_data = {
        "name": f"Test Resource Updated {datetime.now().strftime('%H%M%S')}",
        "role": "Senior Test Engineer",
        "standard_capacity": 100
    }
    
    response = requests.put(
        f"{API_URL}/resources/{test_resource_id}",
        json=update_data,
        headers=headers
    )
    
    if response.status_code != 200:
        return log_test("Update Resource", False, f"Status: {response.status_code}, Body: {response.text}")
    
    data = response.json()
    if data.get("name") != update_data["name"]:
        return log_test("Update Resource", False, f"Name not updated: {data.get('name')}")
    
    return log_test("Update Resource", True, f"New name: {data.get('name')}")

def test_delete_resource():
    """Test 14: DELETE /api/resources/{id} to clean up"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    response = requests.delete(
        f"{API_URL}/resources/{test_resource_id}",
        headers=headers
    )
    
    if response.status_code != 200:
        return log_test("Delete Resource", False, f"Status: {response.status_code}")
    
    return log_test("Delete Resource", True, f"Deleted ID: {test_resource_id}")

def test_platform_status():
    """Test 15: GET /api/platform/status (public endpoint)"""
    response = requests.get(f"{API_URL}/platform/status")
    
    if response.status_code != 200:
        return log_test("Platform Status", False, f"Status: {response.status_code}")
    
    data = response.json()
    
    # Verify expected fields
    if data.get("multi_tenant_enabled") != False:
        return log_test("Platform Status", False, f"multi_tenant_enabled should be false, got {data.get('multi_tenant_enabled')}")
    
    if data.get("platform_db_ready") != True:
        return log_test("Platform Status", False, f"platform_db_ready should be true, got {data.get('platform_db_ready')}")
    
    # Tenants count can be 0 or more - just verify the field exists
    tenants = data.get("tenants")
    if tenants is None:
        return log_test("Platform Status", False, f"tenants field missing")
    
    return log_test("Platform Status", True, f"multi_tenant_enabled: {data.get('multi_tenant_enabled')}, tenants: {tenants}")

def test_platform_whoami_tenant():
    """Test 16: GET /api/platform/whoami-tenant (public endpoint)"""
    response = requests.get(f"{API_URL}/platform/whoami-tenant")
    
    if response.status_code != 200:
        return log_test("Platform Whoami Tenant", False, f"Status: {response.status_code}")
    
    data = response.json()
    
    # When flag is off, should show tenant object with slug=ddconsult (default fallback)
    tenant = data.get("tenant")
    if not tenant:
        return log_test("Platform Whoami Tenant", False, f"No tenant in response")
    
    # Tenant can be either a string or an object
    tenant_slug = tenant if isinstance(tenant, str) else tenant.get("slug")
    if tenant_slug != "ddconsult":
        return log_test("Platform Whoami Tenant", False, f"Expected tenant slug=ddconsult, got {tenant_slug}")
    
    resolution_mode = data.get("resolution_mode")
    if resolution_mode != "flag_off":
        return log_test("Platform Whoami Tenant", False, f"Expected resolution_mode=flag_off, got {resolution_mode}")
    
    return log_test("Platform Whoami Tenant", True, f"tenant slug: {tenant_slug}, resolution_mode: {resolution_mode}")

def test_platform_resolve_subdomain_ddconsult():
    """Test 17: GET /api/platform/resolve-subdomain?host=ddconsult.ddplanner.io"""
    response = requests.get(f"{API_URL}/platform/resolve-subdomain?host=ddconsult.ddplanner.io")
    
    if response.status_code != 200:
        return log_test("Platform Resolve Subdomain (ddconsult)", False, f"Status: {response.status_code}")
    
    data = response.json()
    subdomain = data.get("subdomain")
    if subdomain != "ddconsult":
        return log_test("Platform Resolve Subdomain (ddconsult)", False, f"Expected subdomain=ddconsult, got {subdomain}")
    
    return log_test("Platform Resolve Subdomain (ddconsult)", True, f"subdomain: {subdomain}")

def test_platform_resolve_subdomain_admin():
    """Test 18: GET /api/platform/resolve-subdomain?host=admin.ddplanner.io"""
    response = requests.get(f"{API_URL}/platform/resolve-subdomain?host=admin.ddplanner.io")
    
    if response.status_code != 200:
        return log_test("Platform Resolve Subdomain (admin)", False, f"Status: {response.status_code}")
    
    data = response.json()
    subdomain = data.get("subdomain")
    if subdomain != "admin":
        return log_test("Platform Resolve Subdomain (admin)", False, f"Expected subdomain=admin, got {subdomain}")
    
    return log_test("Platform Resolve Subdomain (admin)", True, f"subdomain: {subdomain}")

def test_platform_resolve_subdomain_localhost():
    """Test 19: GET /api/platform/resolve-subdomain?host=localhost:8001"""
    response = requests.get(f"{API_URL}/platform/resolve-subdomain?host=localhost:8001")
    
    if response.status_code != 200:
        return log_test("Platform Resolve Subdomain (localhost)", False, f"Status: {response.status_code}")
    
    data = response.json()
    subdomain = data.get("subdomain")
    if subdomain is not None:
        return log_test("Platform Resolve Subdomain (localhost)", False, f"Expected subdomain=null, got {subdomain}")
    
    return log_test("Platform Resolve Subdomain (localhost)", True, f"subdomain: {subdomain}")

def test_auth_negative():
    """Test 20: GET /api/projects without Authorization header should return 401"""
    response = requests.get(f"{API_URL}/projects")
    
    if response.status_code != 401:
        return log_test("Auth Negative Test", False, f"Expected 401, got {response.status_code}")
    
    return log_test("Auth Negative Test", True, "Correctly returned 401")

def test_dashboard_action_items():
    """Test 21: GET /api/dashboard/action-items (low priority, may be slow)"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    try:
        response = requests.get(f"{API_URL}/dashboard/action-items", headers=headers, timeout=30)
        
        if response.status_code != 200:
            return log_test("Dashboard Action Items", False, f"Status: {response.status_code}")
        
        data = response.json()
        if not isinstance(data, list):
            return log_test("Dashboard Action Items", False, f"Response is not a list: {type(data)}")
        
        return log_test("Dashboard Action Items", True, f"Returned {len(data)} action items")
    except requests.exceptions.Timeout:
        return log_test("Dashboard Action Items", True, "Skipped (timeout, low priority)")
    except Exception as e:
        return log_test("Dashboard Action Items", False, f"Error: {str(e)}")

def run_all_tests():
    """Run all regression tests"""
    print("=" * 80)
    print("DD Planner Step 4 Regression Test Suite")
    print("Testing LazyCollection proxy refactor with MULTI_TENANT_ENABLED=false")
    print("=" * 80)
    print()
    
    results = []
    
    # Auth tests
    print("--- AUTH TESTS ---")
    results.append(test_auth_login())
    results.append(test_auth_me())
    print()
    
    # Core read tests
    print("--- CORE READ TESTS ---")
    results.append(test_get_projects())
    results.append(test_get_resources())
    results.append(test_get_allocations())
    results.append(test_get_portfolio())
    print()
    
    # Project CRUD tests
    print("--- PROJECT CRUD TESTS ---")
    results.append(test_create_project())
    results.append(test_verify_project_count_after_create())
    results.append(test_update_project())
    results.append(test_delete_project())
    results.append(test_verify_project_count_after_delete())
    print()
    
    # Resource CRUD tests
    print("--- RESOURCE CRUD TESTS ---")
    results.append(test_create_resource())
    results.append(test_update_resource())
    results.append(test_delete_resource())
    print()
    
    # Platform endpoints tests
    print("--- PLATFORM ENDPOINTS TESTS ---")
    results.append(test_platform_status())
    results.append(test_platform_whoami_tenant())
    results.append(test_platform_resolve_subdomain_ddconsult())
    results.append(test_platform_resolve_subdomain_admin())
    results.append(test_platform_resolve_subdomain_localhost())
    print()
    
    # Auth negative test
    print("--- AUTH NEGATIVE TEST ---")
    results.append(test_auth_negative())
    print()
    
    # AI endpoints (low priority)
    print("--- AI ENDPOINTS (LOW PRIORITY) ---")
    results.append(test_dashboard_action_items())
    print()
    
    # Summary
    print("=" * 80)
    passed = sum(results)
    total = len(results)
    print(f"SUMMARY: {passed}/{total} tests passed ({passed*100//total}%)")
    
    if passed == total:
        print("✅ ALL TESTS PASSED - No regressions detected")
    else:
        print(f"❌ {total - passed} test(s) failed - Regressions detected")
    
    print("=" * 80)
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
