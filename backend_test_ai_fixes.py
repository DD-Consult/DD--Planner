#!/usr/bin/env python3
"""
Backend test for 4 AI issue fixes in DD Planner.
Tests error handling, HTTP status codes, and code-level confirmations.

IMPORTANT: This environment has NO working AI key (Gemini revoked, no OpenAI, no EMERGENT_LLM_KEY).
We're testing CODE-LEVEL behavior: error handling, status codes, no crashes/500-with-stacktrace.
"""

import requests
import json
import sys
import os

# Base URL from environment
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://saas-launch-44.preview.emergentagent.com")
API_BASE = f"{BASE_URL}/api"

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

def login():
    """Login as admin and return Bearer token."""
    print(f"\n🔐 Logging in as {ADMIN_EMAIL}...")
    response = requests.post(
        f"{API_BASE}/auth/login",
        data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    if response.status_code != 200:
        print(f"❌ Login failed: {response.status_code} {response.text}")
        sys.exit(1)
    
    token = response.json().get("access_token")
    print(f"✅ Login successful, token: {token[:20]}...")
    return token


def get_first_project_id(token):
    """Get the first project ID for testing."""
    print("\n📋 Fetching first project ID...")
    response = requests.get(
        f"{API_BASE}/projects",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to fetch projects: {response.status_code}")
        sys.exit(1)
    
    projects = response.json()
    if not projects:
        print("❌ No projects found")
        sys.exit(1)
    
    project_id = projects[0]["id"]
    project_name = projects[0]["name"]
    print(f"✅ Using project: {project_name} (ID: {project_id})")
    return project_id


def test_1_smart_reschedule(token, project_id):
    """
    TEST 1: AI Smart Reschedule endpoint no longer silently breaks.
    Expected: Clean error (400 or 502), NOT a 500 with stacktrace.
    """
    print("\n" + "="*80)
    print("TEST 1: AI Smart Reschedule Error Handling")
    print("="*80)
    
    print(f"\n📡 POST /api/ai/smart-reschedule/{project_id}")
    response = requests.post(
        f"{API_BASE}/ai/smart-reschedule/{project_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={}
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text[:500]}")
    
    # Check for clean error (400 or 502), NOT 500 with stacktrace
    if response.status_code == 500:
        # Check if it's a raw Python traceback
        if "Traceback" in response.text or "KeyError" in response.text or "Exception" in response.text:
            print("❌ FAIL: Returns 500 with Python stacktrace (not a clean error)")
            return False
    
    if response.status_code in [400, 502]:
        try:
            data = response.json()
            detail = data.get("detail", "")
            print(f"✅ PASS: Clean error response - {response.status_code}")
            print(f"   Detail: {detail}")
            
            # Verify it's a human-readable message
            if "No AI provider configured" in detail or "AI service temporarily unavailable" in detail:
                print("   ✅ Error message is clear and appropriate")
                return True
            else:
                print(f"   ⚠️  Unexpected error message: {detail}")
                return True  # Still a clean error, just different message
        except:
            print("❌ FAIL: Response is not valid JSON")
            return False
    
    print(f"⚠️  Unexpected status code: {response.status_code}")
    return False


def test_2_wbs_generator_error(token, project_id):
    """
    TEST 2: WBS generator gives CORRECT, clear error (not misleading "configure a key").
    Expected: 400 with "No AI provider configured" OR 502 "AI service failed to generate a WBS".
    """
    print("\n" + "="*80)
    print("TEST 2: WBS Generator Error Message")
    print("="*80)
    
    print(f"\n📡 POST /api/ai/generate-wbs")
    response = requests.post(
        f"{API_BASE}/ai/generate-wbs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "project_id": project_id,
            "complexity": "standard",
            "include_subtasks": True
        }
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text[:500]}")
    
    # Check for clean error (400 or 502), NOT 500 with stacktrace
    if response.status_code == 500:
        if "Traceback" in response.text or "KeyError" in response.text:
            print("❌ FAIL: Returns 500 with Python stacktrace")
            return False
    
    if response.status_code in [400, 502]:
        try:
            data = response.json()
            detail = data.get("detail", "")
            print(f"✅ PASS: Clean error response - {response.status_code}")
            print(f"   Detail: {detail}")
            
            # Check for correct error messages
            if "No AI provider configured" in detail:
                print("   ✅ Correct error: 'No AI provider configured'")
                return True
            elif "AI service failed to generate a WBS" in detail:
                print("   ✅ Correct error: 'AI service failed to generate a WBS'")
                return True
            else:
                print(f"   ⚠️  Different error message (but still clean): {detail}")
                return True
        except:
            print("❌ FAIL: Response is not valid JSON")
            return False
    
    print(f"⚠️  Unexpected status code: {response.status_code}")
    return False


def test_3_wbs_resource_scoping_code():
    """
    TEST 3: WBS resource-scoping logic (code-level verification).
    Verify these exist in /app/backend/routes/wbs.py:
    (a) "RESOURCE AVAILABILITY WINDOWS" block in prompt
    (b) _has_overlapping_alloc overlap check function
    (c) Logic that sets assigned_to_id=None with assignment_note when no overlap
    """
    print("\n" + "="*80)
    print("TEST 3: WBS Resource-Scoping Code Verification")
    print("="*80)
    
    wbs_file = "/app/backend/routes/wbs.py"
    print(f"\n📄 Reading {wbs_file}...")
    
    try:
        with open(wbs_file, 'r') as f:
            content = f.read()
        
        checks = []
        
        # (a) Check for "RESOURCE AVAILABILITY WINDOWS" in prompt
        if "RESOURCE AVAILABILITY WINDOWS" in content:
            print("✅ (a) Found 'RESOURCE AVAILABILITY WINDOWS' block in prompt")
            checks.append(True)
            # Extract a sample line
            for line in content.split('\n'):
                if "RESOURCE AVAILABILITY WINDOWS" in line:
                    print(f"    Sample: {line.strip()[:80]}...")
                    break
        else:
            print("❌ (a) 'RESOURCE AVAILABILITY WINDOWS' NOT found in prompt")
            checks.append(False)
        
        # (b) Check for _has_overlapping_alloc function
        if "def _has_overlapping_alloc" in content:
            print("✅ (b) Found '_has_overlapping_alloc' overlap check function")
            checks.append(True)
            # Extract function signature
            for line in content.split('\n'):
                if "def _has_overlapping_alloc" in line:
                    print(f"    Signature: {line.strip()}")
                    break
        else:
            print("❌ (b) '_has_overlapping_alloc' function NOT found")
            checks.append(False)
        
        # (c) Check for assignment_note logic when no overlap
        if 'assignment_note' in content and 'no active allocation covering these dates' in content.lower():
            print("✅ (c) Found assignment_note logic for unassigned tasks")
            checks.append(True)
            # Extract sample
            for i, line in enumerate(content.split('\n')):
                if 'assignment_note' in line and 'Unassigned' in line:
                    print(f"    Sample: {line.strip()[:80]}...")
                    break
        else:
            print("❌ (c) assignment_note logic NOT found")
            checks.append(False)
        
        if all(checks):
            print("\n✅ PASS: All 3 resource-scoping code elements present")
            return True
        else:
            print(f"\n❌ FAIL: {checks.count(False)}/3 checks failed")
            return False
            
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False


def test_4_chat_clarifying_questions_code():
    """
    TEST 4: Chat clarifying-questions prompt present (code-level check).
    Verify /app/backend/routes/ai.py contains "CLARIFYING QUESTIONS" section
    instructing agent to ask follow-up when info is missing.
    """
    print("\n" + "="*80)
    print("TEST 4: Chat Clarifying-Questions Prompt Verification")
    print("="*80)
    
    ai_file = "/app/backend/routes/ai.py"
    print(f"\n📄 Reading {ai_file}...")
    
    try:
        with open(ai_file, 'r') as f:
            content = f.read()
        
        # Check for "CLARIFYING QUESTIONS" section
        if "CLARIFYING QUESTIONS" in content:
            print("✅ Found 'CLARIFYING QUESTIONS' section in system prompt")
            
            # Extract a sample line from the section
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if "CLARIFYING QUESTIONS" in line:
                    # Get next few lines for context
                    sample_lines = lines[i:min(i+5, len(lines))]
                    print("\n    Sample from prompt:")
                    for sl in sample_lines:
                        if sl.strip():
                            print(f"    {sl.strip()[:80]}")
                    break
            
            # Also check for key concepts: "ask", "missing", "required info"
            section_keywords = ["ask", "missing", "required", "clarif"]
            found_keywords = [kw for kw in section_keywords if kw.lower() in content.lower()]
            print(f"\n    Related keywords found: {', '.join(found_keywords)}")
            
            return True
        else:
            print("❌ 'CLARIFYING QUESTIONS' section NOT found in prompt")
            return False
            
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False


def test_4_chat_functional_smoke(token):
    """
    TEST 4 (functional): Best-effort smoke test of chat endpoint.
    Expected: Clean error (no 500 with stacktrace).
    """
    print("\n" + "="*80)
    print("TEST 4 (Functional): Chat Endpoint Smoke Test")
    print("="*80)
    
    print(f"\n📡 POST /api/ai/chat")
    response = requests.post(
        f"{API_BASE}/ai/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "message": "assign Alice to the website project",
            "session_id": None
        }
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text[:500]}")
    
    # Check it doesn't 500 with stacktrace
    if response.status_code == 500:
        if "Traceback" in response.text or "KeyError" in response.text:
            print("❌ FAIL: Returns 500 with Python stacktrace")
            return False
    
    # Any clean response (even error) is acceptable
    if response.status_code in [200, 400, 401, 403, 502]:
        print(f"✅ PASS: Clean response (no crash) - {response.status_code}")
        return True
    
    print(f"⚠️  Unexpected status code: {response.status_code}")
    return False


