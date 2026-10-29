#!/usr/bin/env python3
"""
HubSpot Proposal Integration Test Suite
Tests the NEW HubSpot proposal integration for DD Planner.

Review Request: Verify HubSpot proposal integration (deal -> proposal, engagement write-back).
Base URL: REACT_APP_BACKEND_URL from frontend/.env, /api prefix.
Login: OAuth2 FORM. Accounts: superadmin@test.com/Super@2026 (super_admin), admin@test.com/admin123 (admin).

TESTS:
1. HUBSPOT DISABLED: as superadmin ensure disabled, as admin GET /api/proposals/hubspot/deals → 200 with ok:false
2. FROM-DEAL WHILE DISABLED: as admin POST /api/proposals/from-deal → 400
3. ENABLE WITH FAKE TOKEN: as superadmin enable with fake token, as admin GET deals → 200 with ok:false + readable error
4. FROM-DEAL WITH FAKE TOKEN: as admin POST /api/proposals/from-deal → 400 with readable error
5. RBAC: admin allowed, qa_resource@test.com gets 403
6. WRITE-BACK IS BEST-EFFORT: proposal send returns 200 even with HubSpot unreachable
7. CLEANUP: disable HubSpot

CRITICAL: every HubSpot call returns 200-with-message (list) or 400-with-detail (from-deal) — NEVER 500/hang.
RBAC 403 for non-admin. Proposal send still 200 with HubSpot enabled+unreachable (write-back best-effort).
"""
import requests
import json
import sys
from datetime import datetime

# Read backend URL from frontend/.env
BACKEND_URL = "https://proposal-approve.preview.emergentagent.com"

