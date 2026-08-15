#!/usr/bin/env python3
"""
Step 7 Regression + New Platform Endpoints Testing
Platform Admin Portal Backend - Tenant CRUD, Impersonation, Audit Log, Dashboard Stats

Test URL: https://a0ac7ee9-2785-4339-ad6f-6886af7a3f1a.preview.emergentagent.com
Feature flag: MULTI_TENANT_ENABLED=false (DO NOT change)
Credentials:
  - Tenant admin: admin@test.com / admin123
  - Platform admin: don@ddconsult.tech / Welcome123! (form-urlencoded)
"""

import requests
import json
import jwt
from datetime import datetime

# Configuration
BASE_URL = "https://a0ac7ee9-2785-4339-ad6f-6886af7a3f1a.preview.emergentagent.com/api"
TENANT_ADMIN_EMAIL = "admin@test.com"
TENANT_ADMIN_PASSWORD = "admin123"
PLATFORM_ADMIN_EMAIL = "don@ddconsult.tech"
PLATFORM_ADMIN_PASSWORD = "Welcome123!"

# Global tokens
TENANT_TOKEN = None
PLATFORM_TOKEN = None

# Test counters
tests_passed = 0
tests_failed = 0
test_results = []

def log_test(test_num, description, passed, details=""):
    """Log test result"""
    global tests_passed, tests_failed
    status = "✅ PASS" if passed else "❌ FAIL"
    if passed:
        tests_passed += 1
    else:
        tests_failed += 1
    result = f"Test {test_num}: {status} - {description}"
    if details:
        result += f"\n  Details: {details}"
    print(result)
    test_results.append({"test": test_num, "description": description, "passed": passed, "details": details})

