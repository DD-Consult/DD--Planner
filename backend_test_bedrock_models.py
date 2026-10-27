#!/usr/bin/env python3
"""
Comprehensive test for NEW Bedrock model-listing endpoint GET /api/settings/ai/bedrock-models
Review Request: Verify the NEW Bedrock model-listing endpoint for DD Planner.

Test Scenarios:
1. NO KEY (nothing saved, none passed): ensure no bedrock key saved, then GET → expect 200 with {ok:false, models:[], message}
2. FAKE KEY via query param: GET with fake key → MUST return 200 (NOT 500/hang), expect {ok:false, models:[], message}
3. FAKE KEY different region: GET with fake key + different region → 200, graceful {ok:false,...}
4. RBAC: as admin@test.com GET → expect 403 (super_admin only)
5. SAVED-KEY path: save fake key, then GET without api_key param → should use saved key, return 200 graceful {ok:false,...}
6. CLEANUP: DELETE /api/settings/ai

Base URL: https://proposal-approve.preview.emergentagent.com
Test credentials: superadmin@test.com/Super@2026 (super_admin), admin@test.com/admin123 (admin)
"""

import requests
import sys
import time

# Configuration
BASE_URL = "https://proposal-approve.preview.emergentagent.com"
SUPERADMIN_EMAIL = "superadmin@test.com"
SUPERADMIN_PASSWORD = "Super@2026"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

def login(email: str, password: str) -> str:
    """Login and return JWT token."""
    url = f"{BASE_URL}/api/auth/login"
    response = requests.post(
        url,
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if response.status_code != 200:
        print(f"❌ Login failed for {email}: {response.status_code} {response.text}")
        sys.exit(1)
    token = response.json().get("access_token")
    if not token:
        print(f"❌ No access_token in login response for {email}")
        sys.exit(1)
    print(f"✅ Login successful for {email}")
    return token

def test_step_1_no_key(superadmin_token: str):
    """TEST 1: NO KEY (nothing saved, none passed) → expect 200 with {ok:false, models:[], message}"""
    print("\n" + "="*80)
    print("TEST 1: NO KEY (nothing saved, none passed)")
    print("="*80)
    
    # First, ensure no bedrock key saved by deleting AI settings
    print("Step 1.1: DELETE /api/settings/ai to ensure no key saved")
    delete_url = f"{BASE_URL}/api/settings/ai"
    delete_resp = requests.delete(delete_url, headers={"Authorization": f"Bearer {superadmin_token}"})
    print(f"DELETE response: {delete_resp.status_code}")
    if delete_resp.status_code == 200:
        print(f"✅ AI settings deleted successfully")
    else:
        print(f"⚠️  DELETE returned {delete_resp.status_code} (may be already empty)")
    
    # Now GET bedrock-models without any key
    print("\nStep 1.2: GET /api/settings/ai/bedrock-models (no key saved, none passed)")
    url = f"{BASE_URL}/api/settings/ai/bedrock-models"
    response = requests.get(url, headers={"Authorization": f"Bearer {superadmin_token}"})
    
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.text}")
    
    # CRITICAL CHECKS
    assert response.status_code == 200, f"❌ Expected 200, got {response.status_code}"
    print("✅ PASS: Returns 200 (NOT 500)")
    
    data = response.json()
    assert data.get("ok") == False, f"❌ Expected ok=false, got {data.get('ok')}"
    print("✅ PASS: ok=false")
    
    assert data.get("models") == [], f"❌ Expected models=[], got {data.get('models')}"
    print("✅ PASS: models=[]")
    
    message = data.get("message", "")
    assert message, f"❌ Expected message, got empty"
    print(f"✅ PASS: message present: '{message}'")
    
    # Check message tells user to enter/save a key
    assert "key" in message.lower() or "enter" in message.lower() or "save" in message.lower(), \
        f"❌ Message should mention key/enter/save, got: '{message}'"
    print(f"✅ PASS: Message tells user to enter/save a key")
    
    print("\n✅✅✅ TEST 1 PASSED: NO KEY scenario returns 200 with {ok:false, models:[], message}")
    return message

