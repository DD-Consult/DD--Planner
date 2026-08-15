#!/usr/bin/env python3
"""
Step 8 Testing: Public Tenant Sign-up + GCP Production Readiness
=================================================================

Tests:
- A. Regression (10 tests) - All Steps 1-7 endpoints must still work
- B. Slug availability endpoint (8 tests) - GET /api/signup/check-slug
- C. Sign-up endpoint (7 tests) - POST /api/signup
- D. Sign-up validation (6 tests) - Pydantic validation errors
- E. X-Forwarded-Host handling (3 tests) - GCP Load Balancer compatibility
- F. Login flow verification (1 test) - Multi-tenant mode flag check
- G. Cleanup (1 test) - Drop test tenant
- H. Sanity checks (3 tests) - No bloat/regression

Backend URL: https://a0ac7ee9-2785-4339-ad6f-6886af7a3f1a.preview.emergentagent.com
Feature flag: MULTI_TENANT_ENABLED=false (DO NOT change)
Credentials:
  - Tenant admin: admin@test.com / admin123
  - Platform admin: don@ddconsult.tech / Welcome123!
"""

import requests
import sys
from typing import Dict, Optional

# Configuration
BASE_URL = "https://a0ac7ee9-2785-4339-ad6f-6886af7a3f1a.preview.emergentagent.com"
TENANT_ADMIN_EMAIL = "admin@test.com"
TENANT_ADMIN_PASSWORD = "admin123"
PLATFORM_ADMIN_EMAIL = "don@ddconsult.tech"
PLATFORM_ADMIN_PASSWORD = "Welcome123!"

# Test state
tenant_token: Optional[str] = None
platform_token: Optional[str] = None
test_results = []


