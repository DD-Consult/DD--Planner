#!/usr/bin/env python3
"""
Comprehensive backend test for NEW SMTP email method (added alongside Resend)
for DD Planner per-workspace email config.

Review Request: Verify SMTP email method with nested resend/smtp blocks,
secret masking, preservation, method switching, test-send, RBAC, and proposal
send with email off.

Test credentials:
- superadmin@test.com / Super@2026 (super_admin role)
- admin@test.com / admin123 (admin role)

Backend URL: https://proposal-approve.preview.emergentagent.com/api
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

# Test state
test_results = []
superadmin_token = None
admin_token = None
test_proposal_id = None


def log_test(step: str, passed: bool, details: str = ""):
    """Log test result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    test_results.append({"step": step, "passed": passed, "details": details})
    print(f"{status} - {step}")
    if details:
        print(f"    {details}")


def login(email: str, password: str) -> str:
    """Login and return access token."""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    raise Exception(f"Login failed: {response.status_code} {response.text}")


def get_headers(token: str) -> dict:
    """Get authorization headers."""
    return {"Authorization": f"Bearer {token}"}


def test_step_1_get_settings():
    """TEST 1: GET /api/integrations/settings → 200. Confirm settings.email exists
    with: method, resend {has_api_key, api_key_masked, from_email, reply_to} (no raw api_key),
    smtp {host, port, username, has_password, from_email, reply_to, use_tls} (no raw password).
    Defaults: smtp.host "smtp.gmail.com", smtp.port 587.
    """
    print("\n" + "="*80)
    print("TEST 1: GET /api/integrations/settings - Verify email structure")
    print("="*80)
    
    response = requests.get(
        f"{BASE_URL}/integrations/settings",
        headers=get_headers(superadmin_token)
    )
    
    if response.status_code != 200:
        log_test("Step 1: GET settings returns 200", False, 
                f"Got {response.status_code}: {response.text}")
        return
    
    log_test("Step 1: GET settings returns 200", True)
    
    data = response.json()
    
    # Check email section exists
    if "email" not in data:
        log_test("Step 1: email section exists", False, "email key not found in response")
        return
    log_test("Step 1: email section exists", True)
    
    email = data["email"]
    
    # Check method field
    if "method" not in email:
        log_test("Step 1: email.method exists", False)
        return
    log_test("Step 1: email.method exists", True, f"method={email['method']}")
    
    # Check resend block
    if "resend" not in email:
        log_test("Step 1: email.resend block exists", False)
        return
    log_test("Step 1: email.resend block exists", True)
    
    resend = email["resend"]
    required_resend_fields = ["has_api_key", "api_key_masked", "from_email", "reply_to"]
    for field in required_resend_fields:
        if field not in resend:
            log_test(f"Step 1: resend.{field} exists", False)
            return
    log_test("Step 1: resend has all required fields", True, 
            f"has_api_key={resend['has_api_key']}, from_email={resend['from_email']}")
    
    # CRITICAL: Check raw api_key is NOT present
    if "api_key" in resend and resend["api_key"]:
        log_test("Step 1: CRITICAL - raw resend.api_key NOT exposed", False,
                f"Found raw api_key: {resend['api_key']}")
        return
    log_test("Step 1: CRITICAL - raw resend.api_key NOT exposed", True)
    
    # Check smtp block
    if "smtp" not in email:
        log_test("Step 1: email.smtp block exists", False)
        return
    log_test("Step 1: email.smtp block exists", True)
    
    smtp = email["smtp"]
    required_smtp_fields = ["host", "port", "username", "has_password", "from_email", 
                           "reply_to", "use_tls"]
    for field in required_smtp_fields:
        if field not in smtp:
            log_test(f"Step 1: smtp.{field} exists", False)
            return
    log_test("Step 1: smtp has all required fields", True,
            f"host={smtp['host']}, port={smtp['port']}, has_password={smtp['has_password']}")
    
    # CRITICAL: Check raw password is NOT present
    if "password" in smtp and smtp["password"]:
        log_test("Step 1: CRITICAL - raw smtp.password NOT exposed", False,
                f"Found raw password: {smtp['password']}")
        return
    log_test("Step 1: CRITICAL - raw smtp.password NOT exposed", True)
    
    # Check defaults
    if smtp["host"] != "smtp.gmail.com":
        log_test("Step 1: smtp.host default is smtp.gmail.com", False,
                f"Got {smtp['host']}")
        return
    log_test("Step 1: smtp.host default is smtp.gmail.com", True)
    
    if smtp["port"] != 587:
        log_test("Step 1: smtp.port default is 587", False, f"Got {smtp['port']}")
        return
    log_test("Step 1: smtp.port default is 587", True)


