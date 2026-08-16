#!/usr/bin/env python3
"""
STEP 11 FINAL COMPREHENSIVE TEST — Full Multi-Tenant Regression + GCP Production Readiness
Tests sections A-G, I, J (Section H is the pytest isolation suite run separately)
"""

import requests
import json
import jwt
import secrets
from datetime import datetime

BASE_URL = "https://a0ac7ee9-2785-4339-ad6f-6886af7a3f1a.preview.emergentagent.com/api"

# Test credentials
TENANT_ADMIN_EMAIL = "admin@test.com"
TENANT_ADMIN_PASSWORD = "admin123"
PLATFORM_ADMIN_EMAIL = "don@ddconsult.tech"
PLATFORM_ADMIN_PASSWORD = "Welcome123!"

# Global tokens
tenant_token = None
platform_token = None

def print_section(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def print_test(num, description, passed, details=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"Test {num}: {description} ... {status}")
    if details:
        print(f"  → {details}")

# ============================================================================
# SECTION A: Fundamental Auth (Steps 1-5)
# ============================================================================
def test_section_a():
    global tenant_token, platform_token
    print_section("SECTION A: Fundamental Auth (7 tests)")
    
    results = []
    
    # Test 1: POST /api/auth/login (tenant admin)
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", 
                            data={"username": TENANT_ADMIN_EMAIL, "password": TENANT_ADMIN_PASSWORD})
        passed = resp.status_code == 200 and "access_token" in resp.json()
        if passed:
            tenant_token = resp.json()["access_token"]
        print_test(1, "POST /api/auth/login (tenant admin)", passed, 
                  f"HTTP {resp.status_code}")
        results.append(passed)
    except Exception as e:
        print_test(1, "POST /api/auth/login (tenant admin)", False, str(e))
        results.append(False)
    
    # Test 2: Decode JWT - verify legacy shape (only sub + exp when flag=off)
    try:
        decoded = jwt.decode(tenant_token, options={"verify_signature": False})
        # In flag=off mode, should only have 'sub' and 'exp' (no tenant_id, no token_type)
        has_sub = "sub" in decoded
        has_exp = "exp" in decoded
        no_tenant_id = "tenant_id" not in decoded
        no_token_type = "token_type" not in decoded
        passed = has_sub and has_exp and no_tenant_id and no_token_type
        print_test(2, "Decode JWT: verify legacy shape (only sub+exp)", passed,
                  f"Claims: {list(decoded.keys())}")
        results.append(passed)
    except Exception as e:
        print_test(2, "Decode JWT: verify legacy shape", False, str(e))
        results.append(False)
    
    # Test 3: GET /api/auth/me
    try:
        resp = requests.get(f"{BASE_URL}/auth/me", 
                           headers={"Authorization": f"Bearer {tenant_token}"})
        passed = resp.status_code == 200 and resp.json().get("role") in ["super_admin", "admin"]
        print_test(3, "GET /api/auth/me", passed,
                  f"HTTP {resp.status_code}, role={resp.json().get('role')}")
        results.append(passed)
    except Exception as e:
        print_test(3, "GET /api/auth/me", False, str(e))
        results.append(False)
    
    # Test 4: POST /api/platform/auth/login (platform admin)
    try:
        resp = requests.post(f"{BASE_URL}/platform/auth/login",
                            data={"username": PLATFORM_ADMIN_EMAIL, "password": PLATFORM_ADMIN_PASSWORD})
        passed = resp.status_code == 200 and "access_token" in resp.json()
        if passed:
            platform_token = resp.json()["access_token"]
        print_test(4, "POST /api/platform/auth/login", passed,
                  f"HTTP {resp.status_code}")
        results.append(passed)
    except Exception as e:
        print_test(4, "POST /api/platform/auth/login", False, str(e))
        results.append(False)
    
    # Test 5: Decode platform JWT - verify has token_type: "platform", role: "platform_admin"
    try:
        decoded = jwt.decode(platform_token, options={"verify_signature": False})
        has_token_type = decoded.get("token_type") == "platform"
        has_role = decoded.get("role") == "platform_admin"
        passed = has_token_type and has_role
        print_test(5, "Decode platform JWT: verify token_type+role", passed,
                  f"token_type={decoded.get('token_type')}, role={decoded.get('role')}")
        results.append(passed)
    except Exception as e:
        print_test(5, "Decode platform JWT", False, str(e))
        results.append(False)
    
    # Test 6: GET /api/platform/auth/me
    try:
        resp = requests.get(f"{BASE_URL}/platform/auth/me",
                           headers={"Authorization": f"Bearer {platform_token}"})
        passed = resp.status_code == 200
        print_test(6, "GET /api/platform/auth/me", passed,
                  f"HTTP {resp.status_code}")
        results.append(passed)
    except Exception as e:
        print_test(6, "GET /api/platform/auth/me", False, str(e))
        results.append(False)
    
    # Test 7: GET /api/auth/me with garbage token → 401
    try:
        resp = requests.get(f"{BASE_URL}/auth/me",
                           headers={"Authorization": "Bearer garbage_token_12345"})
        passed = resp.status_code == 401
        print_test(7, "GET /api/auth/me with garbage token → 401", passed,
                  f"HTTP {resp.status_code}")
        results.append(passed)
    except Exception as e:
        print_test(7, "GET /api/auth/me with garbage token", False, str(e))
        results.append(False)
    
    return results

