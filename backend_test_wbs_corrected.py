#!/usr/bin/env python3
"""
UPDATED Backend test for NEW WBS scheduling capabilities.
This version:
1. Verifies deadline_violated flag via GET (not CREATE response)
2. Uses correct day of week for 2027-03-02 (Tuesday, not Monday)
3. Tests with actual Monday (2027-03-01) for duration_days verification
"""

import requests
import json
from datetime import datetime

BACKEND_URL = "https://ddplanner-fixes.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"
PROJECT_ID = "6ab25bc82be78e05e89230f3"

created_task_ids = []

def login():
    """Login and get JWT token."""
    print("\n" + "="*80)
    print("AUTHENTICATION")
    print("="*80)
    
    response = requests.post(
        f"{BACKEND_URL}/auth/login",
        data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    print(f"POST /api/auth/login")
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"ERROR: Login failed")
        return None
    
    token = response.json()["access_token"]
    print(f"✅ Login successful")
    return token


def get_task_from_list(token, task_id):
    """Fetch task from WBS list to get computed flags."""
    response = requests.get(
        f"{BACKEND_URL}/projects/{PROJECT_ID}/wbs",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code != 200:
        return None
    
    tasks = response.json()
    return next((t for t in tasks if t.get("id") == task_id), None)


def test_2_duration_days_create_corrected(token):
    """TEST 2: duration_days auto-computes end_date (CORRECTED)."""
    print("\n" + "="*80)
    print("TEST 2: duration_days auto-computes end_date (CORRECTED)")
    print("="*80)
    
    # NOTE: 2027-03-02 is TUESDAY, not Monday as stated in review request
    # Let's test with actual Monday: 2027-03-01
    
    print("\n--- Test 2a: duration_days=5 from Monday 2027-03-01 ---")
    
    task_data = {
        "name": "QA Duration Task Monday",
        "start_date": "2027-03-01",  # Monday
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
        return False, None
    
    task = response.json()
    task_id = task.get("id")
    created_task_ids.append(task_id)
    
    start_date = datetime.strptime(task.get("start_date")[:10], "%Y-%m-%d")
    end_date = datetime.strptime(task.get("end_date")[:10], "%Y-%m-%d")
    
    print(f"✅ Task created with ID: {task_id}")
    print(f"   Start date: {task.get('start_date')[:10]} ({start_date.strftime('%A')})")
    print(f"   End date: {task.get('end_date')[:10]} ({end_date.strftime('%A')})")
    print(f"   Duration days: {task.get('duration_days')}")
    
    # ASSERT: end_date should be 2027-03-05 (Mon+5 business days = Mon-Fri → Friday)
    expected_end = "2027-03-05"
    actual_end = task.get("end_date", "")[:10]
    
    if actual_end != expected_end:
        print(f"❌ FAILED: Expected end_date={expected_end}, got {actual_end}")
        return False, task_id
    
    print(f"✅ ASSERTION PASSED: end_date={actual_end} (Mon+5 biz days = Fri)")
    
    # Test 2b: Original test with Tuesday (2027-03-02)
    print("\n--- Test 2b: duration_days=5 from Tuesday 2027-03-02 (as in review request) ---")
    
    task_data_tue = {
        "name": "QA Duration Task Tuesday",
        "start_date": "2027-03-02",  # Tuesday
        "duration_days": 5
    }
    
    response = requests.post(
        f"{BACKEND_URL}/projects/{PROJECT_ID}/wbs/tasks",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json=task_data_tue
    )
    
    print(f"POST /api/projects/{PROJECT_ID}/wbs/tasks")
    print(f"Payload: {json.dumps(task_data_tue, indent=2)}")
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {response.status_code}")
        return False, task_id
    
    task_tue = response.json()
    task_tue_id = task_tue.get("id")
    created_task_ids.append(task_tue_id)
    
    start_date_tue = datetime.strptime(task_tue.get("start_date")[:10], "%Y-%m-%d")
    end_date_tue = datetime.strptime(task_tue.get("end_date")[:10], "%Y-%m-%d")
    
    print(f"✅ Task created with ID: {task_tue_id}")
    print(f"   Start date: {task_tue.get('start_date')[:10]} ({start_date_tue.strftime('%A')})")
    print(f"   End date: {task_tue.get('end_date')[:10]} ({end_date_tue.strftime('%A')})")
    print(f"   Duration days: {task_tue.get('duration_days')}")
    
    # For Tuesday + 5 business days, we expect Monday next week
    expected_end_tue = "2027-03-08"
    actual_end_tue = task_tue.get("end_date", "")[:10]
    
    if actual_end_tue != expected_end_tue:
        print(f"❌ FAILED: Expected end_date={expected_end_tue}, got {actual_end_tue}")
        return False, task_id
    
    print(f"✅ ASSERTION PASSED: end_date={actual_end_tue} (Tue+5 biz days = Mon next week)")
    print(f"   NOTE: Review request incorrectly stated 2027-03-02 is Monday (it's Tuesday)")
    
    # Test 2c: Explicit end_date precedence
    print("\n--- Test 2c: Explicit end_date precedence ---")
    
    task_data_explicit = {
        "name": "QA Dur Explicit",
        "start_date": "2027-03-01",
        "duration_days": 5,
        "end_date": "2027-03-10"
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
        return False, task_id
    
    task_explicit = response.json()
    task_explicit_id = task_explicit.get("id")
    created_task_ids.append(task_explicit_id)
    
    print(f"✅ Task created with ID: {task_explicit_id}")
    print(f"   End date: {task_explicit.get('end_date')[:10]}")
    
    expected_end_explicit = "2027-03-10"
    actual_end_explicit = task_explicit.get("end_date", "")[:10]
    
    if actual_end_explicit != expected_end_explicit:
        print(f"❌ FAILED: Expected end_date={expected_end_explicit}, got {actual_end_explicit}")
        return False, task_id
    
    print(f"✅ ASSERTION PASSED: end_date={actual_end_explicit} (explicit wins)")
    
    return True, task_id


def test_5_deadline_violations_corrected(token):
    """TEST 5: FNLT / deadline violation flags (CORRECTED - check via GET)."""
    print("\n" + "="*80)
    print("TEST 5: FNLT / deadline violation flags (CORRECTED)")
    print("="*80)
    
    # Test 5a: Deadline violation
    print("\n--- Test 5a: Deadline violation ---")
    
    task_data_deadline = {
        "name": "QA Deadline",
        "start_date": "2027-03-01",
        "end_date": "2027-03-20",
        "deadline": "2027-03-10"
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
        return False
    
    task_deadline = response.json()
    task_deadline_id = task_deadline.get("id")
    created_task_ids.append(task_deadline_id)
    
    print(f"✅ Task created with ID: {task_deadline_id}")
    print(f"   CREATE response deadline_violated: {task_deadline.get('deadline_violated')}")
    
    # Fetch via GET to get computed flags
    task_from_get = get_task_from_list(token, task_deadline_id)
    
    if not task_from_get:
        print(f"❌ FAILED: Could not fetch task from GET endpoint")
        return False
    
    print(f"   GET response deadline_violated: {task_from_get.get('deadline_violated')}")
    
    # ASSERT: deadline_violated should be true in GET response
    if not task_from_get.get("deadline_violated"):
        print(f"❌ FAILED: deadline_violated should be true in GET response")
        return False
    
    print(f"✅ ASSERTION PASSED: deadline_violated=true in GET response")
    print(f"   NOTE: Computed flags are calculated in GET endpoint, not CREATE response")
    
    # Test 5b: FNLT constraint violation
    print("\n--- Test 5b: FNLT constraint violation ---")
    
    task_data_fnlt = {
        "name": "QA FNLT",
        "start_date": "2027-03-01",
        "end_date": "2027-03-20",
        "constraint_type": "FNLT",
        "constraint_date": "2027-03-10"
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
        return False
    
    task_fnlt = response.json()
    task_fnlt_id = task_fnlt.get("id")
    created_task_ids.append(task_fnlt_id)
    
    print(f"✅ Task created with ID: {task_fnlt_id}")
    
    # Fetch via GET
    task_fnlt_from_get = get_task_from_list(token, task_fnlt_id)
    
    if not task_fnlt_from_get:
        print(f"❌ FAILED: Could not fetch task from GET endpoint")
        return False
    
    print(f"   GET response constraint_violated: {task_fnlt_from_get.get('constraint_violated')}")
    
    # ASSERT: constraint_violated should be true
    if not task_fnlt_from_get.get("constraint_violated"):
        print(f"❌ FAILED: constraint_violated should be true in GET response")
        return False
    
    print(f"✅ ASSERTION PASSED: constraint_violated=true in GET response")
    
    # Test 5c: Compliant deadline
    print("\n--- Test 5c: Compliant deadline (no violation) ---")
    
    task_data_ontime = {
        "name": "QA OnTime",
        "start_date": "2027-03-01",
        "end_date": "2027-03-05",
        "deadline": "2027-03-10"
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
        return False
    
    task_ontime = response.json()
    task_ontime_id = task_ontime.get("id")
    created_task_ids.append(task_ontime_id)
    
    print(f"✅ Task created with ID: {task_ontime_id}")
    
    # Fetch via GET
    task_ontime_from_get = get_task_from_list(token, task_ontime_id)
    
    if not task_ontime_from_get:
        print(f"❌ FAILED: Could not fetch task from GET endpoint")
        return False
    
    print(f"   GET response deadline_violated: {task_ontime_from_get.get('deadline_violated')}")
    
    # ASSERT: deadline_violated should be false
    if task_ontime_from_get.get("deadline_violated"):
        print(f"❌ FAILED: deadline_violated should be false in GET response")
        return False
    
    print(f"✅ ASSERTION PASSED: deadline_violated=false in GET response")
    
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
        
        if response.status_code == 200:
            print(f"✅ Task {task_id} deleted")
            success_count += 1
        else:
            print(f"❌ Failed to delete task {task_id}")
            fail_count += 1
    
    print(f"\nCleanup summary: {success_count} deleted, {fail_count} failed")
    return fail_count == 0


def main():
    """Run corrected tests."""
    print("="*80)
    print("WBS SCHEDULING BACKEND TESTS (CORRECTED)")
    print("="*80)
    
    token = login()
    if not token:
        print("\n❌ FATAL: Login failed")
        return
    
    results = {}
    
    # TEST 2: duration_days (corrected)
    test_2_result, dur_task_id = test_2_duration_days_create_corrected(token)
    results["test_2_duration_corrected"] = test_2_result
    
    # TEST 5: Deadline violations (corrected)
    results["test_5_deadlines_corrected"] = test_5_deadline_violations_corrected(token)
    
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


if __name__ == "__main__":
    main()
