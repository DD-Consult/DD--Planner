#!/usr/bin/env python3
"""
Comprehensive test for AWS Bedrock AI provider + AI feedback loop.
Tests all endpoints as specified in the review request.
"""
import requests
import json
import sys
from datetime import datetime

# Backend URL from frontend/.env
BASE_URL = "https://proposal-approve.preview.emergentagent.com/api"

# Test credentials
SUPERADMIN_EMAIL = "superadmin@test.com"
SUPERADMIN_PASSWORD = "Super@2026"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def log_test(test_name, status, message=""):
    """Log test result with color coding."""
    if status == "PASS":
        print(f"{GREEN}✅ {test_name}: PASS{RESET}")
        if message:
            print(f"   {message}")
    elif status == "FAIL":
        print(f"{RED}❌ {test_name}: FAIL{RESET}")
        if message:
            print(f"   {RED}{message}{RESET}")
    elif status == "INFO":
        print(f"{BLUE}ℹ️  {test_name}{RESET}")
        if message:
            print(f"   {message}")
    else:
        print(f"{YELLOW}⚠️  {test_name}: {status}{RESET}")
        if message:
            print(f"   {message}")

def login(email, password):
    """Login and return token."""
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": email, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
        else:
            log_test(f"Login as {email}", "FAIL", f"Status: {response.status_code}, Response: {response.text}")
            return None
    except Exception as e:
        log_test(f"Login as {email}", "FAIL", f"Exception: {str(e)}")
        return None