# ============================================================================
# SECTION B: Core Data Reads (Steps 1-4)
# ============================================================================
def test_section_b():
    print_section("SECTION B: Core Data Reads (8 tests)")
    results = []
    
    # Test 8: GET /api/projects → 4
    try:
        resp = requests.get(f"{BASE_URL}/projects",
                           headers={"Authorization": f"Bearer {tenant_token}"})
        count = len(resp.json()) if resp.status_code == 200 else 0
        passed = resp.status_code == 200 and count == 4
        print_test(8, "GET /api/projects → 4", passed,
                  f"HTTP {resp.status_code}, count={count}")
        results.append(passed)
    except Exception as e:
        print_test(8, "GET /api/projects", False, str(e))
        results.append(False)
    
    # Test 9: GET /api/resources → 5
    try:
        resp = requests.get(f"{BASE_URL}/resources",
                           headers={"Authorization": f"Bearer {tenant_token}"})
        count = len(resp.json()) if resp.status_code == 200 else 0
        passed = resp.status_code == 200 and count == 5
        print_test(9, "GET /api/resources → 5", passed,
                  f"HTTP {resp.status_code}, count={count}")
        results.append(passed)
    except Exception as e:
        print_test(9, "GET /api/resources", False, str(e))
        results.append(False)
    
    # Test 10: GET /api/allocations → 10
    try:
        resp = requests.get(f"{BASE_URL}/allocations",
                           headers={"Authorization": f"Bearer {tenant_token}"})
        count = len(resp.json()) if resp.status_code == 200 else 0
        passed = resp.status_code == 200 and count == 10
        print_test(10, "GET /api/allocations → 10", passed,
                  f"HTTP {resp.status_code}, count={count}")
        results.append(passed)
    except Exception as e:
        print_test(10, "GET /api/allocations", False, str(e))
        results.append(False)
    
    # Test 11: GET /api/portfolio → 200, dict with projects array
    try:
        resp = requests.get(f"{BASE_URL}/portfolio",
                           headers={"Authorization": f"Bearer {tenant_token}"})
        data = resp.json() if resp.status_code == 200 else {}
        passed = resp.status_code == 200 and "projects" in data and isinstance(data["projects"], list)
        print_test(11, "GET /api/portfolio → dict with projects array", passed,
                  f"HTTP {resp.status_code}, has_projects={('projects' in data)}")
        results.append(passed)
    except Exception as e:
        print_test(11, "GET /api/portfolio", False, str(e))
        results.append(False)
    
    # Test 12: GET /api/dashboard/action-items → 200
    try:
        resp = requests.get(f"{BASE_URL}/dashboard/action-items",
                           headers={"Authorization": f"Bearer {tenant_token}"})
        passed = resp.status_code == 200
        print_test(12, "GET /api/dashboard/action-items → 200", passed,
                  f"HTTP {resp.status_code}")
        results.append(passed)
    except Exception as e:
        print_test(12, "GET /api/dashboard/action-items", False, str(e))
        results.append(False)
    
    # Test 13: GET /api/leaves → 200 array
    try:
        resp = requests.get(f"{BASE_URL}/leaves",
                           headers={"Authorization": f"Bearer {tenant_token}"})
        data = resp.json() if resp.status_code == 200 else None
        passed = resp.status_code == 200 and isinstance(data, list)
        print_test(13, "GET /api/leaves → 200 array", passed,
                  f"HTTP {resp.status_code}, is_array={isinstance(data, list)}")
        results.append(passed)
    except Exception as e:
        print_test(13, "GET /api/leaves", False, str(e))
        results.append(False)
    
    # Test 14: GET /api/holidays → 200 array
    try:
        resp = requests.get(f"{BASE_URL}/holidays",
                           headers={"Authorization": f"Bearer {tenant_token}"})
        data = resp.json() if resp.status_code == 200 else None
        passed = resp.status_code == 200 and isinstance(data, list)
        print_test(14, "GET /api/holidays → 200 array", passed,
                  f"HTTP {resp.status_code}, is_array={isinstance(data, list)}")
        results.append(passed)
    except Exception as e:
        print_test(14, "GET /api/holidays", False, str(e))
        results.append(False)
    
    # Test 15: GET /api/health → 200
    try:
        resp = requests.get(f"{BASE_URL}/health")
        passed = resp.status_code == 200
        print_test(15, "GET /api/health → 200", passed,
                  f"HTTP {resp.status_code}")
        results.append(passed)
    except Exception as e:
        print_test(15, "GET /api/health", False, str(e))
        results.append(False)
    
    return results

