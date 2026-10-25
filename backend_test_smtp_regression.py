#!/usr/bin/env python3
"""
SMTP Email Send Path Regression Test
=====================================
Review request: Regression + behavior check on the SMTP email send path after a fix.
Base URL = REACT_APP_BACKEND_URL, /api prefix. Login OAuth2 FORM.
Accounts: superadmin@test.com/Super@2026 (super_admin), admin@test.com/admin123 (admin).

Background: SMTP "test email" reported success in prod but mail didn't deliver.
The fix: for Gmail/Workspace hosts the envelope sender (MAIL FROM) now uses the
AUTHENTICATED username (not a different From), captures refused recipients, and
returns clearer messages. Verify the endpoint behaves correctly and gracefully
(we cannot use a real mailbox, so focus on graceful behavior + no regression + no 500s).

TESTS (as superadmin unless noted):
1. Configure SMTP with a Gmail host + a From that DIFFERS from the username, using a fake/invalid app password
2. POST /api/integrations/email/test → MUST return HTTP 200 (NOT 500) with {ok:false, message: string}
3. Configure SMTP with an UNREACHABLE host
4. Port 465 path
5. Switch to Resend with a fake key
6. SECRET SAFETY: GET /api/integrations/settings → confirm raw smtp password and resend api_key are NEVER returned
7. RBAC: as admin@test.com POST /api/integrations/email/test → 403
8. COPY/SHARE GUARANTEE (email misconfigured): proposal send returns link even when email fails
9. CLEANUP: disable email
"""
import requests
import sys
from datetime import datetime

# Backend URL from frontend/.env
BACKEND_URL = "https://proposal-approve.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"

# Test credentials
SUPERADMIN_EMAIL = "superadmin@test.com"
SUPERADMIN_PASSWORD = "Super@2026"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