def test_step_2_save_smtp():
    """TEST 2: SAVE SMTP: PUT /api/integrations/settings with SMTP config → 200.
    Then GET → assert email.enabled true, email.method "smtp", email.smtp.username correct,
    email.smtp.from_email correct, email.smtp.has_password true, and the RAW password
    is NOT present anywhere in the response.
    """
    print("\n" + "="*80)
    print("TEST 2: Save SMTP config and verify secret masking")
    print("="*80)
    
    smtp_config = {
        "email": {
            "enabled": True,
            "method": "smtp",
            "smtp": {
                "host": "smtp.gmail.com",
                "port": 587,
                "username": "sender@example.com",
                "password": "abcd efgh ijkl mnop",
                "from_email": "sender@example.com",
                "reply_to": "hello@example.com",
                "use_tls": True
            }
        }
    }
    
    response = requests.put(
        f"{BASE_URL}/integrations/settings",
        json=smtp_config,
        headers=get_headers(superadmin_token)
    )
    
    if response.status_code != 200:
        log_test("Step 2: PUT SMTP config returns 200", False,
                f"Got {response.status_code}: {response.text}")
        return
    log_test("Step 2: PUT SMTP config returns 200", True)
    
    # Now GET and verify
    response = requests.get(
        f"{BASE_URL}/integrations/settings",
        headers=get_headers(superadmin_token)
    )
    
    if response.status_code != 200:
        log_test("Step 2: GET after save returns 200", False,
                f"Got {response.status_code}")
        return
    log_test("Step 2: GET after save returns 200", True)
    
    data = response.json()
    email = data.get("email", {})
    
    # Verify enabled
    if not email.get("enabled"):
        log_test("Step 2: email.enabled is true", False, f"Got {email.get('enabled')}")
        return
    log_test("Step 2: email.enabled is true", True)
    
    # Verify method
    if email.get("method") != "smtp":
        log_test("Step 2: email.method is smtp", False, f"Got {email.get('method')}")
        return
    log_test("Step 2: email.method is smtp", True)
    
    smtp = email.get("smtp", {})
    
    # Verify username
    if smtp.get("username") != "sender@example.com":
        log_test("Step 2: smtp.username correct", False, f"Got {smtp.get('username')}")
        return
    log_test("Step 2: smtp.username correct", True)
    
    # Verify from_email
    if smtp.get("from_email") != "sender@example.com":
        log_test("Step 2: smtp.from_email correct", False, f"Got {smtp.get('from_email')}")
        return
    log_test("Step 2: smtp.from_email correct", True)
    
    # Verify has_password is true
    if not smtp.get("has_password"):
        log_test("Step 2: smtp.has_password is true", False, f"Got {smtp.get('has_password')}")
        return
    log_test("Step 2: smtp.has_password is true", True)
    
    # CRITICAL: Verify raw password is NOT present anywhere in response
    response_str = json.dumps(data)
    if "abcd efgh ijkl mnop" in response_str:
        log_test("Step 2: CRITICAL - raw password NOT in response", False,
                "Found raw password 'abcd efgh ijkl mnop' in response")
        return
    log_test("Step 2: CRITICAL - raw password NOT in response", True)


def test_step_3_preserve_smtp_password():
    """TEST 3: PRESERVE SMTP PASSWORD: PUT with smtp.password "" (empty) but keep
    other fields, method smtp → 200. GET → email.smtp.has_password still true.
    """
    print("\n" + "="*80)
    print("TEST 3: Preserve SMTP password when empty string submitted")
    print("="*80)
    
    # PUT with empty password
    smtp_config = {
        "email": {
            "enabled": True,
            "method": "smtp",
            "smtp": {
                "host": "smtp.gmail.com",
                "port": 587,
                "username": "sender@example.com",
                "password": "",  # Empty - should preserve existing
                "from_email": "sender@example.com",
                "reply_to": "hello@example.com",
                "use_tls": True
            }
        }
    }
    
    response = requests.put(
        f"{BASE_URL}/integrations/settings",
        json=smtp_config,
        headers=get_headers(superadmin_token)
    )
    
    if response.status_code != 200:
        log_test("Step 3: PUT with empty password returns 200", False,
                f"Got {response.status_code}: {response.text}")
        return
    log_test("Step 3: PUT with empty password returns 200", True)
    
    # GET and verify password is still saved
    response = requests.get(
        f"{BASE_URL}/integrations/settings",
        headers=get_headers(superadmin_token)
    )
    
    if response.status_code != 200:
        log_test("Step 3: GET after empty password PUT returns 200", False)
        return
    log_test("Step 3: GET after empty password PUT returns 200", True)
    
    data = response.json()
    smtp = data.get("email", {}).get("smtp", {})
    
    # CRITICAL: has_password should still be true
    if not smtp.get("has_password"):
        log_test("Step 3: CRITICAL - smtp.has_password still true", False,
                f"Got {smtp.get('has_password')}")
        return
    log_test("Step 3: CRITICAL - smtp.has_password still true", True,
            "Empty password preserved existing secret")