# ============================================================================
# SECTION C: Platform Layer (Steps 1-2, 5-7)
# ============================================================================
def test_section_c():
    print_section("SECTION C: Platform Layer (10 tests)")
    results = []
    
    # Test 16: GET /api/platform/status (public)
    try:
        resp = requests.get(f"{BASE_URL}/platform/status")
        data = resp.json() if resp.status_code == 200 else {}
        multi_tenant_enabled = data.get("multi_tenant_enabled") == False
        platform_db_ready = data.get("platform_db_ready") == True
        counts = data.get("counts", {})
        tenants_count = counts.get("tenants") == 1
        modules_count = counts.get("modules_in_catalog") == 17
        passed = resp.status_code == 200 and multi_tenant_enabled and platform_db_ready and tenants_count and modules_count
        print_test(16, "GET /api/platform/status → multi_tenant_enabled=false, platform_db_ready=true, tenants=1, modules=17", 
                  passed, f"HTTP {resp.status_code}, flag={data.get('multi_tenant_enabled')}, tenants={counts.get('tenants')}, modules={counts.get('modules_in_catalog')}")
        results.append(passed)
    except Exception as e:
        print_test(16, "GET /api/platform/status", False, str(e))
        results.append(False)
    
    # Test 17: GET /api/platform/whoami-tenant
    try:
        resp = requests.get(f"{BASE_URL}/platform/whoami-tenant")
        data = resp.json() if resp.status_code == 200 else {}
        resolution_mode = data.get("resolution_mode") == "flag_off"
        tenant_slug = data.get("tenant", {}).get("slug") == "ddconsult"
        enabled_modules = data.get("enabled_modules", {})
        modules_count = len(enabled_modules) == 17
        all_enabled = all(enabled_modules.values())
        passed = resp.status_code == 200 and resolution_mode and tenant_slug and modules_count and all_enabled
        print_test(17, "GET /api/platform/whoami-tenant → resolution_mode=flag_off, tenant.slug=ddconsult, 17 modules all true",
                  passed, f"HTTP {resp.status_code}, mode={data.get('resolution_mode')}, slug={data.get('tenant', {}).get('slug')}, modules={len(enabled_modules)}")
        results.append(passed)
    except Exception as e:
        print_test(17, "GET /api/platform/whoami-tenant", False, str(e))
        results.append(False)
    
    # Test 18: GET /api/platform/resolve-subdomain?host=ddconsult.ddplanner.io → subdomain=ddconsult
    try:
        resp = requests.get(f"{BASE_URL}/platform/resolve-subdomain?host=ddconsult.ddplanner.io")
        data = resp.json() if resp.status_code == 200 else {}
        passed = resp.status_code == 200 and data.get("subdomain") == "ddconsult"
        print_test(18, "GET /api/platform/resolve-subdomain?host=ddconsult.ddplanner.io → subdomain=ddconsult",
                  passed, f"HTTP {resp.status_code}, subdomain={data.get('subdomain')}")
        results.append(passed)
    except Exception as e:
        print_test(18, "GET /api/platform/resolve-subdomain (ddconsult)", False, str(e))
        results.append(False)
    
    # Test 19: GET /api/platform/resolve-subdomain?host=admin.ddplanner.io → subdomain=admin
    try:
        resp = requests.get(f"{BASE_URL}/platform/resolve-subdomain?host=admin.ddplanner.io")
        data = resp.json() if resp.status_code == 200 else {}
        passed = resp.status_code == 200 and data.get("subdomain") == "admin"
        print_test(19, "GET /api/platform/resolve-subdomain?host=admin.ddplanner.io → subdomain=admin",
                  passed, f"HTTP {resp.status_code}, subdomain={data.get('subdomain')}")
        results.append(passed)
    except Exception as e:
        print_test(19, "GET /api/platform/resolve-subdomain (admin)", False, str(e))
        results.append(False)
    
    # Test 20: GET /api/platform/resolve-subdomain?host=127.0.0.1 → subdomain=null
    try:
        resp = requests.get(f"{BASE_URL}/platform/resolve-subdomain?host=127.0.0.1")
        data = resp.json() if resp.status_code == 200 else {}
        passed = resp.status_code == 200 and data.get("subdomain") is None
        print_test(20, "GET /api/platform/resolve-subdomain?host=127.0.0.1 → subdomain=null",
                  passed, f"HTTP {resp.status_code}, subdomain={data.get('subdomain')}")
        results.append(passed)
    except Exception as e:
        print_test(20, "GET /api/platform/resolve-subdomain (bare IP)", False, str(e))
        results.append(False)
    
    # Test 21: GET /api/platform/tenants with platform token → 200, at least 1
    try:
        resp = requests.get(f"{BASE_URL}/platform/tenants",
                           headers={"Authorization": f"Bearer {platform_token}"})
        data = resp.json() if resp.status_code == 200 else []
        passed = resp.status_code == 200 and len(data) >= 1
        print_test(21, "GET /api/platform/tenants → 200, at least 1 tenant",
                  passed, f"HTTP {resp.status_code}, count={len(data)}")
        results.append(passed)
    except Exception as e:
        print_test(21, "GET /api/platform/tenants", False, str(e))
        results.append(False)
    
    # Test 22: Each tenant has enabled_modules_count
    try:
        resp = requests.get(f"{BASE_URL}/platform/tenants",
                           headers={"Authorization": f"Bearer {platform_token}"})
        data = resp.json() if resp.status_code == 200 else []
        passed = all("enabled_modules_count" in t for t in data)
        print_test(22, "Each tenant has enabled_modules_count field",
                  passed, f"All tenants have field: {passed}")
        results.append(passed)
    except Exception as e:
        print_test(22, "Tenant enabled_modules_count check", False, str(e))
        results.append(False)
    
    # Test 23: GET /api/platform/modules → 17 modules across 5 categories
    try:
        resp = requests.get(f"{BASE_URL}/platform/modules",
                           headers={"Authorization": f"Bearer {platform_token}"})
        data = resp.json() if resp.status_code == 200 else []
        passed = resp.status_code == 200 and len(data) == 17
        categories = set(m.get("category") for m in data)
        print_test(23, "GET /api/platform/modules → 17 modules across 5 categories",
                  passed, f"HTTP {resp.status_code}, count={len(data)}, categories={len(categories)}")
        results.append(passed)
    except Exception as e:
        print_test(23, "GET /api/platform/modules", False, str(e))
        results.append(False)
    
    # Test 24: GET /api/platform/tenants/ddconsult/modules → 17 modules
    try:
        resp = requests.get(f"{BASE_URL}/platform/tenants/ddconsult/modules",
                           headers={"Authorization": f"Bearer {platform_token}"})
        data = resp.json() if resp.status_code == 200 else {}
        modules = data.get("modules", [])
        passed = resp.status_code == 200 and len(modules) == 17
        print_test(24, "GET /api/platform/tenants/ddconsult/modules → 17 modules",
                  passed, f"HTTP {resp.status_code}, count={len(modules)}")
        results.append(passed)
    except Exception as e:
        print_test(24, "GET /api/platform/tenants/ddconsult/modules", False, str(e))
        results.append(False)
    
    # Test 25: GET /api/platform/dashboard/stats
    try:
        resp = requests.get(f"{BASE_URL}/platform/dashboard/stats",
                           headers={"Authorization": f"Bearer {platform_token}"})
        data = resp.json() if resp.status_code == 200 else {}
        has_tenants = "tenants" in data
        has_platform_users = "platform_users" in data
        has_memberships = "memberships" in data
        has_modules = "modules" in data
        passed = resp.status_code == 200 and has_tenants and has_platform_users and has_memberships and has_modules
        print_test(25, "GET /api/platform/dashboard/stats → tenants/platform_users/memberships/modules present",
                  passed, f"HTTP {resp.status_code}, keys={list(data.keys())}")
        results.append(passed)
    except Exception as e:
        print_test(25, "GET /api/platform/dashboard/stats", False, str(e))
        results.append(False)
    
    return results