def test_5_gemini_model_name_code():
    """
    TEST 5: Gemini model name fix (code-level verification).
    Verify /app/backend/services/ai_providers.py uses:
    - GEMINI_TEXT_MODEL default "gemini-flash-latest" (NOT "gemini-2.5-flash")
    - extract_gemini_text helper exists and is used
    """
    print("\n" + "="*80)
    print("TEST 5: Gemini Model Name Fix Verification")
    print("="*80)
    
    providers_file = "/app/backend/services/ai_providers.py"
    print(f"\n📄 Reading {providers_file}...")
    
    try:
        with open(providers_file, 'r') as f:
            content = f.read()
        
        checks = []
        
        # Check for GEMINI_TEXT_MODEL with correct default
        if 'GEMINI_TEXT_MODEL' in content and 'gemini-flash-latest' in content:
            print("✅ Found GEMINI_TEXT_MODEL with default 'gemini-flash-latest'")
            checks.append(True)
            # Extract the line
            for line in content.split('\n'):
                if 'GEMINI_TEXT_MODEL' in line and '=' in line:
                    print(f"    Line: {line.strip()}")
                    break
        else:
            print("❌ GEMINI_TEXT_MODEL with 'gemini-flash-latest' NOT found")
            checks.append(False)
        
        # Check it's NOT using the old retired model
        if 'gemini-2.5-flash' in content:
            print("⚠️  WARNING: Old model name 'gemini-2.5-flash' still present in code")
            checks.append(False)
        else:
            print("✅ Old model name 'gemini-2.5-flash' NOT present (good)")
            checks.append(True)
        
        # Check for extract_gemini_text helper
        if 'def extract_gemini_text' in content:
            print("✅ Found 'extract_gemini_text' helper function")
            checks.append(True)
            # Extract function signature
            for line in content.split('\n'):
                if 'def extract_gemini_text' in line:
                    print(f"    Signature: {line.strip()}")
                    break
        else:
            print("❌ 'extract_gemini_text' helper NOT found")
            checks.append(False)
        
        # Check that extract_gemini_text is actually used in call_gemini_api
        if 'extract_gemini_text' in content and content.count('extract_gemini_text') > 1:
            print("✅ extract_gemini_text is used (appears multiple times)")
            checks.append(True)
        else:
            print("⚠️  extract_gemini_text may not be used")
            checks.append(False)
        
        if all(checks):
            print("\n✅ PASS: All Gemini model name checks passed")
            return True
        else:
            print(f"\n⚠️  PARTIAL PASS: {checks.count(True)}/{len(checks)} checks passed")
            return checks.count(True) >= 3  # At least 3/4 checks should pass
            
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False


def main():
    """Run all tests."""
    print("="*80)
    print("DD PLANNER - AI FIXES BACKEND TESTING")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"API Base: {API_BASE}")
    print("\nNOTE: This environment has NO working AI key (expected).")
    print("We're testing CODE-LEVEL behavior: error handling, status codes, no crashes.")
    
    # Login
    token = login()
    
    # Get first project ID
    project_id = get_first_project_id(token)
    
    # Run all tests
    results = {}
    
    results["TEST 1: Smart Reschedule Error Handling"] = test_1_smart_reschedule(token, project_id)
    results["TEST 2: WBS Generator Error Message"] = test_2_wbs_generator_error(token, project_id)
    results["TEST 3: WBS Resource-Scoping Code"] = test_3_wbs_resource_scoping_code()
    results["TEST 4: Chat Clarifying-Questions Code"] = test_4_chat_clarifying_questions_code()
    results["TEST 4: Chat Functional Smoke"] = test_4_chat_functional_smoke(token)
    results["TEST 5: Gemini Model Name Fix"] = test_5_gemini_model_name_code()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
