#!/usr/bin/env python3
"""
Bug Fix Verification — /api/tenant/modules ignoring toggles in flag=off mode

Tests the fix for the critical bug where GET /api/tenant/modules was returning
all modules as enabled=true even after platform admin toggled them to false.

Root cause: tenant.py was hardcoding all modules to true in backward-compat mode.
Fix: Now always reads actual state from tenant_modules collection.

Test sections:
- TARGETED FIX VERIFICATION (T1-T7): Focus on the specific bug
- FULL REGRESSION (A-E): Ensure no other functionality broke
"""
import requests
import sys
from typing import Dict, Any

BASE_URL = "https://a0ac7ee9-2785-4339-ad6f-6886af7a3f1a.preview.emergentagent.com/api"

# Test credentials
TENANT_ADMIN = {"username": "admin@test.com", "password": "admin123"}
PLATFORM_ADMIN = {"username": "don@ddconsult.tech", "password": "@Ddplanner2026"}

# Test results tracking
results = []
total_tests = 0
passed_tests = 0


def log_test(test_num: str, description: str, passed: bool, details: str = ""):
    """Log a test result."""
    global total_tests, passed_tests
    total_tests += 1
    if passed:
        passed_tests += 1
    
    status = "✅ PASS" if passed else "❌ FAIL"
    results.append(f"{test_num}. {description}: {status}")
    if details:
        results.append(f"   {details}")
    
    print(f"{status} - {test_num}: {description}")
    if details:
        print(f"   {details}")