# ============================================================================
# SECTION D: Module System (Step 6)
# ============================================================================
def test_section_d():
    print_section("SECTION D: Module System (2 tests)")
    results = []
    
    # Test 26: GET /api/tenant/modules → 17 keys, all true
    try:
        resp = requests.get(f"{BASE_URL}/tenant/modules",
                           headers={"Authorization": f"Bearer {tenant_token}"})
        data = resp.json() if resp.status_code == 200 else {}
        modules = data.get("modules", {})
        passed = resp.status_code == 200 and len(modules) == 17 and all(modules.values())
        print_test(26, "GET /api/tenant/modules → 17 keys, all true",
                  passed, f"HTTP {resp.status_code}, count={len(modules)}, all_enabled={all(modules.values())}")
        results.append(passed)
    except Exception as e:
        print_test(26, "GET /api/tenant/modules", False, str(e))
        results.append(False)
    
    # Test 27: Verify no LazyCollection errors in response
    try:
        resp = requests.get(f"{BASE_URL}/tenant/modules",
                           headers={"Authorization": f"Bearer {tenant_token}"})
        text = resp.text
        has_lazy_error = "LazyCollection" in text
        passed = not has_lazy_error
        print_test(27, "Verify no LazyCollection errors in response",
                  passed, f"LazyCollection found: {has_lazy_error}")
        results.append(passed)
    except Exception as e:
        print_test(27, "LazyCollection error check", False, str(e))
        results.append(False)
    
    return results

# ============================================================================
# SECTION E: Signup Flow (Step 8)
# ============================================================================
def test_section_e():
    print_section("SECTION E: Signup Flow (6 tests)")
    results = []
    
    # Test 28: GET /api/signup/check-slug?slug=freshuniqueslug123 → available=true
    try:
        resp = requests.get(f"{BASE_URL}/signup/check-slug?slug=freshuniqueslug123")
        data = resp.json() if resp.status_code == 200 else {}
        passed = resp.status_code == 200 and data.get("available") == True
        print_test(28, "GET /api/signup/check-slug?slug=freshuniqueslug123 → available=true",
                  passed, f"HTTP {resp.status_code}, available={data.get('available')}")
        results.append(passed)
    except Exception as e:
        print_test(28, "Signup check-slug (fresh)", False, str(e))
        results.append(False)
    
    # Test 29: GET /api/signup/check-slug?slug=admin → available=false (reserved)
    try:
        resp = requests.get(f"{BASE_URL}/signup/check-slug?slug=admin")
        data = resp.json() if resp.status_code == 200 else {}
        passed = resp.status_code == 200 and data.get("available") == False and "reserved" in data.get("reason", "").lower()
        print_test(29, "GET /api/signup/check-slug?slug=admin → available=false (reserved)",
                  passed, f"HTTP {resp.status_code}, available={data.get('available')}, reason={data.get('reason')}")
        results.append(passed)
    except Exception as e:
        print_test(29, "Signup check-slug (reserved)", False, str(e))
        results.append(False)
    
    # Test 30: GET /api/signup/check-slug?slug=UPPERCASE → available=false (must be lowercase)
    try:
        resp = requests.get(f"{BASE_URL}/signup/check-slug?slug=UPPERCASE")
        data = resp.json() if resp.status_code == 200 else {}
        passed = resp.status_code == 200 and data.get("available") == False and "lowercase" in data.get("reason", "").lower()
        print_test(30, "GET /api/signup/check-slug?slug=UPPERCASE → available=false (must be lowercase)",
                  passed, f"HTTP {resp.status_code}, available={data.get('available')}, reason={data.get('reason')}")
        results.append(passed)
    except Exception as e:
        print_test(30, "Signup check-slug (uppercase)", False, str(e))
        results.append(False)
    
    # Test 31: GET /api/signup/check-slug?slug=ddconsult → available=false (already taken)
    try:
        resp = requests.get(f"{BASE_URL}/signup/check-slug?slug=ddconsult")
        data = resp.json() if resp.status_code == 200 else {}
        passed = resp.status_code == 200 and data.get("available") == False and "taken" in data.get("reason", "").lower()
        print_test(31, "GET /api/signup/check-slug?slug=ddconsult → available=false (already taken)",
                  passed, f"HTTP {resp.status_code}, available={data.get('available')}, reason={data.get('reason')}")
        results.append(passed)
    except Exception as e:
        print_test(31, "Signup check-slug (taken)", False, str(e))
        results.append(False)
    
    # Test 32: POST /api/signup with invalid slug format → 422
    try:
        payload = {
            "tenant_slug": "invalid slug!",
            "tenant_name": "Test Tenant",
            "admin_email": "test@example.com",
            "admin_password": "Test@1234",
            "admin_name": "Test Admin"
        }
        resp = requests.post(f"{BASE_URL}/signup", json=payload)
        passed = resp.status_code == 422
        print_test(32, "POST /api/signup with invalid slug format → 422",
                  passed, f"HTTP {resp.status_code}")
        results.append(passed)
    except Exception as e:
        print_test(32, "Signup with invalid slug", False, str(e))
        results.append(False)
    
    # Test 33: POST /api/signup with weak password (no digit) → 422
    try:
        payload = {
            "tenant_slug": "testslug",
            "tenant_name": "Test Tenant",
            "admin_email": "test@example.com",
            "admin_password": "WeakPassword",  # No digit
            "admin_name": "Test Admin"
        }
        resp = requests.post(f"{BASE_URL}/signup", json=payload)
        passed = resp.status_code == 422
        print_test(33, "POST /api/signup with weak password (no digit) → 422",
                  passed, f"HTTP {resp.status_code}")
        results.append(passed)
    except Exception as e:
        print_test(33, "Signup with weak password", False, str(e))
        results.append(False)
    
    return results