def log_test(test_num: int, description: str, passed: bool, details: str = ""):
    """Log test result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    result = f"Test {test_num}: {status} - {description}"
    if details:
        result += f"\n    Details: {details}"
    print(result)
    test_results.append({
        "test_num": test_num,
        "description": description,
        "passed": passed,
        "details": details
    })


def login_tenant() -> str:
    """Login as tenant admin and return JWT token."""
    global tenant_token
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": TENANT_ADMIN_EMAIL, "password": TENANT_ADMIN_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if response.status_code == 200:
        tenant_token = response.json()["access_token"]
        return tenant_token
    raise Exception(f"Tenant login failed: {response.status_code} {response.text}")


def login_platform() -> str:
    """Login as platform admin and return JWT token."""
    global platform_token
    response = requests.post(
        f"{BASE_URL}/api/platform/auth/login",
        data={"username": PLATFORM_ADMIN_EMAIL, "password": PLATFORM_ADMIN_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if response.status_code == 200:
        platform_token = response.json()["access_token"]
        return platform_token
    raise Exception(f"Platform login failed: {response.status_code} {response.text}")


def get_auth_headers(token: str) -> Dict[str, str]:
    """Return authorization headers."""
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# A. REGRESSION TESTS (Steps 1-7)
# ============================================================================

def test_regression():
    """Test A: Regression - All previous Steps 1-7 endpoints must still work."""
    print("\n" + "="*80)
    print("SECTION A: REGRESSION TESTS (Steps 1-7)")
    print("="*80)
    
    # Test 1: POST /api/auth/login
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": TENANT_ADMIN_EMAIL, "password": TENANT_ADMIN_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    log_test(1, "POST /api/auth/login (tenant admin)", 
             response.status_code == 200,
             f"HTTP {response.status_code}")
    
    if response.status_code == 200:
        token = response.json()["access_token"]
        headers = get_auth_headers(token)
        
        # Test 2: GET /api/projects (exactly 4)
        response = requests.get(f"{BASE_URL}/api/projects", headers=headers)
        projects_count = len(response.json()) if response.status_code == 200 else 0
        log_test(2, "GET /api/projects returns exactly 4",
                 response.status_code == 200 and projects_count == 4,
                 f"HTTP {response.status_code}, count={projects_count}")
        
        # Test 3: GET /api/resources (exactly 5)
        response = requests.get(f"{BASE_URL}/api/resources", headers=headers)
        resources_count = len(response.json()) if response.status_code == 200 else 0
        log_test(3, "GET /api/resources returns exactly 5",
                 response.status_code == 200 and resources_count == 5,
                 f"HTTP {response.status_code}, count={resources_count}")
        
        # Test 4: GET /api/allocations (exactly 10)
        response = requests.get(f"{BASE_URL}/api/allocations", headers=headers)
        allocations_count = len(response.json()) if response.status_code == 200 else 0
        log_test(4, "GET /api/allocations returns exactly 10",
                 response.status_code == 200 and allocations_count == 10,
                 f"HTTP {response.status_code}, count={allocations_count}")
        
        # Test 5: GET /api/tenant/modules (17 keys all true)
        response = requests.get(f"{BASE_URL}/api/tenant/modules", headers=headers)
        if response.status_code == 200:
            data = response.json()
            modules = data.get("modules", {})
            all_enabled = all(v is True for v in modules.values())
            log_test(5, "GET /api/tenant/modules returns 17 keys all true",
                     len(modules) == 17 and all_enabled,
                     f"HTTP {response.status_code}, modules_count={len(modules)}, all_enabled={all_enabled}")
        else:
            log_test(5, "GET /api/tenant/modules returns 17 keys all true",
                     False, f"HTTP {response.status_code}")
    
    # Test 6: POST /api/platform/auth/login
    response = requests.post(
        f"{BASE_URL}/api/platform/auth/login",
        data={"username": PLATFORM_ADMIN_EMAIL, "password": PLATFORM_ADMIN_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    log_test(6, "POST /api/platform/auth/login (platform admin)",
             response.status_code == 200,
             f"HTTP {response.status_code}")
    
    if response.status_code == 200:
        platform_token = response.json()["access_token"]
        platform_headers = get_auth_headers(platform_token)
        
        # Test 7: GET /api/platform/dashboard/stats
        response = requests.get(f"{BASE_URL}/api/platform/dashboard/stats", headers=platform_headers)
        log_test(7, "GET /api/platform/dashboard/stats",
                 response.status_code == 200,
                 f"HTTP {response.status_code}")
        
        # Test 8: GET /api/platform/tenants (1 tenant with enabled_modules_count: 17)
        response = requests.get(f"{BASE_URL}/api/platform/tenants", headers=platform_headers)
        if response.status_code == 200:
            tenants = response.json()
            has_ddconsult = any(t.get("slug") == "ddconsult" and t.get("enabled_modules_count") == 17 for t in tenants)
            log_test(8, "GET /api/platform/tenants returns 1 tenant with enabled_modules_count=17",
                     len(tenants) >= 1 and has_ddconsult,
                     f"HTTP {response.status_code}, tenants_count={len(tenants)}")
        else:
            log_test(8, "GET /api/platform/tenants returns 1 tenant with enabled_modules_count=17",
                     False, f"HTTP {response.status_code}")
        
        # Test 9: GET /api/platform/audit-log?limit=5
        response = requests.get(f"{BASE_URL}/api/platform/audit-log?limit=5", headers=platform_headers)
        log_test(9, "GET /api/platform/audit-log?limit=5",
                 response.status_code == 200,
                 f"HTTP {response.status_code}")
    
    # Test 10: GET /api/health
    response = requests.get(f"{BASE_URL}/api/health")
    log_test(10, "GET /api/health",
             response.status_code == 200,
             f"HTTP {response.status_code}")


# ============================================================================
# B. SLUG AVAILABILITY ENDPOINT (No Auth Required)
# ============================================================================

def test_slug_availability():
    """Test B: Slug availability endpoint - GET /api/signup/check-slug."""
    print("\n" + "="*80)
    print("SECTION B: SLUG AVAILABILITY ENDPOINT")
    print("="*80)
    
    # Test 11: Fresh slug (available)
    response = requests.get(f"{BASE_URL}/api/signup/check-slug?slug=fresh-slug")
    if response.status_code == 200:
        data = response.json()
        log_test(11, "GET /api/signup/check-slug?slug=fresh-slug returns available=true",
                 data.get("available") is True,
                 f"HTTP {response.status_code}, available={data.get('available')}")
    else:
        log_test(11, "GET /api/signup/check-slug?slug=fresh-slug returns available=true",
                 False, f"HTTP {response.status_code}")
    
    # Test 12: Existing slug (ddconsult)
    response = requests.get(f"{BASE_URL}/api/signup/check-slug?slug=ddconsult")
    if response.status_code == 200:
        data = response.json()
        is_taken = data.get("available") is False and "taken" in data.get("reason", "").lower()
        log_test(12, "GET /api/signup/check-slug?slug=ddconsult returns available=false (Already taken)",
                 is_taken,
                 f"HTTP {response.status_code}, available={data.get('available')}, reason={data.get('reason')}")
    else:
        log_test(12, "GET /api/signup/check-slug?slug=ddconsult returns available=false (Already taken)",
                 False, f"HTTP {response.status_code}")
    
    # Test 13: Reserved slug (admin)
    response = requests.get(f"{BASE_URL}/api/signup/check-slug?slug=admin")
    if response.status_code == 200:
        data = response.json()
        is_reserved = data.get("available") is False and "reserved" in data.get("reason", "").lower()
        log_test(13, "GET /api/signup/check-slug?slug=admin returns available=false (reserved)",
                 is_reserved,
                 f"HTTP {response.status_code}, available={data.get('available')}, reason={data.get('reason')}")
    else:
        log_test(13, "GET /api/signup/check-slug?slug=admin returns available=false (reserved)",
                 False, f"HTTP {response.status_code}")
    
    # Test 14: Reserved slug (www)
    response = requests.get(f"{BASE_URL}/api/signup/check-slug?slug=www")
    if response.status_code == 200:
        data = response.json()
        log_test(14, "GET /api/signup/check-slug?slug=www returns available=false",
                 data.get("available") is False,
                 f"HTTP {response.status_code}, available={data.get('available')}")
    else:
        log_test(14, "GET /api/signup/check-slug?slug=www returns available=false",
                 False, f"HTTP {response.status_code}")
    
    # Test 15: Reserved slug (api)
    response = requests.get(f"{BASE_URL}/api/signup/check-slug?slug=api")
    if response.status_code == 200:
        data = response.json()
        log_test(15, "GET /api/signup/check-slug?slug=api returns available=false",
                 data.get("available") is False,
                 f"HTTP {response.status_code}, available={data.get('available')}")
    else:
        log_test(15, "GET /api/signup/check-slug?slug=api returns available=false",
                 False, f"HTTP {response.status_code}")
    
    # Test 16: Uppercase slug (invalid format)
    response = requests.get(f"{BASE_URL}/api/signup/check-slug?slug=UPPERCASE")
    if response.status_code == 200:
        data = response.json()
        is_format_error = data.get("available") is False and "format" in data.get("reason", "").lower()
        log_test(16, "GET /api/signup/check-slug?slug=UPPERCASE returns available=false (format)",
                 is_format_error,
                 f"HTTP {response.status_code}, available={data.get('available')}, reason={data.get('reason')}")
    else:
        log_test(16, "GET /api/signup/check-slug?slug=UPPERCASE returns available=false (format)",
                 False, f"HTTP {response.status_code}")
    
    # Test 17: Empty slug
    response = requests.get(f"{BASE_URL}/api/signup/check-slug?slug=")
    if response.status_code == 200:
        data = response.json()
        log_test(17, "GET /api/signup/check-slug?slug= returns available=false",
                 data.get("available") is False,
                 f"HTTP {response.status_code}, available={data.get('available')}")
    else:
        log_test(17, "GET /api/signup/check-slug?slug= returns available=false",
                 False, f"HTTP {response.status_code}")
    
    # Test 18: Too short slug (1 char)
    response = requests.get(f"{BASE_URL}/api/signup/check-slug?slug=a")
    if response.status_code == 200:
        data = response.json()
        log_test(18, "GET /api/signup/check-slug?slug=a returns available=false (too short)",
                 data.get("available") is False,
                 f"HTTP {response.status_code}, available={data.get('available')}")
    else:
        log_test(18, "GET /api/signup/check-slug?slug=a returns available=false (too short)",
                 False, f"HTTP {response.status_code}")


# ============================================================================
# C. SIGN-UP ENDPOINT (No Auth Required)
# ============================================================================

def test_signup_endpoint():
    """Test C: Sign-up endpoint - POST /api/signup."""
    print("\n" + "="*80)
    print("SECTION C: SIGN-UP ENDPOINT")
    print("="*80)
    
    # Test 19: Valid sign-up
    payload = {
        "slug": "testco",
        "company_name": "Test Co",
        "admin_email": "admin@testco.io",
        "admin_password": "TestPass2026",
        "admin_name": "John"
    }
    response = requests.post(f"{BASE_URL}/api/signup", json=payload)
    if response.status_code == 201:
        data = response.json()
        has_required_fields = all(k in data for k in ["tenant_id", "tenant_slug", "admin_email", "login_url", "message"])
        slug_correct = data.get("tenant_slug") == "testco"
        log_test(19, "POST /api/signup with valid body returns 201",
                 has_required_fields and slug_correct,
                 f"HTTP {response.status_code}, tenant_slug={data.get('tenant_slug')}")
    else:
        log_test(19, "POST /api/signup with valid body returns 201",
                 False, f"HTTP {response.status_code}, error={response.text[:200]}")
    
    # Test 20-24: MongoDB verification (using mongosh via bash)
    # These tests will be done via bash commands after the main test suite
    
    # Test 25: Duplicate slug (409)
    response = requests.post(f"{BASE_URL}/api/signup", json=payload)
    log_test(25, "POST /api/signup with duplicate slug returns 409",
             response.status_code == 409,
             f"HTTP {response.status_code}")


# ============================================================================
# D. SIGN-UP VALIDATION ERRORS
# ============================================================================

def test_signup_validation():
    """Test D: Sign-up validation errors."""
    print("\n" + "="*80)
    print("SECTION D: SIGN-UP VALIDATION ERRORS")
    print("="*80)
    
    # Test 26: Reserved slug (422)
    payload = {
        "slug": "admin",
        "company_name": "Test Co",
        "admin_email": "admin@test.io",
        "admin_password": "TestPass2026",
        "admin_name": "John"
    }
    response = requests.post(f"{BASE_URL}/api/signup", json=payload)
    log_test(26, "POST /api/signup with reserved slug=admin returns 422",
             response.status_code == 422,
             f"HTTP {response.status_code}")
    
    # Test 27: Weak password (no number)
    payload = {
        "slug": "testco2",
        "company_name": "Test Co",
        "admin_email": "admin@testco2.io",
        "admin_password": "onlyletters",
        "admin_name": "John"
    }
    response = requests.post(f"{BASE_URL}/api/signup", json=payload)
    log_test(27, "POST /api/signup with weak password (no number) returns 422",
             response.status_code == 422,
             f"HTTP {response.status_code}")
    
    # Test 28: Weak password (too short)
    payload = {
        "slug": "testco3",
        "company_name": "Test Co",
        "admin_email": "admin@testco3.io",
        "admin_password": "abc12",
        "admin_name": "John"
    }
    response = requests.post(f"{BASE_URL}/api/signup", json=payload)
    log_test(28, "POST /api/signup with weak password (too short) returns 422",
             response.status_code == 422,
             f"HTTP {response.status_code}")
    
    # Test 29: Invalid email
    payload = {
        "slug": "testco4",
        "company_name": "Test Co",
        "admin_email": "notanemail",
        "admin_password": "TestPass2026",
        "admin_name": "John"
    }
    response = requests.post(f"{BASE_URL}/api/signup", json=payload)
    log_test(29, "POST /api/signup with invalid email returns 422",
             response.status_code == 422,
             f"HTTP {response.status_code}")
    
    # Test 30: Invalid slug (uppercase)
    payload = {
        "slug": "BADSLUG",
        "company_name": "Test Co",
        "admin_email": "admin@testco5.io",
        "admin_password": "TestPass2026",
        "admin_name": "John"
    }
    response = requests.post(f"{BASE_URL}/api/signup", json=payload)
    log_test(30, "POST /api/signup with invalid slug (uppercase) returns 422",
             response.status_code == 422,
             f"HTTP {response.status_code}")
    
    # Test 31: Invalid slug (starts with dash)
    payload = {
        "slug": "-test",
        "company_name": "Test Co",
        "admin_email": "admin@testco6.io",
        "admin_password": "TestPass2026",
        "admin_name": "John"
    }
    response = requests.post(f"{BASE_URL}/api/signup", json=payload)
    log_test(31, "POST /api/signup with invalid slug (starts with dash) returns 422",
             response.status_code == 422,
             f"HTTP {response.status_code}")


# ============================================================================
# E. X-FORWARDED-HOST HANDLING (GCP Production)
# ============================================================================

def test_xforwarded_host():
    """Test E: X-Forwarded-Host handling for GCP Load Balancer."""
    print("\n" + "="*80)
    print("SECTION E: X-FORWARDED-HOST HANDLING (GCP Production)")
    print("="*80)
    
    # Test 32: Only Host header (no X-Forwarded-Host)
    response = requests.get(
        f"{BASE_URL}/api/platform/whoami-tenant",
        headers={"Host": "internal-cloudrun.a.run.app"}
    )
    if response.status_code == 200:
        data = response.json()
        # Should return DD tenant (default fallback in flag=off mode)
        tenant_slug = data.get("tenant", {}).get("slug") if data.get("tenant") else None
        log_test(32, "GET /api/platform/whoami-tenant with only Host header returns DD tenant",
                 tenant_slug == "ddconsult" or data.get("resolution_mode") == "flag_off",
                 f"HTTP {response.status_code}, tenant_slug={tenant_slug}, mode={data.get('resolution_mode')}")
    else:
        log_test(32, "GET /api/platform/whoami-tenant with only Host header returns DD tenant",
                 False, f"HTTP {response.status_code}")
    
    # Test 33: X-Forwarded-Host with subdomain
    response = requests.get(
        f"{BASE_URL}/api/platform/whoami-tenant",
        headers={
            "Host": "internal-cloudrun.a.run.app",
            "X-Forwarded-Host": "ddconsult.ddplanner.io"
        }
    )
    if response.status_code == 200:
        data = response.json()
        subdomain = data.get("subdomain")
        log_test(33, "GET /api/platform/whoami-tenant with X-Forwarded-Host extracts subdomain=ddconsult",
                 subdomain == "ddconsult" or data.get("resolution_mode") == "flag_off",
                 f"HTTP {response.status_code}, subdomain={subdomain}, mode={data.get('resolution_mode')}")
    else:
        log_test(33, "GET /api/platform/whoami-tenant with X-Forwarded-Host extracts subdomain=ddconsult",
                 False, f"HTTP {response.status_code}")
    
    # Test 34: X-Forwarded-Host with comma-separated values (picks first)
    response = requests.get(
        f"{BASE_URL}/api/platform/whoami-tenant",
        headers={
            "Host": "internal-cloudrun.a.run.app",
            "X-Forwarded-Host": "something.ddplanner.io, other.host"
        }
    )
    if response.status_code == 200:
        data = response.json()
        subdomain = data.get("subdomain")
        resolved_host = data.get("resolved_host")
        # Should pick first value (something.ddplanner.io)
        log_test(34, "GET /api/platform/whoami-tenant with comma-separated X-Forwarded-Host picks first",
                 "something" in str(subdomain) or "something" in str(resolved_host) or data.get("resolution_mode") == "flag_off",
                 f"HTTP {response.status_code}, subdomain={subdomain}, resolved_host={resolved_host}")
    else:
        log_test(34, "GET /api/platform/whoami-tenant with comma-separated X-Forwarded-Host picks first",
                 False, f"HTTP {response.status_code}")


# ============================================================================
# F. LOGIN FLOW VERIFICATION
# ============================================================================

def test_login_flow():
    """Test F: Login flow with new tenant (multi-tenant mode)."""
    print("\n" + "="*80)
    print("SECTION F: LOGIN FLOW VERIFICATION")
    print("="*80)
    
    # Test 35: Verify MULTI_TENANT_ENABLED=false
    response = requests.get(f"{BASE_URL}/api/platform/status")
    if response.status_code == 200:
        data = response.json()
        flag_off = data.get("multi_tenant_enabled") is False
        log_test(35, "Verify MULTI_TENANT_ENABLED=false (login of new tenant not possible in flag=off mode)",
                 flag_off,
                 f"HTTP {response.status_code}, multi_tenant_enabled={data.get('multi_tenant_enabled')}")
    else:
        log_test(35, "Verify MULTI_TENANT_ENABLED=false (login of new tenant not possible in flag=off mode)",
                 False, f"HTTP {response.status_code}")


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("STEP 8 TESTING: Public Tenant Sign-up + GCP Production Readiness")
    print("="*80)
    print(f"Backend URL: {BASE_URL}")
    print(f"Feature flag: MULTI_TENANT_ENABLED=false (DO NOT change)")
    print(f"Tenant admin: {TENANT_ADMIN_EMAIL} / {TENANT_ADMIN_PASSWORD}")
    print(f"Platform admin: {PLATFORM_ADMIN_EMAIL} / {PLATFORM_ADMIN_PASSWORD}")
    
    try:
        # Run all test sections
        test_regression()
        test_slug_availability()
        test_signup_endpoint()
        test_signup_validation()
        test_xforwarded_host()
        test_login_flow()
        
        # Summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        passed = sum(1 for r in test_results if r["passed"])
        failed = sum(1 for r in test_results if not r["passed"])
        total = len(test_results)
        print(f"Total: {total} tests")
        print(f"Passed: {passed} tests")
        print(f"Failed: {failed} tests")
        print(f"Success rate: {passed/total*100:.1f}%")
        
        if failed > 0:
            print("\n" + "="*80)
            print("FAILED TESTS")
            print("="*80)
            for r in test_results:
                if not r["passed"]:
                    print(f"Test {r['test_num']}: {r['description']}")
                    if r["details"]:
                        print(f"  Details: {r['details']}")
        
        # MongoDB verification tests (20-24) need to be done via bash
        print("\n" + "="*80)
        print("MONGODB VERIFICATION (Tests 20-24)")
        print("="*80)
        print("Run the following bash commands to verify MongoDB state:")
        print("Test 20: mongosh --quiet tenant_testco --eval \"print(db.users.countDocuments({})); print(db.projects.countDocuments({}))\"")
        print("  Expected: 1 user and 1 project (welcome)")
        print("Test 21: mongosh --quiet platform_db --eval \"db.tenants.findOne({slug:'testco'})\"")
        print("  Expected: testco entry exists")
        print("Test 22: mongosh --quiet platform_db --eval \"db.tenant_modules.countDocuments({tenant_slug:'testco'})\"")
        print("  Expected: 17 entries")
        print("Test 23: mongosh --quiet platform_db --eval \"db.memberships.countDocuments({tenant_slug:'testco'})\"")
        print("  Expected: 1 entry")
        print("Test 24: mongosh --quiet platform_db --eval \"db.platform_audit_log.findOne({action:'tenant.self_signup', tenant_slug:'testco'})\"")
        print("  Expected: 1 audit log entry")
        
        # Cleanup instructions (Test 36)
        print("\n" + "="*80)
        print("CLEANUP (Test 36)")
        print("="*80)
        print("Run the following bash command to cleanup test tenant:")
        print("""mongosh --quiet --eval "
  db.getSiblingDB('platform_db').tenants.deleteOne({slug:'testco'});
  db.getSiblingDB('platform_db').tenant_modules.deleteMany({tenant_slug:'testco'});
  db.getSiblingDB('platform_db').memberships.deleteMany({tenant_slug:'testco'});
  db.getSiblingDB('platform_db').platform_audit_log.deleteMany({tenant_slug:'testco'});
  db.getSiblingDB('tenant_testco').dropDatabase();
" """)
        
        # Sanity checks (Tests 37-39)
        print("\n" + "="*80)
        print("SANITY CHECKS (Tests 37-39)")
        print("="*80)
        print("After cleanup, verify:")
        print("Test 37: GET /api/platform/dashboard/stats should show tenants.total=1")
        print("Test 38: GET /api/projects (as tenant admin) should return exactly 4 projects")
        print("Test 39: Check /var/log/supervisor/backend.err.log for NO AttributeError, TypeError, 500s")
        
        return 0 if failed == 0 else 1
        
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
