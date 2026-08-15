#!/usr/bin/env python3
"""
Bug Fix Verification Test for GET /api/tenant/modules
Testing that module toggles are respected when MULTI_TENANT_ENABLED=false
"""

import requests
import sys

BASE_URL = "https://a0ac7ee9-2785-4339-ad6f-6886af7a3f1a.preview.emergentagent.com"

# Credentials
TENANT_ADMIN_EMAIL = "admin@test.com"
TENANT_ADMIN_PASSWORD = "admin123"
PLATFORM_ADMIN_EMAIL = "don@ddconsult.tech"
PLATFORM_ADMIN_PASSWORD = "Welcome123!"

def print_test(num, description):
    print(f"\n{'='*80}")
    print(f"Test {num}: {description}")
    print('='*80)

def print_result(passed, status_code, details=""):
    result = "PASS" if passed else "FAIL"
    print(f"Result: {result} (HTTP {status_code})")
    if details:
        print(f"Details: {details}")
    return passed

# Test 1: Login as tenant admin
print_test(1, "Login as tenant admin (admin@test.com/admin123)")
try:
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": TENANT_ADMIN_EMAIL, "password": TENANT_ADMIN_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    test1_pass = response.status_code == 200
    if test1_pass:
        TENANT_TOKEN = response.json()["access_token"]
        print_result(True, response.status_code, f"Token obtained: {TENANT_TOKEN[:20]}...")
    else:
        print_result(False, response.status_code, response.text)
        sys.exit(1)
except Exception as e:
    print_result(False, 0, f"Exception: {e}")
    sys.exit(1)

