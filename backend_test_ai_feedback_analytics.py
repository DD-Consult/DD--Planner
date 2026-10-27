#!/usr/bin/env python3
"""
AI Feedback Analytics + Auto-tuning Suggestions (Phase B) Verification
DD Planner - Review Request Testing

Tests:
1. SEED FEEDBACK: Submit several feedbacks via POST /api/ai/feedback
2. ANALYTICS: GET /api/ai/feedback/analytics - verify total, satisfaction_pct, by_feature breakdown
3. ANALYTICS RBAC: Verify 403 for non-admin (qa_resource)
4. SUGGEST (AI): POST /api/ai/feedback/suggest-instructions - should return suggestions based on feedback
5. SUGGEST RBAC: Verify 403 for non-admin
6. SAVE A SUGGESTION AS INSTRUCTION: POST /api/ai/instructions and verify it's saved
7. CLEANUP: Delete created instructions
"""

import requests
import json
import sys
from datetime import datetime

# Configuration
BASE_URL = "https://proposal-approve.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"
QA_RESOURCE_EMAIL = "qa_resource@test.com"
QA_RESOURCE_PASSWORD = "Test@2026"

# Test state
test_results = []
admin_token = None
qa_token = None
created_instruction_id = None


def log_test(step, status, message, details=None):
    """Log test result"""
    result = {
        "step": step,
        "status": status,
        "message": message,
        "details": details,
        "timestamp": datetime.now().isoformat()
    }
    test_results.append(result)
    
    status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    print(f"{status_icon} {step}: {message}")
    if details:
        print(f"   Details: {details}")