def test_step_4_switch_to_resend():
    """TEST 4: SWITCH METHOD TO RESEND & SAVE RESEND: PUT with method=resend and
    resend config → 200. GET → email.method "resend", email.resend.has_api_key true,
    raw key NOT present. IMPORTANT: also confirm email.smtp.has_password is STILL true
    (switching method must not wipe the saved SMTP password).
    """
    print("\n" + "="*80)
    print("TEST 4: Switch to Resend and verify SMTP password preserved")
    print("="*80)
    
    resend_config = {
        "email": {
            "enabled": True,
            "method": "resend",
            "resend": {
                "api_key": "re_test_999888777",
                "from_email": "proposals@example.com",
                "reply_to": ""
            }
        }
    }
    
    response = requests.put(
        f"{BASE_URL}/integrations/settings",
        json=resend_config,
        headers=get_headers(superadmin_token)
    )
    
    if response.status_code != 200:
        log_test("Step 4: PUT Resend config returns 200", False,
                f"Got {response.status_code}: {response.text}")
        return
    log_test("Step 4: PUT Resend config returns 200", True)
    
    # GET and verify
    response = requests.get(
        f"{BASE_URL}/integrations/settings",
        headers=get_headers(superadmin_token)
    )
    
    if response.status_code != 200:
        log_test("Step 4: GET after switch returns 200", False)
        return
    log_test("Step 4: GET after switch returns 200", True)
    
    data = response.json()
    email = data.get("email", {})
    
    # Verify method switched to resend
    if email.get("method") != "resend":
        log_test("Step 4: email.method is resend", False, f"Got {email.get('method')}")
        return
    log_test("Step 4: email.method is resend", True)
    
    resend = email.get("resend", {})
    
    # Verify has_api_key is true
    if not resend.get("has_api_key"):
        log_test("Step 4: resend.has_api_key is true", False,
                f"Got {resend.get('has_api_key')}")
        return
    log_test("Step 4: resend.has_api_key is true", True)
    
    # Verify raw key NOT present
    response_str = json.dumps(data)
    if "re_test_999888777" in response_str:
        log_test("Step 4: raw Resend key NOT in response", False,
                "Found raw key 're_test_999888777' in response")
        return
    log_test("Step 4: raw Resend key NOT in response", True)
    
    # CRITICAL: Verify SMTP password is STILL saved (switching method must not wipe it)
    smtp = email.get("smtp", {})
    if not smtp.get("has_password"):
        log_test("Step 4: CRITICAL - smtp.has_password STILL true after method switch", False,
                f"Got {smtp.get('has_password')} - switching method wiped SMTP password!")
        return
    log_test("Step 4: CRITICAL - smtp.has_password STILL true after method switch", True,
            "Switching method preserved SMTP password")


def test_step_5_test_send_resend_fake_key():
    """TEST 5: TEST-SEND (resend active, fake key): POST /api/integrations/email/test
    {} → 200 with {ok:false, message} (fake key → provider error; must be 200 not 500,
    message is a string).
    """
    print("\n" + "="*80)
    print("TEST 5: Test-send with fake Resend key (graceful failure)")
    print("="*80)
    
    response = requests.post(
        f"{BASE_URL}/integrations/email/test",
        json={},
        headers=get_headers(superadmin_token)
    )
    
    # CRITICAL: Must be 200, not 500
    if response.status_code != 200:
        log_test("Step 5: CRITICAL - test-send returns 200 (not 500)", False,
                f"Got {response.status_code}: {response.text}")
        return
    log_test("Step 5: CRITICAL - test-send returns 200 (not 500)", True)
    
    data = response.json()
    
    # Verify ok is false
    if data.get("ok") is not False:
        log_test("Step 5: response.ok is false", False, f"Got {data.get('ok')}")
        return
    log_test("Step 5: response.ok is false", True)
    
    # Verify message is present and is a string
    message = data.get("message")
    if not message or not isinstance(message, str):
        log_test("Step 5: response.message is a string", False,
                f"Got {type(message)}: {message}")
        return
    log_test("Step 5: response.message is a string", True,
            f"Message: {message[:100]}")


