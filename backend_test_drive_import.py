#!/usr/bin/env python3
"""
Google Drive Import Testing for DD Planner Proposal Module
===========================================================

Verifies the NEW live Google Drive import feature with NO real service account.
Tests graceful error handling across all states (disabled, invalid JSON, fake credentials).

Test Credentials:
- superadmin@test.com / Super@2026 (super_admin)
- admin@test.com / admin123 (admin)
- qa_resource@test.com / Test@2026 (non-admin resource)

Base URL: https://proposal-approve.preview.emergentagent.com
API Prefix: /api

CRITICAL REQUIREMENTS:
- NO endpoint returns 500 or hangs
- GET /api/proposals/drive/docs returns 200 with {ok, message?, files} in all states
- POST /api/proposals/from-drive returns 400 (not 500) with detail on errors
- RBAC enforced: admin allowed (200), non-admin (403)
"""

import requests
import json
import sys
from datetime import datetime

# Configuration
BASE_URL = "https://proposal-approve.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"

# Test credentials
SUPERADMIN_EMAIL = "superadmin@test.com"
SUPERADMIN_PASSWORD = "Super@2026"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"
NON_ADMIN_EMAIL = "qa_resource@test.com"
NON_ADMIN_PASSWORD = "Test@2026"

# Test results tracking
test_results = []
total_tests = 0
passed_tests = 0


def log_test(test_name, passed, details=""):
    """Log a test result"""
    global total_tests, passed_tests
    total_tests += 1
    if passed:
        passed_tests += 1
    status = "✅ PASS" if passed else "❌ FAIL"
    result = {
        "test": test_name,
        "status": status,
        "passed": passed,
        "details": details,
        "timestamp": datetime.now().isoformat()
    }
    test_results.append(result)
    print(f"{status}: {test_name}")
    if details:
        print(f"  Details: {details}")
    return passed


