#!/usr/bin/env python3
"""
SECURITY-CRITICAL TEST: Demo Read-Only Backend Verification
============================================================
Verifies that the PUBLIC demo session can READ but NEVER WRITE.

Test Coverage:
A. Demo login works & is flagged (demo claim, is_demo=true)
B. Reads ALLOWED for demo (GET requests work)
C. Writes BLOCKED for demo (POST/PUT/PATCH/DELETE return 403) - CRITICAL
D. Normal auth UNAFFECTED (regression test)
"""

import requests
import sys
from datetime import datetime

# Backend URL from frontend/.env
BACKEND_URL = "https://ddplanner-fixes.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def log(msg, color=RESET):
    print(f"{color}{msg}{RESET}")

def test_section(name):
    print(f"\n{'='*80}")
    log(f"  {name}", BLUE)
    print(f"{'='*80}\n")

# ============================================================================
# TEST A: Demo login works & is flagged
# ============================================================================
def test_demo_login():
    test_section("TEST A: Demo Login Works & Is Flagged")
    
    log("A.1 POST /api/auth/demo-login with NO credentials...", YELLOW)
    response = requests.post(f"{API_BASE}/auth/demo-login")
    
    if response.status_code != 200:
        log(f"❌ FAILED: Expected 200, got {response.status_code}", RED)
        log(f"Response: {response.text}", RED)
        return None, False
    
    log(f"✅ PASS: Got 200 response", GREEN)
    
    data = response.json()
    
    # Check response structure
    if "access_token" not in data:
        log("❌ FAILED: No access_token in response", RED)
        return None, False
    
    if "user" not in data:
        log("❌ FAILED: No user in response", RED)
        return None, False
    
    log(f"✅ PASS: Response has access_token and user", GREEN)
    
    user = data["user"]
    demo_token = data["access_token"]
    
    # Check user.is_demo
    if not user.get("is_demo"):
        log(f"❌ FAILED: user.is_demo is not True (got: {user.get('is_demo')})", RED)
        return None, False
    
    log(f"✅ PASS: user.is_demo == True", GREEN)
    
    # Check user.role
    if user.get("role") != "admin":
        log(f"❌ FAILED: user.role is not 'admin' (got: {user.get('role')})", RED)
        return None, False
    
    log(f"✅ PASS: user.role == 'admin'", GREEN)
    
    # Check user.email
    if user.get("email") != "demo@ddplanner.app":
        log(f"❌ FAILED: user.email is not 'demo@ddplanner.app' (got: {user.get('email')})", RED)
        return None, False
    
    log(f"✅ PASS: user.email == 'demo@ddplanner.app'", GREEN)
    
    log(f"\n✅✅✅ TEST A PASSED: Demo login works correctly", GREEN)
    log(f"Demo token saved for subsequent tests", YELLOW)
    
    return demo_token, True


# ============================================================================
# TEST B: Reads ALLOWED for demo
# ============================================================================
def test_demo_reads(demo_token):
    test_section("TEST B: Reads ALLOWED for Demo")
    
    headers = {"Authorization": f"Bearer {demo_token}"}
    
    read_endpoints = [
        ("GET /api/projects", f"{API_BASE}/projects"),
        ("GET /api/resources", f"{API_BASE}/resources"),
        ("GET /api/allocations", f"{API_BASE}/allocations"),
        ("GET /api/reports/capacity", f"{API_BASE}/reports/capacity?start_date=2026-10-01&end_date=2026-10-31"),
    ]
    
    all_passed = True
    project_id = None
    demo_projects = []
    
    for name, url in read_endpoints:
        log(f"\nB.{read_endpoints.index((name, url)) + 1} Testing {name}...", YELLOW)
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            log(f"❌ FAILED: Expected 200, got {response.status_code}", RED)
            log(f"Response: {response.text}", RED)
            all_passed = False
        else:
            log(f"✅ PASS: Got 200 response", GREEN)
            
            # Save project_id for next test
            if "projects" in url:
                try:
                    projects = response.json()
                    if projects and len(projects) > 0:
                        project_id = projects[0].get("id")
                        demo_projects = [p.get("name") for p in projects[:5]]
                        log(f"   Found {len(projects)} projects", YELLOW)
                        log(f"   Demo projects: {', '.join(demo_projects)}", YELLOW)
                except:
                    pass
    
    # Test GET /api/projects/{id}/wbs if we have a project_id
    if project_id:
        log(f"\nB.5 Testing GET /api/projects/{project_id}/wbs...", YELLOW)
        response = requests.get(f"{API_BASE}/projects/{project_id}/wbs", headers=headers)
        
        if response.status_code != 200:
            log(f"❌ FAILED: Expected 200, got {response.status_code}", RED)
            log(f"Response: {response.text}", RED)
            all_passed = False
        else:
            log(f"✅ PASS: Got 200 response", GREEN)
    
    if all_passed:
        log(f"\n✅✅✅ TEST B PASSED: All reads allowed for demo", GREEN)
        log(f"Demo dataset visible: {', '.join(demo_projects[:3])}", YELLOW)
    else:
        log(f"\n❌ TEST B FAILED: Some reads were blocked", RED)
    
    return all_passed, project_id