def test_step_6_test_send_smtp_bad_host():
    """TEST 6: TEST-SEND (smtp active, bad host): PUT with smtp config (bad host) →
    POST /api/integrations/email/test {} → 200 with {ok:false, message} (connection/login
    fails; must be 200 not 500, readable message).
    """
    print("\n" + "="*80)
    print("TEST 6: Test-send with bad SMTP host (graceful failure)")
    print("="*80)
    
    # First, switch to SMTP with bad host
    smtp_config = {
        "email": {
            "enabled": True,
            "method": "smtp",
            "smtp": {
                "host": "smtp.invalid.example",
                "port": 587,
                "username": "x@example.com",
                "password": "nopnopnopnop",
                "from_email": "x@example.com",
                "use_tls": True
            }
        }
    }
    
    response = requests.put(
        f"{BASE_URL}/integrations/settings",
        json=smtp_config,
        headers=get_headers(superadmin_token)
    )
    
    if response.status_code != 200:
        log_test("Step 6: PUT bad SMTP config returns 200", False,
                f"Got {response.status_code}")
        return
    log_test("Step 6: PUT bad SMTP config returns 200", True)
    
    # Now test-send
    response = requests.post(
        f"{BASE_URL}/integrations/email/test",
        json={},
        headers=get_headers(superadmin_token)
    )
    
    # CRITICAL: Must be 200, not 500
    if response.status_code != 200:
        log_test("Step 6: CRITICAL - test-send returns 200 (not 500)", False,
                f"Got {response.status_code}: {response.text}")
        return
    log_test("Step 6: CRITICAL - test-send returns 200 (not 500)", True)
    
    data = response.json()
    
    # Verify ok is false
    if data.get("ok") is not False:
        log_test("Step 6: response.ok is false", False, f"Got {data.get('ok')}")
        return
    log_test("Step 6: response.ok is false", True)
    
    # Verify message is present and readable
    message = data.get("message")
    if not message or not isinstance(message, str):
        log_test("Step 6: response.message is a readable string", False,
                f"Got {type(message)}: {message}")
        return
    log_test("Step 6: response.message is a readable string", True,
            f"Message: {message[:100]}")


def test_step_7_rbac():
    """TEST 7: RBAC: as admin@test.com GET /api/integrations/settings → 403;
    PUT → 403; POST /api/integrations/email/test → 403.
    """
    print("\n" + "="*80)
    print("TEST 7: RBAC - admin cannot access integration settings")
    print("="*80)
    
    # GET as admin
    response = requests.get(
        f"{BASE_URL}/integrations/settings",
        headers=get_headers(admin_token)
    )
    
    if response.status_code != 403:
        log_test("Step 7: GET as admin returns 403", False,
                f"Got {response.status_code}")
        return
    log_test("Step 7: GET as admin returns 403", True)
    
    # PUT as admin
    response = requests.put(
        f"{BASE_URL}/integrations/settings",
        json={"email": {"enabled": False}},
        headers=get_headers(admin_token)
    )
    
    if response.status_code != 403:
        log_test("Step 7: PUT as admin returns 403", False,
                f"Got {response.status_code}")
        return
    log_test("Step 7: PUT as admin returns 403", True)
    
    # POST test-send as admin
    response = requests.post(
        f"{BASE_URL}/integrations/email/test",
        json={},
        headers=get_headers(admin_token)
    )
    
    if response.status_code != 403:
        log_test("Step 7: POST test-send as admin returns 403", False,
                f"Got {response.status_code}")
        return
    log_test("Step 7: POST test-send as admin returns 403", True)