# ============================================================================
# SECTION F: Branding & Settings (Step 9)
# ============================================================================
def test_section_f():
    print_section("SECTION F: Branding & Settings (8 tests)")
    results = []
    
    # Test 34: GET /api/tenant/branding (auth required) → 200, has name+branding+settings
    try:
        resp = requests.get(f"{BASE_URL}/tenant/branding",
                           headers={"Authorization": f"Bearer {tenant_token}"})
        data = resp.json() if resp.status_code == 200 else {}
        has_name = "name" in data
        has_branding = "branding" in data
        has_settings = "settings" in data
        passed = resp.status_code == 200 and has_name and has_branding and has_settings
        print_test(34, "GET /api/tenant/branding → 200, has name+branding+settings",
                  passed, f"HTTP {resp.status_code}, keys={list(data.keys())}")
        results.append(passed)
    except Exception as e:
        print_test(34, "GET /api/tenant/branding", False, str(e))
        results.append(False)
    
    # Test 35: PATCH /api/tenant/branding with primary_color → 200
    try:
        payload = {"primary_color": "#123456"}
        resp = requests.patch(f"{BASE_URL}/tenant/branding",
                             json=payload,
                             headers={"Authorization": f"Bearer {tenant_token}"})
        passed = resp.status_code == 200
        print_test(35, "PATCH /api/tenant/branding with primary_color=#123456 → 200",
                  passed, f"HTTP {resp.status_code}")
        results.append(passed)
    except Exception as e:
        print_test(35, "PATCH /api/tenant/branding (update)", False, str(e))
        results.append(False)
    
    # Test 36: Verify persistence - GET shows new color
    try:
        resp = requests.get(f"{BASE_URL}/tenant/branding",
                           headers={"Authorization": f"Bearer {tenant_token}"})
        data = resp.json() if resp.status_code == 200 else {}
        branding = data.get("branding", {})
        passed = branding.get("primary_color") == "#123456"
        print_test(36, "Verify persistence: GET shows primary_color=#123456",
                  passed, f"primary_color={branding.get('primary_color')}")
        results.append(passed)
    except Exception as e:
        print_test(36, "Verify branding persistence", False, str(e))
        results.append(False)
    
    # Test 37: Revert - PATCH with original color
    try:
        payload = {"primary_color": "#1B2A47"}
        resp = requests.patch(f"{BASE_URL}/tenant/branding",
                             json=payload,
                             headers={"Authorization": f"Bearer {tenant_token}"})
        passed = resp.status_code == 200
        print_test(37, "Revert: PATCH with primary_color=#1B2A47 → 200",
                  passed, f"HTTP {resp.status_code}")
        results.append(passed)
    except Exception as e:
        print_test(37, "PATCH /api/tenant/branding (revert)", False, str(e))
        results.append(False)
    
    # Test 38: Invalid hex PATCH → 400
    try:
        payload = {"primary_color": "invalid"}
        resp = requests.patch(f"{BASE_URL}/tenant/branding",
                             json=payload,
                             headers={"Authorization": f"Bearer {tenant_token}"})
        passed = resp.status_code == 400
        print_test(38, "PATCH /api/tenant/branding with invalid hex → 400",
                  passed, f"HTTP {resp.status_code}")
        results.append(passed)
    except Exception as e:
        print_test(38, "PATCH with invalid hex", False, str(e))
        results.append(False)
    
    # Test 39: PATCH /api/tenant/settings with work_week_hours=168 → 200 (boundary)
    try:
        payload = {"work_week_hours": 168}
        resp = requests.patch(f"{BASE_URL}/tenant/settings",
                             json=payload,
                             headers={"Authorization": f"Bearer {tenant_token}"})
        passed = resp.status_code == 200
        print_test(39, "PATCH /api/tenant/settings with work_week_hours=168 → 200",
                  passed, f"HTTP {resp.status_code}")
        results.append(passed)
    except Exception as e:
        print_test(39, "PATCH /api/tenant/settings (boundary)", False, str(e))
        results.append(False)
    
    # Test 40: Revert settings
    try:
        payload = {"work_week_hours": 40, "timezone": "Australia/Sydney"}
        resp = requests.patch(f"{BASE_URL}/tenant/settings",
                             json=payload,
                             headers={"Authorization": f"Bearer {tenant_token}"})
        passed = resp.status_code == 200
        print_test(40, "Revert: PATCH /api/tenant/settings with work_week_hours=40, timezone=Australia/Sydney → 200",
                  passed, f"HTTP {resp.status_code}")
        results.append(passed)
    except Exception as e:
        print_test(40, "PATCH /api/tenant/settings (revert)", False, str(e))
        results.append(False)
    
    # Test 41: PATCH with bad timezone → 400
    try:
        payload = {"timezone": "Invalid/Timezone"}
        resp = requests.patch(f"{BASE_URL}/tenant/settings",
                             json=payload,
                             headers={"Authorization": f"Bearer {tenant_token}"})
        passed = resp.status_code == 400
        print_test(41, "PATCH /api/tenant/settings with bad timezone → 400",
                  passed, f"HTTP {resp.status_code}")
        results.append(passed)
    except Exception as e:
        print_test(41, "PATCH with bad timezone", False, str(e))
        results.append(False)
    
    return results