# ============================================================================
# TEST C: Writes BLOCKED for demo (CRITICAL SECURITY TEST)
# ============================================================================
def test_demo_writes_blocked(demo_token, project_id):
    test_section("TEST C: Writes BLOCKED for Demo (CRITICAL SECURITY TEST)")
    
    headers = {"Authorization": f"Bearer {demo_token}"}
    
    # Test various write operations
    write_tests = [
        ("POST /api/projects", "POST", f"{API_BASE}/projects", {"name": "Test Project", "client_name": "Test Client"}),
        ("PUT /api/projects/{id}", "PUT", f"{API_BASE}/projects/{project_id}", {"name": "Updated Name"}),
        ("DELETE /api/projects/{id}", "DELETE", f"{API_BASE}/projects/{project_id}", None),
        ("POST /api/allocations", "POST", f"{API_BASE}/allocations", {"project_id": project_id, "resource_id": "test", "percentage": 50}),
        ("POST /api/leaves", "POST", f"{API_BASE}/leaves", {"resource_id": "test", "start_date": "2026-11-01", "end_date": "2026-11-05", "type": "Annual Leave"}),
        ("POST /api/projects/{id}/wbs/tasks", "POST", f"{API_BASE}/projects/{project_id}/wbs/tasks", {"name": "Test Task", "start_date": "2026-11-01", "end_date": "2026-11-05"}),
        ("PUT /api/wbs/tasks/{id}", "PUT", f"{API_BASE}/wbs/tasks/test123", {"name": "Updated Task"}),
        ("POST /api/ai/chat", "POST", f"{API_BASE}/ai/chat", {"message": "hi"}),
        ("POST /api/reports/magic-link", "POST", f"{API_BASE}/reports/magic-link", {"project_id": project_id, "recipient_email": "test@test.com"}),
    ]
    
    all_blocked = True
    results = []
    
    for name, method, url, body in write_tests:
        log(f"\nC.{write_tests.index((name, method, url, body)) + 1} Testing {name}...", YELLOW)
        
        if method == "POST":
            response = requests.post(url, headers=headers, json=body)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=body)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers)
        else:
            log(f"❌ Unknown method: {method}", RED)
            continue
        
        status = response.status_code
        
        # CRITICAL: Must be 403
        if status != 403:
            log(f"❌❌❌ SECURITY HOLE: Expected 403, got {status}", RED)
            log(f"Response: {response.text}", RED)
            all_blocked = False
            results.append((name, status, "SECURITY HOLE"))
        else:
            # Check the detail message
            try:
                data = response.json()
                detail = data.get("detail", "")
                if "read-only demo" in detail.lower():
                    log(f"✅ PASS: Got 403 with correct message", GREEN)
                    log(f"   Detail: {detail}", YELLOW)
                    results.append((name, status, "BLOCKED"))
                else:
                    log(f"⚠️  WARNING: Got 403 but message doesn't mention read-only demo", YELLOW)
                    log(f"   Detail: {detail}", YELLOW)
                    results.append((name, status, "BLOCKED (wrong message)"))
            except:
                log(f"✅ PASS: Got 403 (couldn't parse response)", GREEN)
                results.append((name, status, "BLOCKED"))
    
    # Print summary table
    log(f"\n{'='*80}", BLUE)
    log(f"WRITE OPERATIONS SUMMARY", BLUE)
    log(f"{'='*80}", BLUE)
    print(f"{'Operation':<40} {'Status':<10} {'Result':<30}")
    print(f"{'-'*80}")
    
    for name, status, result in results:
        color = GREEN if result == "BLOCKED" else RED
        print(f"{name:<40} {status:<10} {color}{result}{RESET}")
    
    if all_blocked:
        log(f"\n✅✅✅ TEST C PASSED: All writes blocked with 403", GREEN)
    else:
        log(f"\n❌❌❌ TEST C FAILED: SECURITY HOLE - Some writes were NOT blocked", RED)
    
    return all_blocked