def test_step_2_fake_key_us_east_1(superadmin_token: str):
    """TEST 2: FAKE KEY via query param (us-east-1) → MUST return 200 (NOT 500/hang), expect {ok:false, models:[], message}"""
    print("\n" + "="*80)
    print("TEST 2: FAKE KEY via query param (us-east-1)")
    print("="*80)
    
    fake_key = "fake_bedrock_key_123"
    region = "us-east-1"
    
    print(f"Step 2.1: GET /api/settings/ai/bedrock-models?api_key={fake_key}&region={region}")
    url = f"{BASE_URL}/api/settings/ai/bedrock-models?api_key={fake_key}&region={region}"
    
    start_time = time.time()
    response = requests.get(url, headers={"Authorization": f"Bearer {superadmin_token}"}, timeout=30)
    elapsed = time.time() - start_time
    
    print(f"Response status: {response.status_code}")
    print(f"Response time: {elapsed:.2f}s")
    print(f"Response body: {response.text}")
    
    # CRITICAL CHECKS
    assert response.status_code == 200, f"❌ Expected 200, got {response.status_code}"
    print("✅ PASS: Returns 200 (NOT 500/hang)")
    
    assert elapsed < 25, f"❌ Request took {elapsed:.2f}s (should be < 25s)"
    print(f"✅ PASS: Request completed in {elapsed:.2f}s (< 25s)")
    
    data = response.json()
    assert data.get("ok") == False, f"❌ Expected ok=false, got {data.get('ok')}"
    print("✅ PASS: ok=false")
    
    assert data.get("models") == [], f"❌ Expected models=[], got {data.get('models')}"
    print("✅ PASS: models=[]")
    
    message = data.get("message", "")
    assert message, f"❌ Expected message, got empty"
    print(f"✅ PASS: message present: '{message}'")
    
    # Check message is readable (contains error info from Bedrock control plane)
    assert len(message) > 10, f"❌ Message too short: '{message}'"
    print(f"✅ PASS: Message is readable (length {len(message)})")
    
    print("\n✅✅✅ TEST 2 PASSED: FAKE KEY (us-east-1) returns 200 with graceful error message")
    return message

def test_step_3_fake_key_ap_southeast_2(superadmin_token: str):
    """TEST 3: FAKE KEY different region (ap-southeast-2) → 200, graceful {ok:false,...}"""
    print("\n" + "="*80)
    print("TEST 3: FAKE KEY different region (ap-southeast-2)")
    print("="*80)
    
    fake_key = "fake_bedrock_key_123"
    region = "ap-southeast-2"
    
    print(f"Step 3.1: GET /api/settings/ai/bedrock-models?api_key={fake_key}&region={region}")
    url = f"{BASE_URL}/api/settings/ai/bedrock-models?api_key={fake_key}&region={region}"
    
    start_time = time.time()
    response = requests.get(url, headers={"Authorization": f"Bearer {superadmin_token}"}, timeout=30)
    elapsed = time.time() - start_time
    
    print(f"Response status: {response.status_code}")
    print(f"Response time: {elapsed:.2f}s")
    print(f"Response body: {response.text}")
    
    # CRITICAL CHECKS
    assert response.status_code == 200, f"❌ Expected 200, got {response.status_code}"
    print("✅ PASS: Returns 200 (NOT 500/hang)")
    
    assert elapsed < 25, f"❌ Request took {elapsed:.2f}s (should be < 25s)"
    print(f"✅ PASS: Request completed in {elapsed:.2f}s (< 25s)")
    
    data = response.json()
    assert data.get("ok") == False, f"❌ Expected ok=false, got {data.get('ok')}"
    print("✅ PASS: ok=false")
    
    assert data.get("models") == [], f"❌ Expected models=[], got {data.get('models')}"
    print("✅ PASS: models=[]")
    
    message = data.get("message", "")
    assert message, f"❌ Expected message, got empty"
    print(f"✅ PASS: message present: '{message}'")
    
    # Check message is readable
    assert len(message) > 10, f"❌ Message too short: '{message}'"
    print(f"✅ PASS: Message is readable (length {len(message)})")
    
    print("\n✅✅✅ TEST 3 PASSED: FAKE KEY (ap-southeast-2) returns 200 with graceful error message")
    return message

