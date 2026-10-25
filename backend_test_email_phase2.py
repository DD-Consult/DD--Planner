#!/usr/bin/env python3
"""
Backend Test: Email Phase 2 — Editable Templates + Branding
DD Planner - Verify email settings with editable templates and branding configuration.

Review Request:
Verify Email Phase 2 — editable templates + branding — for DD Planner. 
Base URL = REACT_APP_BACKEND_URL, /api prefix. Login OAuth2 FORM. 
Accounts: superadmin@test.com/Super@2026 (super_admin), admin@test.com/admin123 (admin).

The email settings block now supports `templates` (keys: proposal_link, report_link, 
report_code, each {subject, body}) and `branding` {logo_url, accent_color, company_name}. 
Backend stores only overrides that differ from defaults; empty subject/body resets to default. 
Emails render with {merge_field} substitution wrapped in a branded shell.

TESTS (as superadmin unless noted):
1. GET /api/integrations/settings → 200. Confirm settings.email includes: `templates` 
   (all 3 keys each with label, subject, body, is_custom), `branding` {logo_url, 
   accent_color, company_name}, and `default_templates` (all 3 keys with subject/body). 
   Confirm is_custom is false initially for all.
2. SAVE CUSTOM TEMPLATE + BRANDING: PUT /api/integrations/settings with custom template 
   and branding → 200.
3. GET again → assert: branding persisted, custom template persisted with is_custom==true, 
   other templates remain is_custom==false.
4. RESET A TEMPLATE: PUT with templates.proposal_link.subject="" and body="" → 200. 
   GET → is_custom==false and values equal defaults.
5. RENDER CHECK (indirect via proposal send): Re-apply custom template, create proposal, 
   send (email will fail with fake key but send path should return 200).
6. RBAC: as admin@test.com GET /api/integrations/settings → 403.
7. CLEANUP: PUT with defaults to reset.
"""

import requests
import sys
from datetime import datetime

# Backend URL from environment
BASE_URL = "https://proposal-approve.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"

# Test credentials
SUPERADMIN_EMAIL = "superadmin@test.com"
SUPERADMIN_PASSWORD = "Super@2026"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

# Test state
superadmin_token = None
admin_token = None
test_proposal_id = None

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def login(email, password):
    """Login and return JWT token."""
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

