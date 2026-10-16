#!/usr/bin/env python3
"""
REGRESSION SMOKE-TEST: Client Portal Magic-Link Flow
DD Planner - FastAPI + MongoDB

This test verifies the magic-link flow hasn't regressed after recent code changes (RBAC, schemas, AI).
Previously verified 28/28 tests passed. This is a quick regression check.

Test Flow (per review request):
1. Login as admin@test.com / admin123
2. GET /api/projects → pick a valid project id
3. POST /api/reports/magic-link with X-Forwarded-Proto and X-Forwarded-Host headers
   - Assert magic_link starts with https://testhost.example.com/portal/
   - Assert NO internal hosts (0.0.0.0, localhost:8001, :8001)
4. Read token and verification_code from MongoDB report_links collection
5. GET /api/portal/verify/{token} → 200, valid: true, returns project_name + recipient_email
6. POST /api/portal/verify/{token}/confirm with code → 200, verified: true
7. GET /api/portal/report/{token} → 200, returns project data + view_count
8. Negative tests:
   - GET /api/portal/report/{unconfirmed_token} → 403
   - POST confirm with wrong code → 401
   - GET /api/portal/verify/{bogus_token} → 404
9. Confirm no crash when Resend email unconfigured (expected behavior)
10. Clean up test links
"""

import requests
import os
from pymongo import MongoClient
from datetime import datetime

# Configuration
BACKEND_URL = "https://ddplanner-fixes.preview.emergentagent.com"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

# MongoDB connection
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "resource_planner")

# Test results
test_results = []
total_tests = 0
passed_tests = 0
created_link_ids = []  # Track for cleanup

def log_test(test_name, passed, details=""):
    """Log test result"""
    global total_tests, passed_tests
    total_tests += 1
    if passed:
        passed_tests += 1
    status = "✅ PASS" if passed else "❌ FAIL"
    result = f"{status}: {test_name}"
    if details:
        result += f" - {details}"
    test_results.append(result)
    print(result)

def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print(f"REGRESSION TEST SUMMARY: {passed_tests}/{total_tests} tests passed")
    print("="*80)
    for result in test_results:
        print(result)
    print("="*80)

