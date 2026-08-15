#!/usr/bin/env python3
"""
CRITICAL REGRESSION TEST — Step 4 (Multi-tenant DB layer refactor)
Tests that the ContextVar + LazyCollection proxy pattern refactor did not break existing functionality.
Feature flag: MULTI_TENANT_ENABLED=false (current state)
"""

import requests
import json
from typing import Dict, Any, Optional, List

# Configuration
BASE_URL = "https://a0ac7ee9-2785-4339-ad6f-6886af7a3f1a.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"
CLIENT_EMAIL = "client@test.com"
CLIENT_PASSWORD = "client123"

# Test results tracking
test_results = []
regression_found = False

def log_test(test_id: str, name: str, passed: bool, details: str = ""):
    """Log test result"""
    global regression_found
    status = "✅ PASS" if passed else "❌ FAIL"
    result = {
        "test_id": test_id,
        "name": name,
        "passed": passed,
        "details": details
    }
    test_results.append(result)
    print(f"{status} | {test_id} | {name}")
    if details:
        print(f"    Details: {details}")
    if not passed:
        regression_found = True

def login(email: str, password: str) -> Optional[str]:
    """Login and return JWT token"""
    try:
        response = requests.post(
            f"{API_BASE}/auth/login",
            data={"username": email, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
        else:
            print(f"Login failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Login error: {e}")
        return None

def make_request(method: str, endpoint: str, token: Optional[str] = None, 
                 data: Optional[Dict] = None, params: Optional[Dict] = None) -> requests.Response:
    """Make HTTP request with optional auth"""
    url = f"{API_BASE}{endpoint}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    try:
        if method == "GET":
            return requests.get(url, headers=headers, params=params)
        elif method == "POST":
            headers["Content-Type"] = "application/json"
            return requests.post(url, headers=headers, json=data)
        elif method == "PUT":
            headers["Content-Type"] = "application/json"
            return requests.put(url, headers=headers, json=data)
        elif method == "DELETE":
            return requests.delete(url, headers=headers)
    except Exception as e:
        print(f"Request error: {e}")
        raise

def run_tests():
    """Run all regression tests"""
    print("=" * 80)
    print("CRITICAL REGRESSION TEST — Multi-tenant DB Layer Refactor")
    print("=" * 80)
    print()
    
    # Login as admin
    print("Logging in as admin...")
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        print("❌ CRITICAL: Admin login failed. Cannot proceed with tests.")
        return
    print(f"✅ Admin login successful")
    print()
    
    # ========================================================================
    # SECTION A: Auth & Basic Reads (10 tests)
    # ========================================================================
    print("=" * 80)
    print("SECTION A: Auth & Basic Reads")
    print("=" * 80)
    
    # A1: Login returns JWT token
    log_test("A1", "POST /api/auth/login returns JWT token", 
             admin_token is not None, 
             f"Token received: {admin_token[:20]}..." if admin_token else "No token")
    
    # A2: GET /api/auth/me returns user with role
    resp = make_request("GET", "/auth/me", admin_token)
    if resp.status_code == 200:
        user_data = resp.json()
        has_role = "role" in user_data
        log_test("A2", "GET /api/auth/me returns user with role", 
                 has_role and resp.status_code == 200,
                 f"Role: {user_data.get('role', 'MISSING')}, Email: {user_data.get('email', 'MISSING')}")
    else:
        log_test("A2", "GET /api/auth/me returns user with role", False, 
                 f"HTTP {resp.status_code}: {resp.text[:200]}")
    
    # A3: GET /api/projects returns exactly 4 projects
    resp = make_request("GET", "/projects", admin_token)
    if resp.status_code == 200:
        projects = resp.json()
        project_count = len(projects) if isinstance(projects, list) else 0
        log_test("A3", "GET /api/projects returns exactly 4 projects", 
                 project_count == 4,
                 f"Count: {project_count}, Expected: 4")
        # Save project IDs for later tests
        if isinstance(projects, list) and len(projects) > 0:
            global test_project_id
            test_project_id = projects[0].get("id")
    else:
        log_test("A3", "GET /api/projects returns exactly 4 projects", False,
                 f"HTTP {resp.status_code}: {resp.text[:200]}")
    
    # A4: GET /api/resources returns exactly 5 resources
    resp = make_request("GET", "/resources", admin_token)
    if resp.status_code == 200:
        resources = resp.json()
        resource_count = len(resources) if isinstance(resources, list) else 0
        log_test("A4", "GET /api/resources returns exactly 5 resources",
                 resource_count == 5,
                 f"Count: {resource_count}, Expected: 5")
    else:
        log_test("A4", "GET /api/resources returns exactly 5 resources", False,
                 f"HTTP {resp.status_code}: {resp.text[:200]}")
    
    # A5: GET /api/allocations returns exactly 10 allocations
    resp = make_request("GET", "/allocations", admin_token)
    if resp.status_code == 200:
        allocations = resp.json()
        allocation_count = len(allocations) if isinstance(allocations, list) else 0
        log_test("A5", "GET /api/allocations returns exactly 10 allocations",
                 allocation_count == 10,
                 f"Count: {allocation_count}, Expected: 10")
    else:
        log_test("A5", "GET /api/allocations returns exactly 10 allocations", False,
                 f"HTTP {resp.status_code}: {resp.text[:200]}")
    
    # A6: GET /api/portfolio returns portfolio data
    resp = make_request("GET", "/portfolio", admin_token)
    if resp.status_code == 200:
        portfolio = resp.json()
        has_projects = "projects" in portfolio or isinstance(portfolio, list)
        log_test("A6", "GET /api/portfolio returns portfolio data",
                 has_projects and resp.status_code == 200,
                 f"Type: {type(portfolio).__name__}, Keys: {list(portfolio.keys()) if isinstance(portfolio, dict) else 'list'}")
    else:
        log_test("A6", "GET /api/portfolio returns portfolio data", False,
                 f"HTTP {resp.status_code}: {resp.text[:200]}")
    
    # A7: GET /api/dashboard/action-items returns action items
    resp = make_request("GET", "/dashboard/action-items", admin_token)
    if resp.status_code == 200:
        action_items = resp.json()
        log_test("A7", "GET /api/dashboard/action-items returns structure",
                 resp.status_code == 200,
                 f"Type: {type(action_items).__name__}")
    else:
        log_test("A7", "GET /api/dashboard/action-items returns structure", False,
                 f"HTTP {resp.status_code}: {resp.text[:200]}")
    
    # A8: GET /api/health returns healthy status
    resp = make_request("GET", "/health", admin_token)
    if resp.status_code == 200:
        health = resp.json()
        is_healthy = health.get("status") == "healthy" and health.get("database") == "connected"
        log_test("A8", "GET /api/health returns healthy status",
                 is_healthy,
                 f"Status: {health.get('status')}, Database: {health.get('database')}")
    else:
        log_test("A8", "GET /api/health returns healthy status", False,
                 f"HTTP {resp.status_code}: {resp.text[:200]}")
    
    # A9: GET /api/leaves returns array
    resp = make_request("GET", "/leaves", admin_token)
    if resp.status_code == 200:
        leaves = resp.json()
        is_array = isinstance(leaves, list)
        log_test("A9", "GET /api/leaves returns array",
                 is_array,
                 f"Type: {type(leaves).__name__}, Count: {len(leaves) if is_array else 'N/A'}")
    else:
        log_test("A9", "GET /api/leaves returns array", False,
                 f"HTTP {resp.status_code}: {resp.text[:200]}")
    
    # A10: GET /api/holidays returns array
    resp = make_request("GET", "/holidays", admin_token)
    if resp.status_code == 200:
        holidays = resp.json()
        is_array = isinstance(holidays, list)
        log_test("A10", "GET /api/holidays returns array",
                 is_array,
                 f"Type: {type(holidays).__name__}, Count: {len(holidays) if is_array else 'N/A'}")
    else:
        log_test("A10", "GET /api/holidays returns array", False,
                 f"HTTP {resp.status_code}: {resp.text[:200]}")
    
    print()
    
    # ========================================================================
    # SECTION B: Project CRUD (6 tests)
    # ========================================================================
    print("=" * 80)
    print("SECTION B: Project CRUD")
    print("=" * 80)
    
    # B11: POST /api/projects creates new project
    new_project_data = {
        "name": "REGRESSION_TEST",
        "client_name": "Test Client",
        "status": "Pipeline",
        "start_date": "2026-09-01",
        "end_date": "2026-10-01"
    }
    resp = make_request("POST", "/projects", admin_token, data=new_project_data)
    if resp.status_code == 200:
        created_project = resp.json()
        created_project_id = created_project.get("id")
        log_test("B11", "POST /api/projects creates new project",
                 created_project_id is not None,
                 f"Created project ID: {created_project_id}")
    else:
        log_test("B11", "POST /api/projects creates new project", False,
                 f"HTTP {resp.status_code}: {resp.text[:200]}")
        created_project_id = None
    
    # B12: GET /api/projects should now return 5 projects
    resp = make_request("GET", "/projects", admin_token)
    if resp.status_code == 200:
        projects = resp.json()
        project_count = len(projects) if isinstance(projects, list) else 0
        log_test("B12", "GET /api/projects returns 5 projects after create",
                 project_count == 5,
                 f"Count: {project_count}, Expected: 5")
    else:
        log_test("B12", "GET /api/projects returns 5 projects after create", False,
                 f"HTTP {resp.status_code}: {resp.text[:200]}")
    
    # B13: PUT /api/projects/{id} updates project
    if created_project_id:
        update_data = {"name": "REGRESSION_TEST_UPDATED"}
        resp = make_request("PUT", f"/projects/{created_project_id}", admin_token, data=update_data)
        log_test("B13", "PUT /api/projects/{id} updates project",
                 resp.status_code == 200,
                 f"HTTP {resp.status_code}")
    else:
        log_test("B13", "PUT /api/projects/{id} updates project", False,
                 "Skipped: No project ID from B11")
    
    # B14: GET /api/projects/{id} returns updated project
    if created_project_id:
        resp = make_request("GET", f"/projects/{created_project_id}", admin_token)
        if resp.status_code == 200:
            project = resp.json()
            name_updated = project.get("name") == "REGRESSION_TEST_UPDATED"
            log_test("B14", "GET /api/projects/{id} returns updated project",
                     name_updated,
                     f"Name: {project.get('name')}")
        else:
            log_test("B14", "GET /api/projects/{id} returns updated project", False,
                     f"HTTP {resp.status_code}: {resp.text[:200]}")
    else:
        log_test("B14", "GET /api/projects/{id} returns updated project", False,
                 "Skipped: No project ID from B11")
    
    # B15: DELETE /api/projects/{id} deletes project
    if created_project_id:
        resp = make_request("DELETE", f"/projects/{created_project_id}", admin_token)
        log_test("B15", "DELETE /api/projects/{id} deletes project",
                 resp.status_code == 200,
                 f"HTTP {resp.status_code}")
    else:
        log_test("B15", "DELETE /api/projects/{id} deletes project", False,
                 "Skipped: No project ID from B11")
    
    # B16: GET /api/projects should return 4 projects again
    resp = make_request("GET", "/projects", admin_token)
    if resp.status_code == 200:
        projects = resp.json()
        project_count = len(projects) if isinstance(projects, list) else 0
        log_test("B16", "GET /api/projects returns 4 projects after delete",
                 project_count == 4,
                 f"Count: {project_count}, Expected: 4")
    else:
        log_test("B16", "GET /api/projects returns 4 projects after delete", False,
                 f"HTTP {resp.status_code}: {resp.text[:200]}")
    
    print()
    
    # ========================================================================
    # SECTION C: WBS Operations (2 tests)
    # ========================================================================
    print("=" * 80)
    print("SECTION C: WBS Operations")
    print("=" * 80)
    
    # Use first project ID from A3
    if 'test_project_id' in globals() and test_project_id:
        # C17: GET /api/projects/{id}/wbs returns array
        resp = make_request("GET", f"/projects/{test_project_id}/wbs", admin_token)
        if resp.status_code == 200:
            wbs_tasks = resp.json()
            is_array = isinstance(wbs_tasks, list)
            log_test("C17", "GET /api/projects/{id}/wbs returns array",
                     is_array,
                     f"Type: {type(wbs_tasks).__name__}, Count: {len(wbs_tasks) if is_array else 'N/A'}")
        else:
            log_test("C17", "GET /api/projects/{id}/wbs returns array", False,
                     f"HTTP {resp.status_code}: {resp.text[:200]}")
        
        # C18: GET /api/projects/{id}/risks returns array
        resp = make_request("GET", f"/projects/{test_project_id}/risks", admin_token)
        if resp.status_code == 200:
            risks = resp.json()
            is_array = isinstance(risks, list)
            log_test("C18", "GET /api/projects/{id}/risks returns array",
                     is_array,
                     f"Type: {type(risks).__name__}, Count: {len(risks) if is_array else 'N/A'}")
        else:
            log_test("C18", "GET /api/projects/{id}/risks returns array", False,
                     f"HTTP {resp.status_code}: {resp.text[:200]}")
    else:
        log_test("C17", "GET /api/projects/{id}/wbs returns array", False,
                 "Skipped: No project ID available")
        log_test("C18", "GET /api/projects/{id}/risks returns array", False,
                 "Skipped: No project ID available")
    
    print()
    
    # ========================================================================
    # SECTION D: AI Knowledge Base (1 test)
    # ========================================================================
    print("=" * 80)
    print("SECTION D: AI Knowledge Base")
    print("=" * 80)
    
    # D19: GET /api/ai/knowledge-base/status
    resp = make_request("GET", "/ai/knowledge-base/status", admin_token)
    if resp.status_code == 200:
        kb_status = resp.json()
        has_total = "total_sections" in kb_status
        has_indexed = "last_indexed_at" in kb_status
        has_by_source = "by_source" in kb_status
        total_sections = kb_status.get("total_sections", 0)
        is_valid = has_total and has_by_source and total_sections == 146
        log_test("D19", "GET /api/ai/knowledge-base/status returns correct structure",
                 is_valid,
                 f"Total sections: {total_sections}, Expected: 146, Has by_source: {has_by_source}")
    else:
        log_test("D19", "GET /api/ai/knowledge-base/status returns correct structure", False,
                 f"HTTP {resp.status_code}: {resp.text[:200]}")
    
    print()
    
    # ========================================================================
    # SECTION E: Platform Endpoints (6 tests)
    # ========================================================================
    print("=" * 80)
    print("SECTION E: Platform Endpoints")
    print("=" * 80)
    
    # E20: GET /api/platform/status (no auth)
    resp = make_request("GET", "/platform/status")
    if resp.status_code == 200:
        status = resp.json()
        multi_tenant_off = status.get("multi_tenant_enabled") == False
        platform_ready = status.get("platform_db_ready") == True
        counts = status.get("counts", {})
        tenant_count = counts.get("tenants", 0)
        module_count = counts.get("modules_in_catalog", 0)
        is_valid = multi_tenant_off and platform_ready and tenant_count == 1 and module_count == 17
        log_test("E20", "GET /api/platform/status returns correct data",
                 is_valid,
                 f"multi_tenant_enabled: {status.get('multi_tenant_enabled')}, platform_db_ready: {status.get('platform_db_ready')}, tenants: {tenant_count}, modules: {module_count}")
    else:
        log_test("E20", "GET /api/platform/status returns correct data", False,
                 f"HTTP {resp.status_code}: {resp.text[:200]}")
    
    # E21: GET /api/platform/whoami-tenant (no auth)
    resp = make_request("GET", "/platform/whoami-tenant")
    if resp.status_code == 200:
        whoami = resp.json()
        resolution_mode = whoami.get("resolution_mode")
        tenant = whoami.get("tenant", {})
        tenant_slug = tenant.get("slug")
        enabled_modules = whoami.get("enabled_modules", {})
        module_count = len(enabled_modules)
        is_valid = resolution_mode == "flag_off" and tenant_slug == "ddconsult" and module_count == 17
        log_test("E21", "GET /api/platform/whoami-tenant returns correct data",
                 is_valid,
                 f"resolution_mode: {resolution_mode}, tenant.slug: {tenant_slug}, enabled_modules count: {module_count}")
    else:
        log_test("E21", "GET /api/platform/whoami-tenant returns correct data", False,
                 f"HTTP {resp.status_code}: {resp.text[:200]}")
    
    # E22: GET /api/platform/resolve-subdomain?host=ddconsult.ddplanner.io
    resp = make_request("GET", "/platform/resolve-subdomain", params={"host": "ddconsult.ddplanner.io"})
    if resp.status_code == 200:
        result = resp.json()
        subdomain = result.get("subdomain")
        is_valid = subdomain == "ddconsult"
        log_test("E22", "GET /api/platform/resolve-subdomain (ddconsult.ddplanner.io)",
                 is_valid,
                 f"subdomain: {subdomain}, Expected: ddconsult")
    else:
        log_test("E22", "GET /api/platform/resolve-subdomain (ddconsult.ddplanner.io)", False,
                 f"HTTP {resp.status_code}: {resp.text[:200]}")
    
    # E23: GET /api/platform/resolve-subdomain?host=admin.ddplanner.io
    resp = make_request("GET", "/platform/resolve-subdomain", params={"host": "admin.ddplanner.io"})
    if resp.status_code == 200:
        result = resp.json()
        subdomain = result.get("subdomain")
        is_valid = subdomain == "admin"
        log_test("E23", "GET /api/platform/resolve-subdomain (admin.ddplanner.io)",
                 is_valid,
                 f"subdomain: {subdomain}, Expected: admin")
    else:
        log_test("E23", "GET /api/platform/resolve-subdomain (admin.ddplanner.io)", False,
                 f"HTTP {resp.status_code}: {resp.text[:200]}")
    
    # E24: GET /api/platform/resolve-subdomain?host=localhost:8001
    resp = make_request("GET", "/platform/resolve-subdomain", params={"host": "localhost:8001"})
    if resp.status_code == 200:
        result = resp.json()
        subdomain = result.get("subdomain")
        is_valid = subdomain is None
        log_test("E24", "GET /api/platform/resolve-subdomain (localhost:8001)",
                 is_valid,
                 f"subdomain: {subdomain}, Expected: null")
    else:
        log_test("E24", "GET /api/platform/resolve-subdomain (localhost:8001)", False,
                 f"HTTP {resp.status_code}: {resp.text[:200]}")
    
    # E25: GET /api/platform/tenants (requires super_admin, admin will get 403)
    resp = make_request("GET", "/platform/tenants", admin_token)
    # Admin should get 403 - this is CORRECT behavior, not a regression
    is_403 = resp.status_code == 403
    log_test("E25", "GET /api/platform/tenants returns 403 for admin (expected)",
             is_403,
             f"HTTP {resp.status_code} (403 is correct for admin role)")
    
    print()
    
    # ========================================================================
    # SECTION F: Auth Negative Tests (2 tests)
    # ========================================================================
    print("=" * 80)
    print("SECTION F: Auth Negative Tests")
    print("=" * 80)
    
    # F26: GET /api/projects without Authorization header returns 401
    resp = make_request("GET", "/projects")
    is_401 = resp.status_code == 401
    log_test("F26", "GET /api/projects without auth returns 401",
             is_401,
             f"HTTP {resp.status_code}")
    
    # F27: GET /api/projects with invalid token returns 401
    resp = make_request("GET", "/projects", token="invalid_token_12345")
    is_401 = resp.status_code == 401
    log_test("F27", "GET /api/projects with invalid token returns 401",
             is_401,
             f"HTTP {resp.status_code}")
    
    print()
    
    # ========================================================================
    # SECTION G: Client Role Access (2 tests)
    # ========================================================================
    print("=" * 80)
    print("SECTION G: Client Role Access")
    print("=" * 80)
    
    # G28: Login as client
    client_token = login(CLIENT_EMAIL, CLIENT_PASSWORD)
    if client_token:
        log_test("G28", "Login as client@test.com successful",
                 True,
                 f"Token received: {client_token[:20]}...")
        
        # G29: GET /api/projects as client returns filtered projects
        resp = make_request("GET", "/projects", client_token)
        if resp.status_code == 200:
            projects = resp.json()
            project_count = len(projects) if isinstance(projects, list) else 0
            # Client may have 0 projects or a filtered subset
            log_test("G29", "GET /api/projects as client returns filtered data",
                     resp.status_code == 200,
                     f"Count: {project_count} (0 or filtered subset is expected)")
        else:
            log_test("G29", "GET /api/projects as client returns filtered data", False,
                     f"HTTP {resp.status_code}: {resp.text[:200]}")
    else:
        log_test("G28", "Login as client@test.com successful", False,
                 "Client login failed")
        log_test("G29", "GET /api/projects as client returns filtered data", False,
                 "Skipped: Client login failed")
    
    print()
    
    # ========================================================================
    # SECTION H: Timesheet Endpoints (1 test)
    # ========================================================================
    print("=" * 80)
    print("SECTION H: Timesheet Endpoints")
    print("=" * 80)
    
    # H30: GET /api/timesheets/history or /api/timesheets/my-week
    resp = make_request("GET", "/timesheets/history", admin_token)
    if resp.status_code == 200:
        timesheets = resp.json()
        log_test("H30", "GET /api/timesheets/history returns data",
                 True,
                 f"Type: {type(timesheets).__name__}")
    else:
        # Try alternative endpoint
        resp = make_request("GET", "/timesheets/my-week", admin_token)
        if resp.status_code == 200:
            timesheets = resp.json()
            log_test("H30", "GET /api/timesheets/my-week returns data",
                     True,
                     f"Type: {type(timesheets).__name__}")
        else:
            log_test("H30", "GET /api/timesheets endpoints return data", False,
                     f"Both /history and /my-week failed. HTTP {resp.status_code}: {resp.text[:200]}")
    
    print()
    
    # ========================================================================
    # FINAL SUMMARY
    # ========================================================================
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed_count = sum(1 for r in test_results if r["passed"])
    failed_count = sum(1 for r in test_results if not r["passed"])
    total_count = len(test_results)
    
    print(f"Total Tests: {total_count}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {failed_count}")
    print()
    
    if failed_count > 0:
        print("FAILED TESTS:")
        for result in test_results:
            if not result["passed"]:
                print(f"  ❌ {result['test_id']} | {result['name']}")
                if result["details"]:
                    print(f"     {result['details']}")
        print()
    
    # Final verdict
    print("=" * 80)
    if regression_found:
        print("REGRESSION VERDICT: FAIL")
        print("⚠️  One or more tests failed. Review the failures above.")
    else:
        print("REGRESSION VERDICT: PASS")
        print("✅ All tests passed. No regressions detected.")
    print("=" * 80)

if __name__ == "__main__":
    run_tests()
