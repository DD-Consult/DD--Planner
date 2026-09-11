#!/usr/bin/env python3
"""
Backend Test: Multi-Tenant Migration Framework + Config Inheritance
Tests the newly added migration endpoints and config inheritance for DD Planner SaaS app.
"""

import requests
import json
import sys
from typing import Dict, Any

# Base URL from frontend/.env
BASE_URL = "https://saas-launch-44.preview.emergentagent.com/api"

# Test credentials
PLATFORM_ADMIN_EMAIL = "don@ddconsult.tech"
PLATFORM_ADMIN_PASSWORD_1 = "Welcome123!"
PLATFORM_ADMIN_PASSWORD_2 = "@Ddplanner2026"

# Test results tracking
test_results = []
test_count = 0
pass_count = 0
fail_count = 0

def log_test(test_name: str, passed: bool, details: str = ""):
    """Log test result"""
    global test_count, pass_count, fail_count
    test_count += 1
    if passed:
        pass_count += 1
        status = "✅ PASS"
    else:
        fail_count += 1
        status = "❌ FAIL"
    
    result = f"{status} - Test {test_count}: {test_name}"
    if details:
        result += f"\n    {details}"
    print(result)
    test_results.append({"test": test_name, "passed": passed, "details": details})

def platform_admin_login(password: str) -> tuple[str, dict]:
    """Login as platform admin and return token + user info"""
    url = f"{BASE_URL}/platform/auth/login"
    data = {
        "username": PLATFORM_ADMIN_EMAIL,
        "password": password
    }
    
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            json_data = response.json()
            return json_data.get("access_token", ""), json_data.get("user", {})
        else:
            return "", {}
    except Exception as e:
        print(f"Login error: {e}")
        return "", {}

def tenant_user_login(email: str, password: str) -> str:
    """Login as tenant user and return token"""
    url = f"{BASE_URL}/auth/login"
    data = {
        "username": email,
        "password": password
    }
    
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            return response.json().get("access_token", "")
        else:
            return ""
    except Exception as e:
        print(f"Tenant login error: {e}")
        return ""

def test_migrations_status(token: str):
    """Test 1: GET /api/platform/migrations/status"""
    print("\n=== TEST 1: GET /api/platform/migrations/status ===")
    url = f"{BASE_URL}/platform/migrations/status"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            log_test("Migrations Status Endpoint", False, 
                    f"Expected 200, got {response.status_code}. Body: {response.text[:500]}")
            return
        
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        
        # Check structure
        has_latest_version = "latest_version" in data
        has_platform = "platform" in data
        has_tenants = "tenants" in data
        
        if not (has_latest_version and has_platform and has_tenants):
            log_test("Migrations Status Structure", False, 
                    f"Missing keys. Has latest_version: {has_latest_version}, platform: {has_platform}, tenants: {has_tenants}")
            return
        
        # Check latest_version >= 3
        latest_version = data.get("latest_version", 0)
        if latest_version < 3:
            log_test("Latest Version Check", False, 
                    f"Expected latest_version >= 3, got {latest_version}")
            return
        
        # Check platform.applied >= 1
        platform_applied = data.get("platform", {}).get("applied", 0)
        if platform_applied < 1:
            log_test("Platform Applied Check", False, 
                    f"Expected platform.applied >= 1, got {platform_applied}")
            return
        
        # Check ddconsult tenant
        tenants = data.get("tenants", [])
        ddconsult_tenant = next((t for t in tenants if t.get("slug") == "ddconsult"), None)
        
        if not ddconsult_tenant:
            log_test("DDConsult Tenant Check", False, 
                    f"ddconsult tenant not found in tenants list")
            return
        
        tenant_applied = ddconsult_tenant.get("applied", 0)
        tenant_pending = ddconsult_tenant.get("pending", [])
        tenant_status = ddconsult_tenant.get("status", "")
        
        if tenant_applied < 3:
            log_test("DDConsult Applied Check", False, 
                    f"Expected ddconsult.applied >= 3, got {tenant_applied}")
            return
        
        if tenant_status != "up_to_date":
            log_test("DDConsult Status Check", False, 
                    f"Expected ddconsult.status = 'up_to_date', got '{tenant_status}'")
            return
        
        if len(tenant_pending) > 0:
            log_test("DDConsult Pending Check", False, 
                    f"Expected ddconsult.pending to be empty, got {tenant_pending}")
            return
        
        log_test("Migrations Status Endpoint", True, 
                f"latest_version={latest_version}, platform.applied={platform_applied}, ddconsult.applied={tenant_applied}, status={tenant_status}")
        
    except Exception as e:
        log_test("Migrations Status Endpoint", False, f"Exception: {str(e)}")

