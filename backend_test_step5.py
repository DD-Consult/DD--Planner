#!/usr/bin/env python3
"""
Step 5 Regression + New Endpoint Testing — Platform Auth & JWT Extension

Tests 32 scenarios:
- A. Backward compatibility (13 tests) - existing endpoints must work identically to Step 4
- B. NEW Platform Auth endpoints (7 tests) - new /api/platform/auth/login endpoint
- C. Platform admin access (3 tests) - platform admin can access platform endpoints
- D. Access boundaries (5 tests) - verify proper authorization
- E. Basic public endpoints (3 tests) - no auth required
- F. Backend error log check (1 test) - check for errors

Backend URL: https://a0ac7ee9-2785-4339-ad6f-6886af7a3f1a.preview.emergentagent.com
Feature flag: MULTI_TENANT_ENABLED=false (DO NOT change)

Test credentials:
- Tenant admin: admin@test.com / admin123 (in resource_planner DB, admin role)
- Tenant client: client@test.com / client123 (client role)
- Platform admin: don@ddconsult.tech / Welcome123! (in platform_db.platform_users)
"""

import requests
import json
import base64
from typing import Dict, Any, Optional

# Backend URL
BASE_URL = "https://a0ac7ee9-2785-4339-ad6f-6886af7a3f1a.preview.emergentagent.com"

# Test credentials
TENANT_ADMIN = {"username": "admin@test.com", "password": "admin123"}
TENANT_CLIENT = {"username": "client@test.com", "password": "client123"}
PLATFORM_ADMIN = {"username": "don@ddconsult.tech", "password": "Welcome123!"}

# Global tokens
TENANT_TOKEN = None
PLATFORM_TOKEN = None

# Test results
test_results = []