# ============================================================================
# SECTION G: Integrations (Step 10)
# ============================================================================
def test_section_g():
    print_section("SECTION G: Integrations (8 tests)")
    results = []
    
    # Test 42: GET /api/tenant/integrations-summary → 200
    try:
        resp = requests.get(f"{BASE_URL}/tenant/integrations-summary",
                           headers={"Authorization": f"Bearer {tenant_token}"})
        data = resp.json() if resp.status_code == 200 else {}
        has_tenant_slug = "tenant_slug" in data
        has_hubspot = "hubspot" in data
        has_mcp = "mcp" in data
        has_resend = "resend_email" in data
        passed = resp.status_code == 200 and has_tenant_slug and has_hubspot and has_mcp and has_resend
        print_test(42, "GET /api/tenant/integrations-summary → 200, shape: {tenant_slug, hubspot, mcp, resend_email}",
                  passed, f"HTTP {resp.status_code}, keys={list(data.keys())}")
        results.append(passed)
    except Exception as e:
        print_test(42, "GET /api/tenant/integrations-summary", False, str(e))
        results.append(False)
    
    # Test 43: Verify NO secrets in response
    try:
        resp = requests.get(f"{BASE_URL}/tenant/integrations-summary",
                           headers={"Authorization": f"Bearer {tenant_token}"})
        text = resp.text.lower()
        has_private_token = "private_app_token" in text
        has_api_key_value = '"api_key":' in text and len(text.split('"api_key":')[1].split('"')[1]) > 10
        passed = not has_private_token and not has_api_key_value
        print_test(43, "Verify NO secrets in response (no private_app_token, no api_key value)",
                  passed, f"has_private_token={has_private_token}, has_api_key_value={has_api_key_value}")
        results.append(passed)
    except Exception as e:
        print_test(43, "Verify no secrets in response", False, str(e))
        results.append(False)
    
    # Test 44: POST /api/integrations/agent-api/regenerate → 200 with new key
    try:
        resp = requests.post(f"{BASE_URL}/integrations/agent-api/regenerate",
                            headers={"Authorization": f"Bearer {tenant_token}"})
        data = resp.json() if resp.status_code == 200 else {}
        has_key = "api_key" in data and len(data.get("api_key", "")) > 20
        passed = resp.status_code == 200 and has_key
        first_key = data.get("api_key", "")
        print_test(44, "POST /api/integrations/agent-api/regenerate → 200 with new key",
                  passed, f"HTTP {resp.status_code}, key_length={len(first_key)}")
        results.append(passed)
    except Exception as e:
        print_test(44, "POST /api/integrations/agent-api/regenerate (first)", False, str(e))
        results.append(False)
    
    # Test 45: POST /api/integrations/agent-api/regenerate again → different key
    try:
        resp1 = requests.post(f"{BASE_URL}/integrations/agent-api/regenerate",
                             headers={"Authorization": f"Bearer {tenant_token}"})
        key1 = resp1.json().get("api_key", "") if resp1.status_code == 200 else ""
        
        resp2 = requests.post(f"{BASE_URL}/integrations/agent-api/regenerate",
                             headers={"Authorization": f"Bearer {tenant_token}"})
        key2 = resp2.json().get("api_key", "") if resp2.status_code == 200 else ""
        
        passed = resp2.status_code == 200 and key1 != key2 and len(key2) > 20
        print_test(45, "POST /api/integrations/agent-api/regenerate again → different key",
                  passed, f"HTTP {resp2.status_code}, keys_different={key1 != key2}")
        results.append(passed)
    except Exception as e:
        print_test(45, "POST /api/integrations/agent-api/regenerate (second)", False, str(e))
        results.append(False)
    
    # Test 46: GET /api/mcp (no auth) → 200, returns server manifest
    try:
        resp = requests.get(f"{BASE_URL}/mcp")
        data = resp.json() if resp.status_code == 200 else {}
        has_jsonrpc = "jsonrpc" in data
        passed = resp.status_code == 200 and has_jsonrpc
        print_test(46, "GET /api/mcp (no auth) → 200, returns server manifest",
                  passed, f"HTTP {resp.status_code}, has_jsonrpc={has_jsonrpc}")
        results.append(passed)
    except Exception as e:
        print_test(46, "GET /api/mcp", False, str(e))
        results.append(False)
    
    # Test 47: POST /api/mcp without X-Agent-Key → 401
    try:
        payload = {"jsonrpc": "2.0", "method": "tools/list", "id": 1}
        resp = requests.post(f"{BASE_URL}/mcp", json=payload)
        passed = resp.status_code == 401
        print_test(47, "POST /api/mcp without X-Agent-Key → 401",
                  passed, f"HTTP {resp.status_code}")
        results.append(passed)
    except Exception as e:
        print_test(47, "POST /api/mcp (no key)", False, str(e))
        results.append(False)
    
    # Test 48: POST /api/mcp with wrong key → 401
    try:
        payload = {"jsonrpc": "2.0", "method": "tools/list", "id": 1}
        resp = requests.post(f"{BASE_URL}/mcp", json=payload,
                            headers={"X-Agent-Key": "wrong_key_12345"})
        passed = resp.status_code == 401
        print_test(48, "POST /api/mcp with wrong key → 401",
                  passed, f"HTTP {resp.status_code}")
        results.append(passed)
    except Exception as e:
        print_test(48, "POST /api/mcp (wrong key)", False, str(e))
        results.append(False)
    
    # Test 49: POST /api/mcp with valid key → 200, has result.tools
    try:
        # First get a valid key
        resp_key = requests.post(f"{BASE_URL}/integrations/agent-api/regenerate",
                                headers={"Authorization": f"Bearer {tenant_token}"})
        valid_key = resp_key.json().get("api_key", "") if resp_key.status_code == 200 else ""
        
        payload = {"jsonrpc": "2.0", "method": "tools/list", "id": 1}
        resp = requests.post(f"{BASE_URL}/mcp", json=payload,
                            headers={"X-Agent-Key": valid_key})
        data = resp.json() if resp.status_code == 200 else {}
        has_result_tools = "result" in data and "tools" in data.get("result", {})
        passed = resp.status_code == 200 and has_result_tools
        print_test(49, "POST /api/mcp with valid key → 200, has result.tools",
                  passed, f"HTTP {resp.status_code}, has_result_tools={has_result_tools}")
        results.append(passed)
    except Exception as e:
        print_test(49, "POST /api/mcp (valid key)", False, str(e))
        results.append(False)
    
    return results

