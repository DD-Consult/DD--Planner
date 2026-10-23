#!/usr/bin/env python3
"""
Comprehensive Email Configuration Testing Script
Tests per-workspace Email (Resend) configuration + proposal/report email routing

Review Request Tests:
A) EMAIL SETTINGS CRUD (super_admin only) - 4 tests
B) TEST-SEND ENDPOINT - 2 tests
C) PROPOSAL SEND returns link when email is OFF - 2 tests

Backend URL: https://proposal-approve.preview.emergentagent.com/api
Credentials:
  - Super Admin: superadmin@test.com / Super@2026
  - Admin: admin@test.com / admin123
"""

import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "https://proposal-approve.preview.emergentagent.com/api"
SUPERADMIN_EMAIL = "superadmin@test.com"
SUPERADMIN_PASSWORD = "Super@2026"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

# Test tracking
tests_passed = 0
tests_failed = 0
test_results = []


def log_test(test_name, passed, details=""):
    """Log test result"""
    global tests_passed, tests_failed
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {test_name}")
    if details:
        print(f"  Details: {details}")
    
    test_results.append({
        "test": test_name,
        "passed": passed,
        "details": details
    })
    
    if passed:
        tests_passed += 1
    else:
        tests_failed += 1


def login(email, password):
    """Login and return JWT token"""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token")
    else:
        print(f"❌ Login failed for {email}: {response.status_code} - {response.text}")
        return None


