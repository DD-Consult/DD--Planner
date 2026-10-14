#!/usr/bin/env python3
"""
Comprehensive test for magic link / smart link for client report flow.
Tests the fix where generated link uses public host from x-forwarded headers.

Test Flow:
1. Authenticate as admin
2. Get valid project_id
3. Create link WITH forwarded headers - assert public URL format
4. Create link WITHOUT forwarded headers - assert non-crashing fallback
5. Verify token
6. Confirm verification code (read from MongoDB)
7. Fetch report
8. Negative checks (wrong code, bogus token, before confirm, revoked)
9. Admin link management
"""

import requests
import os
from pymongo import MongoClient
from datetime import datetime

# Configuration
BACKEND_URL = "http://localhost:8001"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

# MongoDB connection (read from backend/.env)
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "resource_planner")

# Test results
test_results = []
total_tests = 0
passed_tests = 0

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
    print(f"TEST SUMMARY: {passed_tests}/{total_tests} tests passed")
    print("="*80)
    for result in test_results:
        print(result)
    print("="*80)

# Step 1: Authenticate as admin
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
        print(f"Token: {token[:20]}...")
    else:
        log_test("Admin authentication", False, f"HTTP {auth_response.status_code}: {auth_response.text}")
        print_summary()
        exit(1)
except Exception as e:
    log_test("Admin authentication", False, f"Exception: {e}")
    print_summary()
    exit(1)

# Headers for authenticated requests
auth_headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# Step 2: Get valid project_id (directly from MongoDB to avoid API validation issues)
print("\n=== STEP 2: GET VALID PROJECT_ID ===")
try:
    mongo_client = MongoClient(MONGO_URL)
    db = mongo_client[DB_NAME]
    projects_collection_db = db.projects
    
    # Get the Website Redesign project
    project_doc = projects_collection_db.find_one({"name": "Website Redesign"})
    
    if project_doc:
        project_id = str(project_doc["_id"])
        project_name = project_doc.get("name", "Unknown")
        log_test("Get valid project from MongoDB", True, f"Using '{project_name}' (ID: {project_id})")
        print(f"Project ID: {project_id}")
        print(f"Project Name: {project_name}")
    else:
        log_test("Get valid project from MongoDB", False, "Project not found")
        print_summary()
        exit(1)
except Exception as e:
    log_test("Get valid project from MongoDB", False, f"Exception: {e}")
    print_summary()
    exit(1)

# Step 3A: Create magic link WITH forwarded headers
print("\n=== STEP 3A: CREATE MAGIC LINK WITH FORWARDED HEADERS ===")
try:
    create_payload = {
        "project_id": project_id,
        "recipient_email": "client@test.com",
        "report_type": "project_status",
        "report_period": "last_week"
    }
    
    # Include X-Forwarded headers to simulate ingress/proxy
    forwarded_headers = {
        **auth_headers,
        "X-Forwarded-Proto": "https",
        "X-Forwarded-Host": "testhost.example.com"
    }
    
    create_response = requests.post(
        f"{BACKEND_URL}/api/reports/magic-link",
        json=create_payload,
        headers=forwarded_headers
    )
    
    if create_response.status_code == 200:
        link_data = create_response.json()
        magic_link_with_headers = link_data.get("magic_link")
        token_with_headers = link_data.get("token")
        
        log_test("Create magic link (with headers)", True, f"HTTP 200, link created")
        print(f"Magic Link: {magic_link_with_headers}")
        print(f"Token: {token_with_headers[:20]}...")
        
        # KEY ASSERTION: Check if link uses public host from forwarded headers
        expected_prefix = "https://testhost.example.com/portal/"
        if magic_link_with_headers.startswith(expected_prefix):
            log_test("Magic link uses forwarded host", True, f"Link starts with {expected_prefix}")
        else:
            log_test("Magic link uses forwarded host", False, f"Expected prefix '{expected_prefix}', got '{magic_link_with_headers}'")
        
        # Check that link does NOT contain internal hosts
        internal_hosts = ["0.0.0.0", "127.0.0.1", "localhost:8001", ":8001"]
        contains_internal = any(host in magic_link_with_headers for host in internal_hosts)
        if not contains_internal:
            log_test("Magic link does NOT contain internal host", True, "No internal hosts found")
        else:
            log_test("Magic link does NOT contain internal host", False, f"Link contains internal host: {magic_link_with_headers}")
        
        # Verify response contains required fields
        required_fields = ["magic_link", "token", "project_id", "recipient_email", "report_type", "report_period", "created_at", "expires_at"]
        missing_fields = [f for f in required_fields if f not in link_data]
        if not missing_fields:
            log_test("Response contains required fields", True, f"All {len(required_fields)} fields present")
        else:
            log_test("Response contains required fields", False, f"Missing fields: {missing_fields}")
    else:
        log_test("Create magic link (with headers)", False, f"HTTP {create_response.status_code}: {create_response.text}")
        print_summary()
        exit(1)