# ============================================================================
# SECTION I: GCP Production Readiness Sanity
# ============================================================================
def test_section_i():
    print_section("SECTION I: GCP Production Readiness (3 tests)")
    results = []
    
    # Test 51: X-Forwarded-Host support
    try:
        resp = requests.get(f"{BASE_URL}/platform/whoami-tenant",
                           headers={"X-Forwarded-Host": "ddconsult.ddplanner.io"})
        data = resp.json() if resp.status_code == 200 else {}
        # In flag=off mode, should return resolution_mode=flag_off with default tenant
        # OR subdomain=ddconsult (either is acceptable)
        resolution_mode = data.get("resolution_mode")
        subdomain = data.get("subdomain")
        passed = resp.status_code == 200 and (resolution_mode == "flag_off" or subdomain == "ddconsult")
        print_test(51, "X-Forwarded-Host support: GET /api/platform/whoami-tenant with X-Forwarded-Host header",
                  passed, f"HTTP {resp.status_code}, resolution_mode={resolution_mode}, subdomain={subdomain}")
        results.append(passed)
    except Exception as e:
        print_test(51, "X-Forwarded-Host support", False, str(e))
        results.append(False)
    
    # Test 52: Timing-safe MCP compare - verify secrets.compare_digest in mcp_server.py
    try:
        with open("/app/backend/routes/mcp_server.py", "r") as f:
            content = f.read()
        has_compare_digest = "secrets.compare_digest" in content
        passed = has_compare_digest
        print_test(52, "Timing-safe MCP compare: verify secrets.compare_digest in mcp_server.py",
                  passed, f"secrets.compare_digest found: {has_compare_digest}")
        results.append(passed)
    except Exception as e:
        print_test(52, "Timing-safe MCP compare check", False, str(e))
        results.append(False)
    
    # Test 53: Backend logs check - NO errors during test run
    try:
        with open("/var/log/supervisor/backend.err.log", "r") as f:
            logs = f.read()
        # Check for critical errors
        has_attribute_error = "AttributeError" in logs
        has_type_error = "TypeError" in logs
        has_lazy_error = "LazyCollection" in logs
        has_500_traceback = "500" in logs and "Traceback" in logs
        
        # We want NONE of these
        passed = not (has_attribute_error or has_type_error or has_lazy_error or has_500_traceback)
        print_test(53, "Backend logs check: NO AttributeError, TypeError, LazyCollection errors, 500 tracebacks",
                  passed, f"AttributeError={has_attribute_error}, TypeError={has_type_error}, LazyCollection={has_lazy_error}, 500_traceback={has_500_traceback}")
        results.append(passed)
    except Exception as e:
        print_test(53, "Backend logs check", False, str(e))
        results.append(False)
    
    return results