def login_tenant_admin() -> str:
    """Login as tenant admin and return JWT token."""
    resp = requests.post(
        f"{BASE_URL}/auth/login",
        data=TENANT_ADMIN,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if resp.status_code == 200:
        return resp.json()["access_token"]
    raise Exception(f"Tenant admin login failed: {resp.status_code}")


def login_platform_admin() -> str:
    """Login as platform admin and return JWT token."""
    resp = requests.post(
        f"{BASE_URL}/platform/auth/login",
        data=PLATFORM_ADMIN,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if resp.status_code == 200:
        return resp.json()["access_token"]
    raise Exception(f"Platform admin login failed: {resp.status_code}")


def get_tenant_modules(tenant_token: str) -> Dict[str, Any]:
    """Get tenant modules endpoint."""
    resp = requests.get(
        f"{BASE_URL}/tenant/modules",
        headers={"Authorization": f"Bearer {tenant_token}"}
    )
    return resp


def toggle_module(platform_token: str, module_key: str, enabled: bool) -> Dict[str, Any]:
    """Toggle a single module via platform admin."""
    resp = requests.put(
        f"{BASE_URL}/platform/tenants/ddconsult/modules/{module_key}",
        params={"enabled": str(enabled).lower()},
        headers={"Authorization": f"Bearer {platform_token}"}
    )
    return resp


def bulk_toggle_modules(platform_token: str, modules: Dict[str, bool]) -> Dict[str, Any]:
    """Bulk toggle modules via platform admin."""
    resp = requests.put(
        f"{BASE_URL}/platform/tenants/ddconsult/modules",
        json={"modules": modules},
        headers={"Authorization": f"Bearer {platform_token}"}
    )
    return resp


def run_targeted_fix_verification():
    """Run T1-T7: Targeted fix verification tests."""
    print("\n" + "="*80)
    print("TARGETED FIX VERIFICATION (T1-T7)")
    print("="*80 + "\n")
    
    try:
        tenant_token = login_tenant_admin()
        platform_token = login_platform_admin()
    except Exception as e:
        print(f"❌ FATAL: Could not login: {e}")
        return
    
    # T1. Baseline - timesheets should be true initially
    resp = get_tenant_modules(tenant_token)
    if resp.status_code == 200:
        data = resp.json()
        timesheets_enabled = data.get("modules", {}).get("timesheets", None)
        log_test(
            "T1",
            "Baseline - GET /api/tenant/modules with admin JWT",
            resp.status_code == 200 and timesheets_enabled == True,
            f"HTTP {resp.status_code}, modules.timesheets={timesheets_enabled}"
        )
    else:
        log_test("T1", "Baseline - GET /api/tenant/modules", False, f"HTTP {resp.status_code}")
    
    # T2. Platform admin toggles timesheets OFF
    resp = toggle_module(platform_token, "timesheets", False)
    log_test(
        "T2",
        "Platform admin toggles timesheets OFF",
        resp.status_code == 200,
        f"HTTP {resp.status_code}"
    )
    
    # T3. THE FIX - timesheets should now be false (this was the bug)
    resp = get_tenant_modules(tenant_token)
    if resp.status_code == 200:
        data = resp.json()
        timesheets_enabled = data.get("modules", {}).get("timesheets", None)
        log_test(
            "T3",
            "**THE FIX** - GET /api/tenant/modules shows timesheets=false",
            resp.status_code == 200 and timesheets_enabled == False,
            f"HTTP {resp.status_code}, modules.timesheets={timesheets_enabled} (MUST BE FALSE)"
        )
    else:
        log_test("T3", "**THE FIX** - GET /api/tenant/modules", False, f"HTTP {resp.status_code}")
    
    # T4. Toggle back ON
    resp = toggle_module(platform_token, "timesheets", True)
    log_test(
        "T4",
        "Toggle timesheets back ON",
        resp.status_code == 200,
        f"HTTP {resp.status_code}"
    )
    
    # T5. Revert verified - timesheets should be true again
    resp = get_tenant_modules(tenant_token)
    if resp.status_code == 200:
        data = resp.json()
        timesheets_enabled = data.get("modules", {}).get("timesheets", None)
        log_test(
            "T5",
            "Revert verified - timesheets back to true",
            resp.status_code == 200 and timesheets_enabled == True,
            f"HTTP {resp.status_code}, modules.timesheets={timesheets_enabled}"
        )
    else:
        log_test("T5", "Revert verified", False, f"HTTP {resp.status_code}")
    
    # T6. Response multi_tenant_enabled field
    resp = get_tenant_modules(tenant_token)
    if resp.status_code == 200:
        data = resp.json()
        mte = data.get("multi_tenant_enabled", None)
        log_test(
            "T6",
            "Response multi_tenant_enabled field is false",
            resp.status_code == 200 and mte == False,
            f"HTTP {resp.status_code}, multi_tenant_enabled={mte}"
        )
    else:
        log_test("T6", "Response multi_tenant_enabled field", False, f"HTTP {resp.status_code}")
    
    # T7. Bulk toggle also affects tenant endpoint
    # First, toggle reports and ai_intelligence to false
    resp = bulk_toggle_modules(platform_token, {"reports": False, "ai_intelligence": False})
    bulk_success = resp.status_code == 200
    
    # Then check tenant endpoint
    resp = get_tenant_modules(tenant_token)
    if resp.status_code == 200 and bulk_success:
        data = resp.json()
        reports = data.get("modules", {}).get("reports", None)
        ai_intel = data.get("modules", {}).get("ai_intelligence", None)
        log_test(
            "T7",
            "Bulk toggle affects tenant endpoint",
            reports == False and ai_intel == False,
            f"HTTP {resp.status_code}, reports={reports}, ai_intelligence={ai_intel}"
        )
        
        # Revert back to true
        bulk_toggle_modules(platform_token, {"reports": True, "ai_intelligence": True})
    else:
        log_test("T7", "Bulk toggle affects tenant endpoint", False, f"HTTP {resp.status_code}")


def run_full_regression():
    """Run A-E: Full regression suite."""
    print("\n" + "="*80)
    print("FULL REGRESSION (A-E)")
    print("="*80 + "\n")
    
    try:
        tenant_token = login_tenant_admin()
        platform_token = login_platform_admin()
    except Exception as e:
        print(f"❌ FATAL: Could not login: {e}")
        return
    
    # A. Auth & core reads
    print("\n--- A. Auth & Core Reads ---")
    
    # A1. Login admin@test.com
    resp = requests.post(
        f"{BASE_URL}/auth/login",
        data=TENANT_ADMIN,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    log_test("A1", "Login admin@test.com", resp.status_code == 200, f"HTTP {resp.status_code}")
    
    # A2. GET /api/auth/me
    resp = requests.get(f"{BASE_URL}/auth/me", headers={"Authorization": f"Bearer {tenant_token}"})
    log_test("A2", "GET /api/auth/me", resp.status_code == 200, f"HTTP {resp.status_code}")
    
    # A3. GET /api/projects
    resp = requests.get(f"{BASE_URL}/projects", headers={"Authorization": f"Bearer {tenant_token}"})
    if resp.status_code == 200:
        count = len(resp.json())
        log_test("A3", "GET /api/projects", count == 4, f"HTTP {resp.status_code}, {count} projects")
    else:
        log_test("A3", "GET /api/projects", False, f"HTTP {resp.status_code}")
    
    # A4. GET /api/resources
    resp = requests.get(f"{BASE_URL}/resources", headers={"Authorization": f"Bearer {tenant_token}"})
    if resp.status_code == 200:
        count = len(resp.json())
        log_test("A4", "GET /api/resources", count == 5, f"HTTP {resp.status_code}, {count} resources")
    else:
        log_test("A4", "GET /api/resources", False, f"HTTP {resp.status_code}")
    
    # A5. GET /api/allocations
    resp = requests.get(f"{BASE_URL}/allocations", headers={"Authorization": f"Bearer {tenant_token}"})
    if resp.status_code == 200:
        count = len(resp.json())
        log_test("A5", "GET /api/allocations", count == 10, f"HTTP {resp.status_code}, {count} allocations")
    else:
        log_test("A5", "GET /api/allocations", False, f"HTTP {resp.status_code}")
    
    # A6. GET /api/portfolio
    resp = requests.get(f"{BASE_URL}/portfolio", headers={"Authorization": f"Bearer {tenant_token}"})
    log_test("A6", "GET /api/portfolio", resp.status_code == 200, f"HTTP {resp.status_code}")
    
    # A7. GET /api/dashboard/action-items
    resp = requests.get(f"{BASE_URL}/dashboard/action-items", headers={"Authorization": f"Bearer {tenant_token}"})
    log_test("A7", "GET /api/dashboard/action-items", resp.status_code == 200, f"HTTP {resp.status_code}")
    
    # B. Platform auth still works
    print("\n--- B. Platform Auth ---")
    
    # B8. POST /api/platform/auth/login
    resp = requests.post(
        f"{BASE_URL}/platform/auth/login",
        data=PLATFORM_ADMIN,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    log_test("B8", "POST /api/platform/auth/login", resp.status_code == 200, f"HTTP {resp.status_code}")
    
    # B9. GET /api/platform/auth/me
    resp = requests.get(f"{BASE_URL}/platform/auth/me", headers={"Authorization": f"Bearer {platform_token}"})
    log_test("B9", "GET /api/platform/auth/me", resp.status_code == 200, f"HTTP {resp.status_code}")
    
    # B10. GET /api/platform/tenants
    resp = requests.get(f"{BASE_URL}/platform/tenants", headers={"Authorization": f"Bearer {platform_token}"})
    if resp.status_code == 200:
        count = len(resp.json())
        log_test("B10", "GET /api/platform/tenants", count == 1, f"HTTP {resp.status_code}, {count} tenant")
    else:
        log_test("B10", "GET /api/platform/tenants", False, f"HTTP {resp.status_code}")
    
    # B11. GET /api/platform/modules
    resp = requests.get(f"{BASE_URL}/platform/modules", headers={"Authorization": f"Bearer {platform_token}"})
    if resp.status_code == 200:
        count = len(resp.json())
        log_test("B11", "GET /api/platform/modules", count == 17, f"HTTP {resp.status_code}, {count} modules")
    else:
        log_test("B11", "GET /api/platform/modules", False, f"HTTP {resp.status_code}")
    
    # C. Dependency validation still works
    print("\n--- C. Dependency Validation ---")
    
    # C12. Try to disable projects while enabling wbs (should fail)
    resp = bulk_toggle_modules(platform_token, {"projects": False, "wbs": True})
    if resp.status_code == 400:
        error_msg = resp.json().get("detail", "")
        has_dependency_error = "depends on" in error_msg.lower() or "dependency" in error_msg.lower()
        log_test("C12", "Dependency validation blocks invalid toggle", has_dependency_error, f"HTTP {resp.status_code}, error: {error_msg}")
    else:
        log_test("C12", "Dependency validation blocks invalid toggle", False, f"HTTP {resp.status_code} (expected 400)")
    
    # D. Authorization still enforced
    print("\n--- D. Authorization ---")
    
    # D13. Tenant admin cannot toggle modules
    resp = toggle_module(tenant_token, "timesheets", False)
    log_test("D13", "Tenant admin cannot toggle modules (403)", resp.status_code == 403, f"HTTP {resp.status_code}")
    
    # D14. No auth returns 401
    resp = requests.put(f"{BASE_URL}/platform/tenants/ddconsult/modules/timesheets?enabled=false")
    log_test("D14", "No auth returns 401", resp.status_code == 401, f"HTTP {resp.status_code}")
    
    # D15. GET /api/tenant/modules without auth returns 401
    resp = requests.get(f"{BASE_URL}/tenant/modules")
    log_test("D15", "GET /api/tenant/modules without auth returns 401", resp.status_code == 401, f"HTTP {resp.status_code}")
    
    # E. Sanity
    print("\n--- E. Sanity Checks ---")
    
    # E16. GET /api/health
    resp = requests.get(f"{BASE_URL}/health")
    log_test("E16", "GET /api/health", resp.status_code == 200, f"HTTP {resp.status_code}")
    
    # E17. GET /api/platform/status
    resp = requests.get(f"{BASE_URL}/platform/status")
    if resp.status_code == 200:
        data = resp.json()
        mte = data.get("multi_tenant_enabled", None)
        log_test("E17", "GET /api/platform/status", mte == False, f"HTTP {resp.status_code}, multi_tenant_enabled={mte}")
    else:
        log_test("E17", "GET /api/platform/status", False, f"HTTP {resp.status_code}")
    
    # E18. Backend log check
    print("\n   Checking backend logs for errors...")
    import subprocess
    try:
        result = subprocess.run(
            ["tail", "-n", "200", "/var/log/supervisor/backend.err.log"],
            capture_output=True,
            text=True,
            timeout=5
        )
        log_content = result.stdout.lower()
        
        # Check for critical errors
        has_errors = any(x in log_content for x in [
            "attributeerror",
            "typeerror",
            "traceback (most recent call last)",
            "500 internal server error"
        ])
        
        log_test("E18", "Backend logs clean (no critical errors)", not has_errors, 
                "No AttributeError, TypeError, or 500 errors found" if not has_errors else "ERRORS FOUND in logs")
    except Exception as e:
        log_test("E18", "Backend logs check", False, f"Could not check logs: {e}")


def print_summary():
    """Print final summary."""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80 + "\n")
    
    for line in results:
        print(line)
    
    print(f"\n{'='*80}")
    if total_tests > 0:
        print(f"TOTAL: {passed_tests}/{total_tests} tests passed ({passed_tests/total_tests*100:.1f}%)")
    else:
        print("TOTAL: 0/0 tests (no tests were run)")
        return False
    
    # Determine verdict
    if passed_tests == total_tests:
        verdict = "PASS ✅"
        verdict_detail = "All tests passed. Bug fix verified and no regressions detected."
    elif passed_tests >= total_tests * 0.95:
        verdict = "PARTIAL PASS ⚠️"
        verdict_detail = f"{total_tests - passed_tests} test(s) failed. Review failures above."
    else:
        verdict = "FAIL ❌"
        verdict_detail = f"{total_tests - passed_tests} test(s) failed. Critical issues detected."
    
    print(f"\nREGRESSION VERDICT: {verdict}")
    print(f"{verdict_detail}")
    print("="*80 + "\n")
    
    # Check if T3 (the critical bug fix) passed
    t3_result = [r for r in results if r.startswith("T3.")]
    if t3_result and "✅ PASS" in t3_result[0]:
        print("🎯 BUG FIX VERIFIED: T3 passed - tenant endpoint now respects module toggles in flag=off mode")
    elif t3_result and "❌ FAIL" in t3_result[0]:
        print("⚠️ BUG FIX NOT VERIFIED: T3 failed - tenant endpoint still not respecting toggles")
    
    return passed_tests == total_tests


if __name__ == "__main__":
    print("="*80)
    print("BUG FIX VERIFICATION TEST SUITE")
    print("Testing: /api/tenant/modules ignoring toggles in flag=off mode")
    print("="*80)
    
    run_targeted_fix_verification()
    run_full_regression()
    
    success = print_summary()
    sys.exit(0 if success else 1)