# Test credentials
SUPERADMIN_EMAIL = "superadmin@test.com"
SUPERADMIN_PASSWORD = "Super@2026"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"
QA_EMAIL = "qa_resource@test.com"
QA_PASSWORD = "Test@2026"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def login(email, password):
    """Login and return access token"""
    log(f"Logging in as {email}...")
    r = requests.post(
        f"{BACKEND_URL}/api/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if r.status_code != 200:
        log(f"❌ Login failed: {r.status_code} {r.text[:200]}")
        return None
    token = r.json().get("access_token")
    log(f"✅ Login successful, token: {token[:20]}...")
    return token

def test_1_hubspot_disabled(superadmin_token, admin_token):
    """TEST 1: HUBSPOT DISABLED - ensure disabled, GET deals returns 200 with ok:false"""
    log("\n=== TEST 1: HUBSPOT DISABLED ===")
    
    # Step 1a: Disable HubSpot as superadmin
    log("Step 1a: Disabling HubSpot as superadmin...")
    r = requests.put(
        f"{BACKEND_URL}/api/integrations/settings",
        json={
            "hubspot": {
                "enabled": False,
                "private_app_token": "",
                "portal_id": "",
                "trigger_stage": "closedwon",
                "sync_status_updates": True,
                "default_project_status": "Pipeline"
            }
        },
        headers={"Authorization": f"Bearer {superadmin_token}"}
    )
    if r.status_code != 200:
        log(f"❌ Failed to disable HubSpot: {r.status_code} {r.text[:200]}")
        return False
    log("✅ HubSpot disabled successfully")
    
    # Step 1b: As admin, GET /api/proposals/hubspot/deals
    log("Step 1b: As admin, GET /api/proposals/hubspot/deals...")
    r = requests.get(
        f"{BACKEND_URL}/api/proposals/hubspot/deals",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    # CRITICAL: Must return 200 (NOT 500)
    if r.status_code != 200:
        log(f"❌ CRITICAL FAILURE: Expected 200, got {r.status_code}")
        log(f"Response: {r.text[:500]}")
        return False
    
    data = r.json()
    log(f"Response: {json.dumps(data, indent=2)}")
    
    # Check response structure
    if not isinstance(data, dict):
        log(f"❌ Response is not a dict: {type(data)}")
        return False
    
    if data.get("ok") is not False:
        log(f"❌ Expected ok:false, got ok:{data.get('ok')}")
        return False
    
    if not data.get("message"):
        log(f"❌ Expected message field, got: {data}")
        return False
    
    if not isinstance(data.get("deals"), list):
        log(f"❌ Expected deals array, got: {type(data.get('deals'))}")
        return False
    
    if len(data.get("deals", [])) != 0:
        log(f"❌ Expected empty deals array, got {len(data.get('deals', []))} deals")
        return False
    
    message = data.get("message", "")
    log(f"✅ TEST 1 PASSED: Returns 200 with ok:false, deals:[], message: '{message}'")
    
    # Verify message mentions HubSpot not configured/enabled
    if "hubspot" not in message.lower() or ("not configured" not in message.lower() and "not enabled" not in message.lower()):
        log(f"⚠️  Message doesn't clearly mention HubSpot not configured/enabled: '{message}'")
    
    return True

def test_2_from_deal_while_disabled(admin_token):
    """TEST 2: FROM-DEAL WHILE DISABLED - POST /api/proposals/from-deal returns 400"""
    log("\n=== TEST 2: FROM-DEAL WHILE DISABLED ===")
    
    log("POST /api/proposals/from-deal with HubSpot disabled...")
    r = requests.post(
        f"{BACKEND_URL}/api/proposals/from-deal",
        json={"deal_id": "12345", "use_ai": False},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    # CRITICAL: Must return 400 (NOT 500)
    if r.status_code != 400:
        log(f"❌ CRITICAL FAILURE: Expected 400, got {r.status_code}")
        log(f"Response: {r.text[:500]}")
        return False
    
    data = r.json()
    log(f"Response: {json.dumps(data, indent=2)}")
    
    detail = data.get("detail", "")
    if not detail:
        log(f"❌ Expected detail field in error response")
        return False
    
    # Verify detail mentions HubSpot not configured
    if "hubspot" not in detail.lower() or "not configured" not in detail.lower():
        log(f"⚠️  Detail doesn't clearly mention HubSpot not configured: '{detail}'")
    
    log(f"✅ TEST 2 PASSED: Returns 400 with detail: '{detail}'")
    return True

def test_3_enable_with_fake_token(superadmin_token, admin_token):
    """TEST 3: ENABLE WITH FAKE TOKEN - GET deals returns 200 with ok:false + readable error"""
    log("\n=== TEST 3: ENABLE WITH FAKE TOKEN ===")
    
    # Step 3a: Enable HubSpot with fake token as superadmin
    log("Step 3a: Enabling HubSpot with fake token as superadmin...")
    r = requests.put(
        f"{BACKEND_URL}/api/integrations/settings",
        json={
            "hubspot": {
                "enabled": True,
                "private_app_token": "pat-na1-fake-token-xyz",
                "portal_id": "123",
                "trigger_stage": "closedwon",
                "sync_status_updates": True,
                "default_project_status": "Pipeline"
            }
        },
        headers={"Authorization": f"Bearer {superadmin_token}"}
    )
    if r.status_code != 200:
        log(f"❌ Failed to enable HubSpot: {r.status_code} {r.text[:200]}")
        return False
    log("✅ HubSpot enabled with fake token")
    
    # Step 3b: As admin, GET /api/proposals/hubspot/deals
    log("Step 3b: As admin, GET /api/proposals/hubspot/deals (allow ~20s for timeout)...")
    try:
        r = requests.get(
            f"{BACKEND_URL}/api/proposals/hubspot/deals",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=25  # Allow up to 25s (review request says ~20s)
        )
    except requests.exceptions.Timeout:
        log(f"❌ CRITICAL FAILURE: Request timed out (>25s) - should return within ~20s")
        return False
    
    # CRITICAL: Must return 200 (NOT 500/hang)
    if r.status_code != 200:
        log(f"❌ CRITICAL FAILURE: Expected 200, got {r.status_code}")
        log(f"Response: {r.text[:500]}")
        return False
    
    data = r.json()
    log(f"Response: {json.dumps(data, indent=2)}")
    
    # Check response structure
    if data.get("ok") is not False:
        log(f"❌ Expected ok:false, got ok:{data.get('ok')}")
        return False
    
    if not isinstance(data.get("deals"), list):
        log(f"❌ Expected deals array, got: {type(data.get('deals'))}")
        return False
    
    if len(data.get("deals", [])) != 0:
        log(f"❌ Expected empty deals array, got {len(data.get('deals', []))} deals")
        return False
    
    message = data.get("message", "")
    if not message:
        log(f"❌ Expected message field with readable error")
        return False
    
    log(f"✅ TEST 3 PASSED: Returns 200 with ok:false, deals:[], message: '{message}'")
    
    # Verify message contains readable HubSpot auth/API error (401/invalid token)
    if "401" in message or "invalid" in message.lower() or "unauthorized" in message.lower() or "auth" in message.lower():
        log(f"✅ Message contains readable HubSpot auth/API error")
    else:
        log(f"⚠️  Message doesn't clearly indicate auth error: '{message}'")
    
    return True

def test_4_from_deal_with_fake_token(admin_token):
    """TEST 4: FROM-DEAL WITH FAKE TOKEN - POST /api/proposals/from-deal returns 400 with readable error"""
    log("\n=== TEST 4: FROM-DEAL WITH FAKE TOKEN ===")
    
    log("POST /api/proposals/from-deal with fake HubSpot token...")
    try:
        r = requests.post(
            f"{BACKEND_URL}/api/proposals/from-deal",
            json={"deal_id": "12345", "use_ai": False},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=25
        )
    except requests.exceptions.Timeout:
        log(f"❌ CRITICAL FAILURE: Request timed out (>25s)")
        return False
    
    # CRITICAL: Must return 400 (NOT 500)
    if r.status_code != 400:
        log(f"❌ CRITICAL FAILURE: Expected 400, got {r.status_code}")
        log(f"Response: {r.text[:500]}")
        return False
    
    data = r.json()
    log(f"Response: {json.dumps(data, indent=2)}")
    
    detail = data.get("detail", "")
    if not detail:
        log(f"❌ Expected detail field in error response")
        return False
    
    log(f"✅ TEST 4 PASSED: Returns 400 with detail: '{detail}'")
    
    # Verify detail contains readable error (couldn't read the HubSpot deal / 401)
    if "401" in detail or "couldn't read" in detail.lower() or "hubspot" in detail.lower():
        log(f"✅ Detail contains readable HubSpot error")
    else:
        log(f"⚠️  Detail doesn't clearly indicate HubSpot error: '{detail}'")
    
    return True

def test_5_rbac(admin_token, qa_token):
    """TEST 5: RBAC - admin allowed, qa_resource gets 403"""
    log("\n=== TEST 5: RBAC ===")
    
    # Step 5a: Admin can access GET deals
    log("Step 5a: Admin GET /api/proposals/hubspot/deals...")
    r = requests.get(
        f"{BACKEND_URL}/api/proposals/hubspot/deals",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    if r.status_code != 200:
        log(f"❌ Admin should get 200, got {r.status_code}")
        return False
    log(f"✅ Admin allowed (200)")
    
    # Step 5b: Admin can access POST from-deal
    log("Step 5b: Admin POST /api/proposals/from-deal...")
    r = requests.post(
        f"{BACKEND_URL}/api/proposals/from-deal",
        json={"deal_id": "12345", "use_ai": False},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    if r.status_code not in [400, 200]:  # 400 is expected (fake token), 200 would be success
        log(f"❌ Admin should get 200 or 400, got {r.status_code}")
        return False
    log(f"✅ Admin allowed ({r.status_code})")
    
    # Step 5c: QA resource (non-admin) gets 403 on GET deals
    log("Step 5c: QA resource GET /api/proposals/hubspot/deals...")
    r = requests.get(
        f"{BACKEND_URL}/api/proposals/hubspot/deals",
        headers={"Authorization": f"Bearer {qa_token}"}
    )
    if r.status_code != 403:
        log(f"❌ CRITICAL FAILURE: QA resource should get 403, got {r.status_code}")
        log(f"Response: {r.text[:200]}")
        return False
    log(f"✅ QA resource denied (403)")
    
    # Step 5d: QA resource gets 403 on POST from-deal
    log("Step 5d: QA resource POST /api/proposals/from-deal...")
    r = requests.post(
        f"{BACKEND_URL}/api/proposals/from-deal",
        json={"deal_id": "12345", "use_ai": False},
        headers={"Authorization": f"Bearer {qa_token}"}
    )
    if r.status_code != 403:
        log(f"❌ CRITICAL FAILURE: QA resource should get 403, got {r.status_code}")
        log(f"Response: {r.text[:200]}")
        return False
    log(f"✅ QA resource denied (403)")
    
    log(f"✅ TEST 5 PASSED: RBAC working correctly (admin allowed, non-admin 403)")
    return True

def test_6_write_back_best_effort(admin_token):
    """TEST 6: WRITE-BACK IS BEST-EFFORT - proposal send returns 200 even with HubSpot unreachable"""
    log("\n=== TEST 6: WRITE-BACK IS BEST-EFFORT ===")
    
    # Step 6a: Create a proposal
    log("Step 6a: Creating proposal as admin...")
    r = requests.post(
        f"{BACKEND_URL}/api/proposals",
        json={"client_name": "HubSpot WB Co", "proposal_title": "WB Test"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    if r.status_code != 200:
        log(f"❌ Failed to create proposal: {r.status_code} {r.text[:200]}")
        return False
    
    proposal = r.json()
    proposal_id = proposal.get("id")
    log(f"✅ Proposal created: {proposal_id}")
    
    # Step 6b: Set contact_email on the proposal
    log("Step 6b: Setting contact_email on proposal...")
    r = requests.get(
        f"{BACKEND_URL}/api/proposals/{proposal_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    if r.status_code != 200:
        log(f"❌ Failed to get proposal: {r.status_code}")
        return False
    
    proposal_data = r.json()
    data = proposal_data.get("data", {})
    data["contact_email"] = "c@example.com"
    
    r = requests.put(
        f"{BACKEND_URL}/api/proposals/{proposal_id}",
        json={"data": data},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    if r.status_code != 200:
        log(f"❌ Failed to update proposal: {r.status_code} {r.text[:200]}")
        return False
    log(f"✅ Contact email set")
    
    # Step 6c: Send the proposal (HubSpot write-back will be attempted but should not block)
    log("Step 6c: Sending proposal (HubSpot enabled+unreachable, write-back best-effort)...")
    r = requests.post(
        f"{BACKEND_URL}/api/proposals/{proposal_id}/send",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    # CRITICAL: Must return 200 (write-back failure must not block)
    if r.status_code != 200:
        log(f"❌ CRITICAL FAILURE: Expected 200, got {r.status_code}")
        log(f"Response: {r.text[:500]}")
        return False
    
    send_result = r.json()
    log(f"Response: {json.dumps(send_result, indent=2)}")
    
    # Check proposal_link is present
    proposal_link = send_result.get("proposal_link")
    if not proposal_link:
        log(f"❌ Expected proposal_link in response")
        return False
    
    if "/proposal/" not in proposal_link:
        log(f"❌ proposal_link doesn't contain /proposal/: {proposal_link}")
        return False
    
    log(f"✅ TEST 6 PASSED: Proposal send returns 200 with proposal_link (write-back best-effort)")
    log(f"   Proposal link: {proposal_link}")
    
    # Store proposal_id for cleanup
    return proposal_id

def test_7_cleanup(superadmin_token, proposal_id):
    """TEST 7: CLEANUP - disable HubSpot, delete test proposal"""
    log("\n=== TEST 7: CLEANUP ===")
    
    # Step 7a: Disable HubSpot
    log("Step 7a: Disabling HubSpot as superadmin...")
    r = requests.put(
        f"{BACKEND_URL}/api/integrations/settings",
        json={
            "hubspot": {
                "enabled": False,
                "private_app_token": "",
                "portal_id": "",
                "trigger_stage": "closedwon",
                "sync_status_updates": True,
                "default_project_status": "Pipeline"
            }
        },
        headers={"Authorization": f"Bearer {superadmin_token}"}
    )
    if r.status_code != 200:
        log(f"❌ Failed to disable HubSpot: {r.status_code} {r.text[:200]}")
        return False
    log("✅ HubSpot disabled")
    
    # Step 7b: Try to delete test proposal (it's Sent now, so will fail with 400 - that's expected)
    if proposal_id:
        log(f"Step 7b: Attempting to delete test proposal {proposal_id}...")
        r = requests.delete(
            f"{BACKEND_URL}/api/proposals/{proposal_id}",
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        if r.status_code == 200:
            log(f"✅ Test proposal deleted")
        elif r.status_code == 400:
            log(f"✅ Test proposal is Sent (cannot delete) - expected")
        else:
            log(f"⚠️  Unexpected status deleting proposal: {r.status_code}")
    
    log(f"✅ TEST 7 PASSED: Cleanup complete")
    return True

def main():
    log("=" * 80)
    log("HubSpot Proposal Integration Test Suite")
    log("=" * 80)
    log(f"Backend URL: {BACKEND_URL}")
    
    # Login
    superadmin_token = login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)
    if not superadmin_token:
        log("❌ Failed to login as superadmin")
        sys.exit(1)
    
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        log("❌ Failed to login as admin")
        sys.exit(1)
    
    qa_token = login(QA_EMAIL, QA_PASSWORD)
    if not qa_token:
        log("❌ Failed to login as qa_resource")
        sys.exit(1)
    
    # Run tests
    results = []
    proposal_id = None
    
    # TEST 1: HubSpot disabled
    results.append(("TEST 1: HubSpot disabled", test_1_hubspot_disabled(superadmin_token, admin_token)))
    
    # TEST 2: FROM-DEAL while disabled
    results.append(("TEST 2: FROM-DEAL while disabled", test_2_from_deal_while_disabled(admin_token)))
    
    # TEST 3: Enable with fake token
    results.append(("TEST 3: Enable with fake token", test_3_enable_with_fake_token(superadmin_token, admin_token)))
    
    # TEST 4: FROM-DEAL with fake token
    results.append(("TEST 4: FROM-DEAL with fake token", test_4_from_deal_with_fake_token(admin_token)))
    
    # TEST 5: RBAC
    results.append(("TEST 5: RBAC", test_5_rbac(admin_token, qa_token)))
    
    # TEST 6: Write-back best-effort
    result = test_6_write_back_best_effort(admin_token)
    if isinstance(result, str):
        # Returned proposal_id
        proposal_id = result
        results.append(("TEST 6: Write-back best-effort", True))
    else:
        results.append(("TEST 6: Write-back best-effort", result))
    
    # TEST 7: Cleanup
    results.append(("TEST 7: Cleanup", test_7_cleanup(superadmin_token, proposal_id)))
    
    # Summary
    log("\n" + "=" * 80)
    log("TEST SUMMARY")
    log("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        log(f"{status}: {test_name}")
    
    log("=" * 80)
    log(f"TOTAL: {passed}/{total} tests passed ({passed*100//total}% success rate)")
    log("=" * 80)
    
    if passed == total:
        log("✅✅✅ ALL TESTS PASSED ✅✅✅")
        sys.exit(0)
    else:
        log(f"❌ {total - passed} test(s) failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