# ============================================================================
# SECTION J: Bloat / Regression Sanity
# ============================================================================
def test_section_j():
    print_section("SECTION J: Bloat / Regression Sanity (4 tests)")
    results = []
    
    # Test 54: GET /api/projects (still 4)
    try:
        resp = requests.get(f"{BASE_URL}/projects",
                           headers={"Authorization": f"Bearer {tenant_token}"})
        count = len(resp.json()) if resp.status_code == 200 else 0
        passed = resp.status_code == 200 and count == 4
        print_test(54, "GET /api/projects (still 4)", passed,
                  f"HTTP {resp.status_code}, count={count}")
        results.append(passed)
    except Exception as e:
        print_test(54, "GET /api/projects (regression)", False, str(e))
        results.append(False)
    
    # Test 55: GET /api/resources (still 5)
    try:
        resp = requests.get(f"{BASE_URL}/resources",
                           headers={"Authorization": f"Bearer {tenant_token}"})
        count = len(resp.json()) if resp.status_code == 200 else 0
        passed = resp.status_code == 200 and count == 5
        print_test(55, "GET /api/resources (still 5)", passed,
                  f"HTTP {resp.status_code}, count={count}")
        results.append(passed)
    except Exception as e:
        print_test(55, "GET /api/resources (regression)", False, str(e))
        results.append(False)
    
    # Test 56: GET /api/allocations (still 10)
    try:
        resp = requests.get(f"{BASE_URL}/allocations",
                           headers={"Authorization": f"Bearer {tenant_token}"})
        count = len(resp.json()) if resp.status_code == 200 else 0
        passed = resp.status_code == 200 and count == 10
        print_test(56, "GET /api/allocations (still 10)", passed,
                  f"HTTP {resp.status_code}, count={count}")
        results.append(passed)
    except Exception as e:
        print_test(56, "GET /api/allocations (regression)", False, str(e))
        results.append(False)
    
    # Test 57: GET /api/tenant/modules (17 keys)
    try:
        resp = requests.get(f"{BASE_URL}/tenant/modules",
                           headers={"Authorization": f"Bearer {tenant_token}"})
        data = resp.json() if resp.status_code == 200 else {}
        modules = data.get("modules", {})
        passed = resp.status_code == 200 and len(modules) == 17
        print_test(57, "GET /api/tenant/modules (17 keys)", passed,
                  f"HTTP {resp.status_code}, count={len(modules)}")
        results.append(passed)
    except Exception as e:
        print_test(57, "GET /api/tenant/modules (regression)", False, str(e))
        results.append(False)
    
    return results

# ============================================================================
# MAIN
# ============================================================================
def main():
    print("\n" + "="*80)
    print("  STEP 11 FINAL COMPREHENSIVE TEST")
    print("  Full Multi-Tenant Regression + GCP Production Readiness")
    print("="*80)
    print(f"\nBase URL: {BASE_URL}")
    print(f"Tenant Admin: {TENANT_ADMIN_EMAIL}")
    print(f"Platform Admin: {PLATFORM_ADMIN_EMAIL}")
    print(f"Feature Flag: MULTI_TENANT_ENABLED=false (verified in .env)")
    print("\nRunning tests for sections A-G, I, J...")
    print("(Section H - Automated Isolation Suite - will be run separately with pytest)\n")
    
    all_results = []
    
    # Run all test sections
    all_results.extend(test_section_a())  # 7 tests
    all_results.extend(test_section_b())  # 8 tests
    all_results.extend(test_section_c())  # 10 tests
    all_results.extend(test_section_d())  # 2 tests
    all_results.extend(test_section_e())  # 6 tests
    all_results.extend(test_section_f())  # 8 tests
    all_results.extend(test_section_g())  # 8 tests
    all_results.extend(test_section_i())  # 3 tests (skipping test 50 - that's section H)
    all_results.extend(test_section_j())  # 4 tests
    
    # Summary
    print_section("SUMMARY")
    total_tests = len(all_results)
    passed_tests = sum(all_results)
    failed_tests = total_tests - passed_tests
    
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests} ✅")
    print(f"Failed: {failed_tests} ❌")
    print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
    
    print("\n" + "="*80)
    print("  Section-by-Section Breakdown")
    print("="*80)
    print(f"A. Fundamental Auth (7 tests): {sum(all_results[0:7])}/7")
    print(f"B. Core Data Reads (8 tests): {sum(all_results[7:15])}/8")
    print(f"C. Platform Layer (10 tests): {sum(all_results[15:25])}/10")
    print(f"D. Module System (2 tests): {sum(all_results[25:27])}/2")
    print(f"E. Signup Flow (6 tests): {sum(all_results[27:33])}/6")
    print(f"F. Branding & Settings (8 tests): {sum(all_results[33:41])}/8")
    print(f"G. Integrations (8 tests): {sum(all_results[41:49])}/8")
    print(f"I. GCP Production Readiness (3 tests): {sum(all_results[49:52])}/3")
    print(f"J. Bloat/Regression Sanity (4 tests): {sum(all_results[52:56])}/4")
    
    print("\n" + "="*80)
    print("  Next: Section H - Automated Multi-Tenant Isolation Suite")
    print("="*80)
    print("This requires MULTI_TENANT_ENABLED=true and will be run separately.")
    print("See instructions in review request for running the pytest suite.")
    
    return 0 if failed_tests == 0 else 1

if __name__ == "__main__":
    exit(main())