except Exception as e:
    log_test("Create magic link (with headers)", False, f"Exception: {e}")
    print_summary()
    exit(1)

# Step 3B: Create magic link WITHOUT forwarded headers (fallback test)
print("\n=== STEP 3B: CREATE MAGIC LINK WITHOUT FORWARDED HEADERS (FALLBACK) ===")
try:
    create_payload_2 = {
        "project_id": project_id,
        "recipient_email": "client2@test.com",
        "report_type": "project_status",
        "report_period": "last_month"
    }
    
    # No X-Forwarded headers - should fall back to request.base_url
    create_response_2 = requests.post(
        f"{BACKEND_URL}/api/reports/magic-link",
        json=create_payload_2,
        headers=auth_headers
    )
    
    if create_response_2.status_code == 200:
        link_data_2 = create_response_2.json()
        magic_link_without_headers = link_data_2.get("magic_link")
        token_without_headers = link_data_2.get("token")
        
        log_test("Create magic link (without headers)", True, f"HTTP 200, link created")
        print(f"Magic Link (fallback): {magic_link_without_headers}")
        print(f"Token: {token_without_headers[:20]}...")
        
        # Check that link is a valid absolute URL (not crashing)
        if magic_link_without_headers and magic_link_without_headers.startswith("http"):
            log_test("Fallback link is valid absolute URL", True, f"Link starts with http")
        else:
            log_test("Fallback link is valid absolute URL", False, f"Invalid URL: {magic_link_without_headers}")
        
        # Check that link contains /portal/ path
        if "/portal/" in magic_link_without_headers:
            log_test("Fallback link contains /portal/ path", True)
        else:
            log_test("Fallback link contains /portal/ path", False, f"Missing /portal/ in {magic_link_without_headers}")
    else:
        log_test("Create magic link (without headers)", False, f"HTTP {create_response_2.status_code}: {create_response_2.text}")
except Exception as e:
    log_test("Create magic link (without headers)", False, f"Exception: {e}")

# Step 4: Read verification code from MongoDB
print("\n=== STEP 4: READ VERIFICATION CODE FROM MONGODB ===")
try:
    mongo_client = MongoClient(MONGO_URL)
    db = mongo_client[DB_NAME]
    report_links_collection = db.report_links
    
    # Find the link document by token
    link_doc = report_links_collection.find_one({"token": token_with_headers})
    
    if link_doc:
        verification_code = link_doc.get("verification_code")
        log_test("Read verification code from MongoDB", True, f"Code: {verification_code}")
        print(f"Verification Code: {verification_code}")
        print(f"Link ID: {link_doc['_id']}")
        link_id = str(link_doc['_id'])
    else:
        log_test("Read verification code from MongoDB", False, "Link document not found")
        print_summary()
        exit(1)
except Exception as e:
    log_test("Read verification code from MongoDB", False, f"Exception: {e}")
    print_summary()
    exit(1)