def test_step_8_proposal_send_email_off():
    """TEST 8: COPY/SHARE STILL WORKS WHEN EMAIL OFF: PUT email disabled → As admin,
    create proposal, set contact_email, POST /api/proposals/{id}/send → 200 and MUST
    return proposal_link (contains "/proposal/"), email_sent=false, email_message (string).
    Link present regardless.
    """
    print("\n" + "="*80)
    print("TEST 8: Proposal send returns link when email is OFF")
    print("="*80)
    
    global test_proposal_id
    
    # First, disable email
    config = {
        "email": {
            "enabled": False,
            "method": "smtp",
            "smtp": {
                "host": "smtp.gmail.com",
                "port": 587,
                "username": "",
                "password": "",
                "from_email": "",
                "reply_to": ""
            }
        }
    }
    
    response = requests.put(
        f"{BASE_URL}/integrations/settings",
        json=config,
        headers=get_headers(superadmin_token)
    )
    
    if response.status_code != 200:
        log_test("Step 8: Disable email returns 200", False,
                f"Got {response.status_code}")
        return
    log_test("Step 8: Disable email returns 200", True)
    
    # Create proposal as admin
    proposal_data = {
        "client_name": "SMTP Test Co",
        "proposal_title": "SMTP Test"
    }
    
    response = requests.post(
        f"{BASE_URL}/proposals",
        json=proposal_data,
        headers=get_headers(admin_token)
    )
    
    if response.status_code != 200:
        log_test("Step 8: Create proposal returns 200", False,
                f"Got {response.status_code}: {response.text}")
        return
    log_test("Step 8: Create proposal returns 200", True)
    
    proposal = response.json()
    test_proposal_id = proposal.get("id")
    
    if not test_proposal_id:
        log_test("Step 8: Proposal has id", False, "No id in response")
        return
    log_test("Step 8: Proposal has id", True, f"id={test_proposal_id}")
    
    # Get proposal and set contact_email
    response = requests.get(
        f"{BASE_URL}/proposals/{test_proposal_id}",
        headers=get_headers(admin_token)
    )
    
    if response.status_code != 200:
        log_test("Step 8: GET proposal returns 200", False)
        return
    log_test("Step 8: GET proposal returns 200", True)
    
    proposal_data = response.json()
    proposal_data["data"]["contact_email"] = "client@example.com"
    
    # Update proposal with contact_email
    response = requests.put(
        f"{BASE_URL}/proposals/{test_proposal_id}",
        json=proposal_data,
        headers=get_headers(admin_token)
    )
    
    if response.status_code != 200:
        log_test("Step 8: PUT proposal with contact_email returns 200", False,
                f"Got {response.status_code}")
        return
    log_test("Step 8: PUT proposal with contact_email returns 200", True)
    
    # Send proposal
    response = requests.post(
        f"{BASE_URL}/proposals/{test_proposal_id}/send",
        json={},
        headers=get_headers(admin_token)
    )
    
    if response.status_code != 200:
        log_test("Step 8: POST send proposal returns 200", False,
                f"Got {response.status_code}: {response.text}")
        return
    log_test("Step 8: POST send proposal returns 200", True)
    
    data = response.json()
    
    # CRITICAL: Verify proposal_link is present
    proposal_link = data.get("proposal_link")
    if not proposal_link:
        log_test("Step 8: CRITICAL - proposal_link present", False,
                "No proposal_link in response")
        return
    log_test("Step 8: CRITICAL - proposal_link present", True)
    
    # Verify link contains "/proposal/"
    if "/proposal/" not in proposal_link:
        log_test("Step 8: proposal_link contains /proposal/", False,
                f"Got {proposal_link}")
        return
    log_test("Step 8: proposal_link contains /proposal/", True, f"Link: {proposal_link}")
    
    # Verify email_sent is false
    if data.get("email_sent") is not False:
        log_test("Step 8: email_sent is false", False, f"Got {data.get('email_sent')}")
        return
    log_test("Step 8: email_sent is false", True)
    
    # Verify email_message is present and is a string
    email_message = data.get("email_message")
    if not email_message or not isinstance(email_message, str):
        log_test("Step 8: email_message is a string", False,
                f"Got {type(email_message)}: {email_message}")
        return
    log_test("Step 8: email_message is a string", True, f"Message: {email_message}")