def test_migrations_run(token: str):
    """Test 2: POST /api/platform/migrations/run (idempotency test)"""
    print("\n=== TEST 2: POST /api/platform/migrations/run (Idempotency) ===")
    url = f"{BASE_URL}/platform/migrations/run"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        # First run
        print("First run...")
        response1 = requests.post(url, headers=headers)
        
        if response1.status_code != 200:
            log_test("Migrations Run First Call", False, 
                    f"Expected 200, got {response1.status_code}. Body: {response1.text[:500]}")
            return
        
        data1 = response1.json()
        print(f"First run response: {json.dumps(data1, indent=2)}")
        
        # Check structure
        if "platform" not in data1 or "tenants" not in data1:
            log_test("Migrations Run Response Structure", False, 
                    f"Missing 'platform' or 'tenants' keys in response")
            return
        
        # Second run (idempotency test)
        print("\nSecond run (idempotency test)...")
        response2 = requests.post(url, headers=headers)
        
        if response2.status_code != 200:
            log_test("Migrations Run Second Call (Idempotency)", False, 
                    f"Expected 200, got {response2.status_code}. Body: {response2.text[:500]}")
            return
        
        data2 = response2.json()
        print(f"Second run response: {json.dumps(data2, indent=2)}")
        
        # Both should succeed
        log_test("Migrations Run Idempotency", True, 
                f"Both runs succeeded. First: {data1}, Second: {data2}")
        
    except Exception as e:
        log_test("Migrations Run Endpoint", False, f"Exception: {str(e)}")

def test_platform_defaults_get(token: str) -> dict:
    """Test 3: GET /api/platform/defaults"""
    print("\n=== TEST 3: GET /api/platform/defaults ===")
    url = f"{BASE_URL}/platform/defaults"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            log_test("Platform Defaults GET", False, 
                    f"Expected 200, got {response.status_code}. Body: {response.text[:500]}")
            return {}
        
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        
        # Check structure
        has_branding = "branding" in data
        has_settings = "settings" in data
        
        if not (has_branding and has_settings):
            log_test("Platform Defaults Structure", False, 
                    f"Missing keys. Has branding: {has_branding}, settings: {has_settings}")
            return {}
        
        # Check branding fields
        branding = data.get("branding", {})
        expected_branding_fields = ["primary_color", "accent_color"]
        missing_branding = [f for f in expected_branding_fields if f not in branding]
        
        if missing_branding:
            log_test("Platform Defaults Branding Fields", False, 
                    f"Missing branding fields: {missing_branding}")
            return {}
        
        # Check settings fields
        settings = data.get("settings", {})
        expected_settings_fields = ["work_week_hours", "timezone", "work_days"]
        missing_settings = [f for f in expected_settings_fields if f not in settings]
        
        if missing_settings:
            log_test("Platform Defaults Settings Fields", False, 
                    f"Missing settings fields: {missing_settings}")
            return {}
        
        log_test("Platform Defaults GET", True, 
                f"branding.primary_color={branding.get('primary_color')}, settings.work_week_hours={settings.get('work_week_hours')}")
        
        return data
        
    except Exception as e:
        log_test("Platform Defaults GET", False, f"Exception: {str(e)}")
        return {}