# Step 5: Verify token (GET /api/portal/verify/{token})
print("\n=== STEP 5: VERIFY TOKEN ===")
try:
    verify_response = requests.get(
        f"{BACKEND_URL}/api/portal/verify/{token_with_headers}"
    )
    
    if verify_response.status_code == 200:
        verify_data = verify_response.json()
        log_test("Verify token", True, f"HTTP 200, token valid")
        print(f"Valid: {verify_data.get('valid')}")
        print(f"Project Name: {verify_data.get('project_name')}")
        print(f"Recipient Email: {verify_data.get('recipient_email')}")
        print(f"Expires At: {verify_data.get('expires_at')}")
        
        # Check required fields
        required_verify_fields = ["valid", "project_name", "recipient_email", "expires_at"]
        missing_verify_fields = [f for f in required_verify_fields if f not in verify_data]
        if not missing_verify_fields:
            log_test("Verify response contains required fields", True)
        else:
            log_test("Verify response contains required fields", False, f"Missing: {missing_verify_fields}")
        
        # Check valid=true
        if verify_data.get("valid") == True:
            log_test("Token is valid", True)
        else:
            log_test("Token is valid", False, f"valid={verify_data.get('valid')}")
    else:
        log_test("Verify token", False, f"HTTP {verify_response.status_code}: {verify_response.text}")
except Exception as e:
    log_test("Verify token", False, f"Exception: {e}")

# Step 6A: Confirm with WRONG code (negative test)
print("\n=== STEP 6A: CONFIRM WITH WRONG CODE (NEGATIVE TEST) ===")
try:
    wrong_code = "000000"
    confirm_wrong_response = requests.post(
        f"{BACKEND_URL}/api/portal/verify/{token_with_headers}/confirm",
        json={"verification_code": wrong_code}
    )
    
    if confirm_wrong_response.status_code == 401:
        log_test("Confirm with wrong code returns 401", True, "Correctly rejected")
        print(f"Response: {confirm_wrong_response.json()}")
    else:
        log_test("Confirm with wrong code returns 401", False, f"Expected 401, got {confirm_wrong_response.status_code}")
except Exception as e:
    log_test("Confirm with wrong code returns 401", False, f"Exception: {e}")

# Step 6B: Confirm with CORRECT code
print("\n=== STEP 6B: CONFIRM WITH CORRECT CODE ===")
try:
    confirm_response = requests.post(
        f"{BACKEND_URL}/api/portal/verify/{token_with_headers}/confirm",
        json={"verification_code": verification_code}
    )
    
    if confirm_response.status_code == 200:
        confirm_data = confirm_response.json()
        log_test("Confirm with correct code", True, f"HTTP 200, access granted")
        print(f"Verified: {confirm_data.get('verified')}")
        print(f"Message: {confirm_data.get('message')}")
        
        # Check verified=true
        if confirm_data.get("verified") == True:
            log_test("Verification successful", True)
        else:
            log_test("Verification successful", False, f"verified={confirm_data.get('verified')}")
    else:
        log_test("Confirm with correct code", False, f"HTTP {confirm_response.status_code}: {confirm_response.text}")
        print_summary()
        exit(1)
except Exception as e:
    log_test("Confirm with correct code", False, f"Exception: {e}")
    print_summary()
    exit(1)

