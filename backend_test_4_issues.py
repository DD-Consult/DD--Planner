#!/usr/bin/env python3
"""
Backend API Testing for 4 Reported Issues (Re-run after /api/projects/create-full fix)
Test URL: https://enhance-feedback-2.preview.emergentagent.com
"""

import requests
import json
from datetime import datetime, timedelta
import time

# Configuration
BASE_URL = "https://enhance-feedback-2.preview.emergentagent.com/api"
TEST_USER = "admin@test.com"
TEST_PASSWORD = "admin123"

# Global token storage
token = None
test_results = {
    "issue_1": {"name": "Timesheet Pre-fill", "passed": False, "details": []},
    "issue_2": {"name": "New Projects with Allocations", "passed": False, "details": []},
    "issue_3": {"name": "WBS Percentage Updates", "passed": False, "details": []},
    "issue_6": {"name": "AI Multi-step Actions", "passed": False, "details": []},
}

def login():
    """Login and get JWT token"""
    global token
    print("\n" + "="*80)
    print("TEST: Login")
    print("="*80)
    
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={
            "username": TEST_USER,
            "password": TEST_PASSWORD
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        token = data.get("access_token")
        print(f"✅ Login successful. Token: {token[:20]}...")
        return True
    else:
        print(f"❌ Login failed: {response.text}")
        return False

def get_headers():
    """Get authorization headers"""
    return {"Authorization": f"Bearer {token}"}

# ============================================================================
# ISSUE 1: Timesheet Pre-fill
# ============================================================================

def test_issue_1_timesheet_prefill():
    """
    Issue 1: Timesheet pre-fill (/api/timesheets/auto-fill?week_start=2026-09-14)
    - Test that auto-fill succeeds and returns created/updated counts
    - Verify GET /api/timesheets/history returns entries with proper phase_name and project_name
    """
    print("\n" + "="*80)
    print("ISSUE 1: Timesheet Pre-fill")
    print("="*80)
    
    issue = test_results["issue_1"]
    
    # Test 1.1: Auto-fill timesheets for week 2026-09-14
    print("\n[Test 1.1] POST /api/timesheets/auto-fill?week_start=2026-09-14")
    response = requests.post(
        f"{BASE_URL}/timesheets/auto-fill?week_start=2026-09-14",
        headers=get_headers()
    )
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        print(f"✅ Auto-fill successful")
        print(f"   Created: {data.get('created', 0)}")
        print(f"   Updated: {data.get('updated', 0)}")
        print(f"   Skipped: {data.get('skipped', 0)}")
        print(f"   Total: {data.get('total', 0)}")
        issue["details"].append(f"✅ Auto-fill returned: created={data.get('created')}, updated={data.get('updated')}, total={data.get('total')}")
    else:
        print(f"❌ Auto-fill failed: {response.text}")
        issue["details"].append(f"❌ Auto-fill failed with status {response.status_code}: {response.text[:200]}")
        return False
    
    # Test 1.2: Verify GET /api/timesheets/history returns entries with proper phase_name and project_name
    print("\n[Test 1.2] GET /api/timesheets/history")
    response = requests.get(
        f"{BASE_URL}/timesheets/history?weeks=4",
        headers=get_headers()
    )
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        weeks = data.get("weeks", [])
        print(f"✅ History retrieved: {len(weeks)} weeks")
        
        # Check for entries with phase_name and project_name
        has_valid_entries = False
        blank_or_unknown_count = 0
        
        for week in weeks:
            for entry in week.get("entries", []):
                project_name = entry.get("project_name", "")
                phase_name = entry.get("phase_name", "")
                
                # Check if project_name or phase_name are blank or "Unknown"
                if not project_name or project_name in ["Unknown Project", "Unknown"]:
                    blank_or_unknown_count += 1
                    print(f"⚠️  Entry with blank/Unknown project_name: {entry.get('id')}")
                
                if project_name and project_name not in ["Unknown Project", "Unknown"]:
                    has_valid_entries = True
                    print(f"✅ Valid entry: project='{project_name}', phase='{phase_name}'")
                    break
            if has_valid_entries:
                break
        
        if has_valid_entries and blank_or_unknown_count == 0:
            print(f"✅ All timesheet entries have proper project_name and phase_name")
            issue["details"].append(f"✅ Timesheet history has valid project_name and phase_name fields")
            issue["passed"] = True
        elif has_valid_entries:
            print(f"⚠️  Some entries have valid names, but {blank_or_unknown_count} have blank/Unknown values")
            issue["details"].append(f"⚠️  {blank_or_unknown_count} entries have blank/Unknown project_name")
            issue["passed"] = False
        else:
            print(f"❌ No valid timesheet entries found with proper project_name")
            issue["details"].append(f"❌ No valid timesheet entries with proper project_name")
            issue["passed"] = False
    else:
        print(f"❌ History retrieval failed: {response.text}")
        issue["details"].append(f"❌ History retrieval failed with status {response.status_code}")
        return False
    
    return issue["passed"]


# ============================================================================
# ISSUE 2: New Projects with Allocations
# ============================================================================

def test_issue_2_create_project_full():
    """
    Issue 2: Test POST /api/projects/create-full and verify allocations
    - Create a new project with allocations
    - Verify GET /api/allocations returns allocations with proper project_name and client_name
    - Ensure project_name and client_name are NOT blank or "Unknown"
    """
    print("\n" + "="*80)
    print("ISSUE 2: New Projects with Allocations (create-full)")
    print("="*80)
    
    issue = test_results["issue_2"]
    
    # First, get a resource ID to allocate
    print("\n[Test 2.0] GET /api/resources to find a resource")
    response = requests.get(f"{BASE_URL}/resources", headers=get_headers())
    if response.status_code != 200:
        print(f"❌ Failed to get resources: {response.text}")
        issue["details"].append(f"❌ Failed to get resources")
        return False
    
    resources = response.json()
    if not resources:
        print(f"❌ No resources found")
        issue["details"].append(f"❌ No resources found")
        return False
    
    resource_id = resources[0]["id"]
    resource_name = resources[0]["name"]
    print(f"✅ Using resource: {resource_name} (ID: {resource_id})")
    
    # Test 2.1: Create project with allocations using create-full
    print("\n[Test 2.1] POST /api/projects/create-full")
    
    project_data = {
        "name": f"Test Project {datetime.now().strftime('%Y%m%d%H%M%S')}",
        "client_name": "Test Client Corp",
        "status": "Active",
        "budgeted_hours": 200,
        "phases": [
            {"name": "Planning", "duration_weeks": 2},
            {"name": "Execution", "duration_weeks": 4},
            {"name": "Closure", "duration_weeks": 1}
        ],
        "allocations": [
            {
                "resource_id": resource_id,
                "percentage": 50,
                "role": "Developer"
            }
        ]
    }
    
    response = requests.post(
        f"{BASE_URL}/projects/create-full",
        json=project_data,
        headers=get_headers()
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code in [200, 201]:
        data = response.json()
        project_id = data.get("project_id")
        print(f"✅ Project created successfully")
        print(f"   Project ID: {project_id}")
        print(f"   Phases created: {data.get('phases_created', 0)}")
        print(f"   Allocations created: {data.get('allocations_created', 0)}")
        issue["details"].append(f"✅ Project created: ID={project_id}, phases={data.get('phases_created')}, allocations={data.get('allocations_created')}")
    else:
        print(f"❌ Project creation failed: {response.text}")
        issue["details"].append(f"❌ Project creation failed with status {response.status_code}: {response.text[:200]}")
        return False
    
    # Test 2.2: Verify allocations have proper project_name and client_name
    print("\n[Test 2.2] GET /api/allocations to verify project_name and client_name")
    response = requests.get(f"{BASE_URL}/allocations", headers=get_headers())
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        allocations = response.json()
        print(f"✅ Retrieved {len(allocations)} allocations")
        
        # Find allocations for our newly created project
        project_allocations = [a for a in allocations if a.get("project_id") == project_id]
        
        if not project_allocations:
            print(f"❌ No allocations found for project {project_id}")
            issue["details"].append(f"❌ No allocations found for newly created project")
            return False
        
        print(f"✅ Found {len(project_allocations)} allocations for new project")
        
        # Check each allocation for proper project_name and client_name
        all_valid = True
        for alloc in project_allocations:
            project_name = alloc.get("project_name", "")
            client_name = alloc.get("client_name", "")
            
            print(f"\nAllocation ID: {alloc.get('id')}")
            print(f"  Resource: {alloc.get('resource_name')}")
            print(f"  Project Name: '{project_name}'")
            print(f"  Client Name: '{client_name}'")
            
            # Check if project_name is blank or "Unknown"
            if not project_name or project_name in ["Unknown", "Unknown Project"]:
                print(f"  ❌ project_name is blank or Unknown")
                issue["details"].append(f"❌ Allocation {alloc.get('id')} has blank/Unknown project_name")
                all_valid = False
            else:
                print(f"  ✅ project_name is valid")
            
            # Check if client_name is blank or "Unknown"
            if not client_name or client_name in ["Unknown", "Unknown Client"]:
                print(f"  ❌ client_name is blank or Unknown")
                issue["details"].append(f"❌ Allocation {alloc.get('id')} has blank/Unknown client_name")
                all_valid = False
            else:
                print(f"  ✅ client_name is valid")
        
        if all_valid:
            print(f"\n✅ All allocations have proper project_name and client_name")
            issue["details"].append(f"✅ All {len(project_allocations)} allocations have valid project_name and client_name")
            issue["passed"] = True
        else:
            print(f"\n❌ Some allocations have blank or Unknown values")
            issue["passed"] = False
    else:
        print(f"❌ Failed to get allocations: {response.text}")
        issue["details"].append(f"❌ Failed to get allocations with status {response.status_code}")
        return False
    
    return issue["passed"]


# ============================================================================
# ISSUE 3: WBS Percentage Updates
# ============================================================================

def test_issue_3_wbs_percentage():
    """
    Issue 3: WBS percentage updates
    - Create a WBS task with progress_percentage
    - Update progress_percentage to 100
    - Verify status is automatically set to "done"
    """
    print("\n" + "="*80)
    print("ISSUE 3: WBS Percentage Updates")
    print("="*80)
    
    issue = test_results["issue_3"]
    
    # First, get a project to create WBS task in
    print("\n[Test 3.0] GET /api/projects to find a project")
    response = requests.get(f"{BASE_URL}/projects", headers=get_headers())
    if response.status_code != 200:
        print(f"❌ Failed to get projects: {response.text}")
        issue["details"].append(f"❌ Failed to get projects")
        return False
    
    projects = response.json()
    if not projects:
        print(f"❌ No projects found")
        issue["details"].append(f"❌ No projects found")
        return False
    
    project_id = projects[0]["id"]
    project_name = projects[0]["name"]
    print(f"✅ Using project: {project_name} (ID: {project_id})")
    
    # Test 3.1: Create a WBS task
    print("\n[Test 3.1] POST /api/projects/{project_id}/wbs/tasks")
    
    task_data = {
        "name": f"Test Task {datetime.now().strftime('%H%M%S')}",
        "description": "Test task for progress percentage",
        "status": "in_progress",
        "priority": "medium",
        "estimated_hours": 10,
        "progress_percentage": 50
    }
    
    response = requests.post(
        f"{BASE_URL}/projects/{project_id}/wbs/tasks",
        json=task_data,
        headers=get_headers()
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code in [200, 201]:
        task = response.json()
        task_id = task.get("id")
        print(f"✅ Task created successfully")
        print(f"   Task ID: {task_id}")
        print(f"   Initial progress: {task.get('progress_percentage')}%")
        print(f"   Initial status: {task.get('status')}")
        issue["details"].append(f"✅ Task created: ID={task_id}, progress={task.get('progress_percentage')}%, status={task.get('status')}")
    else:
        print(f"❌ Task creation failed: {response.text}")
        issue["details"].append(f"❌ Task creation failed with status {response.status_code}: {response.text[:200]}")
        return False
    
    # Test 3.2: Update progress_percentage to 100
    print("\n[Test 3.2] PUT /api/wbs/tasks/{task_id} with progress_percentage=100")
    
    update_data = {
        "progress_percentage": 100
    }
    
    response = requests.put(
        f"{BASE_URL}/wbs/tasks/{task_id}",
        json=update_data,
        headers=get_headers()
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        updated_task = response.json()
        progress = updated_task.get("progress_percentage")
        status = updated_task.get("status")
        
        print(f"✅ Task updated successfully")
        print(f"   Progress: {progress}%")
        print(f"   Status: {status}")
        
        # Verify status is "done"
        if status == "done":
            print(f"✅ Status automatically set to 'done' when progress=100")
            issue["details"].append(f"✅ Status automatically set to 'done' when progress_percentage=100")
            issue["passed"] = True
        else:
            print(f"❌ Status is '{status}', expected 'done'")
            issue["details"].append(f"❌ Status is '{status}' instead of 'done' when progress_percentage=100")
            issue["passed"] = False
    else:
        print(f"❌ Task update failed: {response.text}")
        issue["details"].append(f"❌ Task update failed with status {response.status_code}: {response.text[:200]}")
        return False
    
    # Test 3.3: Verify setting status to "done" also sets progress to 100
    print("\n[Test 3.3] Create another task and set status to 'done'")
    
    task_data2 = {
        "name": f"Test Task 2 {datetime.now().strftime('%H%M%S')}",
        "description": "Test task for status update",
        "status": "in_progress",
        "priority": "medium",
        "estimated_hours": 10,
        "progress_percentage": 50
    }
    
    response = requests.post(
        f"{BASE_URL}/projects/{project_id}/wbs/tasks",
        json=task_data2,
        headers=get_headers()
    )
    
    if response.status_code in [200, 201]:
        task2 = response.json()
        task2_id = task2.get("id")
        print(f"✅ Task 2 created: ID={task2_id}, progress={task2.get('progress_percentage')}%")
        
        # Update status to "done"
        update_data2 = {"status": "done"}
        response = requests.put(
            f"{BASE_URL}/wbs/tasks/{task2_id}",
            json=update_data2,
            headers=get_headers()
        )
        
        if response.status_code == 200:
            updated_task2 = response.json()
            progress2 = updated_task2.get("progress_percentage")
            status2 = updated_task2.get("status")
            
            print(f"✅ Task 2 updated: progress={progress2}%, status={status2}")
            
            if progress2 == 100:
                print(f"✅ Progress automatically set to 100 when status='done'")
                issue["details"].append(f"✅ Progress automatically set to 100 when status='done'")
            else:
                print(f"⚠️  Progress is {progress2}%, expected 100")
                issue["details"].append(f"⚠️  Progress is {progress2}% instead of 100 when status='done'")
    
    return issue["passed"]


# ============================================================================
# ISSUE 6: AI Multi-step Actions
# ============================================================================

def test_issue_6_ai_multistep():
    """
    Issue 6: AI multi-step actions with placeholder resolution
    - POST /api/ai/chat/execute-plan with a multi-step plan
    - Plan contains create_project and create_allocation with <step_0_id> placeholder
    - Verify both steps succeed and placeholder is resolved
    """
    print("\n" + "="*80)
    print("ISSUE 6: AI Multi-step Actions with Placeholder Resolution")
    print("="*80)
    
    issue = test_results["issue_6"]
    
    # First, get a resource ID for allocation
    print("\n[Test 6.0] GET /api/resources to find a resource")
    response = requests.get(f"{BASE_URL}/resources", headers=get_headers())
    if response.status_code != 200:
        print(f"❌ Failed to get resources: {response.text}")
        issue["details"].append(f"❌ Failed to get resources")
        return False
    
    resources = response.json()
    if not resources:
        print(f"❌ No resources found")
        issue["details"].append(f"❌ No resources found")
        return False
    
    resource_id = resources[0]["id"]
    resource_name = resources[0]["name"]
    print(f"✅ Using resource: {resource_name} (ID: {resource_id})")
    
    # Test 6.1: Execute multi-step plan with placeholder
    print("\n[Test 6.1] POST /api/ai/chat/execute-plan with multi-step plan")
    
    plan = {
        "steps": [
            {
                "step_id": "step_0",
                "action": "create_project",
                "params": {
                    "name": f"AI Test Project {datetime.now().strftime('%Y%m%d%H%M%S')}",
                    "client_name": "AI Test Client",
                    "status": "Active",
                    "budgeted_hours": 150,
                    "phases": [
                        {"name": "Phase 1", "duration_weeks": 2}
                    ]
                }
            },
            {
                "step_id": "step_1",
                "action": "create_allocation",
                "params": {
                    "project_id": "<step_0_id>",
                    "resource_id": resource_id,
                    "percentage": 60,
                    "role": "Developer"
                }
            }
        ]
    }
    
    response = requests.post(
        f"{BASE_URL}/ai/chat/execute-plan",
        json=plan,
        headers=get_headers()
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        
        # Check if both steps succeeded
        steps_results = result.get("steps", [])
        
        if len(steps_results) >= 2:
            step_0 = steps_results[0]
            step_1 = steps_results[1]
            
            print(f"\nStep 0 (create_project):")
            print(f"  Status: {step_0.get('status')}")
            print(f"  Result: {step_0.get('result', {})}")
            
            print(f"\nStep 1 (create_allocation):")
            print(f"  Status: {step_1.get('status')}")
            print(f"  Result: {step_1.get('result', {})}")
            
            # Verify both steps succeeded
            if step_0.get("status") == "success" and step_1.get("status") == "success":
                print(f"\n✅ Both steps succeeded")
                
                # Verify placeholder was resolved
                project_id = step_0.get("result", {}).get("project_id")
                allocation_project_id = step_1.get("result", {}).get("project_id")
                
                if project_id and allocation_project_id == project_id:
                    print(f"✅ Placeholder <step_0_id> was correctly resolved to {project_id}")
                    issue["details"].append(f"✅ Multi-step plan executed: project created (ID={project_id}), allocation created with resolved placeholder")
                    issue["passed"] = True
                else:
                    print(f"❌ Placeholder resolution failed: project_id={project_id}, allocation_project_id={allocation_project_id}")
                    issue["details"].append(f"❌ Placeholder <step_0_id> was not correctly resolved")
                    issue["passed"] = False
            else:
                print(f"❌ One or both steps failed")
                issue["details"].append(f"❌ Step 0 status: {step_0.get('status')}, Step 1 status: {step_1.get('status')}")
                issue["passed"] = False
        else:
            print(f"❌ Expected 2 steps in result, got {len(steps_results)}")
            issue["details"].append(f"❌ Expected 2 steps in result, got {len(steps_results)}")
            issue["passed"] = False
    else:
        print(f"❌ Execute plan failed: {response.text}")
        issue["details"].append(f"❌ Execute plan failed with status {response.status_code}: {response.text[:200]}")
        return False
    
    return issue["passed"]


# ============================================================================
# Main Test Runner
# ============================================================================

def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    total_tests = len(test_results)
    passed_tests = sum(1 for issue in test_results.values() if issue["passed"])
    
    for issue_key, issue in test_results.items():
        status = "✅ PASSED" if issue["passed"] else "❌ FAILED"
        print(f"\n{issue_key.upper()}: {issue['name']} - {status}")
        for detail in issue["details"]:
            print(f"  {detail}")
    
    print(f"\n{'='*80}")
    print(f"OVERALL: {passed_tests}/{total_tests} tests passed")
    print(f"{'='*80}\n")
    
    return passed_tests == total_tests


def main():
    """Main test execution"""
    print("="*80)
    print("Backend API Testing - 4 Issues Re-run")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"Test User: {TEST_USER}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Login
    if not login():
        print("\n❌ Login failed. Cannot proceed with tests.")
        return False
    
    # Run all tests
    try:
        test_issue_1_timesheet_prefill()
        time.sleep(1)  # Brief pause between tests
        
        test_issue_2_create_project_full()
        time.sleep(1)
        
        test_issue_3_wbs_percentage()
        time.sleep(1)
        
        test_issue_6_ai_multistep()
        
    except Exception as e:
        print(f"\n❌ Test execution error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Print summary
    all_passed = print_summary()
    
    return all_passed


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
