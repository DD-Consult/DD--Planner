#!/usr/bin/env python3
"""
Backend test for NEW WBS scheduling capabilities (ADDITIVE/backward-compatible).
Tests duration_days, SNET constraint, FNLT/deadline violations, dependency_links, critical-path.

Review Request: Test new WBS scheduling backend capabilities in DD Planner (FastAPI + MongoDB).
All additions are ADDITIVE/backward-compatible.

AUTH: Login as admin@test.com / admin123
PROJECT: Use project "Website Redesign" id `6ab25bc82be78e05e89230f3` (has ~30 WBS tasks)

TESTS:
1. Regression — existing WBS list still works
2. duration_days auto-computes end_date (create)
3. duration_days on update
4. SNET constraint snaps start
5. FNLT / deadline violation flags
6. dependency_links accepted (additive)
7. Critical path endpoint
"""

import requests
import json
from datetime import datetime, timedelta

# Backend URL from frontend/.env
BACKEND_URL = "https://ddplanner-fixes.preview.emergentagent.com/api"

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

# Test project
PROJECT_ID = "6ab25bc82be78e05e89230f3"  # Website Redesign

# Track created tasks for cleanup
created_task_ids = []

def login():
    """Login and get JWT token."""
    print("\n" + "="*80)
    print("AUTHENTICATION")
    print("="*80)
    
    response = requests.post(
        f"{BACKEND_URL}/auth/login",
        data={
            "username": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    print(f"POST /api/auth/login")
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"ERROR: Login failed")
        print(f"Response: {response.text}")
        return None
    
    data = response.json()
    token = data.get("access_token")
    print(f"✅ Login successful")
    print(f"Token: {token[:50]}...")
    return token


def test_1_regression_wbs_list(token):
    """TEST 1: Regression — existing WBS list still works."""
    print("\n" + "="*80)
    print("TEST 1: REGRESSION - Existing WBS list still works")
    print("="*80)
    
    response = requests.get(
        f"{BACKEND_URL}/projects/{PROJECT_ID}/wbs",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    print(f"GET /api/projects/{PROJECT_ID}/wbs")
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {response.status_code}")
        print(f"Response: {response.text}")
        return False
    
    tasks = response.json()
    print(f"✅ SUCCESS: Got {len(tasks)} tasks")
    
    # Check that tasks have existing fields
    if tasks:
        sample_task = tasks[0]
        required_fields = ["name", "start_date", "end_date", "dependencies", "progress_percentage"]
        missing_fields = [f for f in required_fields if f not in sample_task]
        
        if missing_fields:
            print(f"❌ FAILED: Missing fields in task: {missing_fields}")
            return False
        
        print(f"✅ Sample task has all required fields: {required_fields}")
        print(f"   Task name: {sample_task.get('name')}")
        print(f"   Start date: {sample_task.get('start_date')}")
        print(f"   End date: {sample_task.get('end_date')}")
        print(f"   Progress: {sample_task.get('progress_percentage')}%")
    
    return True


def test_2_duration_days_create(token):
    """TEST 2: duration_days auto-computes end_date (create)."""
    print("\n" + "="*80)
    print("TEST 2: duration_days auto-computes end_date (create)")
    print("="*80)
    
    # Test 2a: duration_days=5 from Monday 2027-03-02
    print("\n--- Test 2a: duration_days=5 from Monday 2027-03-02 ---")
    
    task_data = {
        "name": "QA Duration Task",
        "start_date": "2027-03-02",  # Monday
        "duration_days": 5
    }
    
    response = requests.post(
        f"{BACKEND_URL}/projects/{PROJECT_ID}/wbs/tasks",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json=task_data
    )
    
    print(f"POST /api/projects/{PROJECT_ID}/wbs/tasks")
    print(f"Payload: {json.dumps(task_data, indent=2)}")
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {response.status_code}")
        print(f"Response: {response.text}")
        return False, None
    
    task = response.json()
    task_id = task.get("id")
    created_task_ids.append(task_id)
    
    print(f"✅ Task created with ID: {task_id}")
    print(f"   Start date: {task.get('start_date')}")
    print(f"   End date: {task.get('end_date')}")
    print(f"   Duration days: {task.get('duration_days')}")
    
    # ASSERT: end_date should be 2027-03-06 (Mon+5 business days = Mon-Fri → Friday)
    expected_end = "2027-03-06"
    actual_end = task.get("end_date", "")[:10]
    
    if actual_end != expected_end:
        print(f"❌ FAILED: Expected end_date={expected_end}, got {actual_end}")
        return False, task_id
    
    print(f"✅ ASSERTION PASSED: end_date={actual_end} (Mon+5 biz days = Fri)")
    
    # Test 2b: Explicit end_date precedence
    print("\n--- Test 2b: Explicit end_date precedence ---")
    
    task_data_explicit = {
        "name": "QA Dur Explicit",
        "start_date": "2027-03-02",
        "duration_days": 5,
        "end_date": "2027-03-10"  # Explicit end_date should win
    }
    
    response = requests.post(
        f"{BACKEND_URL}/projects/{PROJECT_ID}/wbs/tasks",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json=task_data_explicit
    )
    
    print(f"POST /api/projects/{PROJECT_ID}/wbs/tasks")
    print(f"Payload: {json.dumps(task_data_explicit, indent=2)}")
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {response.status_code}")
        print(f"Response: {response.text}")
        return False, task_id
    
    task_explicit = response.json()
    task_explicit_id = task_explicit.get("id")
    created_task_ids.append(task_explicit_id)
    
    print(f"✅ Task created with ID: {task_explicit_id}")
    print(f"   Start date: {task_explicit.get('start_date')}")
    print(f"   End date: {task_explicit.get('end_date')}")
    
    # ASSERT: end_date should remain 2027-03-10 (explicit wins)
    expected_end_explicit = "2027-03-10"
    actual_end_explicit = task_explicit.get("end_date", "")[:10]
    
    if actual_end_explicit != expected_end_explicit:
        print(f"❌ FAILED: Expected end_date={expected_end_explicit}, got {actual_end_explicit}")
        return False, task_id
    
    print(f"✅ ASSERTION PASSED: end_date={actual_end_explicit} (explicit wins)")
    
    return True, task_id


def test_3_duration_days_update(token, task_id):
    """TEST 3: duration_days on update."""
    print("\n" + "="*80)
    print("TEST 3: duration_days on update")
    print("="*80)
    
    if not task_id:
        print("❌ FAILED: No task_id from test 2")
        return False
    
    # Update duration_days to 3 (start stays 2027-03-02 Monday)
    update_data = {
        "duration_days": 3
    }
    
    response = requests.put(
        f"{BACKEND_URL}/wbs/tasks/{task_id}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json=update_data
    )
    
    print(f"PUT /api/wbs/tasks/{task_id}")
    print(f"Payload: {json.dumps(update_data, indent=2)}")
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {response.status_code}")
        print(f"Response: {response.text}")
        return False
    
    task = response.json()
    
    print(f"✅ Task updated")
    print(f"   Start date: {task.get('start_date')}")
    print(f"   End date: {task.get('end_date')}")
    print(f"   Duration days: {task.get('duration_days')}")
    
    # ASSERT: end_date should now be 2027-03-04 (Mon+3 biz = Wed)
    expected_end = "2027-03-04"
    actual_end = task.get("end_date", "")[:10]
    
    if actual_end != expected_end:
        print(f"❌ FAILED: Expected end_date={expected_end}, got {actual_end}")
        return False
    
    print(f"✅ ASSERTION PASSED: end_date={actual_end} (Mon+3 biz days = Wed)")
    
    return True


def test_4_snet_constraint(token):
    """TEST 4: SNET constraint snaps start."""
    print("\n" + "="*80)
    print("TEST 4: SNET constraint snaps start")
    print("="*80)
    
    # Create task with SNET constraint
    # start_date=2027-03-01 (before constraint), constraint_date=2027-03-08
    task_data = {
        "name": "QA SNET",
        "start_date": "2027-03-01",
        "constraint_type": "SNET",
        "constraint_date": "2027-03-08"
    }
    
    response = requests.post(
        f"{BACKEND_URL}/projects/{PROJECT_ID}/wbs/tasks",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json=task_data
    )
    
    print(f"POST /api/projects/{PROJECT_ID}/wbs/tasks")
    print(f"Payload: {json.dumps(task_data, indent=2)}")
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {response.status_code}")
        print(f"Response: {response.text}")
        return False
    
    task = response.json()
    task_id = task.get("id")
    created_task_ids.append(task_id)
    
    print(f"✅ Task created with ID: {task_id}")
    print(f"   Original start_date: 2027-03-01")
    print(f"   Constraint type: {task.get('constraint_type')}")
    print(f"   Constraint date: {task.get('constraint_date')}")
    print(f"   Actual start_date: {task.get('start_date')}")
    
    # ASSERT: start_date was snapped to >= 2027-03-08
    actual_start = task.get("start_date", "")[:10]
    constraint_date = "2027-03-08"
    
    if actual_start < constraint_date:
        print(f"❌ FAILED: start_date={actual_start} should be >= {constraint_date}")
        return False
    
    print(f"✅ ASSERTION PASSED: start_date={actual_start} was snapped to >= {constraint_date}")
    
    return True


def test_5_deadline_violations(token):
    """TEST 5: FNLT / deadline violation flags."""
    print("\n" + "="*80)
    print("TEST 5: FNLT / deadline violation flags")
    print("="*80)
    
    # Test 5a: Deadline violation
    print("\n--- Test 5a: Deadline violation ---")
    
    task_data_deadline = {
        "name": "QA Deadline",
        "start_date": "2027-03-01",
        "end_date": "2027-03-20",
        "deadline": "2027-03-10"  # end > deadline
    }
    
    response = requests.post(
        f"{BACKEND_URL}/projects/{PROJECT_ID}/wbs/tasks",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json=task_data_deadline
    )
    
    print(f"POST /api/projects/{PROJECT_ID}/wbs/tasks")
    print(f"Payload: {json.dumps(task_data_deadline, indent=2)}")
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {response.status_code}")
        print(f"Response: {response.text}")
        return False
    
    task_deadline = response.json()
    task_deadline_id = task_deadline.get("id")
    created_task_ids.append(task_deadline_id)
    
    print(f"✅ Task created with ID: {task_deadline_id}")
    print(f"   End date: {task_deadline.get('end_date')}")
    print(f"   Deadline: {task_deadline.get('deadline')}")
    print(f"   deadline_violated: {task_deadline.get('deadline_violated')}")
    
    # ASSERT: deadline_violated should be true
    if not task_deadline.get("deadline_violated"):
        print(f"❌ FAILED: deadline_violated should be true (end 03-20 > deadline 03-10)")
        return False
    
    print(f"✅ ASSERTION PASSED: deadline_violated=true")
    
    # Test 5b: FNLT constraint violation
    print("\n--- Test 5b: FNLT constraint violation ---")
    
    task_data_fnlt = {
        "name": "QA FNLT",
        "start_date": "2027-03-01",
        "end_date": "2027-03-20",
        "constraint_type": "FNLT",
        "constraint_date": "2027-03-10"  # end > constraint
    }
    
    response = requests.post(
        f"{BACKEND_URL}/projects/{PROJECT_ID}/wbs/tasks",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json=task_data_fnlt
    )
    
    print(f"POST /api/projects/{PROJECT_ID}/wbs/tasks")
    print(f"Payload: {json.dumps(task_data_fnlt, indent=2)}")
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {response.status_code}")
        print(f"Response: {response.text}")
        return False
    
    task_fnlt = response.json()
    task_fnlt_id = task_fnlt.get("id")
    created_task_ids.append(task_fnlt_id)
    
    print(f"✅ Task created with ID: {task_fnlt_id}")
    print(f"   End date: {task_fnlt.get('end_date')}")
    print(f"   Constraint type: {task_fnlt.get('constraint_type')}")
    print(f"   Constraint date: {task_fnlt.get('constraint_date')}")
    print(f"   constraint_violated: {task_fnlt.get('constraint_violated')}")
    
    # ASSERT: constraint_violated should be true
    if not task_fnlt.get("constraint_violated"):
        print(f"❌ FAILED: constraint_violated should be true (end 03-20 > FNLT 03-10)")
        return False
    
    print(f"✅ ASSERTION PASSED: constraint_violated=true")
    
    # Test 5c: Compliant deadline (no violation)
    print("\n--- Test 5c: Compliant deadline (no violation) ---")
    
    task_data_ontime = {
        "name": "QA OnTime",
        "start_date": "2027-03-01",
        "end_date": "2027-03-05",
        "deadline": "2027-03-10"  # end < deadline
    }
    
    response = requests.post(
        f"{BACKEND_URL}/projects/{PROJECT_ID}/wbs/tasks",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json=task_data_ontime
    )
    
    print(f"POST /api/projects/{PROJECT_ID}/wbs/tasks")
    print(f"Payload: {json.dumps(task_data_ontime, indent=2)}")
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {response.status_code}")
        print(f"Response: {response.text}")
        return False
    
    task_ontime = response.json()
    task_ontime_id = task_ontime.get("id")
    created_task_ids.append(task_ontime_id)
    
    print(f"✅ Task created with ID: {task_ontime_id}")
    print(f"   End date: {task_ontime.get('end_date')}")
    print(f"   Deadline: {task_ontime.get('deadline')}")
    print(f"   deadline_violated: {task_ontime.get('deadline_violated')}")
    
    # ASSERT: deadline_violated should be false
    if task_ontime.get("deadline_violated"):
        print(f"❌ FAILED: deadline_violated should be false (end 03-05 < deadline 03-10)")
        return False
    
    print(f"✅ ASSERTION PASSED: deadline_violated=false")
    
    return True


def test_6_dependency_links(token, predecessor_task_id):
    """TEST 6: dependency_links accepted (additive)."""
    print("\n" + "="*80)
    print("TEST 6: dependency_links accepted (additive)")
    print("="*80)
    
    if not predecessor_task_id:
        print("❌ FAILED: No predecessor_task_id from test 2")
        return False
    
    # Create task with dependency_links
    task_data = {
        "name": "QA DepLink",
        "start_date": "2027-03-02",
        "end_date": "2027-03-06",
        "dependency_links": [
            {
                "predecessor_id": predecessor_task_id,
                "type": "SS",
                "lag_days": 2
            }
        ]
    }
    
    response = requests.post(
        f"{BACKEND_URL}/projects/{PROJECT_ID}/wbs/tasks",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json=task_data
    )
    
    print(f"POST /api/projects/{PROJECT_ID}/wbs/tasks")
    print(f"Payload: {json.dumps(task_data, indent=2)}")
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {response.status_code}")
        print(f"Response: {response.text}")
        return False
    
    task = response.json()
    task_id = task.get("id")
    created_task_ids.append(task_id)
    
    print(f"✅ Task created with ID: {task_id}")
    print(f"   dependency_links: {task.get('dependency_links')}")
    
    # ASSERT: dependency_links should round-trip
    dep_links = task.get("dependency_links", [])
    if not dep_links:
        print(f"❌ FAILED: dependency_links is empty")
        return False
    
    if len(dep_links) != 1:
        print(f"❌ FAILED: Expected 1 dependency_link, got {len(dep_links)}")
        return False
    
    link = dep_links[0]
    if link.get("predecessor_id") != predecessor_task_id:
        print(f"❌ FAILED: predecessor_id mismatch")
        return False
    
    if link.get("type") != "SS":
        print(f"❌ FAILED: Expected type=SS, got {link.get('type')}")
        return False
    
    if link.get("lag_days") != 2:
        print(f"❌ FAILED: Expected lag_days=2, got {link.get('lag_days')}")
        return False
    
    print(f"✅ ASSERTION PASSED: dependency_links round-trips correctly")
    print(f"   predecessor_id: {link.get('predecessor_id')}")
    print(f"   type: {link.get('type')}")
    print(f"   lag_days: {link.get('lag_days')}")
    
    # Also check that legacy dependencies still works
    print(f"   Legacy dependencies field: {task.get('dependencies')}")
    
    return True


def test_7_critical_path(token):
    """TEST 7: Critical path endpoint."""
    print("\n" + "="*80)
    print("TEST 7: Critical path endpoint")
    print("="*80)
    
    # Test 7a: Critical path for Website Redesign project
    print("\n--- Test 7a: Critical path for Website Redesign ---")
    
    response = requests.get(
        f"{BACKEND_URL}/projects/{PROJECT_ID}/wbs/critical-path",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    print(f"GET /api/projects/{PROJECT_ID}/wbs/critical-path")
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {response.status_code}")
        print(f"Response: {response.text}")
        return False
    
    data = response.json()
    
    print(f"✅ SUCCESS: Got critical path data")
    print(f"   critical_task_ids: {data.get('critical_task_ids')}")
    print(f"   project_duration_days: {data.get('project_duration_days')}")
    print(f"   task_slack (sample): {list(data.get('task_slack', {}).items())[:3]}")
    
    # ASSERT: Response has required keys
    required_keys = ["critical_task_ids", "project_duration_days", "task_slack"]
    missing_keys = [k for k in required_keys if k not in data]
    
    if missing_keys:
        print(f"❌ FAILED: Missing keys: {missing_keys}")
        return False
    
    print(f"✅ ASSERTION PASSED: Response has all required keys")
    
    # ASSERT: critical_task_ids is a list
    if not isinstance(data.get("critical_task_ids"), list):
        print(f"❌ FAILED: critical_task_ids should be a list")
        return False
    
    print(f"✅ ASSERTION PASSED: critical_task_ids is a list")
    
    # ASSERT: project_duration_days is a number
    if not isinstance(data.get("project_duration_days"), (int, float)):
        print(f"❌ FAILED: project_duration_days should be a number")
        return False
    
    print(f"✅ ASSERTION PASSED: project_duration_days is a number")
    
    # ASSERT: task_slack is a dict/object
    if not isinstance(data.get("task_slack"), dict):
        print(f"❌ FAILED: task_slack should be a dict")
        return False
    
    print(f"✅ ASSERTION PASSED: task_slack is a dict")
    
    # Test 7b: Critical path for project with no WBS tasks (Mobile App)
    print("\n--- Test 7b: Critical path for project with no WBS tasks ---")
    
    # Try Mobile App project (6ab25bc82be78e05e89230f4)
    empty_project_id = "6ab25bc82be78e05e89230f4"
    
    response = requests.get(
        f"{BACKEND_URL}/projects/{empty_project_id}/wbs/critical-path",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    print(f"GET /api/projects/{empty_project_id}/wbs/critical-path")
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {response.status_code}")
        print(f"Response: {response.text}")
        return False
    
    data_empty = response.json()
    
    print(f"✅ SUCCESS: Got critical path data for empty project")
    print(f"   critical_task_ids: {data_empty.get('critical_task_ids')}")
    print(f"   project_duration_days: {data_empty.get('project_duration_days')}")
    print(f"   task_slack: {data_empty.get('task_slack')}")
    
    # ASSERT: Empty project should return empty lists/dicts
    expected_empty = {
        "critical_task_ids": [],
        "project_duration_days": 0,
        "task_slack": {}
    }
    
    if data_empty.get("critical_task_ids") != expected_empty["critical_task_ids"]:
        print(f"❌ FAILED: Expected empty critical_task_ids")
        return False
    
    if data_empty.get("project_duration_days") != expected_empty["project_duration_days"]:
        print(f"❌ FAILED: Expected project_duration_days=0")
        return False
    
    if data_empty.get("task_slack") != expected_empty["task_slack"]:
        print(f"❌ FAILED: Expected empty task_slack")
        return False
    
    print(f"✅ ASSERTION PASSED: Empty project returns correct empty structure")
    
    return True


def cleanup_tasks(token):
    """Delete all created tasks."""
    print("\n" + "="*80)
    print("CLEANUP: Deleting created tasks")
    print("="*80)
    
    success_count = 0
    fail_count = 0
    
    for task_id in created_task_ids:
        response = requests.delete(
            f"{BACKEND_URL}/wbs/tasks/{task_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        print(f"DELETE /api/wbs/tasks/{task_id}")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"✅ Task {task_id} deleted")
            success_count += 1
        else:
            print(f"❌ Failed to delete task {task_id}")
            print(f"Response: {response.text}")
            fail_count += 1
    
    print(f"\nCleanup summary: {success_count} deleted, {fail_count} failed")
    return fail_count == 0


def main():
    """Run all tests."""
    print("="*80)
    print("WBS SCHEDULING BACKEND TESTS")
    print("="*80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Project ID: {PROJECT_ID}")
    print(f"Admin: {ADMIN_EMAIL}")
    
    # Login
    token = login()
    if not token:
        print("\n❌ FATAL: Login failed")
        return
    
    # Track test results
    results = {}
    
    # TEST 1: Regression
    results["test_1_regression"] = test_1_regression_wbs_list(token)
    
    # TEST 2: duration_days create
    test_2_result, dur_task_id = test_2_duration_days_create(token)
    results["test_2_duration_create"] = test_2_result
    
    # TEST 3: duration_days update
    results["test_3_duration_update"] = test_3_duration_days_update(token, dur_task_id)
    
    # TEST 4: SNET constraint
    results["test_4_snet"] = test_4_snet_constraint(token)
    
    # TEST 5: Deadline violations
    results["test_5_deadlines"] = test_5_deadline_violations(token)
    
    # TEST 6: dependency_links
    results["test_6_dep_links"] = test_6_dependency_links(token, dur_task_id)
    
    # TEST 7: Critical path
    results["test_7_critical_path"] = test_7_critical_path(token)
    
    # Cleanup
    cleanup_success = cleanup_tasks(token)
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print(f"Cleanup: {'✅ SUCCESS' if cleanup_success else '❌ FAILED'}")
    
    if passed == total and cleanup_success:
        print("\n🎉 ALL TESTS PASSED!")
    else:
        print("\n⚠️  SOME TESTS FAILED")


if __name__ == "__main__":
    main()