# Step 7: Fetch report (GET /api/portal/report/{token})
print("\n=== STEP 7: FETCH REPORT ===")
try:
    report_response = requests.get(
        f"{BACKEND_URL}/api/portal/report/{token_with_headers}"
    )
    
    if report_response.status_code == 200:
        report_data = report_response.json()
        log_test("Fetch report", True, f"HTTP 200, report retrieved")
        print(f"Project Name: {report_data.get('project', {}).get('name')}")
        print(f"Report Type: {report_data.get('report_type')}")
        print(f"Report Period: {report_data.get('report_period')}")
        print(f"View Count: {report_data.get('view_count')}")
        print(f"Created At: {report_data.get('created_at')}")
        print(f"Expires At: {report_data.get('expires_at')}")
        
        # Check required fields
        required_report_fields = ["project", "report_type", "report_period", "view_count", "created_at", "expires_at"]
        missing_report_fields = [f for f in required_report_fields if f not in report_data]
        if not missing_report_fields:
            log_test("Report response contains required fields", True)
        else:
            log_test("Report response contains required fields", False, f"Missing: {missing_report_fields}")
        
        # Check project has expected fields
        project_data = report_data.get("project", {})
        if "name" in project_data and "status" in project_data:
            log_test("Project data has expected fields", True, f"name, status present")
        else:
            log_test("Project data has expected fields", False, f"Missing name or status")
        
        # Check view_count is 1 (first view)
        view_count = report_data.get("view_count")
        if view_count == 1:
            log_test("View count is 1 (first view)", True)
        else:
            log_test("View count is 1 (first view)", False, f"view_count={view_count}")
    else:
        log_test("Fetch report", False, f"HTTP {report_response.status_code}: {report_response.text}")
except Exception as e:
    log_test("Fetch report", False, f"Exception: {e}")

# Step 8A: Negative test - Fetch report BEFORE confirming (use second token)
print("\n=== STEP 8A: NEGATIVE TEST - FETCH REPORT BEFORE CONFIRMING ===")
try:
    # Use the second token that was created without headers (not yet verified)
    report_before_confirm_response = requests.get(
        f"{BACKEND_URL}/api/portal/report/{token_without_headers}"
    )
    
    if report_before_confirm_response.status_code == 403:
        log_test("Fetch report before confirm returns 403", True, "Correctly blocked")
        print(f"Response: {report_before_confirm_response.json()}")
    else:
        log_test("Fetch report before confirm returns 403", False, f"Expected 403, got {report_before_confirm_response.status_code}")
except Exception as e:
    log_test("Fetch report before confirm returns 403", False, f"Exception: {e}")

# Step 8B: Negative test - Verify with bogus token
print("\n=== STEP 8B: NEGATIVE TEST - VERIFY WITH BOGUS TOKEN ===")
try:
    bogus_token = "bogus-token-12345"
    verify_bogus_response = requests.get(
        f"{BACKEND_URL}/api/portal/verify/{bogus_token}"
    )
    
    if verify_bogus_response.status_code == 404:
        log_test("Verify bogus token returns 404", True, "Correctly rejected")
        print(f"Response: {verify_bogus_response.json()}")
    else:
        log_test("Verify bogus token returns 404", False, f"Expected 404, got {verify_bogus_response.status_code}")
except Exception as e:
    log_test("Verify bogus token returns 404", False, f"Exception: {e}")

# Step 8C: Negative test - Rate limit (3 wrong attempts)
print("\n=== STEP 8C: NEGATIVE TEST - RATE LIMIT (3 WRONG ATTEMPTS) ===")
try:
    # Create a fresh link for rate limit testing
    create_payload_3 = {
        "project_id": project_id,
        "recipient_email": "ratelimit@test.com",
        "report_type": "project_status",
        "report_period": "this_week"
    }
    
    create_response_3 = requests.post(
        f"{BACKEND_URL}/api/reports/magic-link",
        json=create_payload_3,
        headers=auth_headers
    )
    
    if create_response_3.status_code == 200:
        link_data_3 = create_response_3.json()
        token_ratelimit = link_data_3.get("token")
        
        # Attempt 1, 2, 3 with wrong code
        for attempt in range(1, 4):
            wrong_response = requests.post(
                f"{BACKEND_URL}/api/portal/verify/{token_ratelimit}/confirm",
                json={"verification_code": "999999"}
            )
            print(f"Attempt {attempt}: HTTP {wrong_response.status_code}")
        
        # Attempt 4 should return 429 (rate limited)
        fourth_attempt = requests.post(
            f"{BACKEND_URL}/api/portal/verify/{token_ratelimit}/confirm",
            json={"verification_code": "999999"}
        )
        
        if fourth_attempt.status_code == 429:
            log_test("Rate limit after 3 wrong attempts", True, "4th attempt returns 429")
            print(f"Response: {fourth_attempt.json()}")
        else:
            log_test("Rate limit after 3 wrong attempts", False, f"Expected 429, got {fourth_attempt.status_code}")
    else:
        log_test("Rate limit test setup", False, f"Failed to create test link: HTTP {create_response_3.status_code}")