def setup_auth():
    """Setup authentication tokens"""
    global TENANT_TOKEN, PLATFORM_TOKEN
    
    print("\n=== SETUP: Authentication ===")
    
    # Login as tenant admin
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": TENANT_ADMIN_EMAIL, "password": TENANT_ADMIN_PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if response.status_code == 200:
            TENANT_TOKEN = response.json()["access_token"]
            print(f"✅ Tenant admin login successful")
            
            # Verify JWT shape (should have only sub + exp when flag=off)
            payload = jwt.decode(TENANT_TOKEN, options={"verify_signature": False})
            print(f"  Tenant JWT payload keys: {list(payload.keys())}")
        else:
            print(f"❌ Tenant admin login failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Tenant admin login error: {e}")
        return False
    
    # Login as platform admin
    try:
        response = requests.post(
            f"{BASE_URL}/platform/auth/login",
            data={"username": PLATFORM_ADMIN_EMAIL, "password": PLATFORM_ADMIN_PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if response.status_code == 200:
            PLATFORM_TOKEN = response.json()["access_token"]
            print(f"✅ Platform admin login successful")
            
            # Verify JWT shape
            payload = jwt.decode(PLATFORM_TOKEN, options={"verify_signature": False})
            print(f"  Platform JWT payload keys: {list(payload.keys())}")
        else:
            print(f"❌ Platform admin login failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Platform admin login error: {e}")
        return False
    
    return True

def test_regression():
    """Section A: Regression tests - all previous endpoints must still work"""
    print("\n=== SECTION A: REGRESSION TESTS ===")
    
    # Test 1: POST /api/auth/login
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": TENANT_ADMIN_EMAIL, "password": TENANT_ADMIN_PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if response.status_code == 200:
            token = response.json()["access_token"]
            payload = jwt.decode(token, options={"verify_signature": False})
            # Should have ONLY sub + exp (legacy shape when flag=off)
            has_only_sub_exp = set(payload.keys()) == {"sub", "exp"}
            log_test(1, "POST /api/auth/login → 200, JWT with sub + exp only", 
                    has_only_sub_exp, 
                    f"JWT keys: {list(payload.keys())}")
        else:
            log_test(1, "POST /api/auth/login → 200", False, f"HTTP {response.status_code}")
    except Exception as e:
        log_test(1, "POST /api/auth/login", False, str(e))
    
    # Test 2: GET /api/projects with tenant admin → exactly 4 projects
    try:
        response = requests.get(
            f"{BASE_URL}/projects",
            headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
        )
        if response.status_code == 200:
            projects = response.json()
            count = len(projects)
            log_test(2, "GET /api/projects → 200, exactly 4 projects", 
                    count == 4, 
                    f"Found {count} projects")
        else:
            log_test(2, "GET /api/projects → 200", False, f"HTTP {response.status_code}")
    except Exception as e:
        log_test(2, "GET /api/projects", False, str(e))
    
    # Test 3: GET /api/resources → exactly 5
    try:
        response = requests.get(
            f"{BASE_URL}/resources",
            headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
        )
        if response.status_code == 200:
            resources = response.json()
            count = len(resources)
            log_test(3, "GET /api/resources → 200, exactly 5", 
                    count == 5, 
                    f"Found {count} resources")
        else:
            log_test(3, "GET /api/resources → 200", False, f"HTTP {response.status_code}")
    except Exception as e:
        log_test(3, "GET /api/resources", False, str(e))
    
    # Test 4: GET /api/allocations → exactly 10
    try:
        response = requests.get(
            f"{BASE_URL}/allocations",
            headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
        )
        if response.status_code == 200:
            allocations = response.json()
            count = len(allocations)
            log_test(4, "GET /api/allocations → 200, exactly 10", 
                    count == 10, 
                    f"Found {count} allocations")
        else:
            log_test(4, "GET /api/allocations → 200", False, f"HTTP {response.status_code}")
    except Exception as e:
        log_test(4, "GET /api/allocations", False, str(e))
    
    # Test 5: GET /api/portfolio → 200
    try:
        response = requests.get(
            f"{BASE_URL}/portfolio",
            headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
        )
        log_test(5, "GET /api/portfolio → 200", 
                response.status_code == 200, 
                f"HTTP {response.status_code}")
    except Exception as e:
        log_test(5, "GET /api/portfolio", False, str(e))
    
    # Test 6: GET /api/dashboard/action-items → 200
    try:
        response = requests.get(
            f"{BASE_URL}/dashboard/action-items",
            headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
        )
        log_test(6, "GET /api/dashboard/action-items → 200", 
                response.status_code == 200, 
                f"HTTP {response.status_code}")
    except Exception as e:
        log_test(6, "GET /api/dashboard/action-items", False, str(e))
    
    # Test 7: GET /api/tenant/modules → 200, has 17 keys, all true
    try:
        response = requests.get(
            f"{BASE_URL}/tenant/modules",
            headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
        )
        if response.status_code == 200:
            data = response.json()
            modules = data.get("modules", {})
            count = len(modules)
            all_true = all(v is True for v in modules.values())
            log_test(7, "GET /api/tenant/modules → 200, 17 keys, all true", 
                    count == 17 and all_true, 
                    f"Found {count} modules, all_true={all_true}")
        else:
            log_test(7, "GET /api/tenant/modules → 200", False, f"HTTP {response.status_code}")
    except Exception as e:
        log_test(7, "GET /api/tenant/modules", False, str(e))
    
    # Test 8: POST /api/platform/auth/login → 200, saves PLATFORM_TOKEN
    try:
        response = requests.post(
            f"{BASE_URL}/platform/auth/login",
            data={"username": PLATFORM_ADMIN_EMAIL, "password": PLATFORM_ADMIN_PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        log_test(8, "POST /api/platform/auth/login → 200", 
                response.status_code == 200, 
                f"HTTP {response.status_code}")
    except Exception as e:
        log_test(8, "POST /api/platform/auth/login", False, str(e))
    
    # Test 9: GET /api/platform/auth/me → 200, role=platform_admin
    try:
        response = requests.get(
            f"{BASE_URL}/platform/auth/me",
            headers={"Authorization": f"Bearer {PLATFORM_TOKEN}"}
        )
        if response.status_code == 200:
            user = response.json()
            role = user.get("role")
            log_test(9, "GET /api/platform/auth/me → 200, role=platform_admin", 
                    role == "platform_admin", 
                    f"role={role}")
        else:
            log_test(9, "GET /api/platform/auth/me → 200", False, f"HTTP {response.status_code}")
    except Exception as e:
        log_test(9, "GET /api/platform/auth/me", False, str(e))
    
    # Test 10: GET /api/platform/status (no auth) → 200
    try:
        response = requests.get(f"{BASE_URL}/platform/status")
        log_test(10, "GET /api/platform/status (no auth) → 200", 
                response.status_code == 200, 
                f"HTTP {response.status_code}")
    except Exception as e:
        log_test(10, "GET /api/platform/status", False, str(e))
    
    # Test 11: GET /api/health → 200
    try:
        response = requests.get(f"{BASE_URL}/health")
        log_test(11, "GET /api/health → 200", 
                response.status_code == 200, 
                f"HTTP {response.status_code}")
    except Exception as e:
        log_test(11, "GET /api/health", False, str(e))

def test_dashboard_stats():
    """Section B: NEW - Dashboard stats endpoint"""
    print("\n=== SECTION B: NEW - DASHBOARD STATS ===")
    
    # Test 12: GET /api/platform/dashboard/stats
    try:
        response = requests.get(
            f"{BASE_URL}/platform/dashboard/stats",
            headers={"Authorization": f"Bearer {PLATFORM_TOKEN}"}
        )
        if response.status_code == 200:
            data = response.json()
            has_tenants = "tenants" in data and "total" in data["tenants"]
            has_platform_users = "platform_users" in data
            has_memberships = "memberships" in data
            has_modules = "modules" in data and len(data["modules"]) == 17
            has_recent_audit = "recent_audit" in data
            
            all_present = has_tenants and has_platform_users and has_memberships and has_modules and has_recent_audit
            
            details = f"tenants={has_tenants}, platform_users={has_platform_users}, memberships={has_memberships}, modules={has_modules}, recent_audit={has_recent_audit}"
            if all_present:
                details += f" | tenants.total={data['tenants']['total']}, platform_users={data['platform_users']}, memberships={data['memberships']}"
            
            log_test(12, "GET /api/platform/dashboard/stats → 200 with all fields", 
                    all_present, 
                    details)
        else:
            log_test(12, "GET /api/platform/dashboard/stats → 200", False, f"HTTP {response.status_code}")
    except Exception as e:
        log_test(12, "GET /api/platform/dashboard/stats", False, str(e))

def test_tenants_list_enrichment():
    """Section C: NEW - Tenants list with enrichment"""
    print("\n=== SECTION C: NEW - TENANTS LIST ENRICHMENT ===")
    
    # Test 13: GET /api/platform/tenants with enrichment
    try:
        response = requests.get(
            f"{BASE_URL}/platform/tenants",
            headers={"Authorization": f"Bearer {PLATFORM_TOKEN}"}
        )
        if response.status_code == 200:
            tenants = response.json()
            count = len(tenants)
            if count >= 1:
                dd_tenant = next((t for t in tenants if t.get("slug") == "ddconsult"), None)
                if dd_tenant:
                    has_enabled_modules_count = "enabled_modules_count" in dd_tenant
                    enabled_count = dd_tenant.get("enabled_modules_count", 0)
                    log_test(13, "GET /api/platform/tenants → 200, DD Consulting has enabled_modules_count=17", 
                            has_enabled_modules_count and enabled_count == 17, 
                            f"Found {count} tenants, DD Consulting enabled_modules_count={enabled_count}")
                else:
                    log_test(13, "GET /api/platform/tenants → DD Consulting tenant", False, "DD Consulting tenant not found")
            else:
                log_test(13, "GET /api/platform/tenants → 200", False, f"Expected at least 1 tenant, found {count}")
        else:
            log_test(13, "GET /api/platform/tenants → 200", False, f"HTTP {response.status_code}")
    except Exception as e:
        log_test(13, "GET /api/platform/tenants", False, str(e))

def test_tenant_crud():
    """Section D: NEW - Tenant CRUD"""
    print("\n=== SECTION D: NEW - TENANT CRUD ===")
    
    global ACME_TEST_ID
    ACME_TEST_ID = None
    
    # Test 14: POST /api/platform/tenants - Create acme-test
    try:
        payload = {
            "slug": "acme-test",
            "name": "Acme Test",
            "owner_email": "admin@acme-test.io",
            "owner_password": "AcmeTest2026!",
            "enabled_modules": ["projects", "resources", "allocations"]
        }
        response = requests.post(
            f"{BASE_URL}/platform/tenants",
            headers={"Authorization": f"Bearer {PLATFORM_TOKEN}", "Content-Type": "application/json"},
            json=payload
        )
        if response.status_code == 201:
            data = response.json()
            has_id = "id" in data
            slug_correct = data.get("slug") == "acme-test"
            status_active = data.get("status") == "active"
            is_default_false = data.get("is_default") == False
            
            all_correct = has_id and slug_correct and status_active and is_default_false
            
            if has_id:
                ACME_TEST_ID = data["id"]
            
            log_test(14, "POST /api/platform/tenants → 201, acme-test created", 
                    all_correct, 
                    f"id={has_id}, slug={slug_correct}, status={status_active}, is_default={is_default_false}")
        else:
            log_test(14, "POST /api/platform/tenants → 201", False, f"HTTP {response.status_code}, body: {response.text[:200]}")
    except Exception as e:
        log_test(14, "POST /api/platform/tenants", False, str(e))
    
    # Test 15: GET /api/platform/tenants - Should now have 2 tenants
    try:
        response = requests.get(
            f"{BASE_URL}/platform/tenants",
            headers={"Authorization": f"Bearer {PLATFORM_TOKEN}"}
        )
        if response.status_code == 200:
            tenants = response.json()
            count = len(tenants)
            acme_tenant = next((t for t in tenants if t.get("slug") == "acme-test"), None)
            if acme_tenant:
                enabled_count = acme_tenant.get("enabled_modules_count", 0)
                log_test(15, "GET /api/platform/tenants → 2 tenants, acme-test has enabled_modules_count=3", 
                        count == 2 and enabled_count == 3, 
                        f"Found {count} tenants, acme-test enabled_modules_count={enabled_count}")
            else:
                log_test(15, "GET /api/platform/tenants → acme-test present", False, "acme-test not found")
        else:
            log_test(15, "GET /api/platform/tenants → 200", False, f"HTTP {response.status_code}")
    except Exception as e:
        log_test(15, "GET /api/platform/tenants", False, str(e))
    
    # Test 16: PATCH /api/platform/tenants/acme-test - Update tenant
    try:
        payload = {
            "status": "suspended",
            "name": "Acme Test Renamed",
            "primary_color": "#ff0000"
        }
        response = requests.patch(
            f"{BASE_URL}/platform/tenants/acme-test",
            headers={"Authorization": f"Bearer {PLATFORM_TOKEN}", "Content-Type": "application/json"},
            json=payload
        )
        if response.status_code == 200:
            data = response.json()
            status_updated = data.get("status") == "suspended"
            name_updated = data.get("name") == "Acme Test Renamed"
            log_test(16, "PATCH /api/platform/tenants/acme-test → 200, status and name updated", 
                    status_updated and name_updated, 
                    f"status={data.get('status')}, name={data.get('name')}")
        else:
            log_test(16, "PATCH /api/platform/tenants/acme-test → 200", False, f"HTTP {response.status_code}")
    except Exception as e:
        log_test(16, "PATCH /api/platform/tenants/acme-test", False, str(e))
    
    # Test 17: GET /api/platform/tenants/acme-test/modules
    try:
        response = requests.get(
            f"{BASE_URL}/platform/tenants/acme-test/modules",
            headers={"Authorization": f"Bearer {PLATFORM_TOKEN}"}
        )
        if response.status_code == 200:
            data = response.json()
            tenant_slug = data.get("tenant_slug")
            modules = data.get("modules", [])
            # modules is a list of objects, not a dict
            enabled_count = sum(1 for m in modules if m.get("enabled") is True)
            disabled_count = sum(1 for m in modules if m.get("enabled") is False)
            
            log_test(17, "GET /api/platform/tenants/acme-test/modules → 200, 3 enabled, 14 disabled", 
                    tenant_slug == "acme-test" and enabled_count == 3 and disabled_count == 14, 
                    f"tenant_slug={tenant_slug}, enabled={enabled_count}, disabled={disabled_count}")
        else:
            log_test(17, "GET /api/platform/tenants/acme-test/modules → 200", False, f"HTTP {response.status_code}")
    except Exception as e:
        log_test(17, "GET /api/platform/tenants/acme-test/modules", False, str(e))
    
    # Test 18: GET /api/platform/tenants/acme-test/users
    try:
        response = requests.get(
            f"{BASE_URL}/platform/tenants/acme-test/users",
            headers={"Authorization": f"Bearer {PLATFORM_TOKEN}"}
        )
        if response.status_code == 200:
            users = response.json()
            count = len(users)
            if count == 1:
                user = users[0]
                email_correct = user.get("email") == "admin@acme-test.io"
                role_correct = user.get("role") == "super_admin"
                must_change_password = user.get("must_change_password") == True
                no_password_hash = "password_hash" not in user
                
                all_correct = email_correct and role_correct and must_change_password and no_password_hash
                
                log_test(18, "GET /api/platform/tenants/acme-test/users → 1 user, no password_hash", 
                        all_correct, 
                        f"count={count}, email={email_correct}, role={role_correct}, must_change_password={must_change_password}, no_password_hash={no_password_hash}")
            else:
                log_test(18, "GET /api/platform/tenants/acme-test/users → 1 user", False, f"Expected 1 user, found {count}")
        else:
            log_test(18, "GET /api/platform/tenants/acme-test/users → 200", False, f"HTTP {response.status_code}")
    except Exception as e:
        log_test(18, "GET /api/platform/tenants/acme-test/users", False, str(e))
    
    # Test 19: POST /api/platform/tenants/acme-test/impersonate
    try:
        response = requests.post(
            f"{BASE_URL}/platform/tenants/acme-test/impersonate",
            headers={"Authorization": f"Bearer {PLATFORM_TOKEN}"}
        )
        if response.status_code == 200:
            data = response.json()
            has_access_token = "access_token" in data
            tenant_slug_correct = data.get("tenant_slug") == "acme-test"
            has_expires_in = "expires_in_seconds" in data
            expires_in = data.get("expires_in_seconds", 0)
            
            # Decode JWT to verify payload
            if has_access_token:
                token = data["access_token"]
                payload = jwt.decode(token, options={"verify_signature": False})
                token_type = payload.get("token_type")
                tenant_slug_jwt = payload.get("tenant_slug")
                role = payload.get("role")
                impersonator = payload.get("impersonator")
                
                jwt_correct = (token_type == "tenant" and 
                              tenant_slug_jwt == "acme-test" and 
                              role == "super_admin" and 
                              impersonator == PLATFORM_ADMIN_EMAIL)
                
                all_correct = has_access_token and tenant_slug_correct and has_expires_in and expires_in == 900 and jwt_correct
                
                log_test(19, "POST /api/platform/tenants/acme-test/impersonate → 200, JWT correct", 
                        all_correct, 
                        f"tenant_slug={tenant_slug_correct}, expires_in={expires_in}, JWT: token_type={token_type}, tenant_slug={tenant_slug_jwt}, role={role}, impersonator={impersonator}")
            else:
                log_test(19, "POST /api/platform/tenants/acme-test/impersonate → access_token", False, "No access_token in response")
        else:
            log_test(19, "POST /api/platform/tenants/acme-test/impersonate → 200", False, f"HTTP {response.status_code}")
    except Exception as e:
        log_test(19, "POST /api/platform/tenants/acme-test/impersonate", False, str(e))
    
    # Test 20: DELETE /api/platform/tenants/acme-test
    try:
        response = requests.delete(
            f"{BASE_URL}/platform/tenants/acme-test",
            headers={"Authorization": f"Bearer {PLATFORM_TOKEN}"}
        )
        if response.status_code == 200:
            data = response.json()
            status_deleted = data.get("status") == "deleted"
            log_test(20, "DELETE /api/platform/tenants/acme-test → 200, status=deleted", 
                    status_deleted, 
                    f"status={data.get('status')}")
        else:
            log_test(20, "DELETE /api/platform/tenants/acme-test → 200", False, f"HTTP {response.status_code}")
    except Exception as e:
        log_test(20, "DELETE /api/platform/tenants/acme-test", False, str(e))
    
    # Test 21: DELETE /api/platform/tenants/ddconsult (default tenant) → 400
    try:
        response = requests.delete(
            f"{BASE_URL}/platform/tenants/ddconsult",
            headers={"Authorization": f"Bearer {PLATFORM_TOKEN}"}
        )
        is_400 = response.status_code == 400
        has_error_message = "Cannot delete the default tenant" in response.text
        log_test(21, "DELETE /api/platform/tenants/ddconsult → 400, cannot delete default", 
                is_400 and has_error_message, 
                f"HTTP {response.status_code}, message_present={has_error_message}")
    except Exception as e:
        log_test(21, "DELETE /api/platform/tenants/ddconsult", False, str(e))

def test_duplicate_slug_prevention():
    """Section E: NEW - Duplicate slug prevention"""
    print("\n=== SECTION E: NEW - DUPLICATE SLUG PREVENTION ===")
    
    # Test 22: POST /api/platform/tenants with duplicate slug → 409
    try:
        payload = {
            "slug": "ddconsult",
            "name": "Dup",
            "owner_email": "x@x.com",
            "owner_password": "12345678"
        }
        response = requests.post(
            f"{BASE_URL}/platform/tenants",
            headers={"Authorization": f"Bearer {PLATFORM_TOKEN}", "Content-Type": "application/json"},
            json=payload
        )
        is_409 = response.status_code == 409
        log_test(22, "POST /api/platform/tenants with duplicate slug → 409", 
                is_409, 
                f"HTTP {response.status_code}")
    except Exception as e:
        log_test(22, "POST /api/platform/tenants duplicate slug", False, str(e))

def test_audit_log():
    """Section F: NEW - Audit log"""
    print("\n=== SECTION F: NEW - AUDIT LOG ===")
    
    # Test 23: GET /api/platform/audit-log?limit=10
    try:
        response = requests.get(
            f"{BASE_URL}/platform/audit-log?limit=10",
            headers={"Authorization": f"Bearer {PLATFORM_TOKEN}"}
        )
        if response.status_code == 200:
            entries = response.json()
            count = len(entries)
            
            # Check for expected actions
            actions = [e.get("action") for e in entries]
            has_create = "tenant.create" in actions
            has_update = "tenant.update" in actions
            has_impersonate = "tenant.impersonate" in actions
            has_delete = "tenant.delete" in actions
            
            log_test(23, "GET /api/platform/audit-log?limit=10 → 200, has tenant actions", 
                    count > 0 and (has_create or has_update or has_impersonate or has_delete), 
                    f"Found {count} entries, actions: create={has_create}, update={has_update}, impersonate={has_impersonate}, delete={has_delete}")
        else:
            log_test(23, "GET /api/platform/audit-log?limit=10 → 200", False, f"HTTP {response.status_code}")
    except Exception as e:
        log_test(23, "GET /api/platform/audit-log", False, str(e))
    
    # Test 24: GET /api/platform/audit-log?tenant_slug=acme-test
    try:
        response = requests.get(
            f"{BASE_URL}/platform/audit-log?tenant_slug=acme-test",
            headers={"Authorization": f"Bearer {PLATFORM_TOKEN}"}
        )
        if response.status_code == 200:
            entries = response.json()
            # All entries should be for acme-test
            all_acme = all(e.get("tenant_slug") == "acme-test" for e in entries if "tenant_slug" in e)
            log_test(24, "GET /api/platform/audit-log?tenant_slug=acme-test → 200, only acme-test entries", 
                    all_acme, 
                    f"Found {len(entries)} entries, all_acme={all_acme}")
        else:
            log_test(24, "GET /api/platform/audit-log?tenant_slug=acme-test → 200", False, f"HTTP {response.status_code}")
    except Exception as e:
        log_test(24, "GET /api/platform/audit-log tenant filter", False, str(e))
    
    # Test 25: GET /api/platform/audit-log?action=tenant.create
    try:
        response = requests.get(
            f"{BASE_URL}/platform/audit-log?action=tenant.create",
            headers={"Authorization": f"Bearer {PLATFORM_TOKEN}"}
        )
        if response.status_code == 200:
            entries = response.json()
            # All entries should be tenant.create
            all_create = all(e.get("action") == "tenant.create" for e in entries)
            log_test(25, "GET /api/platform/audit-log?action=tenant.create → 200, only creation entries", 
                    all_create, 
                    f"Found {len(entries)} entries, all_create={all_create}")
        else:
            log_test(25, "GET /api/platform/audit-log?action=tenant.create → 200", False, f"HTTP {response.status_code}")
    except Exception as e:
        log_test(25, "GET /api/platform/audit-log action filter", False, str(e))

def test_authorization():
    """Section G: Authorization"""
    print("\n=== SECTION G: AUTHORIZATION ===")
    
    # Test 26: GET /api/platform/dashboard/stats with tenant JWT → 403
    try:
        response = requests.get(
            f"{BASE_URL}/platform/dashboard/stats",
            headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
        )
        is_403 = response.status_code == 403
        log_test(26, "GET /api/platform/dashboard/stats with tenant JWT → 403", 
                is_403, 
                f"HTTP {response.status_code}")
    except Exception as e:
        log_test(26, "GET /api/platform/dashboard/stats auth check", False, str(e))
    
    # Test 27: POST /api/platform/tenants without auth → 401
    try:
        payload = {
            "slug": "test",
            "name": "Test",
            "owner_email": "test@test.com",
            "owner_password": "12345678"
        }
        response = requests.post(
            f"{BASE_URL}/platform/tenants",
            headers={"Content-Type": "application/json"},
            json=payload
        )
        is_401 = response.status_code == 401
        log_test(27, "POST /api/platform/tenants without auth → 401", 
                is_401, 
                f"HTTP {response.status_code}")
    except Exception as e:
        log_test(27, "POST /api/platform/tenants no auth", False, str(e))
    
    # Test 28: POST /api/platform/tenants/ddconsult/impersonate with tenant JWT → 403
    try:
        response = requests.post(
            f"{BASE_URL}/platform/tenants/ddconsult/impersonate",
            headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
        )
        is_403 = response.status_code == 403
        log_test(28, "POST /api/platform/tenants/ddconsult/impersonate with tenant JWT → 403", 
                is_403, 
                f"HTTP {response.status_code}")
    except Exception as e:
        log_test(28, "POST impersonate with tenant JWT", False, str(e))

def test_cleanup():
    """Section H: Cleanup"""
    print("\n=== SECTION H: CLEANUP ===")
    
    # Test 29: Cleanup acme-test tenant from MongoDB
    try:
        import subprocess
        
        cleanup_script = """
mongosh --quiet --eval "
  db.getSiblingDB('platform_db').tenants.deleteOne({slug:'acme-test'});
  db.getSiblingDB('platform_db').tenant_modules.deleteMany({tenant_slug:'acme-test'});
  db.getSiblingDB('platform_db').memberships.deleteMany({tenant_slug:'acme-test'});
  db.getSiblingDB('tenant_acme_test').dropDatabase();
  print('Cleanup complete');
"
"""
        result = subprocess.run(cleanup_script, shell=True, capture_output=True, text=True, timeout=10)
        success = result.returncode == 0 and "Cleanup complete" in result.stdout
        log_test(29, "Cleanup acme-test tenant from MongoDB", 
                success, 
                f"returncode={result.returncode}, output: {result.stdout[:100]}")
    except Exception as e:
        log_test(29, "Cleanup acme-test tenant", False, str(e))

def test_backend_logs():
    """Section I: Sanity check backend log"""
    print("\n=== SECTION I: BACKEND LOG CHECK ===")
    
    # Test 30: Check backend logs for errors
    try:
        import subprocess
        
        result = subprocess.run(
            "tail -n 200 /var/log/supervisor/backend.err.log | grep -E '(AttributeError|TypeError|500|Traceback)' | head -20",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        has_errors = len(result.stdout.strip()) > 0
        
        if has_errors:
            log_test(30, "Backend logs check - No critical errors", 
                    False, 
                    f"Found errors:\n{result.stdout[:500]}")
        else:
            log_test(30, "Backend logs check - No critical errors", 
                    True, 
                    "No AttributeError, TypeError, or 500 tracebacks found")
    except Exception as e:
        log_test(30, "Backend logs check", False, str(e))

def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total tests: {tests_passed + tests_failed}")
    print(f"✅ Passed: {tests_passed}")
    print(f"❌ Failed: {tests_failed}")
    print(f"Success rate: {(tests_passed / (tests_passed + tests_failed) * 100):.1f}%")
    
    if tests_failed > 0:
        print("\n❌ FAILED TESTS:")
        for result in test_results:
            if not result["passed"]:
                print(f"  - Test {result['test']}: {result['description']}")
                if result["details"]:
                    print(f"    {result['details']}")
    
    print("\n" + "="*80)
    if tests_failed == 0:
        print("REGRESSION VERDICT: PASS ✅")
        print("All endpoints working correctly. No regressions detected.")
    else:
        print("REGRESSION VERDICT: FAIL ❌")
        print(f"{tests_failed} test(s) failed. Review required.")
    print("="*80)

def main():
    """Main test execution"""
    print("="*80)
    print("STEP 7 REGRESSION + NEW PLATFORM ENDPOINTS TESTING")
    print("Platform Admin Portal Backend - Tenant CRUD, Impersonation, Audit Log")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"Feature flag: MULTI_TENANT_ENABLED=false")
    print(f"Tenant admin: {TENANT_ADMIN_EMAIL}")
    print(f"Platform admin: {PLATFORM_ADMIN_EMAIL}")
    print("="*80)
    
    # Setup authentication
    if not setup_auth():
        print("\n❌ Authentication setup failed. Cannot proceed with tests.")
        return
    
    # Run all test sections
    test_regression()
    test_dashboard_stats()
    test_tenants_list_enrichment()
    test_tenant_crud()
    test_duplicate_slug_prevention()
    test_audit_log()
    test_authorization()
    test_cleanup()
    test_backend_logs()
    
    # Print summary
    print_summary()

if __name__ == "__main__":
    main()