def test_section_a_email_settings_crud():
    """A) EMAIL SETTINGS CRUD (super_admin only) - 4 tests"""
    print("\n" + "="*80)
    print("SECTION A: EMAIL SETTINGS CRUD (super_admin only)")
    print("="*80)
    
    # Login as superadmin
    superadmin_token = login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)
    if not superadmin_token:
        log_test("A.0 - Superadmin Login", False, "Failed to login as superadmin")
        return
    log_test("A.0 - Superadmin Login", True, "Successfully authenticated")
    
    headers_super = {"Authorization": f"Bearer {superadmin_token}"}
    
    # TEST 1: GET email settings - confirm structure
    print("\n--- Test A.1: GET /api/integrations/settings ---")
    response = requests.get(f"{BASE_URL}/integrations/settings", headers=headers_super)
    
    if response.status_code == 200:
        settings = response.json()
        email_config = settings.get("email", {})
        
        # Check required keys
        required_keys = ["enabled", "has_api_key", "api_key_masked", "from_email", "reply_to"]
        has_all_keys = all(key in email_config for key in required_keys)
        
        # Check that raw api_key is NOT returned (should be empty string or not present)
        raw_key_not_present = email_config.get("api_key", "") == ""
        
        if has_all_keys and raw_key_not_present:
            log_test("A.1 - GET email settings structure", True, 
                    f"All required keys present: {required_keys}, raw api_key not exposed")
            print(f"  Email config: enabled={email_config.get('enabled')}, "
                  f"has_api_key={email_config.get('has_api_key')}, "
                  f"from_email={email_config.get('from_email')}, "
                  f"reply_to={email_config.get('reply_to')}")
        else:
            log_test("A.1 - GET email settings structure", False, 
                    f"Missing keys or raw api_key exposed. Keys: {list(email_config.keys())}")
    else:
        log_test("A.1 - GET email settings structure", False, 
                f"HTTP {response.status_code}: {response.text}")
    
    # TEST 2: PUT email settings - confirm masking of API key
    print("\n--- Test A.2: PUT /api/integrations/settings (set email config) ---")
    payload = {
        "email": {
            "enabled": True,
            "api_key": "re_test_1234567890abcdef",
            "from_email": "proposals@example.com",
            "reply_to": "hello@example.com"
        }
    }
    response = requests.put(
        f"{BASE_URL}/integrations/settings",
        json=payload,
        headers=headers_super
    )
    
    if response.status_code == 200:
        # Now GET to verify masking
        response_get = requests.get(f"{BASE_URL}/integrations/settings", headers=headers_super)
        if response_get.status_code == 200:
            settings = response_get.json()
            email_config = settings.get("email", {})
            
            # Critical checks
            enabled_correct = email_config.get("enabled") == True
            has_api_key_correct = email_config.get("has_api_key") == True
            from_email_correct = email_config.get("from_email") == "proposals@example.com"
            reply_to_correct = email_config.get("reply_to") == "hello@example.com"
            
            # CRITICAL: Raw key should NOT be present anywhere
            raw_key_not_in_response = "re_test_1234567890abcdef" not in json.dumps(settings)
            api_key_empty = email_config.get("api_key", "") == ""
            
            all_checks = (enabled_correct and has_api_key_correct and from_email_correct 
                         and reply_to_correct and raw_key_not_in_response and api_key_empty)
            
            if all_checks:
                log_test("A.2 - PUT email settings + verify masking", True,
                        f"Settings saved correctly, raw key NOT exposed (only masked: {email_config.get('api_key_masked')})")
            else:
                log_test("A.2 - PUT email settings + verify masking", False,
                        f"enabled={enabled_correct}, has_api_key={has_api_key_correct}, "
                        f"from_email={from_email_correct}, reply_to={reply_to_correct}, "
                        f"raw_key_not_in_response={raw_key_not_in_response}, api_key_empty={api_key_empty}")
        else:
            log_test("A.2 - PUT email settings + verify masking", False,
                    f"GET after PUT failed: HTTP {response_get.status_code}")
    else:
        log_test("A.2 - PUT email settings + verify masking", False,
                f"PUT failed: HTTP {response.status_code}: {response.text}")
    
    # TEST 3: PRESERVE SECRET - PUT with empty api_key should preserve existing key
    print("\n--- Test A.3: PUT with empty api_key (preserve secret) ---")
    payload_preserve = {
        "email": {
            "enabled": True,
            "api_key": "",  # Empty - should preserve existing
            "from_email": "proposals@example.com",
            "reply_to": "hello@example.com"
        }
    }
    response = requests.put(
        f"{BASE_URL}/integrations/settings",
        json=payload_preserve,
        headers=headers_super
    )
    
    if response.status_code == 200:
        # GET to verify has_api_key is still true
        response_get = requests.get(f"{BASE_URL}/integrations/settings", headers=headers_super)
        if response_get.status_code == 200:
            settings = response_get.json()
            email_config = settings.get("email", {})
            
            # has_api_key should STILL be true (preserved)
            has_api_key_preserved = email_config.get("has_api_key") == True
            
            if has_api_key_preserved:
                log_test("A.3 - Preserve secret with empty api_key", True,
                        "Empty api_key preserved the existing key (has_api_key still true)")
            else:
                log_test("A.3 - Preserve secret with empty api_key", False,
                        f"has_api_key={email_config.get('has_api_key')} (expected True)")
        else:
            log_test("A.3 - Preserve secret with empty api_key", False,
                    f"GET after PUT failed: HTTP {response_get.status_code}")
    else:
        log_test("A.3 - Preserve secret with empty api_key", False,
                f"PUT failed: HTTP {response.status_code}: {response.text}")
    
    # TEST 4: RBAC - admin should get 403
    print("\n--- Test A.4: RBAC - admin should get 403 ---")
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        log_test("A.4 - RBAC admin 403", False, "Failed to login as admin")
        return
    
    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    
    # Try GET as admin
    response_get = requests.get(f"{BASE_URL}/integrations/settings", headers=headers_admin)
    get_forbidden = response_get.status_code == 403
    
    # Try PUT as admin
    response_put = requests.put(
        f"{BASE_URL}/integrations/settings",
        json=payload,
        headers=headers_admin
    )
    put_forbidden = response_put.status_code == 403
    
    if get_forbidden and put_forbidden:
        log_test("A.4 - RBAC admin 403", True,
                "Admin correctly denied access (GET: 403, PUT: 403)")
    else:
        log_test("A.4 - RBAC admin 403", False,
                f"Admin should be denied. GET: {response_get.status_code}, PUT: {response_put.status_code}")