def test_1_get_settings_initial():
    """TEST 1: GET /api/integrations/settings → 200. Verify structure."""
    log("\n=== TEST 1: GET /api/integrations/settings (initial state) ===")
    
    headers = {"Authorization": f"Bearer {superadmin_token}"}
    resp = requests.get(f"{API_BASE}/integrations/settings", headers=headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        log(f"Response: {resp.text}")
        return False
    
    data = resp.json()
    log(f"✅ GET /api/integrations/settings returned 200")
    
    # Check email block exists
    if "email" not in data:
        log(f"❌ FAIL: 'email' key not found in response")
        return False
    
    email = data["email"]
    
    # Check templates exist
    if "templates" not in email:
        log(f"❌ FAIL: 'templates' key not found in email block")
        return False
    
    templates = email["templates"]
    required_keys = ["proposal_link", "report_link", "report_code"]
    
    for key in required_keys:
        if key not in templates:
            log(f"❌ FAIL: Template key '{key}' not found")
            return False
        
        tmpl = templates[key]
        # Check each template has required fields
        for field in ["label", "subject", "body", "is_custom"]:
            if field not in tmpl:
                log(f"❌ FAIL: Template '{key}' missing field '{field}'")
                return False
        
        # Initially, is_custom should be false
        if tmpl["is_custom"] != False:
            log(f"❌ FAIL: Template '{key}' has is_custom={tmpl['is_custom']}, expected False initially")
            return False
        
        log(f"✅ Template '{key}': label='{tmpl['label']}', is_custom={tmpl['is_custom']}")
    
    # Check branding exists
    if "branding" not in email:
        log(f"❌ FAIL: 'branding' key not found in email block")
        return False
    
    branding = email["branding"]
    required_branding = ["logo_url", "accent_color", "company_name"]
    
    for field in required_branding:
        if field not in branding:
            log(f"❌ FAIL: Branding field '{field}' not found")
            return False
    
    log(f"✅ Branding: company_name='{branding['company_name']}', accent_color='{branding['accent_color']}', logo_url='{branding['logo_url']}'")
    
    # Check default_templates exists
    if "default_templates" not in email:
        log(f"❌ FAIL: 'default_templates' key not found in email block")
        return False
    
    default_templates = email["default_templates"]
    
    for key in required_keys:
        if key not in default_templates:
            log(f"❌ FAIL: Default template key '{key}' not found")
            return False
        
        dflt = default_templates[key]
        if "subject" not in dflt or "body" not in dflt:
            log(f"❌ FAIL: Default template '{key}' missing subject or body")
            return False
        
        log(f"✅ Default template '{key}': subject='{dflt['subject'][:50]}...'")
    
    log("✅ TEST 1 PASSED: All required fields present, is_custom=false for all templates")
    return True

def test_2_save_custom_template_and_branding():
    """TEST 2: SAVE CUSTOM TEMPLATE + BRANDING."""
    log("\n=== TEST 2: SAVE CUSTOM TEMPLATE + BRANDING ===")
    
    headers = {"Authorization": f"Bearer {superadmin_token}"}
    
    payload = {
        "email": {
            "enabled": True,
            "method": "resend",
            "resend": {
                "api_key": "re_test_123",
                "from_email": "proposals@example.com"
            },
            "branding": {
                "company_name": "Acme Advisory",
                "accent_color": "#FF5722",
                "logo_url": "https://example.com/logo.png"
            },
            "templates": {
                "proposal_link": {
                    "subject": "Your Acme proposal: {proposal_title}",
                    "body": "<p>Hello {client_name}, view it here: {link}</p>"
                }
            }
        }
    }
    
    resp = requests.put(f"{API_BASE}/integrations/settings", json=payload, headers=headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        log(f"Response: {resp.text}")
        return False
    
    log(f"✅ PUT /api/integrations/settings returned 200")
    log("✅ TEST 2 PASSED: Custom template and branding saved")
    return True

def test_3_verify_custom_template_persisted():
    """TEST 3: GET again → verify custom template and branding persisted."""
    log("\n=== TEST 3: VERIFY CUSTOM TEMPLATE PERSISTED ===")
    
    headers = {"Authorization": f"Bearer {superadmin_token}"}
    resp = requests.get(f"{API_BASE}/integrations/settings", headers=headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    data = resp.json()
    email = data["email"]
    
    # Check branding persisted
    branding = email["branding"]
    
    if branding["company_name"] != "Acme Advisory":
        log(f"❌ FAIL: company_name={branding['company_name']}, expected 'Acme Advisory'")
        return False
    
    if branding["accent_color"] != "#FF5722":
        log(f"❌ FAIL: accent_color={branding['accent_color']}, expected '#FF5722'")
        return False
    
    if branding["logo_url"] != "https://example.com/logo.png":
        log(f"❌ FAIL: logo_url={branding['logo_url']}, expected 'https://example.com/logo.png'")
        return False
    
    log(f"✅ Branding persisted: company_name='Acme Advisory', accent_color='#FF5722', logo_url='https://example.com/logo.png'")
    
    # Check custom template persisted
    templates = email["templates"]
    proposal_link = templates["proposal_link"]
    
    if proposal_link["subject"] != "Your Acme proposal: {proposal_title}":
        log(f"❌ FAIL: proposal_link.subject={proposal_link['subject']}, expected 'Your Acme proposal: {{proposal_title}}'")
        return False
    
    if "{client_name}" not in proposal_link["body"]:
        log(f"❌ FAIL: proposal_link.body does not contain '{{client_name}}'")
        return False
    
    if proposal_link["is_custom"] != True:
        log(f"❌ FAIL: proposal_link.is_custom={proposal_link['is_custom']}, expected True")
        return False
    
    log(f"✅ Custom template persisted: subject='Your Acme proposal: {{proposal_title}}', is_custom=True")
    
    # Check other templates remain is_custom=false
    for key in ["report_link", "report_code"]:
        if templates[key]["is_custom"] != False:
            log(f"❌ FAIL: Template '{key}' has is_custom={templates[key]['is_custom']}, expected False")
            return False
        log(f"✅ Template '{key}' remains is_custom=False (default)")
    
    log("✅ TEST 3 PASSED: Custom template and branding persisted correctly")
    return True

def test_4_reset_template():
    """TEST 4: RESET A TEMPLATE (empty subject/body)."""
    log("\n=== TEST 4: RESET A TEMPLATE ===")
    
    headers = {"Authorization": f"Bearer {superadmin_token}"}
    
    # Send empty subject and body to reset
    payload = {
        "email": {
            "templates": {
                "proposal_link": {
                    "subject": "",
                    "body": ""
                }
            }
        }
    }
    
    resp = requests.put(f"{API_BASE}/integrations/settings", json=payload, headers=headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        log(f"Response: {resp.text}")
        return False
    
    log(f"✅ PUT with empty subject/body returned 200")
    
    # GET and verify reset
    resp = requests.get(f"{API_BASE}/integrations/settings", headers=headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    data = resp.json()
    email = data["email"]
    templates = email["templates"]
    default_templates = email["default_templates"]
    
    proposal_link = templates["proposal_link"]
    default_proposal = default_templates["proposal_link"]
    
    # Check is_custom is now false
    if proposal_link["is_custom"] != False:
        log(f"❌ FAIL: proposal_link.is_custom={proposal_link['is_custom']}, expected False after reset")
        return False
    
    # Check subject and body match defaults
    if proposal_link["subject"] != default_proposal["subject"]:
        log(f"❌ FAIL: proposal_link.subject does not match default after reset")
        log(f"  Got: {proposal_link['subject']}")
        log(f"  Expected: {default_proposal['subject']}")
        return False
    
    if proposal_link["body"] != default_proposal["body"]:
        log(f"❌ FAIL: proposal_link.body does not match default after reset")
        return False
    
    log(f"✅ Template reset: is_custom=False, subject and body match defaults")
    log("✅ TEST 4 PASSED: Template reset to defaults successfully")
    return True

def test_5_render_check_via_proposal_send():
    """TEST 5: RENDER CHECK (indirect via proposal send)."""
    log("\n=== TEST 5: RENDER CHECK VIA PROPOSAL SEND ===")
    
    global test_proposal_id
    
    headers = {"Authorization": f"Bearer {superadmin_token}"}
    
    # Re-apply custom template
    log("Re-applying custom template...")
    payload = {
        "email": {
            "enabled": True,
            "method": "resend",
            "resend": {
                "api_key": "re_test_fake_key",
                "from_email": "proposals@example.com"
            },
            "templates": {
                "proposal_link": {
                    "subject": "Your Acme proposal: {proposal_title}",
                    "body": "<p>Hello {client_name}, view it here: {link}</p>"
                }
            }
        }
    }
    
    resp = requests.put(f"{API_BASE}/integrations/settings", json=payload, headers=headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Could not re-apply custom template: {resp.status_code}")
        return False
    
    log("✅ Custom template re-applied")
    
    # Login as admin to create proposal
    log("Logging in as admin to create proposal...")
    admin_token_local = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token_local:
        log("❌ FAIL: Could not login as admin")
        return False
    
    admin_headers = {"Authorization": f"Bearer {admin_token_local}"}
    
    # Create a proposal
    log("Creating test proposal...")
    proposal_payload = {
        "client_name": "Globex",
        "proposal_title": "Transformation 2026"
    }
    
    resp = requests.post(f"{API_BASE}/proposals", json=proposal_payload, headers=admin_headers)
    
    if resp.status_code not in [200, 201]:
        log(f"❌ FAIL: Could not create proposal: {resp.status_code} {resp.text}")
        return False
    
    proposal = resp.json()
    test_proposal_id = proposal.get("id")
    log(f"✅ Proposal created: id={test_proposal_id}")
    
    # Get proposal and set contact_email
    resp = requests.get(f"{API_BASE}/proposals/{test_proposal_id}", headers=admin_headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Could not get proposal: {resp.status_code}")
        return False
    
    proposal_data = resp.json()
    proposal_data["data"]["contact_email"] = "client@example.com"
    
    # Update proposal
    resp = requests.put(f"{API_BASE}/proposals/{test_proposal_id}", json=proposal_data, headers=admin_headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Could not update proposal: {resp.status_code}")
        return False
    
    log("✅ Proposal updated with contact_email")
    
    # Send proposal (email will fail with fake key, but send path should return 200)
    log("Sending proposal (email will fail gracefully with fake key)...")
    resp = requests.post(f"{API_BASE}/proposals/{test_proposal_id}/send", headers=admin_headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Send endpoint returned {resp.status_code}, expected 200")
        log(f"Response: {resp.text}")
        return False
    
    send_result = resp.json()
    
    # Check response has expected fields
    if "proposal_link" not in send_result:
        log(f"❌ FAIL: 'proposal_link' not in send response")
        return False
    
    if "email_sent" not in send_result:
        log(f"❌ FAIL: 'email_sent' not in send response")
        return False
    
    if "email_message" not in send_result:
        log(f"❌ FAIL: 'email_message' not in send response")
        return False
    
    log(f"✅ Send returned 200 with proposal_link: {send_result['proposal_link'][:50]}...")
    log(f"   email_sent={send_result['email_sent']}, email_message='{send_result['email_message'][:80]}...'")
    
    log("✅ TEST 5 PASSED: Send path works with custom template (200 response)")
    return True

def test_6_rbac_admin_403():
    """TEST 6: RBAC - admin should get 403."""
    log("\n=== TEST 6: RBAC - ADMIN GET 403 ===")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = requests.get(f"{API_BASE}/integrations/settings", headers=headers)
    
    if resp.status_code != 403:
        log(f"❌ FAIL: Expected 403, got {resp.status_code}")
        log(f"Response: {resp.text}")
        return False
    
    log(f"✅ Admin correctly received 403 Forbidden")
    log("✅ TEST 6 PASSED: RBAC working correctly")
    return True

def test_7_cleanup():
    """TEST 7: CLEANUP - reset to defaults."""
    log("\n=== TEST 7: CLEANUP ===")
    
    headers = {"Authorization": f"Bearer {superadmin_token}"}
    
    # Reset email settings to defaults
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
            },
            "templates": {
                "proposal_link": {"subject": "", "body": ""},
                "report_link": {"subject": "", "body": ""},
                "report_code": {"subject": "", "body": ""}
            },
            "branding": {
                "company_name": "DD Consulting",
                "accent_color": "#1570EF",
                "logo_url": ""
            }
        }
    }
    
    resp = requests.put(f"{API_BASE}/integrations/settings", json=payload, headers=headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Cleanup PUT returned {resp.status_code}")
        log(f"Response: {resp.text}")
        return False
    
    log("✅ Email settings reset to defaults")
    
    # Delete test proposal if it exists and is Draft
    if test_proposal_id:
        log(f"Attempting to delete test proposal {test_proposal_id}...")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        resp = requests.delete(f"{API_BASE}/proposals/{test_proposal_id}", headers=admin_headers)
        
        if resp.status_code == 200:
            log(f"✅ Test proposal deleted")
        elif resp.status_code == 400:
            log(f"⚠️  Proposal is Sent, cannot delete (expected)")
        else:
            log(f"⚠️  Delete returned {resp.status_code} (non-critical)")
    
    log("✅ TEST 7 PASSED: Cleanup completed")
    return True

def main():
    global superadmin_token, admin_token
    
    log("=" * 80)
    log("Backend Test: Email Phase 2 — Editable Templates + Branding")
    log("=" * 80)
    
    # Login
    superadmin_token = login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)
    if not superadmin_token:
        log("❌ CRITICAL: Could not login as superadmin")
        sys.exit(1)
    
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        log("❌ CRITICAL: Could not login as admin")
        sys.exit(1)
    
    # Run tests
    tests = [
        ("TEST 1: GET settings initial state", test_1_get_settings_initial),
        ("TEST 2: Save custom template + branding", test_2_save_custom_template_and_branding),
        ("TEST 3: Verify custom template persisted", test_3_verify_custom_template_persisted),
        ("TEST 4: Reset template to defaults", test_4_reset_template),
        ("TEST 5: Render check via proposal send", test_5_render_check_via_proposal_send),
        ("TEST 6: RBAC - admin gets 403", test_6_rbac_admin_403),
        ("TEST 7: Cleanup", test_7_cleanup),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            log(f"❌ EXCEPTION in {name}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    # Summary
    log("\n" + "=" * 80)
    log("TEST SUMMARY")
    log("=" * 80)
    log(f"Total tests: {passed + failed}")
    log(f"✅ Passed: {passed}")
    log(f"❌ Failed: {failed}")
    
    if failed == 0:
        log("\n🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        log(f"\n⚠️  {failed} TEST(S) FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()