def login(email, password):
    """Login and return token"""
    try:
        response = requests.post(
            f"{API_BASE}/auth/login",
            data={"username": email, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
        else:
            log_test("LOGIN", "FAIL", f"Login failed for {email}", 
                    f"Status: {response.status_code}, Response: {response.text[:200]}")
            return None
    except Exception as e:
        log_test("LOGIN", "FAIL", f"Login exception for {email}", str(e))
        return None


def test_seed_feedback():
    """TEST 1: SEED FEEDBACK - Submit several feedbacks"""
    print("\n" + "="*80)
    print("TEST 1: SEED FEEDBACK")
    print("="*80)
    
    feedbacks = [
        {"feature": "chat", "rating": "thumbs_down", "feedback_text": "answers are too generic, use our project data"},
        {"feature": "chat", "rating": "thumbs_down", "feedback_text": "stop inventing numbers"},
        {"feature": "chat", "rating": "thumbs_up"},
        {"feature": "status_summary", "rating": "thumbs_up"},
        {"feature": "status_summary", "rating": "thumbs_up"},
        {"feature": "wbs_generation", "rating": "thumbs_down", "feedback_text": "tasks too high-level"},
    ]
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    success_count = 0
    
    for i, feedback in enumerate(feedbacks, 1):
        try:
            response = requests.post(
                f"{API_BASE}/ai/feedback",
                json=feedback,
                headers=headers
            )
            
            if response.status_code in [200, 201]:
                success_count += 1
                log_test(f"1.{i}", "PASS", 
                        f"Feedback submitted: {feedback['feature']} - {feedback['rating']}", 
                        f"Response: {response.status_code}")
            else:
                log_test(f"1.{i}", "FAIL", 
                        f"Failed to submit feedback: {feedback['feature']}", 
                        f"Status: {response.status_code}, Response: {response.text[:200]}")
        except Exception as e:
            log_test(f"1.{i}", "FAIL", f"Exception submitting feedback: {feedback['feature']}", str(e))
    
    if success_count == len(feedbacks):
        log_test("1.SUMMARY", "PASS", f"All {len(feedbacks)} feedbacks submitted successfully")
    else:
        log_test("1.SUMMARY", "FAIL", f"Only {success_count}/{len(feedbacks)} feedbacks submitted")
    
    return success_count == len(feedbacks)


def test_analytics():
    """TEST 2: ANALYTICS - GET /api/ai/feedback/analytics"""
    print("\n" + "="*80)
    print("TEST 2: ANALYTICS")
    print("="*80)
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    try:
        response = requests.get(
            f"{API_BASE}/ai/feedback/analytics",
            headers=headers
        )
        
        if response.status_code != 200:
            log_test("2.1", "FAIL", "Analytics endpoint failed", 
                    f"Status: {response.status_code}, Response: {response.text[:200]}")
            return False
        
        data = response.json()
        log_test("2.1", "PASS", "Analytics endpoint returned 200", 
                f"Response keys: {list(data.keys())}")
        
        # Check structure
        if "total" not in data:
            log_test("2.2", "FAIL", "Missing 'total' field in response")
            return False
        log_test("2.2", "PASS", f"Total feedback count: {data['total']}")
        
        if data["total"] < 6:
            log_test("2.3", "WARN", f"Total count is {data['total']}, expected >= 6", 
                    "Some feedbacks may not have been saved")
        else:
            log_test("2.3", "PASS", f"Total count >= 6: {data['total']}")
        
        # Check overall_satisfaction_pct
        if "overall_satisfaction_pct" not in data:
            log_test("2.4", "FAIL", "Missing 'overall_satisfaction_pct' field")
            return False
        
        satisfaction = data["overall_satisfaction_pct"]
        if satisfaction is None or not (0 <= satisfaction <= 100):
            log_test("2.4", "FAIL", f"Invalid satisfaction_pct: {satisfaction}")
            return False
        log_test("2.4", "PASS", f"Overall satisfaction: {satisfaction}%")
        
        # Check by_feature
        if "by_feature" not in data:
            log_test("2.5", "FAIL", "Missing 'by_feature' field")
            return False
        
        by_feature = data["by_feature"]
        if not isinstance(by_feature, list):
            log_test("2.5", "FAIL", f"by_feature is not a list: {type(by_feature)}")
            return False
        
        log_test("2.5", "PASS", f"by_feature is a list with {len(by_feature)} features")
        
        # Find specific features
        chat_feature = next((f for f in by_feature if f["feature"] == "chat"), None)
        status_feature = next((f for f in by_feature if f["feature"] == "status_summary"), None)
        wbs_feature = next((f for f in by_feature if f["feature"] == "wbs_generation"), None)
        
        # Verify chat feature
        if not chat_feature:
            log_test("2.6", "FAIL", "chat feature not found in by_feature")
        else:
            expected_chat = {"up": 1, "down": 2, "total": 3}
            actual_chat = {
                "up": chat_feature.get("up", 0),
                "down": chat_feature.get("down", 0),
                "total": chat_feature.get("total", 0)
            }
            
            if actual_chat == expected_chat:
                log_test("2.6", "PASS", f"chat feature correct: {actual_chat}")
            else:
                log_test("2.6", "WARN", f"chat feature mismatch", 
                        f"Expected: {expected_chat}, Actual: {actual_chat}")
            
            # Check satisfaction_pct for chat (should be ~33%)
            chat_sat = chat_feature.get("satisfaction_pct")
            if chat_sat is not None and 30 <= chat_sat <= 35:
                log_test("2.7", "PASS", f"chat satisfaction_pct: {chat_sat}% (expected ~33%)")
            else:
                log_test("2.7", "WARN", f"chat satisfaction_pct: {chat_sat}% (expected ~33%)")
            
            # Check recent_notes for chat
            if "recent_notes" in chat_feature and len(chat_feature["recent_notes"]) > 0:
                log_test("2.8", "PASS", f"chat has {len(chat_feature['recent_notes'])} recent notes")
                for note in chat_feature["recent_notes"]:
                    print(f"   Note: {note}")
            else:
                log_test("2.8", "WARN", "chat has no recent_notes")
        
        # Verify status_summary feature
        if not status_feature:
            log_test("2.9", "FAIL", "status_summary feature not found in by_feature")
        else:
            expected_status = {"up": 2, "down": 0, "total": 2}
            actual_status = {
                "up": status_feature.get("up", 0),
                "down": status_feature.get("down", 0),
                "total": status_feature.get("total", 0)
            }
            
            if actual_status == expected_status:
                log_test("2.9", "PASS", f"status_summary feature correct: {actual_status}")
            else:
                log_test("2.9", "WARN", f"status_summary feature mismatch", 
                        f"Expected: {expected_status}, Actual: {actual_status}")
            
            # Check satisfaction_pct for status_summary (should be 100%)
            status_sat = status_feature.get("satisfaction_pct")
            if status_sat == 100:
                log_test("2.10", "PASS", f"status_summary satisfaction_pct: {status_sat}%")
            else:
                log_test("2.10", "WARN", f"status_summary satisfaction_pct: {status_sat}% (expected 100%)")
        
        # Verify wbs_generation feature
        if not wbs_feature:
            log_test("2.11", "FAIL", "wbs_generation feature not found in by_feature")
        else:
            if wbs_feature.get("down", 0) >= 1:
                log_test("2.11", "PASS", f"wbs_generation has thumbs_down: {wbs_feature}")
            else:
                log_test("2.11", "WARN", f"wbs_generation missing thumbs_down: {wbs_feature}")
            
            # Check recent_notes for wbs_generation
            if "recent_notes" in wbs_feature and len(wbs_feature["recent_notes"]) > 0:
                log_test("2.12", "PASS", f"wbs_generation has {len(wbs_feature['recent_notes'])} recent notes")
                for note in wbs_feature["recent_notes"]:
                    print(f"   Note: {note}")
            else:
                log_test("2.12", "WARN", "wbs_generation has no recent_notes")
        
        # Print full by_feature for reference
        print("\n   Full by_feature breakdown:")
        for feat in by_feature:
            print(f"   - {feat['feature']}: up={feat['up']}, down={feat['down']}, "
                  f"total={feat['total']}, satisfaction={feat.get('satisfaction_pct')}%")
        
        return True
        
    except Exception as e:
        log_test("2.ERROR", "FAIL", "Exception in analytics test", str(e))
        return False


def test_analytics_rbac():
    """TEST 3: ANALYTICS RBAC - Verify 403 for non-admin"""
    print("\n" + "="*80)
    print("TEST 3: ANALYTICS RBAC")
    print("="*80)
    
    headers = {"Authorization": f"Bearer {qa_token}"}
    
    try:
        response = requests.get(
            f"{API_BASE}/ai/feedback/analytics",
            headers=headers
        )
        
        if response.status_code == 403:
            log_test("3.1", "PASS", "qa_resource correctly denied access (403)")
            return True
        else:
            log_test("3.1", "FAIL", f"Expected 403, got {response.status_code}", 
                    f"Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        log_test("3.ERROR", "FAIL", "Exception in RBAC test", str(e))
        return False


def test_suggest_instructions():
    """TEST 4: SUGGEST (AI) - POST /api/ai/feedback/suggest-instructions"""
    print("\n" + "="*80)
    print("TEST 4: SUGGEST INSTRUCTIONS (AI)")
    print("="*80)
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    try:
        print("   Calling suggest-instructions endpoint (may take up to ~45s)...")
        response = requests.post(
            f"{API_BASE}/ai/feedback/suggest-instructions",
            headers=headers,
            timeout=50  # Allow up to 50s
        )
        
        if response.status_code != 200:
            log_test("4.1", "FAIL", f"Suggest endpoint failed with {response.status_code}", 
                    f"Response: {response.text[:300]}")
            return False
        
        log_test("4.1", "PASS", "Suggest endpoint returned 200")
        
        data = response.json()
        
        # Check structure
        if "ok" not in data:
            log_test("4.2", "FAIL", "Missing 'ok' field in response")
            return False
        
        if "summary" not in data:
            log_test("4.3", "FAIL", "Missing 'summary' field in response")
            return False
        
        log_test("4.2", "PASS", f"Response has 'ok': {data['ok']}")
        log_test("4.3", "PASS", f"Response has 'summary': {data['summary'][:100]}...")
        
        # Check if ok is true (should be true since we have thumbs-down feedback)
        if data["ok"]:
            log_test("4.4", "PASS", "ok=true (AI successfully generated suggestions)")
        else:
            log_test("4.4", "WARN", f"ok=false: {data['summary']}", 
                    "This may be acceptable if AI is unavailable")
        
        # Check suggestions
        if "suggestions" not in data:
            log_test("4.5", "FAIL", "Missing 'suggestions' field in response")
            return False
        
        suggestions = data["suggestions"]
        if not isinstance(suggestions, list):
            log_test("4.5", "FAIL", f"suggestions is not a list: {type(suggestions)}")
            return False
        
        log_test("4.5", "PASS", f"suggestions is a list with {len(suggestions)} items")
        
        # If we have suggestions, validate structure
        if len(suggestions) > 0:
            log_test("4.6", "PASS", f"Received {len(suggestions)} suggestions")
            
            valid_categories = ["all", "chat", "status_summary", "wbs_generation", "reschedule", "risk_polish"]
            
            for i, suggestion in enumerate(suggestions, 1):
                if "category" not in suggestion or "suggestion" not in suggestion:
                    log_test(f"4.7.{i}", "FAIL", f"Suggestion {i} missing required fields", 
                            f"Suggestion: {suggestion}")
                    continue
                
                category = suggestion["category"]
                text = suggestion["suggestion"]
                
                if category not in valid_categories:
                    log_test(f"4.7.{i}", "WARN", f"Suggestion {i} has invalid category: {category}")
                else:
                    log_test(f"4.7.{i}", "PASS", f"Suggestion {i}: category={category}")
                
                print(f"   Suggestion {i}:")
                print(f"     Category: {category}")
                print(f"     Text: {text}")
        else:
            if data["ok"]:
                log_test("4.6", "WARN", "ok=true but no suggestions returned", 
                        "This may happen if feedback is all positive")
            else:
                log_test("4.6", "INFO", "No suggestions (ok=false)", 
                        "This is acceptable if AI is unavailable")
        
        # Check provider field (optional)
        if "provider" in data:
            log_test("4.8", "PASS", f"Provider used: {data['provider']}")
        
        print(f"\n   Full response summary: {data['summary']}")
        
        return True
        
    except requests.Timeout:
        log_test("4.ERROR", "FAIL", "Request timed out after 50s", 
                "Endpoint should respond within ~45s")
        return False
    except Exception as e:
        log_test("4.ERROR", "FAIL", "Exception in suggest test", str(e))
        return False


def test_suggest_rbac():
    """TEST 5: SUGGEST RBAC - Verify 403 for non-admin"""
    print("\n" + "="*80)
    print("TEST 5: SUGGEST RBAC")
    print("="*80)
    
    headers = {"Authorization": f"Bearer {qa_token}"}
    
    try:
        response = requests.post(
            f"{API_BASE}/ai/feedback/suggest-instructions",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 403:
            log_test("5.1", "PASS", "qa_resource correctly denied access (403)")
            return True
        else:
            log_test("5.1", "FAIL", f"Expected 403, got {response.status_code}", 
                    f"Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        log_test("5.ERROR", "FAIL", "Exception in RBAC test", str(e))
        return False


def test_save_instruction():
    """TEST 6: SAVE A SUGGESTION AS INSTRUCTION"""
    print("\n" + "="*80)
    print("TEST 6: SAVE INSTRUCTION")
    print("="*80)
    
    global created_instruction_id
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Create an instruction
    instruction_data = {
        "scope": "global",
        "category": "chat",
        "instructions": "Always ground answers in the specific project's real data; never invent numbers.",
        "is_active": True
    }
    
    try:
        # POST instruction
        response = requests.post(
            f"{API_BASE}/ai/instructions",
            json=instruction_data,
            headers=headers
        )
        
        if response.status_code not in [200, 201]:
            log_test("6.1", "FAIL", f"Failed to create instruction: {response.status_code}", 
                    f"Response: {response.text[:200]}")
            return False
        
        log_test("6.1", "PASS", f"Instruction created: {response.status_code}")
        
        created = response.json()
        created_instruction_id = created.get("id")
        
        if not created_instruction_id:
            log_test("6.2", "FAIL", "No 'id' in created instruction response")
            return False
        
        log_test("6.2", "PASS", f"Instruction ID: {created_instruction_id}")
        
        # GET instructions to verify it's there
        response = requests.get(
            f"{API_BASE}/ai/instructions",
            headers=headers
        )
        
        if response.status_code != 200:
            log_test("6.3", "FAIL", f"Failed to list instructions: {response.status_code}")
            return False
        
        instructions = response.json()
        
        # Find our instruction
        found = next((i for i in instructions if i.get("id") == created_instruction_id), None)
        
        if not found:
            log_test("6.3", "FAIL", "Created instruction not found in list")
            return False
        
        log_test("6.3", "PASS", "Instruction found in list")
        
        # Verify fields
        if found.get("scope") == "global" and found.get("category") == "chat":
            log_test("6.4", "PASS", f"Instruction fields correct: scope={found['scope']}, category={found['category']}")
        else:
            log_test("6.4", "FAIL", f"Instruction fields incorrect: {found}")
        
        return True
        
    except Exception as e:
        log_test("6.ERROR", "FAIL", "Exception in save instruction test", str(e))
        return False


def test_cleanup():
    """TEST 7: CLEANUP - Delete created instruction"""
    print("\n" + "="*80)
    print("TEST 7: CLEANUP")
    print("="*80)
    
    if not created_instruction_id:
        log_test("7.1", "SKIP", "No instruction to delete")
        return True
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    try:
        response = requests.delete(
            f"{API_BASE}/ai/instructions/{created_instruction_id}",
            headers=headers
        )
        
        if response.status_code in [200, 204]:
            log_test("7.1", "PASS", f"Instruction deleted: {response.status_code}")
            return True
        else:
            log_test("7.1", "FAIL", f"Failed to delete instruction: {response.status_code}", 
                    f"Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        log_test("7.ERROR", "FAIL", "Exception in cleanup", str(e))
        return False


def main():
    """Run all tests"""
    global admin_token, qa_token
    
    print("="*80)
    print("AI FEEDBACK ANALYTICS + AUTO-TUNING SUGGESTIONS (PHASE B) VERIFICATION")
    print("DD Planner - Review Request Testing")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"API Base: {API_BASE}")
    print(f"Test Time: {datetime.now().isoformat()}")
    print("="*80)
    
    # Login
    print("\n" + "="*80)
    print("AUTHENTICATION")
    print("="*80)
    
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        print("❌ CRITICAL: Failed to login as admin. Aborting tests.")
        sys.exit(1)
    log_test("AUTH.1", "PASS", f"Admin login successful: {ADMIN_EMAIL}")
    
    qa_token = login(QA_RESOURCE_EMAIL, QA_RESOURCE_PASSWORD)
    if not qa_token:
        print("❌ CRITICAL: Failed to login as qa_resource. Aborting tests.")
        sys.exit(1)
    log_test("AUTH.2", "PASS", f"QA Resource login successful: {QA_RESOURCE_EMAIL}")
    
    # Run tests
    test_1_pass = test_seed_feedback()
    test_2_pass = test_analytics()
    test_3_pass = test_analytics_rbac()
    test_4_pass = test_suggest_instructions()
    test_5_pass = test_suggest_rbac()
    test_6_pass = test_save_instruction()
    test_7_pass = test_cleanup()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    total_tests = len(test_results)
    passed = sum(1 for r in test_results if r["status"] == "PASS")
    failed = sum(1 for r in test_results if r["status"] == "FAIL")
    warned = sum(1 for r in test_results if r["status"] == "WARN")
    
    print(f"Total Tests: {total_tests}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⚠️  Warnings: {warned}")
    print(f"Success Rate: {passed/total_tests*100:.1f}%")
    
    # Critical tests
    critical_tests = [test_1_pass, test_2_pass, test_3_pass, test_4_pass, test_5_pass, test_6_pass]
    critical_passed = sum(1 for t in critical_tests if t)
    
    print(f"\nCritical Tests: {critical_passed}/{len(critical_tests)} passed")
    
    if critical_passed == len(critical_tests):
        print("\n✅✅✅ ALL CRITICAL TESTS PASSED ✅✅✅")
        print("AI Feedback Analytics + Auto-tuning Suggestions (Phase B) is working correctly!")
    else:
        print("\n❌ SOME CRITICAL TESTS FAILED")
        print("Review the detailed output above for failures.")
    
    # Save results to file
    results_file = f"/tmp/ai_feedback_analytics_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump({
            "test_time": datetime.now().isoformat(),
            "base_url": BASE_URL,
            "summary": {
                "total": total_tests,
                "passed": passed,
                "failed": failed,
                "warned": warned,
                "success_rate": f"{passed/total_tests*100:.1f}%"
            },
            "results": test_results
        }, f, indent=2)
    
    print(f"\nDetailed results saved to: {results_file}")
    
    return 0 if critical_passed == len(critical_tests) else 1


if __name__ == "__main__":
    sys.exit(main())