def test_section_b_test_send_endpoint():
    """B) TEST-SEND ENDPOINT - 2 tests"""
    print("\n" + "="*80)
    print("SECTION B: TEST-SEND ENDPOINT")
    print("="*80)
    
    # Login as superadmin
    superadmin_token = login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)
    if not superadmin_token:
        log_test("B.0 - Superadmin Login", False, "Failed to login as superadmin")
        return
    
    headers_super = {"Authorization": f"Bearer {superadmin_token}"}
    
    # TEST 5: Test-send with fake key (should return 200 with message, not 500)
    print("\n--- Test B.1: POST /api/integrations/email/test (with fake key) ---")
    response = requests.post(
        f"{BASE_URL}/integrations/email/test",
        json={},
        headers=headers_super
    )
    
    if response.status_code == 200:
        data = response.json()
        has_ok = "ok" in data
        has_message = "message" in data and isinstance(data.get("message"), str)
        
        if has_ok and has_message:
            log_test("B.1 - Test-send endpoint returns 200 with message", True,
                    f"ok={data.get('ok')}, message='{data.get('message')[:100]}...'")
            print(f"  Full message: {data.get('message')}")
        else:
            log_test("B.1 - Test-send endpoint returns 200 with message", False,
                    f"Missing ok or message fields. Response: {data}")
    else:
        log_test("B.1 - Test-send endpoint returns 200 with message", False,
                f"Expected 200, got HTTP {response.status_code}: {response.text}")
    
    # TEST 6: Disable email and test-send (should return 200 with "not configured" message)
    print("\n--- Test B.2: Test-send with email disabled ---")
    
    # First disable email
    payload_disable = {
        "email": {
            "enabled": False,
            "api_key": "",
            "from_email": "proposals@example.com",
            "reply_to": ""
        }
    }
    response_disable = requests.put(
        f"{BASE_URL}/integrations/settings",
        json=payload_disable,
        headers=headers_super
    )
    
    if response_disable.status_code == 200:
        # Now test-send
        response = requests.post(
            f"{BASE_URL}/integrations/email/test",
            json={},
            headers=headers_super
        )
        
        if response.status_code == 200:
            data = response.json()
            ok_is_false = data.get("ok") == False
            message_contains_not_configured = "not configured" in data.get("message", "").lower()
            
            if ok_is_false and message_contains_not_configured:
                log_test("B.2 - Test-send with email disabled", True,
                        f"Correctly returns ok=false with 'not configured' message: '{data.get('message')}'")
            else:
                log_test("B.2 - Test-send with email disabled", False,
                        f"ok={data.get('ok')}, message='{data.get('message')}'")
        else:
            log_test("B.2 - Test-send with email disabled", False,
                    f"Expected 200, got HTTP {response.status_code}: {response.text}")
    else:
        log_test("B.2 - Test-send with email disabled", False,
                f"Failed to disable email: HTTP {response_disable.status_code}")


