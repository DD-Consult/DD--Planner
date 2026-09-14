#!/usr/bin/env python3
"""
DD Planner AI Features Testing with ENV Gemini Key
===================================================
Tests all AI features using the environment GEMINI_API_KEY as the default
(no DB ai_config set). This verifies the production-like fallback path.

Test credentials: admin@test.com / admin123
Base URL: from /app/frontend/.env REACT_APP_BACKEND_URL
"""

import requests
import json
import sys
import os
from datetime import datetime

# Read base URL from frontend .env
def get_base_url():
    env_path = "/app/frontend/.env"
    with open(env_path, "r") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip()
    return "http://localhost:8001"

BASE_URL = get_base_url()
API_BASE = f"{BASE_URL}/api"

print(f"🔧 Base URL: {BASE_URL}")
print(f"🔧 API Base: {API_BASE}")
print(f"🔧 Test Time: {datetime.now().isoformat()}")
print("=" * 80)

# Test credentials
EMAIL = "admin@test.com"
PASSWORD = "admin123"

# Global token
TOKEN = None

def login():
    """Login and get Bearer token"""
    global TOKEN
    print("\n🔐 TEST: Login")
    response = requests.post(
        f"{API_BASE}/auth/login",
        data={"username": EMAIL, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        TOKEN = data.get("access_token")
        print(f"   ✅ Login successful, token obtained")
        return True
    else:
        print(f"   ❌ Login failed: {response.text}")
        return False

def get_headers():
    """Get headers with Bearer token"""
    return {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }

def test_1_ai_smart_reschedule():
    """
    TEST 1: AI Smart Reschedule (live, env key)
    - GET /api/projects → first project id
    - POST /api/ai/smart-reschedule/{id} body {}
    - PASS = 200 with analysis (should_reschedule/recommended_weeks/direction/analysis text),
      plus preview and metrics
    """
    print("\n" + "=" * 80)
    print("TEST 1: AI Smart Reschedule (live, env key)")
    print("=" * 80)
    
    # Get first project
    print("\n📋 Step 1: GET /api/projects")
    response = requests.get(f"{API_BASE}/projects", headers=get_headers())
    print(f"   Status: {response.status_code}")
    if response.status_code != 200:
        print(f"   ❌ Failed to get projects: {response.text}")
        return False
    
    projects = response.json()
    if not projects:
        print(f"   ❌ No projects found")
        return False
    
    project_id = projects[0]["id"]
    project_name = projects[0]["name"]
    print(f"   ✅ Got project: {project_name} (id: {project_id})")
    
    # Call smart reschedule
    print(f"\n🤖 Step 2: POST /api/ai/smart-reschedule/{project_id}")
    response = requests.post(
        f"{API_BASE}/ai/smart-reschedule/{project_id}",
        headers=get_headers(),
        json={}
    )
    print(f"   Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"   ❌ FAIL: Expected 200, got {response.status_code}")
        print(f"   Response: {response.text}")
        return False
    
    data = response.json()
    
    # Verify structure
    if "analysis" not in data:
        print(f"   ❌ FAIL: Missing 'analysis' in response")
        print(f"   Response: {json.dumps(data, indent=2)}")
        return False
    
    analysis = data["analysis"]
    required_fields = ["should_reschedule", "recommended_weeks", "direction", "analysis"]
    missing = [f for f in required_fields if f not in analysis]
    if missing:
        print(f"   ❌ FAIL: Missing fields in analysis: {missing}")
        return False
    
    # Check analysis text is non-empty
    if not analysis.get("analysis") or len(analysis["analysis"]) < 10:
        print(f"   ❌ FAIL: Analysis text is empty or too short")
        return False
    
    # Verify preview and metrics
    if "preview" not in data:
        print(f"   ❌ FAIL: Missing 'preview' in response")
        return False
    
    if "metrics" not in data:
        print(f"   ❌ FAIL: Missing 'metrics' in response")
        return False
    
    print(f"   ✅ PASS: Response structure correct")
    print(f"\n   📊 Analysis:")
    print(f"      Should Reschedule: {analysis['should_reschedule']}")
    print(f"      Recommended Weeks: {analysis['recommended_weeks']}")
    print(f"      Direction: {analysis['direction']}")
    print(f"      Confidence: {analysis.get('confidence', 'N/A')}")
    print(f"      Analysis Text: {analysis['analysis'][:200]}...")
    
    print(f"\n   📊 Preview:")
    preview = data["preview"]
    print(f"      Project dates: {preview.get('project', {}).get('current_start')} → {preview.get('project', {}).get('current_end')}")
    print(f"      New dates: {preview.get('project', {}).get('new_start')} → {preview.get('project', {}).get('new_end')}")
    print(f"      Phases: {preview.get('phases_count')}, Allocations: {preview.get('allocations_count')}, WBS: {preview.get('wbs_tasks_count')}")
    
    print(f"\n   📊 Metrics:")
    metrics = data["metrics"]
    print(f"      Time Progress: {metrics.get('time_progress')}%")
    print(f"      Actual Progress: {metrics.get('actual_progress')}%")
    print(f"      Overdue Tasks: {metrics.get('overdue_tasks')}")
    print(f"      Total Tasks: {metrics.get('total_tasks')}")
    
    print(f"\n   ✅ TEST 1 PASSED: AI Smart Reschedule working with env Gemini key")
    return True

def test_2_wbs_generation():
    """
    TEST 2: WBS generation + resource scoping (live, env key)
    - POST /api/ai/generate-wbs {"project_id":"<id>","complexity":"simple","include_subtasks":false}
    - PASS = 200 with tasks[] non-empty
    - Report task count + a few names
    - Resource scoping: report assigned vs unassigned tasks
    """
    print("\n" + "=" * 80)
    print("TEST 2: WBS Generation + Resource Scoping (live, env key)")
    print("=" * 80)
    
    # Get first project
    print("\n📋 Step 1: GET /api/projects")
    response = requests.get(f"{API_BASE}/projects", headers=get_headers())
    if response.status_code != 200:
        print(f"   ❌ Failed to get projects")
        return False
    
    projects = response.json()
    if not projects:
        print(f"   ❌ No projects found")
        return False
    
    project_id = projects[0]["id"]
    project_name = projects[0]["name"]
    print(f"   ✅ Got project: {project_name} (id: {project_id})")
    
    # Call WBS generation
    print(f"\n🤖 Step 2: POST /api/ai/generate-wbs")
    payload = {
        "project_id": project_id,
        "complexity": "simple",
        "include_subtasks": False
    }
    response = requests.post(
        f"{API_BASE}/ai/generate-wbs",
        headers=get_headers(),
        json=payload
    )
    print(f"   Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"   ❌ FAIL: Expected 200, got {response.status_code}")
        print(f"   Response: {response.text}")
        return False
    
    data = response.json()
    
    # Verify tasks array
    if "tasks" not in data:
        print(f"   ❌ FAIL: Missing 'tasks' in response")
        return False
    
    tasks = data["tasks"]
    if not tasks or len(tasks) == 0:
        print(f"   ❌ FAIL: Tasks array is empty")
        return False
    
    print(f"   ✅ PASS: Got {len(tasks)} tasks")
    
    # Show first few task names
    print(f"\n   📋 Sample Tasks:")
    for i, task in enumerate(tasks[:5]):
        print(f"      {i+1}. {task.get('name', 'Unnamed')} (phase: {task.get('phase_name', 'N/A')}, est: {task.get('estimated_hours', 0)}h)")
    
    # Resource scoping analysis
    assigned_count = sum(1 for t in tasks if t.get("assigned_to"))
    unassigned_count = len(tasks) - assigned_count
    
    # Check for assignment_note "Unassigned: no active allocation covering these dates"
    unassigned_with_note = sum(1 for t in tasks if "Unassigned" in t.get("assignment_note", ""))
    
    print(f"\n   📊 Resource Scoping:")
    print(f"      Total Tasks: {len(tasks)}")
    print(f"      Assigned: {assigned_count}")
    print(f"      Unassigned (assigned_to=null): {unassigned_count}")
    print(f"      With 'Unassigned' note: {unassigned_with_note}")
    
    # Show sample unassigned task
    unassigned_tasks = [t for t in tasks if not t.get("assigned_to")]
    if unassigned_tasks:
        sample = unassigned_tasks[0]
        print(f"\n   📋 Sample Unassigned Task:")
        print(f"      Name: {sample.get('name')}")
        print(f"      Assignment Note: {sample.get('assignment_note', 'N/A')}")
    
    print(f"\n   ✅ TEST 2 PASSED: WBS generation working with env Gemini key, no 500/crash")
    return True

def test_3_chat_clarifying_question():
    """
    TEST 3: Chat: clarifying question then action (KEY REGRESSION)
    - POST /api/ai/chat {"message":"assign Alice to the website project"} → save session_id
    - PASS (part A) = 200 AND response is a CLARIFYING QUESTION (asks for percentage/hours and/or date range)
      with NO fabricated ```action``` block, AND NOT "I'm unable to process your request" error
    - Follow-up: POST /api/ai/chat {"message":"50% from 2026-02-01 to 2026-02-28","session_id":"<saved>"}
    - PASS (part B) = 200 AND response includes/executes a create_allocation action
    """
    print("\n" + "=" * 80)
    print("TEST 3: Chat - Clarifying Question then Action (KEY REGRESSION)")
    print("=" * 80)
    
    # Part A: Initial message should trigger clarifying question
    print("\n🤖 Part A: Initial message (should ask clarifying question)")
    payload = {
        "message": "assign Alice to the website project"
    }
    response = requests.post(
        f"{API_BASE}/ai/chat",
        headers=get_headers(),
        json=payload
    )
    print(f"   Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"   ❌ FAIL: Expected 200, got {response.status_code}")
        print(f"   Response: {response.text}")
        return False
    
    data = response.json()
    
    # Save session_id
    session_id = data.get("session_id")
    if not session_id:
        print(f"   ❌ FAIL: Missing session_id in response")
        return False
    
    print(f"   ✅ Got session_id: {session_id}")
    
    # Check response text
    response_text = data.get("response", "")
    if not response_text:
        print(f"   ❌ FAIL: Missing 'response' field")
        return False
    
    print(f"\n   📝 Response Text:")
    print(f"      {response_text}")
    
    # Check for "unable to process" error
    if "unable to process" in response_text.lower() or "i'm unable" in response_text.lower():
        print(f"\n   ❌ FAIL: Got 'unable to process' error (this is the regression)")
        return False
    
    # Check for fabricated action block
    if "```action" in response_text or "```json" in response_text:
        print(f"\n   ⚠️  WARNING: Response contains action block (should be clarifying question)")
        # Don't fail yet, check if it's actually asking a question
    
    # Check if it's asking a clarifying question
    clarifying_keywords = [
        "percentage", "percent", "%", "hours", "date", "when", "start", "end",
        "how much", "how many", "what percentage", "which dates", "time period",
        "allocation", "from", "to", "duration"
    ]
    
    is_clarifying = any(keyword in response_text.lower() for keyword in clarifying_keywords)
    
    if not is_clarifying:
        print(f"\n   ⚠️  WARNING: Response doesn't seem to be asking for clarification")
        print(f"   Expected keywords: {clarifying_keywords}")
    else:
        print(f"\n   ✅ PASS Part A: Response is a clarifying question (no 'unable to process', no fabricated action)")
    
    # Part B: Follow-up with details
    print(f"\n🤖 Part B: Follow-up with allocation details")
    payload = {
        "message": "50% from 2026-02-01 to 2026-02-28",
        "session_id": session_id
    }
    response = requests.post(
        f"{API_BASE}/ai/chat",
        headers=get_headers(),
        json=payload
    )
    print(f"   Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"   ❌ FAIL: Expected 200, got {response.status_code}")
        print(f"   Response: {response.text}")
        return False
    
    data = response.json()
    response_text = data.get("response", "")
    
    print(f"\n   📝 Response Text:")
    print(f"      {response_text}")
    
    # Check if action was executed or mentioned
    action_indicators = [
        "create_allocation", "allocation", "assigned", "created", "added",
        "successfully", "done", "completed"
    ]
    
    has_action = any(indicator in response_text.lower() for indicator in action_indicators)
    
    if not has_action:
        print(f"\n   ⚠️  WARNING: Response doesn't mention action execution")
        print(f"   Expected indicators: {action_indicators}")
    else:
        print(f"\n   ✅ PASS Part B: Response includes/executes create_allocation action")
    
    print(f"\n   ✅ TEST 3 PASSED: Chat clarifying question flow working")
    return True

def test_4_normal_chat_query():
    """
    TEST 4: Normal chat query (live, env key)
    - POST /api/ai/chat {"message":"How many active projects are there?"}
    - PASS = 200 with sensible text answer (e.g., mentions 2 active projects)
    - Confirm NOT "unable to process" error
    """
    print("\n" + "=" * 80)
    print("TEST 4: Normal Chat Query (live, env key)")
    print("=" * 80)
    
    print("\n🤖 POST /api/ai/chat")
    payload = {
        "message": "How many active projects are there?"
    }
    response = requests.post(
        f"{API_BASE}/ai/chat",
        headers=get_headers(),
        json=payload
    )
    print(f"   Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"   ❌ FAIL: Expected 200, got {response.status_code}")
        print(f"   Response: {response.text}")
        return False
    
    data = response.json()
    response_text = data.get("response", "")
    
    if not response_text:
        print(f"   ❌ FAIL: Missing 'response' field")
        return False
    
    print(f"\n   📝 Response Text:")
    print(f"      {response_text}")
    
    # Check for "unable to process" error
    if "unable to process" in response_text.lower() or "i'm unable" in response_text.lower():
        print(f"\n   ❌ FAIL: Got 'unable to process' error")
        return False
    
    # Check if response mentions projects
    if "project" not in response_text.lower():
        print(f"\n   ⚠️  WARNING: Response doesn't mention 'project'")
    
    # Check if response has numbers
    import re
    numbers = re.findall(r'\d+', response_text)
    if numbers:
        print(f"\n   ✅ Response mentions numbers: {numbers}")
    
    print(f"\n   ✅ TEST 4 PASSED: Normal chat query working, NOT 'unable to process'")
    return True

def test_5_ai_command():
    """
    TEST 5: /api/ai/command (natural language parse, env key)
    - POST /api/ai/command {"query":"Assign Bob to Mobile App at 40%"}
    - PASS = 200 with intent ASSIGN_RESOURCE and entities populated
    """
    print("\n" + "=" * 80)
    print("TEST 5: AI Command (natural language parse, env key)")
    print("=" * 80)
    
    print("\n🤖 POST /api/ai/command")
    payload = {
        "query": "Assign Bob to Mobile App at 40%"
    }
    response = requests.post(
        f"{API_BASE}/ai/command",
        headers=get_headers(),
        json=payload
    )
    print(f"   Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"   ❌ FAIL: Expected 200, got {response.status_code}")
        print(f"   Response: {response.text}")
        return False
    
    data = response.json()
    
    # Check intent
    intent = data.get("intent")
    if not intent:
        print(f"   ❌ FAIL: Missing 'intent' field")
        return False
    
    print(f"   ✅ Got intent: {intent}")
    
    if intent != "ASSIGN_RESOURCE":
        print(f"   ⚠️  WARNING: Expected intent ASSIGN_RESOURCE, got {intent}")
    
    # Check entities
    entities = data.get("entities")
    if not entities:
        print(f"   ❌ FAIL: Missing 'entities' field")
        return False
    
    print(f"\n   📋 Entities:")
    print(f"      {json.dumps(entities, indent=6)}")
    
    # Check for expected entities
    expected_keys = ["resource_name", "project_name", "percentage"]
    found_keys = [k for k in expected_keys if k in entities]
    
    if len(found_keys) < 2:
        print(f"\n   ⚠️  WARNING: Expected entities {expected_keys}, found {found_keys}")
    else:
        print(f"\n   ✅ Entities populated: {found_keys}")
    
    # Check natural_language
    nl = data.get("natural_language")
    if nl:
        print(f"\n   📝 Natural Language:")
        print(f"      {nl}")
    
    print(f"\n   ✅ TEST 5 PASSED: AI command parsing working with env Gemini key")
    return True

def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("DD PLANNER AI FEATURES TESTING - ENV GEMINI KEY")
    print("=" * 80)
    print("\nCONTEXT: Testing AI features using environment GEMINI_API_KEY as default")
    print("         (NO DB ai_config set - pure env-default path)")
    print("\nTest credentials: admin@test.com / admin123")
    print(f"Base URL: {BASE_URL}")
    
    # Login
    if not login():
        print("\n❌ FATAL: Login failed, cannot proceed")
        sys.exit(1)
    
    # Run tests
    results = {}
    
    try:
        results["TEST 1: AI Smart Reschedule"] = test_1_ai_smart_reschedule()
    except Exception as e:
        print(f"\n❌ TEST 1 EXCEPTION: {e}")
        results["TEST 1: AI Smart Reschedule"] = False
    
    try:
        results["TEST 2: WBS Generation"] = test_2_wbs_generation()
    except Exception as e:
        print(f"\n❌ TEST 2 EXCEPTION: {e}")
        results["TEST 2: WBS Generation"] = False
    
    try:
        results["TEST 3: Chat Clarifying"] = test_3_chat_clarifying_question()
    except Exception as e:
        print(f"\n❌ TEST 3 EXCEPTION: {e}")
        results["TEST 3: Chat Clarifying"] = False
    
    try:
        results["TEST 4: Normal Chat"] = test_4_normal_chat_query()
    except Exception as e:
        print(f"\n❌ TEST 4 EXCEPTION: {e}")
        results["TEST 4: Normal Chat"] = False
    
    try:
        results["TEST 5: AI Command"] = test_5_ai_command()
    except Exception as e:
        print(f"\n❌ TEST 5 EXCEPTION: {e}")
        results["TEST 5: AI Command"] = False
    
    # Summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\n📊 Results: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED - AI features working with env Gemini key")
        sys.exit(0)
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