# Test 2: Login as platform admin
print_test(2, "Login as platform admin (don@ddconsult.tech/Welcome123!)")
try:
    response = requests.post(
        f"{BASE_URL}/api/platform/auth/login",
        data={"username": PLATFORM_ADMIN_EMAIL, "password": PLATFORM_ADMIN_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    test2_pass = response.status_code == 200
    if test2_pass:
        PLATFORM_TOKEN = response.json()["access_token"]
        print_result(True, response.status_code, f"Token obtained: {PLATFORM_TOKEN[:20]}...")
    else:
        print_result(False, response.status_code, response.text)
        sys.exit(1)
except Exception as e:
    print_result(False, 0, f"Exception: {e}")
    sys.exit(1)

# Test 3: GET /api/tenant/modules with TENANT_TOKEN (initial state)
print_test(3, "GET /api/tenant/modules with TENANT_TOKEN (expect timesheets=true)")
try:
    response = requests.get(
        f"{BASE_URL}/api/tenant/modules",
        headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
    )
    test3_pass = response.status_code == 200
    if test3_pass:
        data = response.json()
        timesheets_enabled = data.get("modules", {}).get("timesheets", False)
        test3_pass = timesheets_enabled == True
        print_result(test3_pass, response.status_code, f"timesheets={timesheets_enabled}, expected=true")
    else:
        print_result(False, response.status_code, response.text)
        sys.exit(1)
except Exception as e:
    print_result(False, 0, f"Exception: {e}")
    sys.exit(1)

# Test 4: PUT /api/platform/tenants/ddconsult/modules/timesheets?enabled=false
print_test(4, "PUT /api/platform/tenants/ddconsult/modules/timesheets?enabled=false with PLATFORM_TOKEN")
try:
    response = requests.put(
        f"{BASE_URL}/api/platform/tenants/ddconsult/modules/timesheets?enabled=false",
        headers={"Authorization": f"Bearer {PLATFORM_TOKEN}"}
    )
    test4_pass = response.status_code == 200
    if test4_pass:
        data = response.json()
        print_result(True, response.status_code, f"Response: {data}")
    else:
        print_result(False, response.status_code, response.text)
        sys.exit(1)
except Exception as e:
    print_result(False, 0, f"Exception: {e}")
    sys.exit(1)

# Test 5: THE CRITICAL TEST - GET /api/tenant/modules again (should show timesheets=false)
print_test(5, "THE CRITICAL TEST: GET /api/tenant/modules with TENANT_TOKEN (expect timesheets=FALSE)")
try:
    response = requests.get(
        f"{BASE_URL}/api/tenant/modules",
        headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
    )
    test5_pass = response.status_code == 200
    if test5_pass:
        data = response.json()
        timesheets_enabled = data.get("modules", {}).get("timesheets", True)
        test5_pass = timesheets_enabled == False
        print_result(test5_pass, response.status_code, f"timesheets={timesheets_enabled}, expected=FALSE — THIS IS THE FIX VERIFICATION")
        if not test5_pass:
            print("❌ BUG STILL PRESENT: Tenant endpoint not respecting module toggle!")
    else:
        print_result(False, response.status_code, response.text)
        sys.exit(1)
except Exception as e:
    print_result(False, 0, f"Exception: {e}")
    sys.exit(1)

# Test 6: Cleanup - PUT enabled=true
print_test(6, "Cleanup: PUT /api/platform/tenants/ddconsult/modules/timesheets?enabled=true")
try:
    response = requests.put(
        f"{BASE_URL}/api/platform/tenants/ddconsult/modules/timesheets?enabled=true",
        headers={"Authorization": f"Bearer {PLATFORM_TOKEN}"}
    )
    test6_pass = response.status_code == 200
    if test6_pass:
        # Verify it's back to true
        response2 = requests.get(
            f"{BASE_URL}/api/tenant/modules",
            headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
        )
        if response2.status_code == 200:
            data = response2.json()
            timesheets_enabled = data.get("modules", {}).get("timesheets", False)
            test6_pass = timesheets_enabled == True
            print_result(test6_pass, response.status_code, f"timesheets={timesheets_enabled} after cleanup, expected=true")
        else:
            print_result(False, response2.status_code, "Failed to verify cleanup")
    else:
        print_result(False, response.status_code, response.text)
except Exception as e:
    print_result(False, 0, f"Exception: {e}")

# Test 7: Regression - GET /api/projects (expect 4)
print_test(7, "Regression: GET /api/projects (expect 4 projects)")
try:
    response = requests.get(
        f"{BASE_URL}/api/projects",
        headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
    )
    test7_pass = response.status_code == 200
    if test7_pass:
        data = response.json()
        projects_count = len(data)
        test7_pass = projects_count == 4
        print_result(test7_pass, response.status_code, f"projects_count={projects_count}, expected=4")
    else:
        print_result(False, response.status_code, response.text)
except Exception as e:
    print_result(False, 0, f"Exception: {e}")

# Test 8: Regression - GET /api/resources (expect 5)
print_test(8, "Regression: GET /api/resources (expect 5 resources)")
try:
    response = requests.get(
        f"{BASE_URL}/api/resources",
        headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
    )
    test8_pass = response.status_code == 200
    if test8_pass:
        data = response.json()
        resources_count = len(data)
        test8_pass = resources_count == 5
        print_result(test8_pass, response.status_code, f"resources_count={resources_count}, expected=5")
    else:
        print_result(False, response.status_code, response.text)
except Exception as e:
    print_result(False, 0, f"Exception: {e}")

# Test 9: Regression - GET /api/allocations (expect 10)
print_test(9, "Regression: GET /api/allocations (expect 10 allocations)")
try:
    response = requests.get(
        f"{BASE_URL}/api/allocations",
        headers={"Authorization": f"Bearer {TENANT_TOKEN}"}
    )
    test9_pass = response.status_code == 200
    if test9_pass:
        data = response.json()
        allocations_count = len(data)
        test9_pass = allocations_count == 10
        print_result(test9_pass, response.status_code, f"allocations_count={allocations_count}, expected=10")
    else:
        print_result(False, response.status_code, response.text)
except Exception as e:
    print_result(False, 0, f"Exception: {e}")

# Test 10: Regression - GET /api/health
print_test(10, "Regression: GET /api/health")
try:
    response = requests.get(f"{BASE_URL}/api/health")
    test10_pass = response.status_code == 200
    if test10_pass:
        data = response.json()
        print_result(True, response.status_code, f"Health: {data}")
    else:
        print_result(False, response.status_code, response.text)
except Exception as e:
    print_result(False, 0, f"Exception: {e}")

# Final verdict
print("\n" + "="*80)
print("FINAL VERDICT")
print("="*80)

all_tests = [test1_pass, test2_pass, test3_pass, test4_pass, test5_pass, test6_pass, test7_pass, test8_pass, test9_pass, test10_pass]
passed_count = sum(all_tests)
total_count = len(all_tests)

print(f"Tests passed: {passed_count}/{total_count}")
print(f"\nTest 1 (Tenant login): {'PASS' if test1_pass else 'FAIL'}")
print(f"Test 2 (Platform login): {'PASS' if test2_pass else 'FAIL'}")
print(f"Test 3 (Initial state timesheets=true): {'PASS' if test3_pass else 'FAIL'}")
print(f"Test 4 (Toggle timesheets to false): {'PASS' if test4_pass else 'FAIL'}")
print(f"Test 5 (THE FIX - timesheets=false reflected): {'PASS' if test5_pass else 'FAIL'} ⭐")
print(f"Test 6 (Cleanup - timesheets back to true): {'PASS' if test6_pass else 'FAIL'}")
print(f"Test 7 (Projects count=4): {'PASS' if test7_pass else 'FAIL'}")
print(f"Test 8 (Resources count=5): {'PASS' if test8_pass else 'FAIL'}")
print(f"Test 9 (Allocations count=10): {'PASS' if test9_pass else 'FAIL'}")
print(f"Test 10 (Health check): {'PASS' if test10_pass else 'FAIL'}")

if all(all_tests):
    print("\n✅ VERDICT: PASS - Bug fix verified successfully!")
    sys.exit(0)
else:
    print("\n❌ VERDICT: FAIL - Some tests failed")
    sys.exit(1)
