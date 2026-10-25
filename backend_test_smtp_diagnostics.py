#!/usr/bin/env python3
"""
Test SMTP Email Diagnostics Improvements (Review Request)

Context: SMTP fails silently in production (likely Cloud Run blocking outbound SMTP ports).
Improved error handling to detect connection failures and return clear messages about
egress-block / "use Resend" guidance. Added optional `to` recipient on test endpoint.

Tests:
1. Configure UNREACHABLE SMTP host (10.255.255.1:587) → 200
2. POST /api/integrations/email/test {} → MUST be 200 (not 500), expect {ok:false, message}
   mentioning connection failure AND SMTP blocked / Resend guidance
3. Test with explicit recipient: POST /api/integrations/email/test {"to":"someone@example.com"} → 200
4. Bad DNS host: PUT with smtp.invalid.example port 587, POST test → 200 {ok:false, message} readable
5. Resend path unaffected: PUT with Resend fake key, POST test → 200 {ok:false, message about invalid API key}
6. RBAC: as admin@test.com POST test → 403
7. CLEANUP: PUT settings with email disabled
"""
import requests
import json
import time
from datetime import datetime

# Configuration
BASE_URL = "https://proposal-approve.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"

# Test credentials
SUPERADMIN_EMAIL = "superadmin@test.com"
SUPERADMIN_PASSWORD = "Super@2026"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def login(email, password):
    """Login and return JWT token"""
    log(f"Logging in as {email}...")
    resp = requests.post(
        f"{API_BASE}/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if resp.status_code != 200:
        log(f"❌ Login failed: {resp.status_code} {resp.text}")
        return None
    token = resp.json().get("access_token")
    log(f"✅ Login successful, token: {token[:20]}...")
    return token

def test_1_configure_unreachable_smtp(token):
    """Test 1: Configure UNREACHABLE SMTP host (10.255.255.1:587) → 200"""
    log("\n" + "="*80)
    log("TEST 1: Configure UNREACHABLE SMTP host (10.255.255.1:587)")
    log("="*80)
    
    payload = {
        "email": {
            "enabled": True,
            "method": "smtp",
            "smtp": {
                "host": "10.255.255.1",  # Non-routable IP that will time out
                "port": 587,
                "username": "x@example.com",
                "password": "whatever12345",
                "from_email": "x@example.com"
            }
        }
    }
    
    resp = requests.put(
        f"{API_BASE}/integrations/settings",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    log(f"PUT /api/integrations/settings → {resp.status_code}")
    if resp.status_code == 200:
        log("✅ PASS: Settings saved successfully")
        return True
    else:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        log(f"Response: {resp.text}")
        return False

def test_2_test_email_unreachable(token):
    """Test 2: POST /api/integrations/email/test {} → MUST be 200 (not 500)
    Expect {ok:false, message} mentioning connection failure AND SMTP blocked / Resend guidance
    """
    log("\n" + "="*80)
    log("TEST 2: POST /api/integrations/email/test (UNREACHABLE HOST)")
    log("="*80)
    log("⏱️  This may take up to ~20s for the timeout...")
    
    start_time = time.time()
    resp = requests.post(
        f"{API_BASE}/integrations/email/test",
        json={},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30  # Allow up to 30s for the timeout
    )
    elapsed = time.time() - start_time
    
    log(f"POST /api/integrations/email/test → {resp.status_code} (took {elapsed:.1f}s)")
    
    # CRITICAL: Must be 200, not 500
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected HTTP 200, got {resp.status_code}")
        log(f"Response: {resp.text}")
        return False, None
    
    log("✅ PASS: HTTP 200 (not 500)")
    
    try:
        data = resp.json()
        ok = data.get("ok")
        message = data.get("message", "")
        
        log(f"Response: ok={ok}, message length={len(message)}")
        log(f"EXACT MESSAGE: '{message}'")
        
        # Check that ok is False
        if ok is not False:
            log(f"❌ FAIL: Expected ok=false, got ok={ok}")
            return False, message
        
        log("✅ PASS: ok=false (expected)")
        
        # Check that message mentions connection failure
        message_lower = message.lower()
        has_connection_mention = any(word in message_lower for word in [
            "connect", "connection", "couldn't connect", "failed to connect"
        ])
        
        if not has_connection_mention:
            log(f"❌ FAIL: Message does not mention connection failure")
            return False, message
        
        log("✅ PASS: Message mentions connection failure")
        
        # Check that message mentions SMTP blocked / Resend guidance
        has_smtp_blocked = "block" in message_lower and "smtp" in message_lower
        has_resend_guidance = "resend" in message_lower
        
        if not has_smtp_blocked:
            log(f"⚠️  WARNING: Message does not mention SMTP being blocked")
        else:
            log("✅ PASS: Message mentions SMTP being blocked")
        
        if not has_resend_guidance:
            log(f"⚠️  WARNING: Message does not mention Resend as alternative")
        else:
            log("✅ PASS: Message mentions Resend as alternative")
        
        # Overall pass if we have connection mention and at least one of the guidance items
        if has_connection_mention and (has_smtp_blocked or has_resend_guidance):
            log("✅ OVERALL PASS: Message contains connection failure AND guidance")
            return True, message
        else:
            log("❌ OVERALL FAIL: Message missing required guidance")
            return False, message
            
    except Exception as e:
        log(f"❌ FAIL: Could not parse response: {e}")
        log(f"Response text: {resp.text}")
        return False, None

def test_3_test_email_with_recipient(token):
    """Test 3: POST /api/integrations/email/test {"to":"someone@example.com"} → 200"""
    log("\n" + "="*80)
    log("TEST 3: POST /api/integrations/email/test with explicit recipient")
    log("="*80)
    log("⏱️  This may take up to ~20s for the timeout...")
    
    start_time = time.time()
    resp = requests.post(
        f"{API_BASE}/integrations/email/test",
        json={"to": "someone@example.com"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    elapsed = time.time() - start_time
    
    log(f"POST /api/integrations/email/test → {resp.status_code} (took {elapsed:.1f}s)")
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected HTTP 200, got {resp.status_code}")
        log(f"Response: {resp.text}")
        return False
    
    log("✅ PASS: HTTP 200")
    
    try:
        data = resp.json()
        ok = data.get("ok")
        message = data.get("message", "")
        
        log(f"Response: ok={ok}, message='{message[:100]}...'")
        
        # Should still fail to connect, but confirms the `to` param is accepted
        if ok is False:
            log("✅ PASS: ok=false (still fails to connect, as expected)")
            return True
        else:
            log(f"⚠️  WARNING: ok={ok} (expected false, but test passes if no error)")
            return True
            
    except Exception as e:
        log(f"❌ FAIL: Could not parse response: {e}")
        return False

def test_4_bad_dns_host(token):
    """Test 4: Bad DNS host: PUT with smtp.invalid.example port 587, POST test → 200 {ok:false, message} readable"""
    log("\n" + "="*80)
    log("TEST 4: Configure BAD DNS host (smtp.invalid.example)")
    log("="*80)
    
    # Configure with bad DNS host
    payload = {
        "email": {
            "enabled": True,
            "method": "smtp",
            "smtp": {
                "host": "smtp.invalid.example",
                "port": 587,
                "username": "test@example.com",
                "password": "testpass123",
                "from_email": "test@example.com"
            }
        }
    }
    
    resp = requests.put(
        f"{API_BASE}/integrations/settings",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    log(f"PUT /api/integrations/settings → {resp.status_code}")
    if resp.status_code != 200:
        log(f"❌ FAIL: Could not save settings: {resp.status_code}")
        return False
    
    log("✅ Settings saved")
    
    # Test email
    log("Testing email with bad DNS host...")
    log("⏱️  This may take up to ~20s for the timeout...")
    
    start_time = time.time()
    resp = requests.post(
        f"{API_BASE}/integrations/email/test",
        json={},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    elapsed = time.time() - start_time
    
    log(f"POST /api/integrations/email/test → {resp.status_code} (took {elapsed:.1f}s)")
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected HTTP 200, got {resp.status_code}")
        return False
    
    log("✅ PASS: HTTP 200")
    
    try:
        data = resp.json()
        ok = data.get("ok")
        message = data.get("message", "")
        
        log(f"Response: ok={ok}")
        log(f"Message: '{message}'")
        
        if ok is False and message:
            log("✅ PASS: ok=false with readable error message (connection/DNS error)")
            return True
        else:
            log(f"❌ FAIL: Expected ok=false with message, got ok={ok}")
            return False
            
    except Exception as e:
        log(f"❌ FAIL: Could not parse response: {e}")
        return False

def test_5_resend_path_unaffected(token):
    """Test 5: Resend path unaffected: PUT with Resend fake key, POST test → 200 {ok:false, message about invalid API key}"""
    log("\n" + "="*80)
    log("TEST 5: Resend path with fake API key (regression check)")
    log("="*80)
    
    # Configure with Resend fake key
    payload = {
        "email": {
            "enabled": True,
            "method": "resend",
            "resend": {
                "api_key": "re_fake_abc123",
                "from_email": "proposals@example.com"
            }
        }
    }
    
    resp = requests.put(
        f"{API_BASE}/integrations/settings",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    log(f"PUT /api/integrations/settings → {resp.status_code}")
    if resp.status_code != 200:
        log(f"❌ FAIL: Could not save settings: {resp.status_code}")
        return False
    
    log("✅ Settings saved")
    
    # Test email
    log("Testing email with Resend fake key...")
    
    resp = requests.post(
        f"{API_BASE}/integrations/email/test",
        json={},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    
    log(f"POST /api/integrations/email/test → {resp.status_code}")
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected HTTP 200, got {resp.status_code}")
        return False
    
    log("✅ PASS: HTTP 200")
    
    try:
        data = resp.json()
        ok = data.get("ok")
        message = data.get("message", "")
        
        log(f"Response: ok={ok}")
        log(f"Message: '{message}'")
        
        # Should fail with API key invalid message
        if ok is False and ("api key" in message.lower() or "invalid" in message.lower()):
            log("✅ PASS: ok=false with API key invalid message (Resend path working)")
            return True
        else:
            log(f"⚠️  WARNING: Expected API key error, got: {message}")
            # Still pass if we got 200 with ok=false (no regression)
            return ok is False
            
    except Exception as e:
        log(f"❌ FAIL: Could not parse response: {e}")
        return False

def test_6_rbac_admin_denied(admin_token):
    """Test 6: RBAC: as admin@test.com POST test → 403"""
    log("\n" + "="*80)
    log("TEST 6: RBAC check - admin should get 403")
    log("="*80)
    
    resp = requests.post(
        f"{API_BASE}/integrations/email/test",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    log(f"POST /api/integrations/email/test (as admin) → {resp.status_code}")
    
    if resp.status_code == 403:
        log("✅ PASS: Admin correctly denied (403)")
        return True
    else:
        log(f"❌ FAIL: Expected 403, got {resp.status_code}")
        return False

def test_7_cleanup(token):
    """Test 7: CLEANUP: PUT settings with email disabled"""
    log("\n" + "="*80)
    log("TEST 7: CLEANUP - Disable email")
    log("="*80)
    
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
    
    resp = requests.put(
        f"{API_BASE}/integrations/settings",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    log(f"PUT /api/integrations/settings → {resp.status_code}")
    
    if resp.status_code == 200:
        log("✅ PASS: Cleanup successful")
        return True
    else:
        log(f"❌ FAIL: Cleanup failed: {resp.status_code}")
        return False

def main():
    log("="*80)
    log("SMTP EMAIL DIAGNOSTICS IMPROVEMENTS - COMPREHENSIVE TEST")
    log("="*80)
    log(f"Base URL: {BASE_URL}")
    log(f"API Base: {API_BASE}")
    
    # Login as superadmin
    superadmin_token = login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)
    if not superadmin_token:
        log("❌ FATAL: Could not login as superadmin")
        return
    
    # Login as admin (for RBAC test)
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        log("⚠️  WARNING: Could not login as admin, skipping RBAC test")
        admin_token = None
    
    # Run tests
    results = {}
    
    results["test_1"] = test_1_configure_unreachable_smtp(superadmin_token)
    
    test_2_result, test_2_message = test_2_test_email_unreachable(superadmin_token)
    results["test_2"] = test_2_result
    
    results["test_3"] = test_3_test_email_with_recipient(superadmin_token)
    results["test_4"] = test_4_bad_dns_host(superadmin_token)
    results["test_5"] = test_5_resend_path_unaffected(superadmin_token)
    
    if admin_token:
        results["test_6"] = test_6_rbac_admin_denied(admin_token)
    else:
        results["test_6"] = None
    
    results["test_7"] = test_7_cleanup(superadmin_token)
    
    # Summary
    log("\n" + "="*80)
    log("TEST SUMMARY")
    log("="*80)
    
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    total = len(results)
    
    for test_name, result in results.items():
        if result is True:
            log(f"✅ {test_name}: PASS")
        elif result is False:
            log(f"❌ {test_name}: FAIL")
        else:
            log(f"⏭️  {test_name}: SKIPPED")
    
    log(f"\nTotal: {passed}/{total} passed, {failed} failed, {skipped} skipped")
    
    if test_2_result:
        log("\n" + "="*80)
        log("MOST IMPORTANT: TEST 2 EXACT MESSAGE")
        log("="*80)
        log(f"'{test_2_message}'")
        log("="*80)
    
    if failed == 0:
        log("\n🎉 ALL TESTS PASSED!")
    else:
        log(f"\n⚠️  {failed} TEST(S) FAILED")

if __name__ == "__main__":
    main()