def log_test(test_num: int, name: str, passed: bool, expected: str, actual: str, details: str = ""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    result = {
        "test_num": test_num,
        "name": name,
        "status": status,
        "passed": passed,
        "expected": expected,
        "actual": actual,
        "details": details
    }
    test_results.append(result)
    print(f"{status} Test {test_num}: {name}")
    if not passed:
        print(f"  Expected: {expected}")
        print(f"  Actual: {actual}")
        if details:
            print(f"  Details: {details}")


def decode_jwt_payload(token: str) -> Optional[Dict[str, Any]]:
    """Decode JWT payload (middle segment) without verification"""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        # Add padding if needed
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += '=' * padding
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception as e:
        print(f"  JWT decode error: {e}")
        return None


def test_a_backward_compatibility():
    """A. Backward compatibility — existing endpoints must be identical to Step 4"""
    global TENANT_TOKEN
    
    print("\n" + "="*80)
    print("SECTION A: BACKWARD COMPATIBILITY (13 tests)")
    print("="*80)
    
    # Test 1: POST /api/auth/login with admin@test.com/admin123
    print("\nTest 1: Tenant admin login")
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        data=TENANT_ADMIN,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    passed = resp.status_code == 200
    details = ""
    if passed:
        data = resp.json()
        TENANT_TOKEN = data.get("access_token")
        details = f"Token received, user role: {data.get('user', {}).get('role')}"
    log_test(1, "POST /api/auth/login (tenant admin)", passed, "HTTP 200", f"HTTP {resp.status_code}", details)
    
    if not TENANT_TOKEN:
        print("❌ CRITICAL: Cannot proceed without tenant token")
        return
    
    # Test 2: Save token (already done)
    print("\nTest 2: Save TENANT_TOKEN")
    log_test(2, "Save TENANT_TOKEN", True, "Token saved", "Token saved", f"Token length: {len(TENANT_TOKEN)}")
    
    # Test 3: GET /api/auth/me with TENANT_TOKEN
    print("\nTest 3: GET /api/auth/me")
    resp = requests.get(
        f"{BASE_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
    )
    passed = resp.status_code == 200
    details = ""
    if passed:
        data = resp.json()
        details = f"User: {data.get('email')}, Role: {data.get('role')}"
    log_test(3, "GET /api/auth/me", passed, "HTTP 200", f"HTTP {resp.status_code}", details)
    
    # Test 4: Decode JWT payload - should contain ONLY sub and exp (no tenant_id, no token_type)
    print("\nTest 4: Decode JWT payload (backward-compat mode)")
    payload = decode_jwt_payload(TENANT_TOKEN)
    if payload:
        has_sub = "sub" in payload
        has_exp = "exp" in payload
        has_tenant_id = "tenant_id" in payload
        has_token_type = "token_type" in payload
        
        # In flag=off mode, should only have sub and exp
        passed = has_sub and has_exp and not has_tenant_id and not has_token_type
        expected = "Only 'sub' and 'exp' claims (no tenant_id, no token_type)"
        actual = f"Claims: {list(payload.keys())}"
        details = f"sub={payload.get('sub')}, exp={payload.get('exp')}"
        log_test(4, "JWT payload structure (flag=off)", passed, expected, actual, details)
    else:
        log_test(4, "JWT payload structure", False, "Valid JWT", "Failed to decode", "")
    
    # Test 5: GET /api/projects - should return exactly 4 projects
    print("\nTest 5: GET /api/projects")
    resp = requests.get(
        f"{BASE_URL}/api/projects",
        headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
    )
    passed = False
    details = ""
    if resp.status_code == 200:
        data = resp.json()
        project_count = len(data)
        passed = project_count == 4
        details = f"Project count: {project_count}"
    log_test(5, "GET /api/projects (count=4)", passed, "HTTP 200, 4 projects", f"HTTP {resp.status_code}, {details}", details)
    
    # Test 6: GET /api/resources - should return exactly 5
    print("\nTest 6: GET /api/resources")
    resp = requests.get(
        f"{BASE_URL}/api/resources",
        headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
    )
    passed = False
    details = ""
    if resp.status_code == 200:
        data = resp.json()
        resource_count = len(data)
        passed = resource_count == 5
        details = f"Resource count: {resource_count}"
    log_test(6, "GET /api/resources (count=5)", passed, "HTTP 200, 5 resources", f"HTTP {resp.status_code}, {details}", details)
    
    # Test 7: GET /api/allocations - should return exactly 10
    print("\nTest 7: GET /api/allocations")
    resp = requests.get(
        f"{BASE_URL}/api/allocations",
        headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
    )
    passed = False
    details = ""
    if resp.status_code == 200:
        data = resp.json()
        allocation_count = len(data)
        passed = allocation_count == 10
        details = f"Allocation count: {allocation_count}"
    log_test(7, "GET /api/allocations (count=10)", passed, "HTTP 200, 10 allocations", f"HTTP {resp.status_code}, {details}", details)
    
    # Test 8: GET /api/portfolio
    print("\nTest 8: GET /api/portfolio")
    resp = requests.get(
        f"{BASE_URL}/api/portfolio",
        headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
    )
    passed = resp.status_code == 200
    log_test(8, "GET /api/portfolio", passed, "HTTP 200", f"HTTP {resp.status_code}", "")
    
    # Test 9: GET /api/dashboard/action-items
    print("\nTest 9: GET /api/dashboard/action-items")
    resp = requests.get(
        f"{BASE_URL}/api/dashboard/action-items",
        headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
    )
    passed = resp.status_code == 200
    log_test(9, "GET /api/dashboard/action-items", passed, "HTTP 200", f"HTTP {resp.status_code}", "")
    
    # Test 10: GET /api/leaves
    print("\nTest 10: GET /api/leaves")
    resp = requests.get(
        f"{BASE_URL}/api/leaves",
        headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
    )
    passed = resp.status_code == 200
    log_test(10, "GET /api/leaves", passed, "HTTP 200", f"HTTP {resp.status_code}", "")
    
    # Test 11: GET /api/holidays
    print("\nTest 11: GET /api/holidays")
    resp = requests.get(
        f"{BASE_URL}/api/holidays",
        headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
    )
    passed = resp.status_code == 200
    log_test(11, "GET /api/holidays", passed, "HTTP 200", f"HTTP {resp.status_code}", "")
    
    # Test 12: GET /api/ai/knowledge-base/status - should return total_sections: 146
    print("\nTest 12: GET /api/ai/knowledge-base/status")
    resp = requests.get(
        f"{BASE_URL}/api/ai/knowledge-base/status",
        headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
    )
    passed = False
    details = ""
    if resp.status_code == 200:
        data = resp.json()
        total_sections = data.get("total_sections", 0)
        passed = total_sections == 146
        details = f"total_sections: {total_sections}"
    log_test(12, "GET /api/ai/knowledge-base/status (146 sections)", passed, "HTTP 200, total_sections=146", f"HTTP {resp.status_code}, {details}", details)
    
    # Test 13: Create + delete a project
    print("\nTest 13: Create + delete project")
    # Create project
    create_resp = requests.post(
        f"{BASE_URL}/api/projects",
        headers={"Authorization": f"Bearer {TENANT_TOKEN}", "Content-Type": "application/json"},
        json={
            "name": "REGRESSION_TEST_PROJECT",
            "client_name": "Test Client",
            "status": "Active",
            "start_date": "2026-07-01",
            "end_date": "2026-07-31"
        }
    )
    passed = False
    details = ""
    if create_resp.status_code == 200:
        project_data = create_resp.json()
        project_id = project_data.get("id")
        if project_id:
            # Delete project
            delete_resp = requests.delete(
                f"{BASE_URL}/api/projects/{project_id}",
                headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
            )
            passed = delete_resp.status_code == 200
            details = f"Created project {project_id}, delete status: {delete_resp.status_code}"
        else:
            details = "Project created but no ID returned"
    else:
        details = f"Create failed: {create_resp.status_code}"
    log_test(13, "Create + delete project", passed, "Both HTTP 200", details, "")


def test_b_new_platform_auth():
    """B. NEW Platform Auth endpoints"""
    global PLATFORM_TOKEN
    
    print("\n" + "="*80)
    print("SECTION B: NEW PLATFORM AUTH ENDPOINTS (7 tests)")
    print("="*80)
    
    # Test 14: POST /api/platform/auth/login with don@ddconsult.tech/Welcome123!
    print("\nTest 14: Platform admin login")
    resp = requests.post(
        f"{BASE_URL}/api/platform/auth/login",
        data=PLATFORM_ADMIN,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    passed = resp.status_code == 200
    details = ""
    if passed:
        data = resp.json()
        PLATFORM_TOKEN = data.get("access_token")
        user = data.get("user", {})
        details = f"Token received, user: {user.get('email')}, role: {user.get('role')}, must_change_password: {user.get('must_change_password')}"
    log_test(14, "POST /api/platform/auth/login", passed, "HTTP 200", f"HTTP {resp.status_code}", details)
    
    if not PLATFORM_TOKEN:
        print("❌ CRITICAL: Cannot proceed without platform token")
        return
    
    # Test 15: Save token and verify response structure
    print("\nTest 15: Verify platform login response structure")
    resp = requests.post(
        f"{BASE_URL}/api/platform/auth/login",
        data=PLATFORM_ADMIN,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    passed = False
    details = ""
    if resp.status_code == 200:
        data = resp.json()
        user = data.get("user", {})
        has_role = user.get("role") == "platform_admin"
        has_email = user.get("email") == "don@ddconsult.tech"
        has_must_change = "must_change_password" in user
        passed = has_role and has_email and has_must_change
        details = f"role={user.get('role')}, email={user.get('email')}, must_change_password={user.get('must_change_password')}"
    log_test(15, "Platform login response structure", passed, "role=platform_admin, email=don@ddconsult.tech, must_change_password present", details, "")
    
    # Test 16: Decode PLATFORM_TOKEN payload - must contain token_type: "platform", role: "platform_admin", platform_user_id
    print("\nTest 16: Decode PLATFORM_TOKEN payload")
    payload = decode_jwt_payload(PLATFORM_TOKEN)
    if payload:
        has_token_type = payload.get("token_type") == "platform"
        has_role = payload.get("role") == "platform_admin"
        has_platform_user_id = "platform_user_id" in payload
        
        passed = has_token_type and has_role and has_platform_user_id
        expected = "token_type='platform', role='platform_admin', platform_user_id present"
        actual = f"token_type={payload.get('token_type')}, role={payload.get('role')}, platform_user_id={payload.get('platform_user_id')}"
        log_test(16, "PLATFORM_TOKEN payload structure", passed, expected, actual, "")
    else:
        log_test(16, "PLATFORM_TOKEN payload structure", False, "Valid JWT", "Failed to decode", "")
    
    # Test 17: GET /api/platform/auth/me with PLATFORM_TOKEN
    print("\nTest 17: GET /api/platform/auth/me")
    resp = requests.get(
        f"{BASE_URL}/api/platform/auth/me",
        headers={"Authorization": f"Bearer {PLATFORM_TOKEN}"}
    )
    passed = resp.status_code == 200
    details = ""
    if passed:
        data = resp.json()
        details = f"User: {data.get('email')}, Role: {data.get('role')}"
    log_test(17, "GET /api/platform/auth/me", passed, "HTTP 200", f"HTTP {resp.status_code}", details)
    
    # Test 18: POST /api/platform/auth/login with WRONG password
    print("\nTest 18: Platform login with wrong password")
    resp = requests.post(
        f"{BASE_URL}/api/platform/auth/login",
        data={"username": "don@ddconsult.tech", "password": "WrongPassword123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    passed = resp.status_code == 401
    log_test(18, "Platform login with wrong password", passed, "HTTP 401", f"HTTP {resp.status_code}", "")
    
    # Test 19: POST /api/platform/auth/login with non-existent email
    print("\nTest 19: Platform login with non-existent email")
    resp = requests.post(
        f"{BASE_URL}/api/platform/auth/login",
        data={"username": "nonexistent@example.com", "password": "Welcome123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    passed = resp.status_code == 401
    log_test(19, "Platform login with non-existent email", passed, "HTTP 401", f"HTTP {resp.status_code}", "")
    
    # Test 20: POST /api/platform/auth/logout
    print("\nTest 20: POST /api/platform/auth/logout")
    resp = requests.post(
        f"{BASE_URL}/api/platform/auth/logout",
        headers={"Authorization": f"Bearer {PLATFORM_TOKEN}"}
    )
    passed = resp.status_code == 204
    log_test(20, "POST /api/platform/auth/logout", passed, "HTTP 204", f"HTTP {resp.status_code}", "")


def test_c_platform_admin_access():
    """C. Platform admin can access platform endpoints"""
    print("\n" + "="*80)
    print("SECTION C: PLATFORM ADMIN ACCESS (3 tests)")
    print("="*80)
    
    if not PLATFORM_TOKEN:
        print("❌ CRITICAL: No platform token available")
        return
    
    # Test 21: GET /api/platform/tenants with PLATFORM_TOKEN
    print("\nTest 21: GET /api/platform/tenants")
    resp = requests.get(
        f"{BASE_URL}/api/platform/tenants",
        headers={"Authorization": f"Bearer {PLATFORM_TOKEN}"}
    )
    passed = False
    details = ""
    if resp.status_code == 200:
        data = resp.json()
        tenant_count = len(data)
        passed = tenant_count == 1
        if tenant_count > 0:
            details = f"Tenant count: {tenant_count}, first tenant: {data[0].get('slug')}"
        else:
            details = f"Tenant count: {tenant_count}"
    log_test(21, "GET /api/platform/tenants (count=1)", passed, "HTTP 200, 1 tenant (ddconsult)", f"HTTP {resp.status_code}, {details}", details)
    
    # Test 22: GET /api/platform/modules with PLATFORM_TOKEN
    print("\nTest 22: GET /api/platform/modules")
    resp = requests.get(
        f"{BASE_URL}/api/platform/modules",
        headers={"Authorization": f"Bearer {PLATFORM_TOKEN}"}
    )
    passed = False
    details = ""
    if resp.status_code == 200:
        data = resp.json()
        module_count = len(data)
        passed = module_count == 17
        details = f"Module count: {module_count}"
    log_test(22, "GET /api/platform/modules (count=17)", passed, "HTTP 200, 17 modules", f"HTTP {resp.status_code}, {details}", details)
    
    # Test 23: GET /api/platform/tenants/ddconsult/modules with PLATFORM_TOKEN
    print("\nTest 23: GET /api/platform/tenants/ddconsult/modules")
    resp = requests.get(
        f"{BASE_URL}/api/platform/tenants/ddconsult/modules",
        headers={"Authorization": f"Bearer {PLATFORM_TOKEN}"}
    )
    passed = False
    details = ""
    if resp.status_code == 200:
        data = resp.json()
        tenant_slug = data.get("tenant_slug")
        modules = data.get("modules", [])
        module_count = len(modules)
        all_enabled = all(m.get("enabled") for m in modules)
        passed = tenant_slug == "ddconsult" and module_count == 17 and all_enabled
        details = f"tenant_slug={tenant_slug}, module_count={module_count}, all_enabled={all_enabled}"
    log_test(23, "GET /api/platform/tenants/ddconsult/modules", passed, "HTTP 200, tenant_slug=ddconsult, 17 modules all enabled", f"HTTP {resp.status_code}, {details}", details)


def test_d_access_boundaries():
    """D. Access boundaries"""
    print("\n" + "="*80)
    print("SECTION D: ACCESS BOUNDARIES (5 tests)")
    print("="*80)
    
    if not TENANT_TOKEN:
        print("❌ CRITICAL: No tenant token available")
        return
    
    # Test 24: GET /api/platform/tenants with TENANT_TOKEN (regular admin, NOT super_admin)
    print("\nTest 24: GET /api/platform/tenants with TENANT_TOKEN (admin role)")
    resp = requests.get(
        f"{BASE_URL}/api/platform/tenants",
        headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
    )
    passed = resp.status_code == 403
    details = f"Admin role should not have access to platform endpoints in backward-compat mode"
    log_test(24, "GET /api/platform/tenants with admin token", passed, "HTTP 403", f"HTTP {resp.status_code}", details)
    
    # Test 25: GET /api/platform/auth/me with TENANT_TOKEN (regular tenant admin)
    print("\nTest 25: GET /api/platform/auth/me with TENANT_TOKEN")
    resp = requests.get(
        f"{BASE_URL}/api/platform/auth/me",
        headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
    )
    passed = resp.status_code in [401, 403]
    details = f"Tenant admin should not have access to platform auth endpoints"
    log_test(25, "GET /api/platform/auth/me with tenant token", passed, "HTTP 403 or 401", f"HTTP {resp.status_code}", details)
    
    # Test 26: GET /api/platform/auth/me without any token
    print("\nTest 26: GET /api/platform/auth/me without token")
    resp = requests.get(f"{BASE_URL}/api/platform/auth/me")
    passed = resp.status_code == 401
    log_test(26, "GET /api/platform/auth/me without token", passed, "HTTP 401", f"HTTP {resp.status_code}", "")
    
    # Test 27: GET /api/projects without token
    print("\nTest 27: GET /api/projects without token")
    resp = requests.get(f"{BASE_URL}/api/projects")
    passed = resp.status_code == 401
    log_test(27, "GET /api/projects without token", passed, "HTTP 401", f"HTTP {resp.status_code}", "")
    
    # Test 28: GET /api/projects with invalid token
    print("\nTest 28: GET /api/projects with invalid token")
    resp = requests.get(
        f"{BASE_URL}/api/projects",
        headers={"Authorization": "Bearer garbage"}
    )
    passed = resp.status_code == 401
    log_test(28, "GET /api/projects with invalid token", passed, "HTTP 401", f"HTTP {resp.status_code}", "")


def test_e_public_endpoints():
    """E. Basic public endpoints (no auth)"""
    print("\n" + "="*80)
    print("SECTION E: PUBLIC ENDPOINTS (3 tests)")
    print("="*80)
    
    # Test 29: GET /api/health
    print("\nTest 29: GET /api/health")
    resp = requests.get(f"{BASE_URL}/api/health")
    passed = False
    details = ""
    if resp.status_code == 200:
        data = resp.json()
        status = data.get("status")
        passed = status == "healthy"
        details = f"status={status}"
    log_test(29, "GET /api/health", passed, "HTTP 200, status=healthy", f"HTTP {resp.status_code}, {details}", details)
    
    # Test 30: GET /api/platform/status
    print("\nTest 30: GET /api/platform/status")
    resp = requests.get(f"{BASE_URL}/api/platform/status")
    passed = False
    details = ""
    if resp.status_code == 200:
        data = resp.json()
        multi_tenant = data.get("multi_tenant_enabled")
        platform_ready = data.get("platform_db_ready")
        passed = multi_tenant == False and platform_ready == True
        details = f"multi_tenant_enabled={multi_tenant}, platform_db_ready={platform_ready}"
    log_test(30, "GET /api/platform/status", passed, "HTTP 200, multi_tenant_enabled=false, platform_db_ready=true", f"HTTP {resp.status_code}, {details}", details)
    
    # Test 31: GET /api/platform/whoami-tenant
    print("\nTest 31: GET /api/platform/whoami-tenant")
    resp = requests.get(f"{BASE_URL}/api/platform/whoami-tenant")
    passed = False
    details = ""
    if resp.status_code == 200:
        data = resp.json()
        resolution_mode = data.get("resolution_mode")
        tenant = data.get("tenant", {})
        tenant_slug = tenant.get("slug") if tenant else None
        passed = resolution_mode == "flag_off" and tenant_slug == "ddconsult"
        details = f"resolution_mode={resolution_mode}, tenant.slug={tenant_slug}"
    log_test(31, "GET /api/platform/whoami-tenant", passed, "HTTP 200, resolution_mode=flag_off, tenant.slug=ddconsult", f"HTTP {resp.status_code}, {details}", details)


def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    total = len(test_results)
    passed = sum(1 for r in test_results if r["passed"])
    failed = total - passed
    
    print(f"\nTotal tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Pass rate: {passed/total*100:.1f}%")
    
    if failed > 0:
        print("\n" + "="*80)
        print("FAILED TESTS")
        print("="*80)
        for r in test_results:
            if not r["passed"]:
                print(f"\n❌ Test {r['test_num']}: {r['name']}")
                print(f"  Expected: {r['expected']}")
                print(f"  Actual: {r['actual']}")
                if r["details"]:
                    print(f"  Details: {r['details']}")
    
    print("\n" + "="*80)
    print("TEST-BY-TEST RESULTS")
    print("="*80)
    for r in test_results:
        print(f"{r['status']} Test {r['test_num']}: {r['name']}")


def main():
    """Run all tests"""
    print("="*80)
    print("STEP 5 REGRESSION + NEW ENDPOINT TESTING")
    print("Platform Auth & JWT Extension")
    print("="*80)
    print(f"\nBackend URL: {BASE_URL}")
    print(f"Feature flag: MULTI_TENANT_ENABLED=false")
    print(f"\nTest credentials:")
    print(f"  - Tenant admin: {TENANT_ADMIN['username']}")
    print(f"  - Tenant client: {TENANT_CLIENT['username']}")
    print(f"  - Platform admin: {PLATFORM_ADMIN['username']}")
    
    try:
        test_a_backward_compatibility()
        test_b_new_platform_auth()
        test_c_platform_admin_access()
        test_d_access_boundaries()
        test_e_public_endpoints()
        
        print_summary()
        
        # Final verdict
        total = len(test_results)
        passed = sum(1 for r in test_results if r["passed"])
        
        print("\n" + "="*80)
        print("FINAL VERDICT")
        print("="*80)
        if passed == total:
            print("✅ PASS — All tests passed. No regressions detected.")
        else:
            print(f"❌ FAIL — {total - passed} test(s) failed. See details above.")
        
        print("\n" + "="*80)
        print("Test 32: Check backend error log")
        print("="*80)
        print("NOTE: Backend error log check must be performed manually by viewing:")
        print("  /var/log/supervisor/backend.err.log")
        print("Look for: AttributeError, TypeError, JWTError uncaught tracebacks, or 500s")
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
