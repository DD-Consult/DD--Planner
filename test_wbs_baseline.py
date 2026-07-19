#!/usr/bin/env python3
"""
WBS Baseline Feature Testing
DD Planner - Test new WBS baseline endpoints
"""

import requests
import json
from datetime import datetime, timedelta

# Configuration
BASE_URL = "http://localhost:8001"
API_BASE = f"{BASE_URL}/api"

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

# Test results tracking
test_results = []
total_tests = 0
passed_tests = 0
failed_tests = 0


def log_test(test_name, passed, status_code=None, reason="", response_data=None):
    """Log test result"""
    global total_tests, passed_tests, failed_tests
    total_tests += 1
    if passed:
        passed_tests += 1
        result = "✅ PASS"
    else:
        failed_tests += 1
        result = "❌ FAIL"
    
    status_info = f" (Status: {status_code})" if status_code else ""
    test_results.append({
        "test": test_name,
        "result": result,
        "status_code": status_code,
        "reason": reason,
        "response_data": response_data
    })
    print(f"{result}: {test_name}{status_info}")
    if reason:
        print(f"   {reason}")


def login(email, password):
    """Login and return JWT token"""
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
            print(f"❌ Login failed for {email}: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Login exception for {email}: {str(e)}")
        return None


def get_headers(token):
    """Get authorization headers"""
    return {"Authorization": f"Bearer {token}"}


def find_project_with_wbs_tasks(token):
    """Find a project that has WBS tasks"""
    try:
        # Get all projects
        response = requests.get(f"{API_BASE}/projects", headers=get_headers(token))
        if response.status_code != 200:
            return None, None
        
        projects = response.json()
        if not projects:
            return None, None
        
        # Check each project for WBS tasks
        for project in projects:
            project_id = project["id"]
            wbs_response = requests.get(
                f"{API_BASE}/projects/{project_id}/wbs",
                headers=get_headers(token)
            )
            
            if wbs_response.status_code == 200:
                tasks = wbs_response.json()
                if tasks and len(tasks) > 0:
                    print(f"✅ Found project '{project['name']}' with {len(tasks)} WBS task(s)")
                    return project_id, tasks[0]["id"]
        
        # No project with tasks found
        return projects[0]["id"] if projects else None, None
        
    except Exception as e:
        print(f"Error finding project with WBS: {str(e)}")
        return None, None


def create_test_wbs_task(token, project_id):
    """Create a test WBS task for baseline testing"""
    try:
        task_data = {
            "name": "Baseline Test Task",
            "description": "Task created for baseline testing",
            "start_date": "2026-06-01",
            "end_date": "2026-06-10",
            "estimated_hours": 10,
            "status": "todo",
            "priority": "medium"
        }
        
        response = requests.post(
            f"{API_BASE}/projects/{project_id}/wbs/tasks",
            json=task_data,
            headers=get_headers(token)
        )
        
        if response.status_code == 200:
            task = response.json()
            print(f"✅ Created test task: {task['name']} (ID: {task['id']})")
            return task["id"]
        else:
            print(f"❌ Failed to create test task: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Exception creating test task: {str(e)}")
        return None