except Exception as e:
    log_test("Rate limit after 3 wrong attempts", False, f"Exception: {e}")

# Step 9A: Admin list report links
print("\n=== STEP 9A: ADMIN LIST REPORT LINKS ===")
try:
    list_response = requests.get(
        f"{BACKEND_URL}/api/admin/report-links",
        headers=auth_headers
    )
    
    if list_response.status_code == 200:
        links_list = list_response.json()
        log_test("Admin list report links", True, f"HTTP 200, {len(links_list)} links found")
        print(f"Total links: {len(links_list)}")
        
        # Find our test link
        test_link = next((link for link in links_list if link.get("token") == token_with_headers), None)
        if test_link:
            log_test("Test link found in admin list", True)
        else:
            log_test("Test link found in admin list", False, "Link not found")
    else:
        log_test("Admin list report links", False, f"HTTP {list_response.status_code}: {list_response.text}")
except Exception as e:
    log_test("Admin list report links", False, f"Exception: {e}")

# Step 9B: Admin revoke report link
print("\n=== STEP 9B: ADMIN REVOKE REPORT LINK ===")
try:
    revoke_response = requests.delete(
        f"{BACKEND_URL}/api/admin/report-links/{link_id}",
        headers=auth_headers
    )
    
    if revoke_response.status_code == 200:
        log_test("Admin revoke report link", True, f"HTTP 200, link revoked")
        print(f"Response: {revoke_response.json()}")
    else:
        log_test("Admin revoke report link", False, f"HTTP {revoke_response.status_code}: {revoke_response.text}")
except Exception as e:
    log_test("Admin revoke report link", False, f"Exception: {e}")

# Step 9C: Verify revoked link returns 403
print("\n=== STEP 9C: VERIFY REVOKED LINK RETURNS 403 ===")
try:
    verify_revoked_response = requests.get(
        f"{BACKEND_URL}/api/portal/verify/{token_with_headers}"
    )
    
    if verify_revoked_response.status_code == 403:
        log_test("Verify revoked link returns 403", True, "Correctly blocked")
        print(f"Response: {verify_revoked_response.json()}")
    else:
        log_test("Verify revoked link returns 403", False, f"Expected 403, got {verify_revoked_response.status_code}")
except Exception as e:
    log_test("Verify revoked link returns 403", False, f"Exception: {e}")

# Step 10: Cleanup - Delete remaining test links
print("\n=== STEP 10: CLEANUP ===")
try:
    # Get all links for the test project
    cleanup_response = requests.get(
        f"{BACKEND_URL}/api/admin/report-links?project_id={project_id}",
        headers=auth_headers
    )
    
    if cleanup_response.status_code == 200:
        cleanup_links = cleanup_response.json()
        print(f"Found {len(cleanup_links)} links to clean up")
        
        for link in cleanup_links:
            link_id_cleanup = link.get("id")
            if link_id_cleanup:
                delete_response = requests.delete(
                    f"{BACKEND_URL}/api/admin/report-links/{link_id_cleanup}",
                    headers=auth_headers
                )
                print(f"Deleted link {link_id_cleanup}: HTTP {delete_response.status_code}")
        
        log_test("Cleanup test links", True, f"Deleted {len(cleanup_links)} links")
    else:
        log_test("Cleanup test links", False, f"HTTP {cleanup_response.status_code}")
except Exception as e:
    log_test("Cleanup test links", False, f"Exception: {e}")

# Print final summary
print_summary()

# Exit with appropriate code
exit(0 if passed_tests == total_tests else 1)