def test_section_c_proposal_send_with_email_off():
    """C) PROPOSAL SEND returns link when email is OFF - 2 tests"""
    print("\n" + "="*80)
    print("SECTION C: PROPOSAL SEND returns link when email is OFF")
    print("="*80)
    
    # Login as admin (proposals require admin role)
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        log_test("C.0 - Admin Login", False, "Failed to login as admin")
        return
    
    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    
    # TEST 7: Create proposal, set contact_email, send with email OFF
    print("\n--- Test C.1: Proposal send returns link when email is OFF ---")
    
    # Create a test proposal
    create_payload = {
        "client_name": "Email Test Co",
        "proposal_title": "Email Test"
    }
    response_create = requests.post(
        f"{BASE_URL}/proposals",
        json=create_payload,
        headers=headers_admin
    )
    
    if response_create.status_code != 200:
        log_test("C.1 - Proposal send with email OFF", False,
                f"Failed to create proposal: HTTP {response_create.status_code}")
        return
    
    proposal = response_create.json()
    proposal_id = proposal.get("id")
    print(f"  Created proposal: {proposal_id}")
    
    # Get the proposal to update it with contact_email
    response_get = requests.get(f"{BASE_URL}/proposals/{proposal_id}", headers=headers_admin)
    if response_get.status_code != 200:
        log_test("C.1 - Proposal send with email OFF", False,
                f"Failed to get proposal: HTTP {response_get.status_code}")
        return
    
    proposal_data = response_get.json()
    data = proposal_data.get("data", {})
    data["contact_email"] = "client@example.com"
    
    # Update the proposal with contact_email
    update_payload = {"data": data}
    response_update = requests.put(
        f"{BASE_URL}/proposals/{proposal_id}",
        json=update_payload,
        headers=headers_admin
    )
    
    if response_update.status_code != 200:
        log_test("C.1 - Proposal send with email OFF", False,
                f"Failed to update proposal: HTTP {response_update.status_code}")
        return
    
    print(f"  Updated proposal with contact_email=client@example.com")
    
    # Send the proposal (email is currently disabled from Test B.2)
    response_send = requests.post(
        f"{BASE_URL}/proposals/{proposal_id}/send",
        headers=headers_admin
    )
    
    if response_send.status_code == 200:
        send_data = response_send.json()
        
        # CRITICAL checks
        has_proposal_link = "proposal_link" in send_data and "/proposal/" in send_data.get("proposal_link", "")
        has_email_sent = "email_sent" in send_data
        email_sent_is_false = send_data.get("email_sent") == False
        has_email_message = "email_message" in send_data and isinstance(send_data.get("email_message"), str)
        
        all_checks = has_proposal_link and has_email_sent and email_sent_is_false and has_email_message
        
        if all_checks:
            log_test("C.1 - Proposal send with email OFF", True,
                    f"Link returned: {send_data.get('proposal_link')}, "
                    f"email_sent={send_data.get('email_sent')}, "
                    f"email_message='{send_data.get('email_message')}'")
            print(f"  Proposal link: {send_data.get('proposal_link')}")
            print(f"  Email sent: {send_data.get('email_sent')}")
            print(f"  Email message: {send_data.get('email_message')}")
        else:
            log_test("C.1 - Proposal send with email OFF", False,
                    f"Missing required fields or incorrect values. "
                    f"has_proposal_link={has_proposal_link}, "
                    f"email_sent={send_data.get('email_sent')}, "
                    f"has_email_message={has_email_message}")
    else:
        log_test("C.1 - Proposal send with email OFF", False,
                f"Send failed: HTTP {response_send.status_code}: {response_send.text}")
    
    # TEST 8: Cleanup - reset email settings
    print("\n--- Test C.2: Cleanup - reset email settings ---")
    
    superadmin_token = login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)
    if not superadmin_token:
        log_test("C.2 - Cleanup", False, "Failed to login as superadmin for cleanup")
        return
    
    headers_super = {"Authorization": f"Bearer {superadmin_token}"}
    
    cleanup_payload = {
        "email": {
            "enabled": False,
            "api_key": "",
            "from_email": "",
            "reply_to": ""
        }
    }
    response_cleanup = requests.put(
        f"{BASE_URL}/integrations/settings",
        json=cleanup_payload,
        headers=headers_super
    )
    
    if response_cleanup.status_code == 200:
        log_test("C.2 - Cleanup email settings", True, "Email settings reset to clean state")
    else:
        log_test("C.2 - Cleanup email settings", False,
                f"Cleanup failed: HTTP {response_cleanup.status_code}")
    
    # Note: We're NOT deleting the proposal because it's now in "Sent" status
    # and the DELETE endpoint only allows deleting Draft proposals
    print(f"  Note: Proposal {proposal_id} left in 'Sent' status (cannot delete non-Draft)")


def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    total_tests = tests_passed + tests_failed
    pass_rate = (tests_passed / total_tests * 100) if total_tests > 0 else 0
    
    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {tests_passed} ✅")
    print(f"Failed: {tests_failed} ❌")
    print(f"Pass Rate: {pass_rate:.1f}%")
    
    if tests_failed > 0:
        print("\n❌ FAILED TESTS:")
        for result in test_results:
            if not result["passed"]:
                print(f"  - {result['test']}")
                if result["details"]:
                    print(f"    {result['details']}")
    
    print("\n" + "="*80)
    print("CRITICAL ASSERTIONS SUMMARY")
    print("="*80)
    
    critical_tests = [
        "A.2 - PUT email settings + verify masking",
        "A.3 - Preserve secret with empty api_key",
        "B.1 - Test-send endpoint returns 200 with message",
        "C.1 - Proposal send with email OFF"
    ]
    
    for test_name in critical_tests:
        result = next((r for r in test_results if r["test"] == test_name), None)
        if result:
            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            print(f"{status}: {test_name}")


def main():
    """Main test execution"""
    print("="*80)
    print("EMAIL CONFIGURATION TESTING")
    print("="*80)
    print(f"Backend URL: {BASE_URL}")
    print(f"Test Time: {datetime.now().isoformat()}")
    print("="*80)
    
    try:
        # Run all test sections
        test_section_a_email_settings_crud()
        test_section_b_test_send_endpoint()
        test_section_c_proposal_send_with_email_off()
        
        # Print summary
        print_summary()
        
        # Exit with appropriate code
        if tests_failed > 0:
            print("\n❌ SOME TESTS FAILED")
            exit(1)
        else:
            print("\n✅ ALL TESTS PASSED")
            exit(0)
    
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