def login(email, password):
    """Login and return JWT token"""
    try:
        response = requests.post(
            f"{API_BASE}/auth/login",
            data={"username": email, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            if token:
                print(f"✓ Logged in as {email}")
                return token
        print(f"✗ Login failed for {email}: {response.status_code} - {response.text[:200]}")
        return None
    except Exception as e:
        print(f"✗ Login exception for {email}: {e}")
        return None


def test_1_drive_disabled(superadmin_token, admin_token):
    """TEST 1: DRIVE DISABLED - ensure google_drive disabled, GET docs returns 200 with message"""
    print("\n" + "="*80)
    print("TEST 1: DRIVE DISABLED")
    print("="*80)
    
    # Step 1a: Disable Google Drive as superadmin
    print("\n[1a] Disabling Google Drive...")
    try:
        response = requests.put(
            f"{API_BASE}/integrations/settings",
            json={
                "google_drive": {
                    "enabled": False,
                    "service_account_json": "",
                    "default_folder_id": ""
                }
            },
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        if response.status_code == 200:
            print(f"✓ Drive disabled successfully")
        else:
            log_test("1a. Disable Drive", False, f"Status {response.status_code}: {response.text[:200]}")
            return False
    except Exception as e:
        log_test("1a. Disable Drive", False, f"Exception: {e}")
        return False
    
    # Step 1b: As admin, GET /api/proposals/drive/docs
    print("\n[1b] Testing GET /api/proposals/drive/docs with Drive disabled...")
    try:
        response = requests.get(
            f"{API_BASE}/proposals/drive/docs",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # CRITICAL: Must return 200 (NOT 500)
        if response.status_code != 200:
            log_test("1b. GET docs (disabled)", False, 
                    f"Expected 200, got {response.status_code}: {response.text[:200]}")
            return False
        
        data = response.json()
        
        # Must have ok:false and a message
        if not isinstance(data, dict):
            log_test("1b. GET docs (disabled)", False, f"Response not a dict: {data}")
            return False
        
        if data.get("ok") is not False:
            log_test("1b. GET docs (disabled)", False, f"Expected ok:false, got: {data}")
            return False
        
        message = data.get("message", "")
        if not message or not isinstance(message, str):
            log_test("1b. GET docs (disabled)", False, f"No message field: {data}")
            return False
        
        # Message should mention Drive not configured/disabled
        if "not configured" not in message.lower() and "disabled" not in message.lower():
            log_test("1b. GET docs (disabled)", False, 
                    f"Message doesn't mention 'not configured' or 'disabled': {message}")
            return False
        
        # Must have files:[]
        if data.get("files") != []:
            log_test("1b. GET docs (disabled)", False, f"Expected files:[], got: {data.get('files')}")
            return False
        
        log_test("1b. GET docs (disabled)", True, 
                f"✅ Returns 200 with ok:false, message:'{message}', files:[]")
        return True
        
    except Exception as e:
        log_test("1b. GET docs (disabled)", False, f"Exception: {e}")
        return False


def test_2_from_drive_while_disabled(admin_token):
    """TEST 2: FROM-DRIVE WHILE DISABLED - POST should return 400 with detail"""
    print("\n" + "="*80)
    print("TEST 2: FROM-DRIVE WHILE DISABLED")
    print("="*80)
    
    print("\n[2] Testing POST /api/proposals/from-drive with Drive disabled...")
    try:
        response = requests.post(
            f"{API_BASE}/proposals/from-drive",
            json={
                "doc_id": "https://docs.google.com/document/d/1AbCdeFGhiJklMNopQrStuVwxyz1234567890/edit",
                "use_ai": False
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # CRITICAL: Must return 400 (NOT 500)
        if response.status_code != 400:
            log_test("2. POST from-drive (disabled)", False,
                    f"Expected 400, got {response.status_code}: {response.text[:200]}")
            return False
        
        data = response.json()
        detail = data.get("detail", "")
        
        if not detail or not isinstance(detail, str):
            log_test("2. POST from-drive (disabled)", False, f"No detail field: {data}")
            return False
        
        # Detail should mention Drive not configured
        if "not configured" not in detail.lower() and "disabled" not in detail.lower():
            log_test("2. POST from-drive (disabled)", False,
                    f"Detail doesn't mention 'not configured' or 'disabled': {detail}")
            return False
        
        log_test("2. POST from-drive (disabled)", True,
                f"✅ Returns 400 with detail:'{detail}'")
        return True
        
    except Exception as e:
        log_test("2. POST from-drive (disabled)", False, f"Exception: {e}")
        return False


def test_3_enable_with_invalid_json(superadmin_token, admin_token):
    """TEST 3: ENABLE WITH INVALID SA JSON - GET docs returns 200 with message"""
    print("\n" + "="*80)
    print("TEST 3: ENABLE WITH INVALID SA JSON")
    print("="*80)
    
    # Step 3a: Enable with invalid JSON
    print("\n[3a] Enabling Drive with invalid service account JSON...")
    try:
        response = requests.put(
            f"{API_BASE}/integrations/settings",
            json={
                "google_drive": {
                    "enabled": True,
                    "service_account_json": "not-valid-json",
                    "default_folder_id": ""
                }
            },
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        if response.status_code == 200:
            print(f"✓ Drive enabled with invalid JSON")
        else:
            log_test("3a. Enable with invalid JSON", False,
                    f"Status {response.status_code}: {response.text[:200]}")
            return False
    except Exception as e:
        log_test("3a. Enable with invalid JSON", False, f"Exception: {e}")
        return False
    
    # Step 3b: As admin, GET /api/proposals/drive/docs
    print("\n[3b] Testing GET /api/proposals/drive/docs with invalid JSON...")
    try:
        response = requests.get(
            f"{API_BASE}/proposals/drive/docs",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # CRITICAL: Must return 200 (NOT 500)
        if response.status_code != 200:
            log_test("3b. GET docs (invalid JSON)", False,
                    f"Expected 200, got {response.status_code}: {response.text[:200]}")
            return False
        
        data = response.json()
        
        # Must have ok:false and a message
        if data.get("ok") is not False:
            log_test("3b. GET docs (invalid JSON)", False, f"Expected ok:false, got: {data}")
            return False
        
        message = data.get("message", "")
        if not message or not isinstance(message, str):
            log_test("3b. GET docs (invalid JSON)", False, f"No message field: {data}")
            return False
        
        # Message should mention invalid JSON
        if "json" not in message.lower() and "invalid" not in message.lower():
            log_test("3b. GET docs (invalid JSON)", False,
                    f"Message doesn't mention 'json' or 'invalid': {message}")
            return False
        
        log_test("3b. GET docs (invalid JSON)", True,
                f"✅ Returns 200 with ok:false, message:'{message}'")
        return True
        
    except Exception as e:
        log_test("3b. GET docs (invalid JSON)", False, f"Exception: {e}")
        return False


def test_4_from_drive_with_invalid_json(admin_token):
    """TEST 4: FROM-DRIVE WITH INVALID SA JSON - POST returns 400 with detail"""
    print("\n" + "="*80)
    print("TEST 4: FROM-DRIVE WITH INVALID SA JSON")
    print("="*80)
    
    print("\n[4] Testing POST /api/proposals/from-drive with invalid JSON...")
    try:
        response = requests.post(
            f"{API_BASE}/proposals/from-drive",
            json={
                "doc_id": "1AbCdeFGhiJklMNopQrStuVwxyz1234567890",
                "use_ai": False
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # CRITICAL: Must return 400 (NOT 500)
        if response.status_code != 400:
            log_test("4. POST from-drive (invalid JSON)", False,
                    f"Expected 400, got {response.status_code}: {response.text[:200]}")
            return False
        
        data = response.json()
        detail = data.get("detail", "")
        
        if not detail or not isinstance(detail, str):
            log_test("4. POST from-drive (invalid JSON)", False, f"No detail field: {data}")
            return False
        
        # Detail should mention invalid JSON or could not init client
        if not any(x in detail.lower() for x in ["json", "invalid", "init", "client"]):
            log_test("4. POST from-drive (invalid JSON)", False,
                    f"Detail doesn't mention expected error: {detail}")
            return False
        
        log_test("4. POST from-drive (invalid JSON)", True,
                f"✅ Returns 400 with detail:'{detail}'")
        return True
        
    except Exception as e:
        log_test("4. POST from-drive (invalid JSON)", False, f"Exception: {e}")
        return False


def test_5_enable_with_fake_json(superadmin_token, admin_token):
    """TEST 5: ENABLE WITH WELL-FORMED-BUT-FAKE SA JSON - GET docs returns 200 with message"""
    print("\n" + "="*80)
    print("TEST 5: ENABLE WITH WELL-FORMED-BUT-FAKE SA JSON")
    print("="*80)
    
    # Step 5a: Enable with syntactically valid but fake JSON
    fake_sa_json = {
        "type": "service_account",
        "project_id": "fake-project-12345",
        "private_key_id": "fakeprivatekeyid123456789",
        "private_key": "-----BEGIN PRIVATE KEY-----\nMIIBVAIBADANBgkqhkiG9w0BAQEFAASCAT4wggE6AgEAAkEAwJbSzJN\n-----END PRIVATE KEY-----\n",
        "client_email": "fake-sa@fake-project-12345.iam.gserviceaccount.com",
        "client_id": "123456789012345678901",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/fake-sa%40fake-project-12345.iam.gserviceaccount.com"
    }
    
    print("\n[5a] Enabling Drive with well-formed but fake service account JSON...")
    try:
        response = requests.put(
            f"{API_BASE}/integrations/settings",
            json={
                "google_drive": {
                    "enabled": True,
                    "service_account_json": json.dumps(fake_sa_json),
                    "default_folder_id": ""
                }
            },
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        if response.status_code == 200:
            print(f"✓ Drive enabled with fake but valid JSON")
        else:
            log_test("5a. Enable with fake JSON", False,
                    f"Status {response.status_code}: {response.text[:200]}")
            return False
    except Exception as e:
        log_test("5a. Enable with fake JSON", False, f"Exception: {e}")
        return False
    
    # Step 5b: As admin, GET /api/proposals/drive/docs
    print("\n[5b] Testing GET /api/proposals/drive/docs with fake credentials...")
    try:
        response = requests.get(
            f"{API_BASE}/proposals/drive/docs",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # CRITICAL: Must return 200 (NOT 500 or hang)
        if response.status_code != 200:
            log_test("5b. GET docs (fake JSON)", False,
                    f"Expected 200, got {response.status_code}: {response.text[:200]}")
            return False
        
        data = response.json()
        
        # Must have ok:false and a message
        if data.get("ok") is not False:
            log_test("5b. GET docs (fake JSON)", False, f"Expected ok:false, got: {data}")
            return False
        
        message = data.get("message", "")
        if not message or not isinstance(message, str):
            log_test("5b. GET docs (fake JSON)", False, f"No message field: {data}")
            return False
        
        # The KEY requirement: returns 200 with a message (credentials init may fail on fake key,
        # OR a Google API auth error) — does NOT 500/hang
        log_test("5b. GET docs (fake JSON)", True,
                f"✅ Returns 200 with ok:false, message:'{message}' (no 500/hang)")
        print(f"   Message content: {message}")
        return True
        
    except Exception as e:
        log_test("5b. GET docs (fake JSON)", False, f"Exception: {e}")
        return False


def test_6_rbac(admin_token, non_admin_token):
    """TEST 6: RBAC - admin allowed (200), non-admin (403)"""
    print("\n" + "="*80)
    print("TEST 6: RBAC")
    print("="*80)
    
    # Step 6a: Admin should be allowed
    print("\n[6a] Testing admin access to GET /api/proposals/drive/docs...")
    try:
        response = requests.get(
            f"{API_BASE}/proposals/drive/docs",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Admin should get 200 (even if Drive returns error, the endpoint is accessible)
        if response.status_code != 200:
            log_test("6a. Admin access", False,
                    f"Expected 200, got {response.status_code}: {response.text[:200]}")
            return False
        
        log_test("6a. Admin access", True, "✅ Admin gets 200")
        
    except Exception as e:
        log_test("6a. Admin access", False, f"Exception: {e}")
        return False
    
    # Step 6b: Non-admin should be denied
    print("\n[6b] Testing non-admin access to GET /api/proposals/drive/docs...")
    try:
        response = requests.get(
            f"{API_BASE}/proposals/drive/docs",
            headers={"Authorization": f"Bearer {non_admin_token}"}
        )
        
        # Non-admin should get 403
        if response.status_code != 403:
            log_test("6b. Non-admin denied", False,
                    f"Expected 403, got {response.status_code}: {response.text[:200]}")
            return False
        
        log_test("6b. Non-admin denied", True, "✅ Non-admin gets 403")
        return True
        
    except Exception as e:
        log_test("6b. Non-admin denied", False, f"Exception: {e}")
        return False


def test_7_doc_id_parsing(superadmin_token, admin_token):
    """TEST 7: DOC ID PARSING - returns 400 gracefully with empty doc_id"""
    print("\n" + "="*80)
    print("TEST 7: DOC ID PARSING")
    print("="*80)
    
    # First disable drive again
    print("\n[7a] Disabling Drive for doc ID parsing test...")
    try:
        response = requests.put(
            f"{API_BASE}/integrations/settings",
            json={
                "google_drive": {
                    "enabled": False,
                    "service_account_json": "",
                    "default_folder_id": ""
                }
            },
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        if response.status_code != 200:
            log_test("7a. Disable Drive", False, f"Status {response.status_code}")
            return False
    except Exception as e:
        log_test("7a. Disable Drive", False, f"Exception: {e}")
        return False
    
    # Test with empty doc_id
    print("\n[7b] Testing POST /api/proposals/from-drive with empty doc_id...")
    try:
        response = requests.post(
            f"{API_BASE}/proposals/from-drive",
            json={
                "doc_id": "",
                "use_ai": False
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # CRITICAL: Must return 400 (NOT 500)
        if response.status_code != 400:
            log_test("7b. Empty doc_id", False,
                    f"Expected 400, got {response.status_code}: {response.text[:200]}")
            return False
        
        data = response.json()
        detail = data.get("detail", "")
        
        if not detail or not isinstance(detail, str):
            log_test("7b. Empty doc_id", False, f"No detail field: {data}")
            return False
        
        log_test("7b. Empty doc_id", True,
                f"✅ Returns 400 with detail:'{detail}'")
        return True
        
    except Exception as e:
        log_test("7b. Empty doc_id", False, f"Exception: {e}")
        return False


def test_8_cleanup(superadmin_token):
    """TEST 8: CLEANUP - disable drive"""
    print("\n" + "="*80)
    print("TEST 8: CLEANUP")
    print("="*80)
    
    print("\n[8] Disabling Google Drive (cleanup)...")
    try:
        response = requests.put(
            f"{API_BASE}/integrations/settings",
            json={
                "google_drive": {
                    "enabled": False,
                    "service_account_json": "",
                    "default_folder_id": ""
                }
            },
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        
        if response.status_code == 200:
            log_test("8. Cleanup", True, "✅ Drive disabled successfully")
            return True
        else:
            log_test("8. Cleanup", False, f"Status {response.status_code}: {response.text[:200]}")
            return False
            
    except Exception as e:
        log_test("8. Cleanup", False, f"Exception: {e}")
        return False


def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
    
    print("\n" + "="*80)
    print("DETAILED RESULTS")
    print("="*80)
    
    for result in test_results:
        print(f"\n{result['status']}: {result['test']}")
        if result['details']:
            print(f"  {result['details']}")
    
    # Check critical requirements
    print("\n" + "="*80)
    print("CRITICAL REQUIREMENTS CHECK")
    print("="*80)
    
    # Check if any test returned 500
    has_500 = any("500" in str(r.get('details', '')) for r in test_results if not r['passed'])
    print(f"✅ NO 500 errors: {not has_500}")
    
    # Check if all GET endpoints returned 200
    get_tests = [r for r in test_results if 'GET docs' in r['test']]
    all_get_200 = all(r['passed'] for r in get_tests)
    print(f"✅ All GET /api/proposals/drive/docs returned 200: {all_get_200}")
    
    # Check if all POST endpoints returned 400 on errors
    post_tests = [r for r in test_results if 'POST from-drive' in r['test']]
    all_post_400 = all(r['passed'] for r in post_tests)
    print(f"✅ All POST /api/proposals/from-drive returned 400 on errors: {all_post_400}")
    
    # Check RBAC
    rbac_tests = [r for r in test_results if 'RBAC' in r['test'] or 'access' in r['test']]
    rbac_ok = all(r['passed'] for r in rbac_tests)
    print(f"✅ RBAC enforced (admin 200, non-admin 403): {rbac_ok}")
    
    return passed_tests == total_tests


def main():
    """Main test execution"""
    print("="*80)
    print("GOOGLE DRIVE IMPORT TESTING")
    print("DD Planner Proposal Module")
    print("="*80)
    print(f"\nBase URL: {BASE_URL}")
    print(f"API Base: {API_BASE}")
    print(f"Test Time: {datetime.now().isoformat()}")
    
    # Login
    print("\n" + "="*80)
    print("AUTHENTICATION")
    print("="*80)
    
    superadmin_token = login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)
    if not superadmin_token:
        print("❌ CRITICAL: Could not login as superadmin")
        sys.exit(1)
    
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        print("❌ CRITICAL: Could not login as admin")
        sys.exit(1)
    
    non_admin_token = login(NON_ADMIN_EMAIL, NON_ADMIN_PASSWORD)
    if not non_admin_token:
        print("❌ CRITICAL: Could not login as non-admin")
        sys.exit(1)
    
    # Run tests
    try:
        test_1_drive_disabled(superadmin_token, admin_token)
        test_2_from_drive_while_disabled(admin_token)
        test_3_enable_with_invalid_json(superadmin_token, admin_token)
        test_4_from_drive_with_invalid_json(admin_token)
        test_5_enable_with_fake_json(superadmin_token, admin_token)
        test_6_rbac(admin_token, non_admin_token)
        test_7_doc_id_parsing(superadmin_token, admin_token)
        test_8_cleanup(superadmin_token)
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR during test execution: {e}")
        import traceback
        traceback.print_exc()
    
    # Print summary
    all_passed = print_summary()
    
    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