def test_step_9_cleanup():
    """TEST 9: CLEANUP: as superadmin PUT to reset email config. Delete test proposal.
    """
    print("\n" + "="*80)
    print("TEST 9: Cleanup - reset email config and delete test proposal")
    print("="*80)
    
    # Reset email config
    config = {
        "email": {
            "enabled": False,
            "method": "resend",
            "resend": {
                "api_key": "",
                "from_email": "",
                "reply_to": ""
            },
            "smtp": {
                "host": "smtp.gmail.com",
                "port": 587,
                "username": "",
                "password": "",
                "from_email": "",
                "reply_to": ""
            }
        }
    }
    
    response = requests.put(
        f"{BASE_URL}/integrations/settings",
        json=config,
        headers=get_headers(superadmin_token)
    )
    
    if response.status_code != 200:
        log_test("Step 9: Reset email config returns 200", False,
                f"Got {response.status_code}")
        return
    log_test("Step 9: Reset email config returns 200", True)
    
    # Delete test proposal if it exists
    if test_proposal_id:
        response = requests.delete(
            f"{BASE_URL}/proposals/{test_proposal_id}",
            headers=get_headers(admin_token)
        )
        
        if response.status_code == 200:
            log_test("Step 9: Delete test proposal successful", True)
        else:
            log_test("Step 9: Delete test proposal", False,
                    f"Got {response.status_code} (may not exist)")
    else:
        log_test("Step 9: No test proposal to delete", True, "Skipped")


def print_summary():
    """Print test summary."""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for r in test_results if r["passed"])
    total = len(test_results)
    
    print(f"\nTotal: {passed}/{total} tests passed ({passed*100//total}% success rate)\n")
    
    # Group by step
    current_step = None
    for result in test_results:
        step = result["step"].split(":")[0]
        if step != current_step:
            print(f"\n{step}:")
            current_step = step
        
        status = "✅" if result["passed"] else "❌"
        print(f"  {status} {result['step']}")
        if result["details"] and not result["passed"]:
            print(f"      {result['details']}")
    
    # Print critical assertions
    print("\n" + "="*80)
    print("CRITICAL ASSERTIONS")
    print("="*80)
    
    critical_tests = [
        ("Step 1: CRITICAL - raw resend.api_key NOT exposed", 
         "Raw Resend API key never returned in GET response"),
        ("Step 1: CRITICAL - raw smtp.password NOT exposed",
         "Raw SMTP password never returned in GET response"),
        ("Step 2: CRITICAL - raw password NOT in response",
         "Raw SMTP password not present after save"),
        ("Step 3: CRITICAL - smtp.has_password still true",
         "Empty password preserves existing secret"),
        ("Step 4: CRITICAL - smtp.has_password STILL true after method switch",
         "Switching method preserves saved SMTP password"),
        ("Step 5: CRITICAL - test-send returns 200 (not 500)",
         "Test endpoint returns 200 with message (not 500) for fake Resend key"),
        ("Step 6: CRITICAL - test-send returns 200 (not 500)",
         "Test endpoint returns 200 with message (not 500) for bad SMTP host"),
        ("Step 8: CRITICAL - proposal_link present",
         "Proposal send returns link when email is OFF"),
    ]
    
    for test_name, description in critical_tests:
        result = next((r for r in test_results if r["step"] == test_name), None)
        if result:
            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            print(f"{status} - {description}")
    
    print("\n" + "="*80)
    if passed == total:
        print("✅✅✅ ALL TESTS PASSED ✅✅✅")
        print("The NEW SMTP email method is FULLY FUNCTIONAL and working as specified.")
    else:
        print(f"⚠️  {total - passed} test(s) failed")
    print("="*80)


def main():
    """Run all tests."""
    global superadmin_token, admin_token
    
    print("="*80)
    print("SMTP EMAIL METHOD COMPREHENSIVE BACKEND TEST")
    print("="*80)
    print(f"Backend URL: {BASE_URL}")
    print(f"Test credentials: {SUPERADMIN_EMAIL}, {ADMIN_EMAIL}")
    print(f"Test started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Login
        print("\nAuthenticating...")
        superadmin_token = login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)
        print(f"✅ Logged in as {SUPERADMIN_EMAIL}")
        
        admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
        print(f"✅ Logged in as {ADMIN_EMAIL}")
        
        # Run tests
        test_step_1_get_settings()
        test_step_2_save_smtp()
        test_step_3_preserve_smtp_password()
        test_step_4_switch_to_resend()
        test_step_5_test_send_resend_fake_key()
        test_step_6_test_send_smtp_bad_host()
        test_step_7_rbac()
        test_step_8_proposal_send_email_off()
        test_step_9_cleanup()
        
        # Print summary
        print_summary()
        
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