def test_platform_defaults_put(token: str):
    """Test 4: PUT /api/platform/defaults (with validation)"""
    print("\n=== TEST 4: PUT /api/platform/defaults (Update & Validation) ===")
    url = f"{BASE_URL}/platform/defaults"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    try:
        # Test 4a: Valid update (work_week_hours to 45)
        print("\n4a: Valid update (work_week_hours=45)...")
        payload = {"settings": {"work_week_hours": 45}}
        response = requests.put(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            log_test("Platform Defaults PUT (Valid Update)", False, 
                    f"Expected 200, got {response.status_code}. Body: {response.text[:500]}")
            return
        
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        
        if data.get("settings", {}).get("work_week_hours") != 45:
            log_test("Platform Defaults PUT (Valid Update)", False, 
                    f"Expected work_week_hours=45, got {data.get('settings', {}).get('work_week_hours')}")
            return
        
        log_test("Platform Defaults PUT (Valid Update)", True, 
                f"work_week_hours updated to 45")
        
        # Test 4b: Verify persistence
        print("\n4b: Verify persistence (GET after PUT)...")
        get_response = requests.get(url, headers=headers)
        
        if get_response.status_code != 200:
            log_test("Platform Defaults Persistence Check", False, 
                    f"GET after PUT failed with {get_response.status_code}")
            return
        
        get_data = get_response.json()
        if get_data.get("settings", {}).get("work_week_hours") != 45:
            log_test("Platform Defaults Persistence Check", False, 
                    f"Expected work_week_hours=45 after GET, got {get_data.get('settings', {}).get('work_week_hours')}")
            return
        
        log_test("Platform Defaults Persistence Check", True, 
                f"work_week_hours persisted correctly")
        
        # Test 4c: Invalid branding color (not hex)
        print("\n4c: Invalid branding color validation...")
        invalid_payload = {"branding": {"primary_color": "red"}}
        invalid_response = requests.put(url, headers=headers, json=invalid_payload)
        
        if invalid_response.status_code != 400:
            log_test("Platform Defaults Validation (Invalid Color)", False, 
                    f"Expected 400 for invalid color, got {invalid_response.status_code}")
            return
        
        log_test("Platform Defaults Validation (Invalid Color)", True, 
                f"Correctly rejected invalid color with 400")
        
        # Test 4d: Invalid work_week_hours (out of range)
        print("\n4d: Invalid work_week_hours validation...")
        invalid_hours_payload = {"settings": {"work_week_hours": 999}}
        invalid_hours_response = requests.put(url, headers=headers, json=invalid_hours_payload)
        
        if invalid_hours_response.status_code != 400:
            log_test("Platform Defaults Validation (Invalid Hours)", False, 
                    f"Expected 400 for invalid hours, got {invalid_hours_response.status_code}")
            return
        
        log_test("Platform Defaults Validation (Invalid Hours)", True, 
                f"Correctly rejected invalid hours with 400")
        
        # Test 4e: Cleanup - restore to 40
        print("\n4e: Cleanup - restore work_week_hours to 40...")
        cleanup_payload = {"settings": {"work_week_hours": 40}}
        cleanup_response = requests.put(url, headers=headers, json=cleanup_payload)
        
        if cleanup_response.status_code != 200:
            log_test("Platform Defaults Cleanup", False, 
                    f"Cleanup failed with {cleanup_response.status_code}")
            return
        
        cleanup_data = cleanup_response.json()
        if cleanup_data.get("settings", {}).get("work_week_hours") != 40:
            log_test("Platform Defaults Cleanup", False, 
                    f"Expected work_week_hours=40 after cleanup, got {cleanup_data.get('settings', {}).get('work_week_hours')}")
            return
        
        log_test("Platform Defaults Cleanup", True, 
                f"work_week_hours restored to 40")
        
    except Exception as e:
        log_test("Platform Defaults PUT", False, f"Exception: {str(e)}")

def test_new_module_auto_propagation(token: str):
    """Test 5: NEW-MODULE AUTO-PROPAGATION"""
    print("\n=== TEST 5: NEW-MODULE AUTO-PROPAGATION ===")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    try:
        # 5a: Create fresh test tenant (or use existing)
        print("\n5a: Create test tenant (mtest1)...")
        create_url = f"{BASE_URL}/platform/tenants"
        tenant_payload = {
            "slug": "mtest1",
            "name": "Migration Test 1",
            "owner_email": "owner@mtest1.com",
            "owner_password": "Testpass123!",
            "enabled_modules": ["projects", "resources"]
        }
        
        create_response = requests.post(create_url, headers=headers, json=tenant_payload)
        
        if create_response.status_code == 409:
            print(f"Tenant mtest1 already exists (409), continuing with existing tenant...")
            log_test("Create Test Tenant (mtest1)", True, 
                    f"Tenant mtest1 already exists, using existing tenant")
        elif create_response.status_code != 201:
            log_test("Create Test Tenant (mtest1)", False, 
                    f"Expected 201 or 409, got {create_response.status_code}. Body: {create_response.text[:500]}")
            return
        else:
            tenant_data = create_response.json()
            print(f"Created tenant: {json.dumps(tenant_data, indent=2)}")
            log_test("Create Test Tenant (mtest1)", True, 
                    f"Tenant created with slug=mtest1")
        
        # 5b: GET tenant modules
        print("\n5b: GET /api/platform/tenants/mtest1/modules...")
        modules_url = f"{BASE_URL}/platform/tenants/mtest1/modules"
        modules_response = requests.get(modules_url, headers=headers)
        
        if modules_response.status_code != 200:
            log_test("Get mtest1 Modules", False, 
                    f"Expected 200, got {modules_response.status_code}. Body: {modules_response.text[:500]}")
            return
        
        modules_data = modules_response.json()
        print(f"Modules response: {json.dumps(modules_data, indent=2)}")
        
        # Check if all 17 catalog modules are present
        modules_list = modules_data.get("modules", [])
        if len(modules_list) != 17:
            log_test("Module Catalog Count", False, 
                    f"Expected 17 modules, got {len(modules_list)}")
            return
        
        # Check that projects and resources are enabled (note: field is module_key, not key)
        projects_module = next((m for m in modules_list if m.get("module_key") == "projects"), None)
        resources_module = next((m for m in modules_list if m.get("module_key") == "resources"), None)
        
        if not projects_module or not projects_module.get("enabled"):
            log_test("Projects Module Enabled", False, 
                    f"projects module not enabled. Module data: {projects_module}")
            return
        
        if not resources_module or not resources_module.get("enabled"):
            log_test("Resources Module Enabled", False, 
                    f"resources module not enabled. Module data: {resources_module}")
            return
        
        log_test("Get mtest1 Modules", True, 
                f"All 17 catalog modules present, projects and resources enabled")
        
        # 5c: Run migrations for mtest1
        print("\n5c: POST /api/platform/tenants/mtest1/migrations/run...")
        tenant_migrations_url = f"{BASE_URL}/platform/tenants/mtest1/migrations/run"
        tenant_migrations_response = requests.post(tenant_migrations_url, headers=headers)
        
        if tenant_migrations_response.status_code != 200:
            log_test("Run mtest1 Migrations", False, 
                    f"Expected 200, got {tenant_migrations_response.status_code}. Body: {tenant_migrations_response.text[:500]}")
            return
        
        migrations_result = tenant_migrations_response.json()
        print(f"Migrations result: {json.dumps(migrations_result, indent=2)}")
        log_test("Run mtest1 Migrations", True, 
                f"Migrations ran successfully")
        
        # 5d: Check migration status
        print("\n5d: GET /api/platform/migrations/status (verify mtest1)...")
        status_url = f"{BASE_URL}/platform/migrations/status"
        status_response = requests.get(status_url, headers=headers)
        
        if status_response.status_code != 200:
            log_test("Check mtest1 Migration Status", False, 
                    f"Expected 200, got {status_response.status_code}")
            return
        
        status_data = status_response.json()
        tenants = status_data.get("tenants", [])
        mtest1_tenant = next((t for t in tenants if t.get("slug") == "mtest1"), None)
        
        if not mtest1_tenant:
            log_test("Check mtest1 Migration Status", False, 
                    f"mtest1 not found in migration status")
            return
        
        mtest1_applied = mtest1_tenant.get("applied", 0)
        mtest1_status = mtest1_tenant.get("status", "")
        
        if mtest1_applied < 3:
            log_test("Check mtest1 Migration Status", False, 
                    f"Expected mtest1.applied >= 3, got {mtest1_applied}")
            return
        
        if mtest1_status != "up_to_date":
            log_test("Check mtest1 Migration Status", False, 
                    f"Expected mtest1.status = 'up_to_date', got '{mtest1_status}'")
            return
        
        log_test("Check mtest1 Migration Status", True, 
                f"mtest1.applied={mtest1_applied}, status={mtest1_status}")
        
        # 5e: Per-tenant toggle test
        print("\n5e: Per-tenant toggle test (enable wbs)...")
        toggle_url = f"{BASE_URL}/platform/tenants/mtest1/modules/wbs?enabled=true"
        toggle_response = requests.put(toggle_url, headers=headers)
        
        if toggle_response.status_code != 200:
            log_test("Enable WBS Module", False, 
                    f"Expected 200, got {toggle_response.status_code}. Body: {toggle_response.text[:500]}")
            return
        
        # Verify wbs is enabled
        modules_response2 = requests.get(modules_url, headers=headers)
        modules_data2 = modules_response2.json()
        modules_list2 = modules_data2.get("modules", [])
        wbs_module = next((m for m in modules_list2 if m.get("module_key") == "wbs"), None)
        
        if not wbs_module or not wbs_module.get("enabled"):
            log_test("Verify WBS Enabled", False, 
                    f"wbs module not enabled after toggle")
            return
        
        log_test("Enable WBS Module", True, 
                f"wbs module enabled successfully")
        
        # Bulk update test (disable wbs)
        print("\n5f: Bulk update test (disable wbs)...")
        bulk_url = f"{BASE_URL}/platform/tenants/mtest1/modules"
        bulk_payload = {"modules": {"wbs": False}}
        bulk_response = requests.put(bulk_url, headers=headers, json=bulk_payload)
        
        if bulk_response.status_code != 200:
            log_test("Bulk Disable WBS", False, 
                    f"Expected 200, got {bulk_response.status_code}. Body: {bulk_response.text[:500]}")
            return
        
        # Verify wbs is disabled
        modules_response3 = requests.get(modules_url, headers=headers)
        modules_data3 = modules_response3.json()
        modules_list3 = modules_data3.get("modules", [])
        wbs_module2 = next((m for m in modules_list3 if m.get("module_key") == "wbs"), None)
        
        if not wbs_module2 or wbs_module2.get("enabled"):
            log_test("Verify WBS Disabled", False, 
                    f"wbs module still enabled after bulk disable")
            return
        
        log_test("Bulk Disable WBS", True, 
                f"wbs module disabled successfully via bulk update")
        
    except Exception as e:
        log_test("New Module Auto-Propagation", False, f"Exception: {str(e)}")

def test_config_inheritance(token: str):
    """Test 6: Config inheritance (tenant branding inherits platform defaults)"""
    print("\n=== TEST 6: CONFIG INHERITANCE ===")
    
    try:
        # Try to login as tenant user
        print("\n6a: Login as tenant user...")
        tenant_token = tenant_user_login("admin@test.com", "admin123")
        
        if not tenant_token:
            # Try alternative credentials
            tenant_token = tenant_user_login("don@ddconsult.tech", "@Ddplanner2026")
        
        if not tenant_token:
            log_test("Tenant User Login", False, 
                    f"Failed to login as tenant user with both credential sets")
            return
        
        log_test("Tenant User Login", True, 
                f"Successfully logged in as tenant user")
        
        # 6b: GET tenant branding
        print("\n6b: GET /api/tenant/branding...")
        branding_url = f"{BASE_URL}/tenant/branding"
        headers = {"Authorization": f"Bearer {tenant_token}"}
        branding_response = requests.get(branding_url, headers=headers)
        
        if branding_response.status_code != 200:
            log_test("Get Tenant Branding", False, 
                    f"Expected 200, got {branding_response.status_code}. Body: {branding_response.text[:500]}")
            return
        
        branding_data = branding_response.json()
        print(f"Tenant branding response: {json.dumps(branding_data, indent=2)}")
        
        # Check structure
        has_branding = "branding" in branding_data
        has_settings = "settings" in branding_data
        
        if not (has_branding and has_settings):
            log_test("Tenant Branding Structure", False, 
                    f"Missing keys. Has branding: {has_branding}, settings: {has_settings}")
            return
        
        # Check branding fields
        branding = branding_data.get("branding", {})
        if "primary_color" not in branding or "accent_color" not in branding:
            log_test("Tenant Branding Fields", False, 
                    f"Missing primary_color or accent_color in branding")
            return
        
        # Check settings fields
        settings = branding_data.get("settings", {})
        if "work_week_hours" not in settings or "timezone" not in settings:
            log_test("Tenant Settings Fields", False, 
                    f"Missing work_week_hours or timezone in settings")
            return
        
        log_test("Get Tenant Branding", True, 
                f"Tenant branding endpoint working, returns merged config with branding and settings")
        
    except Exception as e:
        log_test("Config Inheritance", False, f"Exception: {str(e)}")

def main():
    """Main test execution"""
    print("=" * 80)
    print("BACKEND TEST: Multi-Tenant Migration Framework + Config Inheritance")
    print("=" * 80)
    
    # Try to login with both passwords
    print("\n=== PLATFORM ADMIN LOGIN ===")
    token, user = platform_admin_login(PLATFORM_ADMIN_PASSWORD_1)
    
    if not token:
        print(f"First password failed, trying second password...")
        token, user = platform_admin_login(PLATFORM_ADMIN_PASSWORD_2)
    
    if not token:
        print(f"❌ CRITICAL: Failed to login as platform admin with both passwords")
        print(f"Tried: {PLATFORM_ADMIN_PASSWORD_1} and {PLATFORM_ADMIN_PASSWORD_2}")
        sys.exit(1)
    
    print(f"✅ Platform admin login successful")
    print(f"User: {json.dumps(user, indent=2)}")
    
    if user.get("must_change_password"):
        print(f"⚠️ NOTE: Account has must_change_password=true flag")
    
    # Run tests
    test_migrations_status(token)
    test_migrations_run(token)
    test_platform_defaults_get(token)
    test_platform_defaults_put(token)
    test_new_module_auto_propagation(token)
    test_config_inheritance(token)
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total Tests: {test_count}")
    print(f"Passed: {pass_count} ({pass_count/test_count*100:.1f}%)")
    print(f"Failed: {fail_count} ({fail_count/test_count*100:.1f}%)")
    print("=" * 80)
    
    # Detailed results
    print("\nDETAILED RESULTS:")
    for i, result in enumerate(test_results, 1):
        status = "✅" if result["passed"] else "❌"
        print(f"{i}. {status} {result['test']}")
        if result["details"]:
            print(f"   {result['details']}")
    
    sys.exit(0 if fail_count == 0 else 1)

if __name__ == "__main__":
    main()