def login(email: str, password: str) -> str:
    """Login and return JWT token"""
    response = requests.post(
        f"{API_BASE}/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if response.status_code != 200:
        print(f"❌ Login failed for {email}: {response.status_code} {response.text}")
        sys.exit(1)
    token = response.json().get("access_token")
    print(f"✅ Logged in as {email}")
    return token

def test_1_configure_gmail_smtp_wrong_password(token: str):
    """TEST 1: Configure SMTP with Gmail host + From that DIFFERS from username + fake app password"""
    print("\n" + "="*80)
    print("TEST 1: Configure SMTP with Gmail host + wrong password")
    print("="*80)
    
    payload = {
        "email": {
            "enabled": True,
            "method": "smtp",
            "smtp": {
                "host": "smtp.gmail.com",
                "port": 587,
                "username": "doneet.dass@ddconsult.tech",
                "password": "fakeapppassword123",
                "from_email": "info@ddconsult.tech",
                "reply_to": "info@ddconsult.tech"
            }
        }
    }
    
    response = requests.put(
        f"{API_BASE}/integrations/settings",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {response.status_code}")
        print(f"Response: {response.text}")
        return False
    
    print(f"✅ PASSED: SMTP configuration saved (status {response.status_code})")
    return True

def test_2_test_email_wrong_password(token: str) -> tuple:
    """TEST 2: POST /api/integrations/email/test → MUST return 200 with {ok:false, message}"""
    print("\n" + "="*80)
    print("TEST 2: Test email with wrong password (MUST be 200, NOT 500)")
    print("="*80)
    
    response = requests.post(
        f"{API_BASE}/integrations/email/test",
        json={},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    status = response.status_code
    data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    
    print(f"Status: {status}")
    print(f"Response: {data}")
    
    if status != 200:
        print(f"❌ FAILED: Expected HTTP 200, got {status}")
        return False, ""
    
    if data.get("ok") is not False:
        print(f"❌ FAILED: Expected ok=false, got ok={data.get('ok')}")
        return False, ""
    
    message = data.get("message", "")
    if not message:
        print(f"❌ FAILED: Expected message string, got empty")
        return False, ""
    
    print(f"✅ PASSED: HTTP 200 with ok=false")
    print(f"📝 Message: {message}")
    
    # Check if message mentions App Password or login failure
    message_lower = message.lower()
    if "app password" in message_lower or "login" in message_lower or "auth" in message_lower:
        print(f"✅ Message correctly indicates SMTP login failure")
    else:
        print(f"⚠️  Message doesn't clearly indicate login failure (but test still passes)")
    
    return True, message

def test_3_unreachable_host(token: str) -> tuple:
    """TEST 3: Configure SMTP with UNREACHABLE host"""
    print("\n" + "="*80)
    print("TEST 3: Configure SMTP with unreachable host")
    print("="*80)
    
    # Configure
    payload = {
        "email": {
            "enabled": True,
            "method": "smtp",
            "smtp": {
                "host": "smtp.invalid.example",
                "port": 587,
                "username": "x@example.com",
                "password": "whatever12345",
                "from_email": "x@example.com"
            }
        }
    }
    
    response = requests.put(
        f"{API_BASE}/integrations/settings",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code != 200:
        print(f"❌ FAILED: Config save failed with {response.status_code}")
        return False, ""
    
    print(f"✅ Config saved")
    
    # Test
    response = requests.post(
        f"{API_BASE}/integrations/email/test",
        json={},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    status = response.status_code
    data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    
    print(f"Status: {status}")
    print(f"Response: {data}")
    
    if status != 200:
        print(f"❌ FAILED: Expected HTTP 200, got {status}")
        return False, ""
    
    if data.get("ok") is not False:
        print(f"❌ FAILED: Expected ok=false, got ok={data.get('ok')}")
        return False, ""
    
    message = data.get("message", "")
    if not message:
        print(f"❌ FAILED: Expected message string, got empty")
        return False, ""
    
    print(f"✅ PASSED: HTTP 200 with ok=false")
    print(f"📝 Message: {message}")
    
    return True, message

def test_4_port_465(token: str) -> tuple:
    """TEST 4: Port 465 path (implicit TLS)"""
    print("\n" + "="*80)
    print("TEST 4: Port 465 path (implicit TLS)")
    print("="*80)
    
    # Configure
    payload = {
        "email": {
            "enabled": True,
            "method": "smtp",
            "smtp": {
                "host": "smtp.invalid.example",
                "port": 465,
                "username": "x@example.com",
                "password": "whatever12345",
                "from_email": "x@example.com"
            }
        }
    }
    
    response = requests.put(
        f"{API_BASE}/integrations/settings",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code != 200:
        print(f"❌ FAILED: Config save failed with {response.status_code}")
        return False, ""
    
    print(f"✅ Config saved")
    
    # Test
    response = requests.post(
        f"{API_BASE}/integrations/email/test",
        json={},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    status = response.status_code
    data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    
    print(f"Status: {status}")
    print(f"Response: {data}")
    
    if status != 200:
        print(f"❌ FAILED: Expected HTTP 200, got {status} (confirms no crash on port 465)")
        return False, ""
    
    if data.get("ok") is not False:
        print(f"❌ FAILED: Expected ok=false, got ok={data.get('ok')}")
        return False, ""
    
    message = data.get("message", "")
    print(f"✅ PASSED: HTTP 200 with ok=false (no crash on port 465)")
    print(f"📝 Message: {message}")
    
    return True, message

def test_5_resend_fake_key(token: str) -> tuple:
    """TEST 5: Switch to Resend with fake key"""
    print("\n" + "="*80)
    print("TEST 5: Switch to Resend with fake key")
    print("="*80)
    
    # Configure
    payload = {
        "email": {
            "enabled": True,
            "method": "resend",
            "resend": {
                "api_key": "re_fake_123",
                "from_email": "proposals@example.com"
            }
        }
    }
    
    response = requests.put(
        f"{API_BASE}/integrations/settings",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code != 200:
        print(f"❌ FAILED: Config save failed with {response.status_code}")
        return False, ""
    
    print(f"✅ Config saved")
    
    # Test
    response = requests.post(
        f"{API_BASE}/integrations/email/test",
        json={},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    status = response.status_code
    data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    
    print(f"Status: {status}")
    print(f"Response: {data}")
    
    if status != 200:
        print(f"❌ FAILED: Expected HTTP 200, got {status}")
        return False, ""
    
    if data.get("ok") is not False:
        print(f"❌ FAILED: Expected ok=false, got ok={data.get('ok')}")
        return False, ""
    
    message = data.get("message", "")
    print(f"✅ PASSED: HTTP 200 with ok=false (Resend path still works)")
    print(f"📝 Message: {message}")
    
    return True, message

def test_6_secret_safety(token: str):
    """TEST 6: GET /api/integrations/settings → confirm secrets are NEVER returned"""
    print("\n" + "="*80)
    print("TEST 6: SECRET SAFETY - GET settings should mask secrets")
    print("="*80)
    
    response = requests.get(
        f"{API_BASE}/integrations/settings",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code != 200:
        print(f"❌ FAILED: GET settings failed with {response.status_code}")
        return False
    
    data = response.json()
    email_cfg = data.get("email", {})
    
    # Check SMTP password
    smtp = email_cfg.get("smtp", {})
    smtp_password = smtp.get("password", None)
    has_password = smtp.get("has_password", False)
    
    if smtp_password and smtp_password != "":
        print(f"❌ FAILED: Raw SMTP password returned: {smtp_password}")
        return False
    
    print(f"✅ SMTP password NOT returned (has_password={has_password})")
    
    # Check Resend API key
    resend = email_cfg.get("resend", {})
    api_key = resend.get("api_key", None)
    has_api_key = resend.get("has_api_key", False)
    api_key_masked = resend.get("api_key_masked", "")
    
    if api_key and api_key != "":
        print(f"❌ FAILED: Raw Resend API key returned: {api_key}")
        return False
    
    print(f"✅ Resend API key NOT returned (has_api_key={has_api_key}, masked={api_key_masked})")
    
    print(f"✅ PASSED: Secrets are properly masked")
    return True

def test_7_rbac_admin(admin_token: str):
    """TEST 7: RBAC - admin should get 403 on test endpoint"""
    print("\n" + "="*80)
    print("TEST 7: RBAC - admin@test.com should get 403")
    print("="*80)
    
    response = requests.post(
        f"{API_BASE}/integrations/email/test",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    status = response.status_code
    print(f"Status: {status}")
    
    if status != 403:
        print(f"❌ FAILED: Expected 403, got {status}")
        return False
    
    print(f"✅ PASSED: Admin correctly denied (403)")
    return True

def test_8_proposal_send_with_bad_email(admin_token: str):
    """TEST 8: COPY/SHARE GUARANTEE - proposal send returns link even when email fails"""
    print("\n" + "="*80)
    print("TEST 8: Proposal send with misconfigured email (MUST return link)")
    print("="*80)
    
    # Create a proposal
    print("Creating test proposal...")
    create_response = requests.post(
        f"{API_BASE}/proposals",
        json={
            "client_name": "EmailFix Co",
            "proposal_title": "Fix Test"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    if create_response.status_code != 200:
        print(f"❌ FAILED: Proposal creation failed with {create_response.status_code}")
        print(f"Response: {create_response.text}")
        return False
    
    proposal_id = create_response.json().get("id")
    print(f"✅ Proposal created: {proposal_id}")
    
    # Get the proposal and set contact_email
    get_response = requests.get(
        f"{API_BASE}/proposals/{proposal_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    if get_response.status_code != 200:
        print(f"❌ FAILED: Get proposal failed with {get_response.status_code}")
        return False
    
    proposal_data = get_response.json()
    proposal_data["data"]["contact_email"] = "client@example.com"
    
    # Update with contact_email
    update_response = requests.put(
        f"{API_BASE}/proposals/{proposal_id}",
        json=proposal_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    if update_response.status_code != 200:
        print(f"❌ FAILED: Update proposal failed with {update_response.status_code}")
        return False
    
    print(f"✅ Proposal updated with contact_email")
    
    # Send proposal (email is misconfigured from test 5)
    send_response = requests.post(
        f"{API_BASE}/proposals/{proposal_id}/send",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    status = send_response.status_code
    data = send_response.json() if send_response.headers.get("content-type", "").startswith("application/json") else {}
    
    print(f"Status: {status}")
    print(f"Response: {data}")
    
    if status != 200:
        print(f"❌ FAILED: Expected 200, got {status}")
        return False
    
    proposal_link = data.get("proposal_link", "")
    email_sent = data.get("email_sent", None)
    email_message = data.get("email_message", "")
    
    if not proposal_link or "/proposal/" not in proposal_link:
        print(f"❌ FAILED: proposal_link missing or invalid: {proposal_link}")
        return False
    
    print(f"✅ proposal_link present: {proposal_link}")
    
    if email_sent is not False:
        print(f"⚠️  WARNING: email_sent={email_sent}, expected False (email misconfigured)")
    else:
        print(f"✅ email_sent=false (as expected)")
    
    if not email_message:
        print(f"⚠️  WARNING: email_message is empty")
    else:
        print(f"✅ email_message present: {email_message}")
    
    print(f"✅ PASSED: Proposal link returned regardless of email failure")
    
    # Cleanup: delete the test proposal
    delete_response = requests.delete(
        f"{API_BASE}/proposals/{proposal_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    if delete_response.status_code == 200:
        print(f"✅ Test proposal deleted")
    
    return True

def test_9_cleanup(token: str):
    """TEST 9: CLEANUP - disable email"""
    print("\n" + "="*80)
    print("TEST 9: CLEANUP - disable email")
    print("="*80)
    
    payload = {
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
        f"{API_BASE}/integrations/settings",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code != 200:
        print(f"❌ FAILED: Cleanup failed with {response.status_code}")
        return False
    
    print(f"✅ PASSED: Email disabled and cleaned up")
    return True

def main():
    print("="*80)
    print("SMTP EMAIL SEND PATH REGRESSION TEST")
    print("="*80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test time: {datetime.now().isoformat()}")
    print()
    
    # Login as superadmin
    superadmin_token = login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)
    
    # Login as admin (for RBAC test)
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    
    results = {}
    messages = {}
    
    # Run tests
    results["test_1"] = test_1_configure_gmail_smtp_wrong_password(superadmin_token)
    results["test_2"], messages["test_2"] = test_2_test_email_wrong_password(superadmin_token)
    results["test_3"], messages["test_3"] = test_3_unreachable_host(superadmin_token)
    results["test_4"], messages["test_4"] = test_4_port_465(superadmin_token)
    results["test_5"], messages["test_5"] = test_5_resend_fake_key(superadmin_token)
    results["test_6"] = test_6_secret_safety(superadmin_token)
    results["test_7"] = test_7_rbac_admin(admin_token)
    results["test_8"] = test_8_proposal_send_with_bad_email(admin_token)
    results["test_9"] = test_9_cleanup(superadmin_token)
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    print()
    print(f"Total: {passed}/{total} tests passed")
    
    # Print exact message strings for steps 2,3,4,5
    print("\n" + "="*80)
    print("EXACT MESSAGE STRINGS (for steps 2,3,4,5)")
    print("="*80)
    print(f"Test 2 (Gmail wrong password): {messages.get('test_2', 'N/A')}")
    print(f"Test 3 (Unreachable host): {messages.get('test_3', 'N/A')}")
    print(f"Test 4 (Port 465): {messages.get('test_4', 'N/A')}")
    print(f"Test 5 (Resend fake key): {messages.get('test_5', 'N/A')}")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