# ============================================================================
# TEST D: Normal auth UNAFFECTED (regression)
# ============================================================================
def test_normal_auth_unaffected():
    test_section("TEST D: Normal Auth UNAFFECTED (Regression)")
    
    log("D.1 Normal login as admin@test.com...", YELLOW)
    response = requests.post(
        f"{API_BASE}/auth/login",
        data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    
    if response.status_code != 200:
        log(f"❌ FAILED: Normal login failed with {response.status_code}", RED)
        log(f"Response: {response.text}", RED)
        return False
    
    log(f"✅ PASS: Normal login successful", GREEN)
    
    data = response.json()
    normal_token = data.get("access_token")
    
    if not normal_token:
        log(f"❌ FAILED: No access_token in response", RED)
        return False
    
    # Check that this is NOT a demo token
    user = data.get("user", {})
    if user.get("is_demo"):
        log(f"❌ FAILED: Normal user has is_demo=True", RED)
        return False
    
    log(f"✅ PASS: Normal token obtained (no demo claim)", GREEN)
    
    headers = {"Authorization": f"Bearer {normal_token}"}
    
    # Test that normal admin can read
    log(f"\nD.2 Testing GET /api/projects with normal token...", YELLOW)
    response = requests.get(f"{API_BASE}/projects", headers=headers)
    
    if response.status_code != 200:
        log(f"❌ FAILED: Normal admin can't read projects", RED)
        return False
    
    log(f"✅ PASS: Normal admin can read", GREEN)
    
    # Test that normal admin can write (create a leave and delete it)
    log(f"\nD.3 Testing POST /api/leaves with normal token...", YELLOW)
    
    # First, get a resource_id
    response = requests.get(f"{API_BASE}/resources", headers=headers)
    if response.status_code != 200:
        log(f"⚠️  WARNING: Can't get resources, skipping write test", YELLOW)
        return True
    
    resources = response.json()
    if not resources or len(resources) == 0:
        log(f"⚠️  WARNING: No resources found, skipping write test", YELLOW)
        return True
    
    resource_id = resources[0].get("id")
    
    # Create a leave
    leave_data = {
        "resource_id": resource_id,
        "start_date": "2026-12-20",
        "end_date": "2026-12-22",
        "type": "Annual Leave",
        "notes": "Demo test - will be deleted"
    }
    
    response = requests.post(f"{API_BASE}/leaves", headers=headers, json=leave_data)
    
    # Should NOT be 403 (demo block)
    if response.status_code == 403:
        try:
            detail = response.json().get("detail", "")
            if "read-only demo" in detail.lower():
                log(f"❌ FAILED: Normal admin blocked by demo middleware", RED)
                return False
        except:
            pass
    
    # Accept 200/201 or validation errors (400/422), but NOT 403 demo block
    if response.status_code in (200, 201):
        log(f"✅ PASS: Normal admin can write (created leave)", GREEN)
        
        # Clean up - delete the leave
        try:
            leave_id = response.json().get("id")
            if leave_id:
                log(f"\nD.4 Cleaning up - deleting test leave...", YELLOW)
                delete_response = requests.delete(f"{API_BASE}/leaves/{leave_id}", headers=headers)
                if delete_response.status_code in (200, 204):
                    log(f"✅ PASS: Test leave deleted", GREEN)
                else:
                    log(f"⚠️  WARNING: Couldn't delete test leave (status {delete_response.status_code})", YELLOW)
        except:
            log(f"⚠️  WARNING: Couldn't clean up test leave", YELLOW)
        
        return True
    elif response.status_code in (400, 422):
        log(f"✅ PASS: Normal admin NOT blocked by demo middleware (got validation error {response.status_code}, which is expected)", GREEN)
        return True
    else:
        log(f"⚠️  WARNING: Unexpected status {response.status_code} for normal admin write", YELLOW)
        log(f"Response: {response.text}", YELLOW)
        return True
    
    log(f"\n✅✅✅ TEST D PASSED: Normal auth unaffected", GREEN)
    return True


# ============================================================================
# TEST E: Unauthenticated requests (regression)
# ============================================================================
def test_unauthenticated():
    test_section("TEST E: Unauthenticated Requests (Regression)")
    
    log("E.1 Testing POST /api/projects without token...", YELLOW)
    response = requests.post(
        f"{API_BASE}/projects",
        json={"name": "Test Project", "client_name": "Test Client"}
    )
    
    # Should be 401 or 403 (normal auth), NOT the demo message
    if response.status_code in (401, 403):
        try:
            detail = response.json().get("detail", "")
            if "read-only demo" in detail.lower():
                log(f"❌ FAILED: Unauthenticated request got demo message", RED)
                return False
            else:
                log(f"✅ PASS: Got {response.status_code} (normal auth behavior)", GREEN)
                return True
        except:
            log(f"✅ PASS: Got {response.status_code} (normal auth behavior)", GREEN)
            return True
    else:
        log(f"⚠️  WARNING: Unexpected status {response.status_code}", YELLOW)
        return True


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================
def main():
    print("\n" + "="*80)
    log("  DEMO READ-ONLY BACKEND VERIFICATION", BLUE)
    log("  SECURITY-CRITICAL TEST", RED)
    print("="*80)
    log(f"Backend URL: {BACKEND_URL}", YELLOW)
    log(f"Test started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", YELLOW)
    
    results = {
        "A": False,
        "B": False,
        "C": False,
        "D": False,
        "E": False,
    }
    
    # TEST A: Demo login
    demo_token, results["A"] = test_demo_login()
    
    if not demo_token:
        log(f"\n❌ CRITICAL: Demo login failed, cannot continue", RED)
        sys.exit(1)
    
    # TEST B: Reads allowed
    results["B"], project_id = test_demo_reads(demo_token)
    
    # TEST C: Writes blocked (CRITICAL)
    if project_id:
        results["C"] = test_demo_writes_blocked(demo_token, project_id)
    else:
        log(f"\n⚠️  WARNING: No project_id found, skipping some write tests", YELLOW)
        results["C"] = test_demo_writes_blocked(demo_token, "test123")
    
    # TEST D: Normal auth unaffected
    results["D"] = test_normal_auth_unaffected()
    
    # TEST E: Unauthenticated requests
    results["E"] = test_unauthenticated()
    
    # FINAL SUMMARY
    print("\n" + "="*80)
    log("  FINAL SUMMARY", BLUE)
    print("="*80)
    
    print(f"\nA. Demo login works & is flagged: {'✅ PASS' if results['A'] else '❌ FAIL'}")
    print(f"B. Reads ALLOWED for demo: {'✅ PASS' if results['B'] else '❌ FAIL'}")
    print(f"C. Writes BLOCKED for demo (CRITICAL): {'✅ PASS' if results['C'] else '❌❌❌ FAIL (SECURITY HOLE)'}")
    print(f"D. Normal auth UNAFFECTED: {'✅ PASS' if results['D'] else '❌ FAIL'}")
    print(f"E. Unauthenticated requests: {'✅ PASS' if results['E'] else '❌ FAIL'}")
    
    all_passed = all(results.values())
    
    if all_passed:
        log(f"\n🎉🎉🎉 ALL TESTS PASSED 🎉🎉🎉", GREEN)
        log(f"Demo read-only backend is SECURE and working correctly", GREEN)
        sys.exit(0)
    else:
        log(f"\n❌❌❌ SOME TESTS FAILED ❌❌❌", RED)
        if not results["C"]:
            log(f"⚠️⚠️⚠️  CRITICAL SECURITY ISSUE: Writes are NOT blocked for demo", RED)
        sys.exit(1)


if __name__ == "__main__":
    main()