def test_wbs_baseline_feature(token):
    """Test the complete WBS baseline feature"""
    print("\n" + "="*80)
    print("WBS BASELINE FEATURE TESTING")
    print("="*80)
    
    # Step 1: Find or create a project with WBS tasks
    print("\n📋 Step 1: Finding project with WBS tasks...")
    project_id, task_id = find_project_with_wbs_tasks(token)
    
    if not project_id:
        log_test("Step 1 - Find project", False, None, "No projects available")
        return
    
    # If no task found, create one
    if not task_id:
        print("   No WBS tasks found. Creating test task...")
        task_id = create_test_wbs_task(token, project_id)
        if not task_id:
            log_test("Step 1 - Create test task", False, None, "Failed to create test task")
            return
    
    log_test("Step 1 - Find/Create WBS task", True, None, 
             f"Using project_id={project_id}, task_id={task_id}")
    
    # Step 2: Get initial task state
    print("\n📋 Step 2: Getting initial task state...")
    try:
        response = requests.get(
            f"{API_BASE}/projects/{project_id}/wbs",
            headers=get_headers(token)
        )
        
        if response.status_code != 200:
            log_test("Step 2 - Get WBS tasks", False, response.status_code, 
                    f"Failed to get WBS tasks: {response.text[:200]}")
            return
        
        tasks = response.json()
        task = next((t for t in tasks if t["id"] == task_id), None)
        
        if not task:
            log_test("Step 2 - Find task in WBS", False, 200, 
                    f"Task {task_id} not found in WBS list")
            return
        
        initial_start = task.get("start_date")
        initial_end = task.get("end_date")
        initial_baseline_start = task.get("baseline_start_date")
        initial_baseline_end = task.get("baseline_end_date")
        
        log_test("Step 2 - Get initial task state", True, 200,
                f"start_date={initial_start}, end_date={initial_end}, "
                f"baseline_start_date={initial_baseline_start}, baseline_end_date={initial_baseline_end}")
        
    except Exception as e:
        log_test("Step 2 - Get initial task state", False, None, str(e))
        return
    
    # Step 3: Set baseline for the task
    print("\n📋 Step 3: Setting baseline for task...")
    try:
        response = requests.post(
            f"{API_BASE}/wbs/tasks/{task_id}/set-baseline",
            headers=get_headers(token)
        )
        
        if response.status_code != 200:
            log_test("Step 3 - Set task baseline", False, response.status_code,
                    f"Failed to set baseline: {response.text[:200]}")
            return
        
        updated_task = response.json()
        baseline_start = updated_task.get("baseline_start_date")
        baseline_end = updated_task.get("baseline_end_date")
        current_start = updated_task.get("start_date")
        current_end = updated_task.get("end_date")
        
        # Verify baseline was set correctly
        if baseline_start == current_start and baseline_end == current_end:
            log_test("Step 3 - Set task baseline", True, 200,
                    f"✓ baseline_start_date={baseline_start} (matches start_date), "
                    f"baseline_end_date={baseline_end} (matches end_date)")
        else:
            log_test("Step 3 - Set task baseline", False, 200,
                    f"Baseline mismatch: baseline_start={baseline_start} vs start={current_start}, "
                    f"baseline_end={baseline_end} vs end={current_end}")
            return
        
    except Exception as e:
        log_test("Step 3 - Set task baseline", False, None, str(e))
        return
    
    # Step 4: Update task end_date
    print("\n📋 Step 4: Updating task end_date (baseline should NOT change)...")
    try:
        new_end_date = "2026-06-20"
        response = requests.put(
            f"{API_BASE}/wbs/tasks/{task_id}",
            json={"end_date": new_end_date},
            headers=get_headers(token)
        )
        
        if response.status_code != 200:
            log_test("Step 4 - Update task end_date", False, response.status_code,
                    f"Failed to update task: {response.text[:200]}")
            return
        
        updated_task = response.json()
        new_current_end = updated_task.get("end_date")
        preserved_baseline_end = updated_task.get("baseline_end_date")
        
        log_test("Step 4 - Update task end_date", True, 200,
                f"Updated end_date to {new_current_end}")
        
    except Exception as e:
        log_test("Step 4 - Update task end_date", False, None, str(e))
        return
    
    # Step 5: Verify baseline preservation
    print("\n📋 Step 5: Verifying baseline preservation...")
    try:
        response = requests.get(
            f"{API_BASE}/projects/{project_id}/wbs",
            headers=get_headers(token)
        )
        
        if response.status_code != 200:
            log_test("Step 5 - Get updated WBS", False, response.status_code,
                    f"Failed to get WBS: {response.text[:200]}")
            return
        
        tasks = response.json()
        task = next((t for t in tasks if t["id"] == task_id), None)
        
        if not task:
            log_test("Step 5 - Find updated task", False, 200,
                    f"Task {task_id} not found")
            return
        
        final_end = task.get("end_date")
        final_baseline_end = task.get("baseline_end_date")
        
        # Verify: end_date changed but baseline_end_date stayed the same
        if final_end == "2026-06-20" and final_baseline_end == baseline_end:
            log_test("Step 5 - Verify baseline preservation", True, 200,
                    f"✓ end_date={final_end} (updated), "
                    f"baseline_end_date={final_baseline_end} (preserved from original {baseline_end})")
        else:
            log_test("Step 5 - Verify baseline preservation", False, 200,
                    f"❌ Baseline NOT preserved: end_date={final_end}, "
                    f"baseline_end_date={final_baseline_end} (expected {baseline_end})")
            return
        
    except Exception as e:
        log_test("Step 5 - Verify baseline preservation", False, None, str(e))
        return
    
    # Step 6: Re-baseline the task
    print("\n📋 Step 6: Re-baselining task (baseline should update to new dates)...")
    try:
        response = requests.post(
            f"{API_BASE}/wbs/tasks/{task_id}/set-baseline",
            headers=get_headers(token)
        )
        
        if response.status_code != 200:
            log_test("Step 6 - Re-baseline task", False, response.status_code,
                    f"Failed to re-baseline: {response.text[:200]}")
            return
        
        rebaselined_task = response.json()
        new_baseline_end = rebaselined_task.get("baseline_end_date")
        current_end = rebaselined_task.get("end_date")
        
        # Verify baseline updated to new end_date
        if new_baseline_end == "2026-06-20" and new_baseline_end == current_end:
            log_test("Step 6 - Re-baseline task", True, 200,
                    f"✓ baseline_end_date updated to {new_baseline_end} (matches new end_date)")
        else:
            log_test("Step 6 - Re-baseline task", False, 200,
                    f"Re-baseline failed: baseline_end={new_baseline_end}, end={current_end}")
            return
        
    except Exception as e:
        log_test("Step 6 - Re-baseline task", False, None, str(e))
        return
    
    # Step 7: Test bulk baseline (set baseline for all tasks in project)
    print("\n📋 Step 7: Testing bulk baseline (all tasks in project)...")
    try:
        response = requests.post(
            f"{API_BASE}/projects/{project_id}/wbs/set-baseline",
            headers=get_headers(token)
        )
        
        if response.status_code != 200:
            log_test("Step 7 - Bulk baseline", False, response.status_code,
                    f"Failed to set bulk baseline: {response.text[:200]}")
            return
        
        result = response.json()
        tasks_baselined = result.get("tasks_baselined", 0)
        
        if tasks_baselined >= 1:
            log_test("Step 7 - Bulk baseline", True, 200,
                    f"✓ Successfully baselined {tasks_baselined} task(s)")
        else:
            log_test("Step 7 - Bulk baseline", False, 200,
                    f"Expected tasks_baselined >= 1, got {tasks_baselined}")
            return
        
    except Exception as e:
        log_test("Step 7 - Bulk baseline", False, None, str(e))
        return
    
    # Step 8: Verify all tasks have baseline set
    print("\n📋 Step 8: Verifying all tasks have baseline dates...")
    try:
        response = requests.get(
            f"{API_BASE}/projects/{project_id}/wbs",
            headers=get_headers(token)
        )
        
        if response.status_code != 200:
            log_test("Step 8 - Verify bulk baseline", False, response.status_code,
                    f"Failed to get WBS: {response.text[:200]}")
            return
        
        tasks = response.json()
        tasks_with_baseline = [t for t in tasks 
                              if t.get("baseline_start_date") and t.get("baseline_end_date")]
        
        if len(tasks_with_baseline) == len(tasks) and len(tasks) > 0:
            log_test("Step 8 - Verify bulk baseline", True, 200,
                    f"✓ All {len(tasks)} task(s) have baseline dates set")
        else:
            log_test("Step 8 - Verify bulk baseline", False, 200,
                    f"Only {len(tasks_with_baseline)}/{len(tasks)} tasks have baseline dates")
            return
        
    except Exception as e:
        log_test("Step 8 - Verify bulk baseline", False, None, str(e))
        return
    
    # Step 9: Test auth check (without token)
    print("\n📋 Step 9: Testing auth check (should return 401/403 without token)...")
    try:
        response = requests.post(
            f"{API_BASE}/projects/{project_id}/wbs/set-baseline"
        )
        
        if response.status_code in [401, 403]:
            log_test("Step 9 - Auth check (no token)", True, response.status_code,
                    f"✓ Correctly returned {response.status_code} (unauthorized)")
        else:
            log_test("Step 9 - Auth check (no token)", False, response.status_code,
                    f"Expected 401/403, got {response.status_code}")
        
    except Exception as e:
        log_test("Step 9 - Auth check (no token)", False, None, str(e))


def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests} ✅")
    print(f"Failed: {failed_tests} ❌")
    
    if total_tests > 0:
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
    
    if failed_tests > 0:
        print("\n" + "="*80)
        print("FAILED TESTS DETAILS")
        print("="*80)
        for result in test_results:
            if "❌" in result["result"]:
                print(f"\n{result['test']}")
                print(f"  Status Code: {result['status_code']}")
                print(f"  Reason: {result['reason']}")


def main():
    """Main test execution"""
    print("="*80)
    print("DD PLANNER - WBS BASELINE FEATURE TESTING")
    print("="*80)
    
    # Login
    print("\n🔐 Logging in as admin...")
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    
    if not admin_token:
        print("❌ CRITICAL: Admin login failed. Cannot proceed with tests.")
        return 1
    
    print("✅ Login successful")
    
    # Run baseline tests
    test_wbs_baseline_feature(admin_token)
    
    # Print summary
    print_summary()
    
    # Return exit code based on results
    return 0 if failed_tests == 0 else 1


if __name__ == "__main__":
    exit(main())