def test_step_4_rbac_admin(admin_token: str):
    """TEST 4: RBAC - as admin@test.com GET → expect 403 (super_admin only)"""
    print("\n" + "="*80)
    print("TEST 4: RBAC - admin should get 403")
    print("="*80)
    
    fake_key = "x"
    region = "us-east-1"
    
    print(f"Step 4.1: GET /api/settings/ai/bedrock-models as admin@test.com")
    url = f"{BASE_URL}/api/settings/ai/bedrock-models?api_key={fake_key}&region={region}"
    response = requests.get(url, headers={"Authorization": f"Bearer {admin_token}"})
    
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.text}")
    
    # CRITICAL CHECK
    assert response.status_code == 403, f"❌ Expected 403, got {response.status_code}"
    print("✅ PASS: Admin gets 403 (super_admin only)")
    
    print("\n✅✅✅ TEST 4 PASSED: RBAC enforced (admin gets 403)")

def test_step_5_saved_key_path(superadmin_token: str):
    """TEST 5: SAVED-KEY path - save fake key, then GET without api_key param → should use saved key"""
    print("\n" + "="*80)
    print("TEST 5: SAVED-KEY path")
    print("="*80)
    
    # Step 5.1: Save bedrock config with fake key
    print("Step 5.1: PUT /api/settings/ai with fake bedrock key")
    put_url = f"{BASE_URL}/api/settings/ai"
    put_body = {
        "provider": "bedrock",
        "api_key": "saved_fake_key_999",
        "bedrock_region": "us-east-1",
        "bedrock_model": "anthropic.claude-3-5-sonnet-20241022-v2:0"
    }
    put_resp = requests.put(put_url, json=put_body, headers={"Authorization": f"Bearer {superadmin_token}"})
    print(f"PUT response: {put_resp.status_code}")
    print(f"PUT body: {put_resp.text}")
    
    assert put_resp.status_code == 200, f"❌ PUT failed: {put_resp.status_code}"
    print("✅ PASS: Bedrock config saved")
    
    # Step 5.2: GET bedrock-models WITHOUT api_key param (should use saved key)
    print("\nStep 5.2: GET /api/settings/ai/bedrock-models (NO api_key param - should use saved key)")
    get_url = f"{BASE_URL}/api/settings/ai/bedrock-models"
    
    start_time = time.time()
    get_resp = requests.get(get_url, headers={"Authorization": f"Bearer {superadmin_token}"}, timeout=30)
    elapsed = time.time() - start_time
    
    print(f"Response status: {get_resp.status_code}")
    print(f"Response time: {elapsed:.2f}s")
    print(f"Response body: {get_resp.text}")
    
    # CRITICAL CHECKS
    assert get_resp.status_code == 200, f"❌ Expected 200, got {get_resp.status_code}"
    print("✅ PASS: Returns 200 (NOT 500)")
    
    assert elapsed < 25, f"❌ Request took {elapsed:.2f}s (should be < 25s)"
    print(f"✅ PASS: Request completed in {elapsed:.2f}s (< 25s)")
    
    data = get_resp.json()
    assert data.get("ok") == False, f"❌ Expected ok=false with fake key, got {data.get('ok')}"
    print("✅ PASS: ok=false (fake key)")
    
    assert data.get("models") == [], f"❌ Expected models=[], got {data.get('models')}"
    print("✅ PASS: models=[]")
    
    message = data.get("message", "")
    assert message, f"❌ Expected message, got empty"
    print(f"✅ PASS: message present: '{message}'")
    
    # Verify it used the saved key (not the "Enter a key" message)
    assert "enter" not in message.lower() and "save" not in message.lower(), \
        f"❌ Message suggests no key, but we saved one: '{message}'"
    print(f"✅ PASS: Used saved key (message doesn't say 'enter/save a key')")
    
    print("\n✅✅✅ TEST 5 PASSED: SAVED-KEY path works correctly")
    return message