# STEP 1: Login as admin@test.com / admin123
print("\n=== STEP 1: AUTHENTICATE AS ADMIN ===")
try:
    auth_response = requests.post(
        f"{BACKEND_URL}/api/auth/login",
        data={
            "username": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    if auth_response.status_code == 200:
        auth_data = auth_response.json()
        token = auth_data.get("access_token")
        log_test("Admin authentication", True, f"Token obtained for {ADMIN_EMAIL}")
        print(f"Token: {token[:30]}...")
    else:
        log_test("Admin authentication", False, f"HTTP {auth_response.status_code}: {auth_response.text}")
        print_summary()
        exit(1)
except Exception as e:
    log_test("Admin authentication", False, f"Exception: {e}")
    print_summary()
    exit(1)

auth_headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# STEP 2: GET /api/projects → pick a valid project id
print("\n=== STEP 2: GET VALID PROJECT ID ===")
try:
    projects_response = requests.get(
        f"{BACKEND_URL}/api/projects",
        headers=auth_headers
    )
    
    if projects_response.status_code == 200:
        projects = projects_response.json()
        if len(projects) > 0:
            project = projects[0]
            project_id = project.get("id")
            project_name = project.get("name")
            log_test("Get projects list", True, f"Found {len(projects)} projects, using '{project_name}' (id: {project_id})")
            print(f"Selected project: {project_name} ({project_id})")
        else:
            log_test("Get projects list", False, "No projects found")
            print_summary()
            exit(1)
    else:
        log_test("Get projects list", False, f"HTTP {projects_response.status_code}: {projects_response.text}")
        print_summary()
        exit(1)
except Exception as e:
    log_test("Get projects list", False, f"Exception: {e}")
    print_summary()
    exit(1)

# STEP 3: POST /api/reports/magic-link with X-Forwarded headers
print("\n=== STEP 3: CREATE MAGIC LINK WITH FORWARDED HEADERS ===")
try:
    # Create magic link with forwarded headers (simulating production ingress)
    create_response = requests.post(
        f"{BACKEND_URL}/api/reports/magic-link",
        headers={
            **auth_headers,
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "testhost.example.com"
        },
        json={
            "project_id": project_id,
            "recipient_email": "client@test.com",
            "report_type": "project_status",
            "report_period": "current"
        }
    )
    
    if create_response.status_code == 200:
        link_data = create_response.json()
        magic_link = link_data.get("magic_link")
        link_token = link_data.get("token")
        link_id = link_data.get("id")
        
        log_test("Create magic link", True, f"Link created with token {link_token[:20]}...")
        print(f"Magic link: {magic_link}")
        print(f"Token: {link_token}")
        print(f"Link ID: {link_id}")
        
        # Track for cleanup
        if link_id:
            created_link_ids.append(link_id)
        
        # CRITICAL ASSERTION: magic_link format
        expected_prefix = "https://testhost.example.com/portal/"
        internal_hosts = ["0.0.0.0", "localhost:8001", ":8001", "127.0.0.1"]
        
        if magic_link.startswith(expected_prefix):
            log_test("Magic link format - correct prefix", True, f"Starts with {expected_prefix}")
        else:
            log_test("Magic link format - correct prefix", False, f"Expected prefix {expected_prefix}, got {magic_link}")
        
        has_internal_host = any(host in magic_link for host in internal_hosts)
        if not has_internal_host:
            log_test("Magic link format - no internal hosts", True, "No internal hosts found")
        else:
            log_test("Magic link format - no internal hosts", False, f"Found internal host in {magic_link}")
        
    else:
        log_test("Create magic link", False, f"HTTP {create_response.status_code}: {create_response.text}")
        print_summary()
        exit(1)
except Exception as e:
    log_test("Create magic link", False, f"Exception: {e}")
    print_summary()
    exit(1)

# STEP 4: Read token and verification_code from MongoDB report_links collection
print("\n=== STEP 4: READ VERIFICATION CODE FROM MONGODB ===")
try:
    mongo_client = MongoClient(MONGO_URL)
    db = mongo_client[DB_NAME]
    report_links_collection = db.report_links
    
    # Find the link we just created
    link_doc = report_links_collection.find_one({"token": link_token})
    
    if link_doc:
        verification_code = link_doc.get("verification_code")
        log_test("Read verification code from MongoDB", True, f"Code: {verification_code}")
        print(f"Verification code from DB: {verification_code}")
    else:
        log_test("Read verification code from MongoDB", False, "Link document not found in DB")
        print_summary()
        exit(1)
except Exception as e:
    log_test("Read verification code from MongoDB", False, f"Exception: {e}")
    print_summary()
    exit(1)

# STEP 5: GET /api/portal/verify/{token} → 200, valid: true
print("\n=== STEP 5: VERIFY TOKEN (PUBLIC ENDPOINT) ===")
try:
    verify_response = requests.get(
        f"{BACKEND_URL}/api/portal/verify/{link_token}"
    )
    
    if verify_response.status_code == 200:
        verify_data = verify_response.json()
        is_valid = verify_data.get("valid")
        returned_project_name = verify_data.get("project_name")
        returned_recipient_email = verify_data.get("recipient_email")
        
        log_test("Verify token endpoint", True, f"valid={is_valid}, project={returned_project_name}, email={returned_recipient_email}")
        print(f"Verify response: {verify_data}")
        
        if is_valid:
            log_test("Token is valid", True, "valid=true")
        else:
            log_test("Token is valid", False, f"valid={is_valid}")
        
        if returned_project_name:
            log_test("Returns project_name", True, f"project_name={returned_project_name}")
        else:
            log_test("Returns project_name", False, "project_name missing")
        
        if returned_recipient_email == "client@test.com":
            log_test("Returns recipient_email", True, f"recipient_email={returned_recipient_email}")
        else:
            log_test("Returns recipient_email", False, f"Expected client@test.com, got {returned_recipient_email}")
    else:
        log_test("Verify token endpoint", False, f"HTTP {verify_response.status_code}: {verify_response.text}")
        print_summary()
        exit(1)
except Exception as e:
    log_test("Verify token endpoint", False, f"Exception: {e}")
    print_summary()
    exit(1)

# STEP 6: POST /api/portal/verify/{token}/confirm with code → 200, verified: true
print("\n=== STEP 6: CONFIRM VERIFICATION CODE ===")
try:
    confirm_response = requests.post(
        f"{BACKEND_URL}/api/portal/verify/{link_token}/confirm",
        json={"verification_code": verification_code}
    )
    
    if confirm_response.status_code == 200:
        confirm_data = confirm_response.json()
        is_verified = confirm_data.get("verified")
        
        log_test("Confirm verification code", True, f"verified={is_verified}")
        print(f"Confirm response: {confirm_data}")
        
        if is_verified:
            log_test("Code verification successful", True, "verified=true")
        else:
            log_test("Code verification successful", False, f"verified={is_verified}")
    else:
        log_test("Confirm verification code", False, f"HTTP {confirm_response.status_code}: {confirm_response.text}")
        print_summary()
        exit(1)
except Exception as e:
    log_test("Confirm verification code", False, f"Exception: {e}")
    print_summary()
    exit(1)

# STEP 7: GET /api/portal/report/{token} → 200, returns project data + view_count
print("\n=== STEP 7: FETCH REPORT (AFTER VERIFICATION) ===")
try:
    report_response = requests.get(
        f"{BACKEND_URL}/api/portal/report/{link_token}"
    )
    
    if report_response.status_code == 200:
        report_data = report_response.json()
        view_count = report_data.get("view_count")
        project_data = report_data.get("project")
        
        log_test("Fetch report after verification", True, f"view_count={view_count}")
        print(f"Report data keys: {list(report_data.keys())}")
        print(f"View count: {view_count}")
        
        if project_data:
            log_test("Returns project data", True, f"Project name: {project_data.get('name')}")
        else:
            log_test("Returns project data", False, "project data missing")
        
        if view_count == 1:
            log_test("View count incremented", True, "view_count=1 on first access")
        else:
            log_test("View count incremented", False, f"Expected view_count=1, got {view_count}")
    else:
        log_test("Fetch report after verification", False, f"HTTP {report_response.status_code}: {report_response.text}")
        print_summary()
        exit(1)
except Exception as e:
    log_test("Fetch report after verification", False, f"Exception: {e}")
    print_summary()
    exit(1)

# STEP 8: NEGATIVE TESTS
print("\n=== STEP 8: NEGATIVE TESTS ===")

# 8a: Create a fresh unconfirmed link for negative test
print("\n--- 8a: Create unconfirmed link for negative test ---")
try:
    unconfirmed_response = requests.post(
        f"{BACKEND_URL}/api/reports/magic-link",
        headers={
            **auth_headers,
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "testhost.example.com"
        },
        json={
            "project_id": project_id,
            "recipient_email": "unconfirmed@test.com",
            "report_type": "project_status",
            "report_period": "current"
        }
    )
    
    if unconfirmed_response.status_code == 200:
        unconfirmed_data = unconfirmed_response.json()
        unconfirmed_token = unconfirmed_data.get("token")
        unconfirmed_link_id = unconfirmed_data.get("id")
        
        log_test("Create unconfirmed link", True, f"Token: {unconfirmed_token[:20]}...")
        
        # Track for cleanup
        if unconfirmed_link_id:
            created_link_ids.append(unconfirmed_link_id)
    else:
        log_test("Create unconfirmed link", False, f"HTTP {unconfirmed_response.status_code}")
        unconfirmed_token = None
except Exception as e:
    log_test("Create unconfirmed link", False, f"Exception: {e}")
    unconfirmed_token = None

# 8b: GET /api/portal/report/{unconfirmed_token} → 403
if unconfirmed_token:
    print("\n--- 8b: Fetch report BEFORE confirmation → 403 ---")
    try:
        unconfirmed_report_response = requests.get(
            f"{BACKEND_URL}/api/portal/report/{unconfirmed_token}"
        )
        
        if unconfirmed_report_response.status_code == 403:
            log_test("Fetch report before confirmation → 403", True, "Correctly blocked with 403")
        else:
            log_test("Fetch report before confirmation → 403", False, f"Expected 403, got {unconfirmed_report_response.status_code}")
    except Exception as e:
        log_test("Fetch report before confirmation → 403", False, f"Exception: {e}")

# 8c: POST confirm with wrong code → 401
print("\n--- 8c: Confirm with wrong code → 401 ---")
try:
    wrong_code_response = requests.post(
        f"{BACKEND_URL}/api/portal/verify/{link_token}/confirm",
        json={"verification_code": "000000"}
    )
    
    if wrong_code_response.status_code == 401:
        log_test("Confirm with wrong code → 401", True, "Correctly rejected with 401")
    else:
        log_test("Confirm with wrong code → 401", False, f"Expected 401, got {wrong_code_response.status_code}")
except Exception as e:
    log_test("Confirm with wrong code → 401", False, f"Exception: {e}")

# 8d: GET /api/portal/verify/{bogus_token} → 404
print("\n--- 8d: Verify bogus token → 404 ---")
try:
    bogus_token = "bogus-token-12345"
    bogus_verify_response = requests.get(
        f"{BACKEND_URL}/api/portal/verify/{bogus_token}"
    )
    
    if bogus_verify_response.status_code == 404:
        log_test("Verify bogus token → 404", True, "Correctly returned 404")
    else:
        log_test("Verify bogus token → 404", False, f"Expected 404, got {bogus_verify_response.status_code}")
except Exception as e:
    log_test("Verify bogus token → 404", False, f"Exception: {e}")

# STEP 9: Confirm no crash when Resend email unconfigured
print("\n=== STEP 9: CONFIRM NO CRASH WHEN RESEND UNCONFIGURED ===")
# This is already verified by the fact that we successfully created links above
# The backend should log that email wasn't sent but not crash
log_test("No crash when Resend unconfigured", True, "Links created successfully without email service")

# STEP 10: Clean up test links
print("\n=== STEP 10: CLEANUP TEST LINKS ===")
cleanup_count = 0
for link_id in created_link_ids:
    try:
        delete_response = requests.delete(
            f"{BACKEND_URL}/api/admin/report-links/{link_id}",
            headers=auth_headers
        )
        
        if delete_response.status_code == 200:
            cleanup_count += 1
            print(f"✅ Deleted link {link_id}")
        else:
            print(f"⚠️  Failed to delete link {link_id}: HTTP {delete_response.status_code}")
    except Exception as e:
        print(f"⚠️  Exception deleting link {link_id}: {e}")

log_test("Cleanup test links", cleanup_count == len(created_link_ids), f"Deleted {cleanup_count}/{len(created_link_ids)} links")

# Print final summary
print_summary()

# Exit with appropriate code
if passed_tests == total_tests:
    print("\n✅✅✅ ALL REGRESSION TESTS PASSED ✅✅✅")
    exit(0)
else:
    print(f"\n❌ REGRESSION FAILED: {total_tests - passed_tests} test(s) failed")
    exit(1)