def test_get_ai_settings(token, expected_status=200, role="superadmin"):
    """Test GET /api/settings/ai"""
    try:
        response = requests.get(
            f"{BASE_URL}/settings/ai",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code != expected_status:
            log_test(f"GET /api/settings/ai (as {role})", "FAIL", 
                    f"Expected {expected_status}, got {response.status_code}")
            return None
        
        if expected_status == 200:
            data = response.json()
            # Verify structure
            required_fields = ["provider", "has_key", "has_emergent_fallback", "bedrock_region", "bedrock_model"]
            missing = [f for f in required_fields if f not in data]
            if missing:
                log_test(f"GET /api/settings/ai (as {role})", "FAIL", 
                        f"Missing fields: {missing}")
                return None
            
            # Verify raw key is NOT returned
            if "api_key" in data and data["api_key"] != "":
                log_test(f"GET /api/settings/ai (as {role})", "FAIL", 
                        "Raw api_key found in response (security issue)")
                return None
            
            log_test(f"GET /api/settings/ai (as {role})", "PASS", 
                    f"Provider: {data.get('provider')}, Has key: {data.get('has_key')}, "
                    f"Region: {data.get('bedrock_region')}, Model: {data.get('bedrock_model')}")
            return data
        else:
            log_test(f"GET /api/settings/ai (as {role})", "PASS", 
                    f"Correctly returned {expected_status}")
            return None
            
    except Exception as e:
        log_test(f"GET /api/settings/ai (as {role})", "FAIL", f"Exception: {str(e)}")
        return None

def test_save_bedrock_settings(token, api_key, region, model):
    """Test PUT /api/settings/ai with bedrock config"""
    try:
        payload = {
            "provider": "bedrock",
            "api_key": api_key,
            "bedrock_region": region,
            "bedrock_model": model
        }
        
        response = requests.put(
            f"{BASE_URL}/settings/ai",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload
        )
        
        if response.status_code != 200:
            log_test("PUT /api/settings/ai (save bedrock)", "FAIL", 
                    f"Status: {response.status_code}, Response: {response.text}")
            return False
        
        log_test("PUT /api/settings/ai (save bedrock)", "PASS", 
                f"Saved bedrock config: region={region}, model={model}")
        return True
        
    except Exception as e:
        log_test("PUT /api/settings/ai (save bedrock)", "FAIL", f"Exception: {str(e)}")
        return False

def test_preserve_key(token, region):
    """Test PUT /api/settings/ai with empty key (should preserve existing)"""
    try:
        payload = {
            "provider": "bedrock",
            "api_key": "",  # Empty key should preserve existing
            "bedrock_region": region
        }
        
        response = requests.put(
            f"{BASE_URL}/settings/ai",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload
        )
        
        if response.status_code != 200:
            log_test("PUT /api/settings/ai (preserve key)", "FAIL", 
                    f"Status: {response.status_code}, Response: {response.text}")
            return False
        
        log_test("PUT /api/settings/ai (preserve key)", "PASS", 
                f"Empty key sent, should preserve existing key")
        return True
        
    except Exception as e:
        log_test("PUT /api/settings/ai (preserve key)", "FAIL", f"Exception: {str(e)}")
        return False

def test_bedrock_test_endpoint(token):
    """Test POST /api/settings/ai/test-bedrock"""
    try:
        response = requests.post(
            f"{BASE_URL}/settings/ai/test-bedrock",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code != 200:
            log_test("POST /api/settings/ai/test-bedrock", "FAIL", 
                    f"Expected 200, got {response.status_code}. Response: {response.text}")
            return None
        
        data = response.json()
        
        # Should return {ok: false, message: ...} with fake key
        if "ok" not in data or "message" not in data:
            log_test("POST /api/settings/ai/test-bedrock", "FAIL", 
                    f"Missing 'ok' or 'message' in response: {data}")
            return None
        
        log_test("POST /api/settings/ai/test-bedrock", "PASS", 
                f"Returned 200 with ok={data['ok']}, message='{data['message'][:100]}...'")
        return data
        
    except Exception as e:
        log_test("POST /api/settings/ai/test-bedrock", "FAIL", f"Exception: {str(e)}")
        return None

def test_ai_feature_fallback(token):
    """Test AI feature with bedrock configured (fake key) - should degrade gracefully"""
    try:
        # Try AI chat endpoint
        response = requests.post(
            f"{BASE_URL}/ai/chat",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"message": "hello"}
        )
        
        if response.status_code == 500:
            log_test("AI feature fallback (chat)", "FAIL", 
                    f"Returned 500 (should degrade gracefully). Response: {response.text}")
            return False
        
        log_test("AI feature fallback (chat)", "PASS", 
                f"Returned {response.status_code} (NOT 500 - graceful degradation)")
        return True
        
    except Exception as e:
        log_test("AI feature fallback (chat)", "FAIL", f"Exception: {str(e)}")
        return False

def test_submit_feedback(token, feature, rating, feedback_text=None, expected_status=201):
    """Test POST /api/ai/feedback"""
    try:
        payload = {
            "feature": feature,
            "rating": rating
        }
        if feedback_text:
            payload["feedback_text"] = feedback_text
        
        response = requests.post(
            f"{BASE_URL}/ai/feedback",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload
        )
        
        if response.status_code != expected_status:
            log_test(f"POST /api/ai/feedback ({feature}, {rating})", "FAIL", 
                    f"Expected {expected_status}, got {response.status_code}. Response: {response.text}")
            return None
        
        if expected_status in [200, 201]:
            data = response.json()
            log_test(f"POST /api/ai/feedback ({feature}, {rating})", "PASS", 
                    f"Feedback submitted successfully")
            return data
        else:
            log_test(f"POST /api/ai/feedback ({feature}, {rating})", "PASS", 
                    f"Correctly returned {expected_status}")
            return None
        
    except Exception as e:
        log_test(f"POST /api/ai/feedback ({feature}, {rating})", "FAIL", f"Exception: {str(e)}")
        return None

def test_feedback_stats(token, expected_status=200):
    """Test GET /api/ai/feedback/stats"""
    try:
        response = requests.get(
            f"{BASE_URL}/ai/feedback/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code != expected_status:
            log_test("GET /api/ai/feedback/stats", "FAIL", 
                    f"Expected {expected_status}, got {response.status_code}. Response: {response.text}")
            return None
        
        if expected_status == 200:
            data = response.json()
            log_test("GET /api/ai/feedback/stats", "PASS", 
                    f"Total: {data.get('total_count')}, By feature: {data.get('by_feature')}, "
                    f"By rating: {data.get('by_rating')}")
            return data
        else:
            log_test("GET /api/ai/feedback/stats", "PASS", 
                    f"Correctly returned {expected_status}")
            return None
        
    except Exception as e:
        log_test("GET /api/ai/feedback/stats", "FAIL", f"Exception: {str(e)}")
        return None

def test_delete_ai_settings(token):
    """Test DELETE /api/settings/ai"""
    try:
        response = requests.delete(
            f"{BASE_URL}/settings/ai",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code != 200:
            log_test("DELETE /api/settings/ai", "FAIL", 
                    f"Status: {response.status_code}, Response: {response.text}")
            return False
        
        log_test("DELETE /api/settings/ai", "PASS", "AI settings cleared")
        return True
        
    except Exception as e:
        log_test("DELETE /api/settings/ai", "FAIL", f"Exception: {str(e)}")
        return False

def main():
    """Run all tests"""
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}AWS Bedrock AI Provider + AI Feedback Loop Test{RESET}")
    print(f"{BLUE}Backend URL: {BASE_URL}{RESET}")
    print(f"{BLUE}{'='*80}{RESET}\n")
    
    passed = 0
    failed = 0
    
    # Step 1: Login as superadmin
    log_test("Step 1", "INFO", "Login as superadmin")
    superadmin_token = login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)
    if not superadmin_token:
        print(f"\n{RED}CRITICAL: Cannot proceed without superadmin token{RESET}")
        sys.exit(1)
    passed += 1
    
    # Step 2: GET /api/settings/ai (initial state)
    log_test("\nStep 2", "INFO", "GET /api/settings/ai - verify structure and defaults")
    initial_settings = test_get_ai_settings(superadmin_token)
    if initial_settings:
        passed += 1
        # Verify defaults
        if initial_settings.get("bedrock_region") and initial_settings.get("bedrock_model"):
            log_test("  Default bedrock config", "PASS", 
                    f"Region: {initial_settings['bedrock_region']}, Model: {initial_settings['bedrock_model']}")
            passed += 1
        else:
            log_test("  Default bedrock config", "FAIL", "Missing default region or model")
            failed += 1
    else:
        failed += 1
    
    # Step 3: SAVE BEDROCK config
    log_test("\nStep 3", "INFO", "PUT /api/settings/ai - save bedrock config with fake key")
    if test_save_bedrock_settings(superadmin_token, "bedrock_test_key_abc123", "us-west-2", 
                                   "us.anthropic.claude-3-5-sonnet-20241022-v2:0"):
        passed += 1
        
        # Verify saved config
        saved_settings = test_get_ai_settings(superadmin_token)
        if saved_settings:
            if saved_settings.get("provider") == "bedrock":
                log_test("  Verify provider", "PASS", "Provider is 'bedrock'")
                passed += 1
            else:
                log_test("  Verify provider", "FAIL", f"Provider is '{saved_settings.get('provider')}'")
                failed += 1
            
            if saved_settings.get("has_key"):
                log_test("  Verify has_key", "PASS", "has_key is True")
                passed += 1
            else:
                log_test("  Verify has_key", "FAIL", "has_key is False")
                failed += 1
            
            if saved_settings.get("bedrock_region") == "us-west-2":
                log_test("  Verify region", "PASS", "Region is 'us-west-2'")
                passed += 1
            else:
                log_test("  Verify region", "FAIL", f"Region is '{saved_settings.get('bedrock_region')}'")
                failed += 1
            
            if saved_settings.get("bedrock_model") == "us.anthropic.claude-3-5-sonnet-20241022-v2:0":
                log_test("  Verify model", "PASS", "Model is correct")
                passed += 1
            else:
                log_test("  Verify model", "FAIL", f"Model is '{saved_settings.get('bedrock_model')}'")
                failed += 1
            
            # CRITICAL: Verify raw key is NOT in response
            response_str = json.dumps(saved_settings)
            if "bedrock_test_key_abc123" in response_str:
                log_test("  Verify key masking", "FAIL", "RAW KEY FOUND IN RESPONSE (SECURITY ISSUE)")
                failed += 1
            else:
                log_test("  Verify key masking", "PASS", "Raw key NOT in response (only masked)")
                passed += 1
        else:
            failed += 1
    else:
        failed += 1
    
    # Step 4: PRESERVE KEY test
    log_test("\nStep 4", "INFO", "PUT /api/settings/ai - empty key should preserve existing")
    if test_preserve_key(superadmin_token, "eu-west-1"):
        passed += 1
        
        # Verify key still present and region updated
        preserved_settings = test_get_ai_settings(superadmin_token)
        if preserved_settings:
            if preserved_settings.get("has_key"):
                log_test("  Verify key preserved", "PASS", "has_key still True")
                passed += 1
            else:
                log_test("  Verify key preserved", "FAIL", "has_key is False (key was lost)")
                failed += 1
            
            if preserved_settings.get("bedrock_region") == "eu-west-1":
                log_test("  Verify region updated", "PASS", "Region updated to 'eu-west-1'")
                passed += 1
            else:
                log_test("  Verify region updated", "FAIL", f"Region is '{preserved_settings.get('bedrock_region')}'")
                failed += 1
        else:
            failed += 1
    else:
        failed += 1
    
    # Step 5: TEST-BEDROCK endpoint
    log_test("\nStep 5", "INFO", "POST /api/settings/ai/test-bedrock - graceful failure with fake key")
    test_result = test_bedrock_test_endpoint(superadmin_token)
    if test_result:
        passed += 1
        if not test_result.get("ok"):
            log_test("  Verify graceful failure", "PASS", "ok=false as expected with fake key")
            passed += 1
        else:
            log_test("  Verify graceful failure", "FAIL", "ok=true (unexpected with fake key)")
            failed += 1
        
        if test_result.get("message"):
            log_test("  Verify error message", "PASS", f"Message: '{test_result['message'][:100]}'")
            passed += 1
        else:
            log_test("  Verify error message", "FAIL", "No error message provided")
            failed += 1
    else:
        failed += 1
    
    # Step 6: RBAC tests (admin should get 403)
    log_test("\nStep 6", "INFO", "RBAC - admin should get 403 on AI settings endpoints")
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if admin_token:
        passed += 1
        
        # GET should return 403
        test_get_ai_settings(admin_token, expected_status=403, role="admin")
        passed += 1
        
        # PUT should return 403
        try:
            response = requests.put(
                f"{BASE_URL}/settings/ai",
                headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"},
                json={"provider": "bedrock", "api_key": "test"}
            )
            if response.status_code == 403:
                log_test("  PUT /api/settings/ai (as admin)", "PASS", "Correctly returned 403")
                passed += 1
            else:
                log_test("  PUT /api/settings/ai (as admin)", "FAIL", f"Expected 403, got {response.status_code}")
                failed += 1
        except Exception as e:
            log_test("  PUT /api/settings/ai (as admin)", "FAIL", f"Exception: {str(e)}")
            failed += 1
        
        # POST test-bedrock should return 403
        try:
            response = requests.post(
                f"{BASE_URL}/settings/ai/test-bedrock",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            if response.status_code == 403:
                log_test("  POST /api/settings/ai/test-bedrock (as admin)", "PASS", "Correctly returned 403")
                passed += 1
            else:
                log_test("  POST /api/settings/ai/test-bedrock (as admin)", "FAIL", 
                        f"Expected 403, got {response.status_code}")
                failed += 1
        except Exception as e:
            log_test("  POST /api/settings/ai/test-bedrock (as admin)", "FAIL", f"Exception: {str(e)}")
            failed += 1
    else:
        failed += 1
    
    # Step 7: AI FEATURE FALLBACK (with bedrock configured + fake key)
    log_test("\nStep 7", "INFO", "AI feature fallback - should NOT 500 with fake bedrock key")
    if test_ai_feature_fallback(admin_token):
        passed += 1
    else:
        failed += 1
    
    # Step 8: AI FEEDBACK submit tests
    log_test("\nStep 8", "INFO", "AI feedback submit - test valid and invalid ratings")
    
    # Valid: thumbs_down with feedback text
    if test_submit_feedback(admin_token, "proposal", "thumbs_down", 
                           "too generic, be more specific"):
        passed += 1
    else:
        failed += 1
    
    # Valid: thumbs_up without feedback text
    if test_submit_feedback(admin_token, "chat", "thumbs_up"):
        passed += 1
    else:
        failed += 1
    
    # Invalid: wrong rating value
    test_submit_feedback(admin_token, "chat", "positive", expected_status=400)
    passed += 1
    
    # Invalid: wrong feature value
    test_submit_feedback(admin_token, "bogus", "thumbs_up", expected_status=400)
    passed += 1
    
    # Step 9: AI FEEDBACK stats
    log_test("\nStep 9", "INFO", "GET /api/ai/feedback/stats - verify stats endpoint")
    stats = test_feedback_stats(admin_token)
    if stats:
        passed += 1
        
        # Verify our submitted feedback is in stats
        if stats.get("total_count", 0) >= 2:
            log_test("  Verify feedback count", "PASS", f"Total count: {stats['total_count']}")
            passed += 1
        else:
            log_test("  Verify feedback count", "FAIL", f"Expected >= 2, got {stats.get('total_count')}")
            failed += 1
        
        by_feature = stats.get("by_feature", {})
        if "proposal" in by_feature or "chat" in by_feature:
            log_test("  Verify by_feature", "PASS", f"Features: {by_feature}")
            passed += 1
        else:
            log_test("  Verify by_feature", "FAIL", f"Expected 'proposal' or 'chat', got {by_feature}")
            failed += 1
    else:
        failed += 1
    
    # Step 10: CLEANUP
    log_test("\nStep 10", "INFO", "DELETE /api/settings/ai - cleanup")
    if test_delete_ai_settings(superadmin_token):
        passed += 1
        
        # Verify settings cleared
        cleared_settings = test_get_ai_settings(superadmin_token)
        if cleared_settings and not cleared_settings.get("has_key"):
            log_test("  Verify settings cleared", "PASS", "has_key is False after delete")
            passed += 1
        else:
            log_test("  Verify settings cleared", "FAIL", "has_key still True after delete")
            failed += 1
    else:
        failed += 1
    
    # Summary
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}TEST SUMMARY{RESET}")
    print(f"{BLUE}{'='*80}{RESET}")
    print(f"{GREEN}Passed: {passed}{RESET}")
    print(f"{RED}Failed: {failed}{RESET}")
    print(f"Total: {passed + failed}")
    
    if failed == 0:
        print(f"\n{GREEN}✅ ALL TESTS PASSED{RESET}\n")
        return 0
    else:
        print(f"\n{RED}❌ SOME TESTS FAILED{RESET}\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