def test_step_6_cleanup(superadmin_token: str):
    """TEST 6: CLEANUP - DELETE /api/settings/ai"""
    print("\n" + "="*80)
    print("TEST 6: CLEANUP")
    print("="*80)
    
    print("Step 6.1: DELETE /api/settings/ai")
    delete_url = f"{BASE_URL}/api/settings/ai"
    delete_resp = requests.delete(delete_url, headers={"Authorization": f"Bearer {superadmin_token}"})
    
    print(f"DELETE response: {delete_resp.status_code}")
    print(f"DELETE body: {delete_resp.text}")
    
    assert delete_resp.status_code == 200, f"❌ DELETE failed: {delete_resp.status_code}"
    print("✅ PASS: AI settings deleted")
    
    print("\n✅✅✅ TEST 6 PASSED: Cleanup successful")

def main():
    print("="*80)
    print("BEDROCK MODEL-LISTING ENDPOINT VERIFICATION")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"Endpoint: GET /api/settings/ai/bedrock-models")
    print(f"Test credentials: {SUPERADMIN_EMAIL} (super_admin), {ADMIN_EMAIL} (admin)")
    print("="*80)
    
    # Login
    print("\n📝 AUTHENTICATION")
    superadmin_token = login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    
    # Run all tests
    test_results = {}
    
    try:
        # TEST 1: NO KEY
        msg1 = test_step_1_no_key(superadmin_token)
        test_results["TEST 1 (NO KEY)"] = {"status": "PASS", "message": msg1}
        
        # TEST 2: FAKE KEY us-east-1
        msg2 = test_step_2_fake_key_us_east_1(superadmin_token)
        test_results["TEST 2 (FAKE KEY us-east-1)"] = {"status": "PASS", "message": msg2}
        
        # TEST 3: FAKE KEY ap-southeast-2
        msg3 = test_step_3_fake_key_ap_southeast_2(superadmin_token)
        test_results["TEST 3 (FAKE KEY ap-southeast-2)"] = {"status": "PASS", "message": msg3}
        
        # TEST 4: RBAC
        test_step_4_rbac_admin(admin_token)
        test_results["TEST 4 (RBAC)"] = {"status": "PASS", "message": "Admin gets 403"}
        
        # TEST 5: SAVED-KEY path
        msg5 = test_step_5_saved_key_path(superadmin_token)
        test_results["TEST 5 (SAVED-KEY path)"] = {"status": "PASS", "message": msg5}
        
        # TEST 6: CLEANUP
        test_step_6_cleanup(superadmin_token)
        test_results["TEST 6 (CLEANUP)"] = {"status": "PASS", "message": "Settings deleted"}
        
    except AssertionError as e:
        print(f"\n❌❌❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌❌❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Final summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    
    for test_name, result in test_results.items():
        print(f"✅ {test_name}: {result['status']}")
        print(f"   Message: {result['message']}")
    
    print("\n" + "="*80)
    print("✅✅✅ ALL 6 TESTS PASSED (100% SUCCESS RATE)")
    print("="*80)
    print("\nKEY FINDINGS:")
    print("1. ✅ NO KEY scenario returns 200 with {ok:false, models:[], message} telling user to enter/save key")
    print("2. ✅ FAKE KEY (us-east-1) returns 200 (NOT 500/hang) with graceful error message from Bedrock control plane")
    print("3. ✅ FAKE KEY (ap-southeast-2) returns 200 with graceful error message")
    print("4. ✅ RBAC enforced: admin gets 403 (super_admin only)")
    print("5. ✅ SAVED-KEY path works: uses saved key when no api_key param provided")
    print("6. ✅ CLEANUP successful")
    print("\nCRITICAL REQUIREMENTS MET:")
    print("✅ Every call returns 200 with readable message (NEVER 500/hang)")
    print("✅ RBAC enforced (admin 403)")
    print("✅ Endpoint works both with passed api_key and with saved key")
    print("✅ All error messages are readable and graceful")

if __name__ == "__main__":
    main()
