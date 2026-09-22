#!/usr/bin/env python3
"""
Backend API Testing for 6 Reported Issues
Test URL: https://base-product-check.preview.emergentagent.com
"""

import requests
import json
from datetime import datetime, timedelta

# Configuration
BASE_URL = "https://base-product-check.preview.emergentagent.com/api"
TEST_USER = "admin@test.com"
TEST_PASSWORD = "admin123"
RESOURCE_ID = "6aabd45b6023b8429321ad67"  # Alice Johnson

# Global token storage
token = None

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
    - Test with user admin@test.com / admin123 (linked to Alice Johnson resource_id 6aabd45b6023b8429321ad67)
    - Verify that POST /api/timesheets/auto-fill succeeds and returns created/updated counts without crashing.
    - Verify that projects without phases or with phases are handled cleanly.
    - Verify GET /api/timesheets/history returns entries with proper phase_name and project_name.
    """
    print("\n" + "="*80)
    print("ISSUE 1: Timesheet Pre-fill")
    print("="*80)
    
    # Test 1.1: Auto-fill timesheets for week 2026-09-14
    print("\n[Test 1.1] POST /api/timesheets/auto-fill?week_start=2026-09-14")
    response = requests.post(
        f"{BASE_URL}/timesheets/auto-fill?week_start=2026-09-14",
        headers=get_headers()
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Auto-fill successful")
        print(f"   Created: {data.get('created', 0)}")
        print(f"   Updated: {data.get('updated', 0)}")
        print(f"   Skipped: {data.get('skipped', 0)}")
        print(f"   Total: {data.get('total', 0)}")
    else:
        print(f"❌ Auto-fill failed: {response.text}")
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
        
        # Check first few entries for phase_name and project_name
        if weeks:
            first_week = weeks[0]
            entries = first_week.get("entries", [])
            print(f"\n   Sample entries from week {first_week.get('week_start')}:")
            for entry in entries[:3]:
                project_name = entry.get("project_name", "MISSING")
                phase_name = entry.get("phase_name", "MISSING")
                print(f"   - Project: {project_name}, Phase: {phase_name}")
                
                if project_name == "MISSING" or project_name == "Unknown Project":
                    print(f"   ❌ ISSUE: project_name is missing or 'Unknown Project'")
                if phase_name == "MISSING" or phase_name == "Unknown Phase":
                    print(f"   ❌ ISSUE: phase_name is missing or 'Unknown Phase'")
        else:
            print("   ⚠️  No timesheet entries found in history")
    else:
        print(f"❌ History retrieval failed: {response.text}")
        return False
    
    return True

# ============================================================================
# ISSUE 2: New Projects Created and Allocated to Resources
# ============================================================================

def test_issue_2_new_project_allocation():
    """
    Issue 2: New projects created and allocated to resources:
    - Create a new project via POST /api/projects or POST /api/projects/create-full.
    - Create an allocation for this project and a resource via POST /api/allocations.
    - Verify that GET /api/allocations and GET /api/my-allocations return the correct project_name and client_name (NOT 'Unknown' or blank).
    """
    print("\n" + "="*80)
    print("ISSUE 2: New Projects Created and Allocated to Resources")
    print("="*80)
    
    # Test 2.1: Create a new project via POST /api/projects/create-full
    print("\n[Test 2.1] POST /api/projects/create-full")
    
    project_data = {
        "name": "Test Project Issue 2",
        "client_name": "Test Client Corp",
        "status": "Active",
        "start_date": "2026-09-14",
        "end_date": "2026-12-31",
        "phases": [
            {"name": "Planning", "duration_weeks": 2},
            {"name": "Execution", "duration_weeks": 4}
        ],
        "allocations": [
            {
                "resource_id": RESOURCE_ID,
                "percentage": 50,
                "role": "Developer"
            }
        ]
    }
    
    response = requests.post(
        f"{BASE_URL}/projects/create-full",
        headers=get_headers(),
        json=project_data
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        data = response.json()
        project_id = data.get("project_id")
        print(f"✅ Project created: {project_id}")
        print(f"   Phases created: {data.get('phases_created', 0)}")
        print(f"   Allocations created: {data.get('allocations_created', 0)}")
    else:
        print(f"❌ Project creation failed: {response.text}")
        return False
    
    # Test 2.2: Verify GET /api/allocations returns correct project_name and client_name
    print("\n[Test 2.2] GET /api/allocations")
    response = requests.get(
        f"{BASE_URL}/allocations",
        headers=get_headers()
    )
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        allocations = response.json()
        print(f"✅ Allocations retrieved: {len(allocations)} total")
        
        # Find our newly created allocation
        found = False
        for alloc in allocations:
            if alloc.get("project_id") == project_id:
                found = True
                project_name = alloc.get("project_name", "MISSING")
                client_name = alloc.get("client_name", "MISSING")
                print(f"\n   Found allocation for new project:")
                print(f"   - Project Name: {project_name}")
                print(f"   - Client Name: {client_name}")
                
                if project_name == "Unknown" or project_name == "MISSING" or not project_name:
                    print(f"   ❌ ISSUE: project_name is 'Unknown', 'MISSING', or blank")
                    return False
                if client_name == "Unknown" or client_name == "MISSING" or not client_name:
                    print(f"   ❌ ISSUE: client_name is 'Unknown', 'MISSING', or blank")
                    return False
                
                print(f"   ✅ project_name and client_name are correct")
                break
        
        if not found:
            print(f"   ❌ ISSUE: Could not find allocation for newly created project")
            return False
    else:
        print(f"❌ Allocations retrieval failed: {response.text}")
        return False
    
    # Test 2.3: Verify GET /api/my-allocations returns correct project_name and client_name
    print("\n[Test 2.3] GET /api/my-allocations")
    response = requests.get(
        f"{BASE_URL}/my-allocations",
        headers=get_headers()
    )
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        allocations = response.json()
        print(f"✅ My allocations retrieved: {len(allocations)} total")
        
        # Find our newly created allocation
        found = False
        for alloc in allocations:
            if alloc.get("project_id") == project_id:
                found = True
                project_name = alloc.get("project_name", "MISSING")
                client_name = alloc.get("client_name", "MISSING")
                print(f"\n   Found allocation for new project:")
                print(f"   - Project Name: {project_name}")
                print(f"   - Client Name: {client_name}")
                
                if project_name == "Unknown" or project_name == "MISSING" or not project_name:
                    print(f"   ❌ ISSUE: project_name is 'Unknown', 'MISSING', or blank")
                    return False
                if client_name == "Unknown" or client_name == "MISSING" or not client_name:
                    print(f"   ❌ ISSUE: client_name is 'Unknown', 'MISSING', or blank")
                    return False
                
                print(f"   ✅ project_name and client_name are correct")
                break
        
        if not found:
            print(f"   ⚠️  Could not find allocation in my-allocations (may be expected if user is not the resource)")
    else:
        print(f"❌ My allocations retrieval failed: {response.text}")
        return False
    
    return True

# ============================================================================
# ISSUE 3: WBS Percentage Updates
# ============================================================================

def test_issue_3_wbs_percentage():
    """
    Issue 3: WBS percentage updates:
    - Create a WBS task via POST /api/projects/{project_id}/wbs/tasks with progress_percentage (e.g. 25).
    - Verify that GET /api/projects/{project_id}/wbs returns progress_percentage.
    - Update the task via PUT /api/wbs/tasks/{task_id} with progress_percentage=75, then 100.
    - Verify that progress_percentage=100 sets status to 'done'.
    """
    print("\n" + "="*80)
    print("ISSUE 3: WBS Percentage Updates")
    print("="*80)
    
    # First, get a project to work with
    print("\n[Test 3.0] GET /api/projects (to find a project)")
    response = requests.get(
        f"{BASE_URL}/projects",
        headers=get_headers()
    )
    
    if response.status_code != 200 or not response.json():
        print(f"❌ Could not get projects")
        return False
    
    projects = response.json()
    project_id = str(projects[0]["id"])
    project_name = projects[0]["name"]
    print(f"✅ Using project: {project_name} (ID: {project_id})")
    
    # Test 3.1: Create a WBS task with progress_percentage=25
    print("\n[Test 3.1] POST /api/projects/{project_id}/wbs/tasks with progress_percentage=25")
    
    task_data = {
        "name": "Test WBS Task Issue 3",
        "description": "Testing progress percentage updates",
        "status": "in_progress",
        "priority": "medium",
        "estimated_hours": 10,
        "progress_percentage": 25,
        "start_date": "2026-09-14",
        "end_date": "2026-09-18"
    }
    
    response = requests.post(
        f"{BASE_URL}/projects/{project_id}/wbs/tasks",
        headers=get_headers(),
        json=task_data
    )
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        task = response.json()
        task_id = task.get("id")
        progress = task.get("progress_percentage")
        print(f"✅ WBS task created: {task_id}")
        print(f"   Progress percentage: {progress}%")
        
        if progress != 25:
            print(f"   ❌ ISSUE: progress_percentage is {progress}, expected 25")
            return False
    else:
        print(f"❌ WBS task creation failed: {response.text}")
        return False
    
    # Test 3.2: Verify GET /api/projects/{project_id}/wbs returns progress_percentage
    print("\n[Test 3.2] GET /api/projects/{project_id}/wbs")
    response = requests.get(
        f"{BASE_URL}/projects/{project_id}/wbs",
        headers=get_headers()
    )
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        tasks = response.json()
        print(f"✅ WBS tasks retrieved: {len(tasks)} total")
        
        # Find our task
        found = False
        for task in tasks:
            if task.get("id") == task_id:
                found = True
                progress = task.get("progress_percentage")
                print(f"\n   Found task: {task.get('name')}")
                print(f"   Progress percentage: {progress}%")
                
                if progress != 25:
                    print(f"   ❌ ISSUE: progress_percentage is {progress}, expected 25")
                    return False
                
                print(f"   ✅ progress_percentage is correct")
                break
        
        if not found:
            print(f"   ❌ ISSUE: Could not find newly created task")
            return False
    else:
        print(f"❌ WBS tasks retrieval failed: {response.text}")
        return False
    
    # Test 3.3: Update task with progress_percentage=75
    print("\n[Test 3.3] PUT /api/wbs/tasks/{task_id} with progress_percentage=75")
    
    update_data = {
        "progress_percentage": 75
    }
    
    response = requests.put(
        f"{BASE_URL}/wbs/tasks/{task_id}",
        headers=get_headers(),
        json=update_data
    )
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        task = response.json()
        progress = task.get("progress_percentage")
        status = task.get("status")
        print(f"✅ WBS task updated")
        print(f"   Progress percentage: {progress}%")
        print(f"   Status: {status}")
        
        if progress != 75:
            print(f"   ❌ ISSUE: progress_percentage is {progress}, expected 75")
            return False
    else:
        print(f"❌ WBS task update failed: {response.text}")
        return False
    
    # Test 3.4: Update task with progress_percentage=100 and verify status='done'
    print("\n[Test 3.4] PUT /api/wbs/tasks/{task_id} with progress_percentage=100")
    
    update_data = {
        "progress_percentage": 100
    }
    
    response = requests.put(
        f"{BASE_URL}/wbs/tasks/{task_id}",
        headers=get_headers(),
        json=update_data
    )
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        task = response.json()
        progress = task.get("progress_percentage")
        status = task.get("status")
        print(f"✅ WBS task updated")
        print(f"   Progress percentage: {progress}%")
        print(f"   Status: {status}")
        
        if progress != 100:
            print(f"   ❌ ISSUE: progress_percentage is {progress}, expected 100")
            return False
        
        if status != "done":
            print(f"   ❌ ISSUE: status is '{status}', expected 'done'")
            return False
        
        print(f"   ✅ progress_percentage=100 correctly set status to 'done'")
    else:
        print(f"❌ WBS task update failed: {response.text}")
        return False
    
    return True

# ============================================================================
# ISSUE 6: AI Actions
# ============================================================================

def test_issue_6_ai_actions():
    """
    Issue 6: AI actions:
    - Test AI action execution: POST /api/ai/chat/execute-plan with a multi-step plan containing create_project followed by create_allocation using placeholder "<step_0_id>".
    - Verify that both steps complete successfully and the allocation has the resolved project_id.
    - Also test POST /api/projects/create-full.
    """
    print("\n" + "="*80)
    print("ISSUE 6: AI Actions")
    print("="*80)
    
    # Test 6.1: POST /api/projects/create-full (already tested in Issue 2, but verify again)
    print("\n[Test 6.1] POST /api/projects/create-full")
    
    project_data = {
        "name": "AI Test Project Issue 6",
        "client_name": "AI Test Client",
        "status": "Active",
        "start_date": "2026-09-14",
        "end_date": "2026-12-31",
        "phases": [
            {"name": "Phase 1", "duration_weeks": 2}
        ],
        "allocations": [
            {
                "resource_id": RESOURCE_ID,
                "percentage": 30,
                "role": "Tester"
            }
        ]
    }
    
    response = requests.post(
        f"{BASE_URL}/projects/create-full",
        headers=get_headers(),
        json=project_data
    )
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        project_id = data.get("project_id")
        print(f"✅ Project created via create-full: {project_id}")
    else:
        print(f"❌ Project creation failed: {response.text}")
        return False
    
    # Test 6.2: POST /api/ai/chat/execute-plan with multi-step plan
    print("\n[Test 6.2] POST /api/ai/chat/execute-plan with multi-step plan")
    
    # Create a multi-step plan: create_project followed by create_allocation using <step_0_id>
    plan_data = {
        "plan": [
            {
                "action": "create_project",
                "params": {
                    "name": "AI Multi-Step Project",
                    "client_name": "AI Multi-Step Client",
                    "status": "Active"
                }
            },
            {
                "action": "create_allocation",
                "params": {
                    "project_id": "<step_0_id>",
                    "resource_id": RESOURCE_ID,
                    "percentage": 40,
                    "role": "Developer"
                }
            }
        ]
    }
    
    response = requests.post(
        f"{BASE_URL}/ai/chat/execute-plan",
        headers=get_headers(),
        json=plan_data
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        data = response.json()
        results = data.get("results", [])
        print(f"✅ Plan executed: {len(results)} steps")
        
        # Verify step 0 (create_project)
        if len(results) > 0:
            step_0 = results[0]
            if step_0.get("success"):
                project_id = step_0.get("result", {}).get("project_id")
                print(f"\n   Step 0 (create_project): ✅ Success")
                print(f"   Project ID: {project_id}")
            else:
                print(f"\n   Step 0 (create_project): ❌ Failed")
                print(f"   Error: {step_0.get('error')}")
                return False
        
        # Verify step 1 (create_allocation with <step_0_id>)
        if len(results) > 1:
            step_1 = results[1]
            if step_1.get("success"):
                allocation_id = step_1.get("result", {}).get("allocation_id")
                resolved_project_id = step_1.get("result", {}).get("project_id")
                print(f"\n   Step 1 (create_allocation): ✅ Success")
                print(f"   Allocation ID: {allocation_id}")
                print(f"   Resolved Project ID: {resolved_project_id}")
                
                # Verify that <step_0_id> was resolved to actual project_id
                if resolved_project_id == project_id:
                    print(f"   ✅ <step_0_id> correctly resolved to {project_id}")
                else:
                    print(f"   ❌ ISSUE: <step_0_id> not resolved correctly")
                    print(f"      Expected: {project_id}")
                    print(f"      Got: {resolved_project_id}")
                    return False
            else:
                print(f"\n   Step 1 (create_allocation): ❌ Failed")
                print(f"   Error: {step_1.get('error')}")
                return False
    else:
        print(f"❌ Plan execution failed: {response.text}")
        return False
    
    return True

# ============================================================================
# Main Test Runner
# ============================================================================

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("BACKEND API TESTING - 6 REPORTED ISSUES")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"Test User: {TEST_USER}")
    print(f"Resource ID: {RESOURCE_ID}")
    
    # Login first
    if not login():
        print("\n❌ Login failed. Cannot proceed with tests.")
        return
    
    # Run all tests
    results = {
        "Issue 1: Timesheet Pre-fill": test_issue_1_timesheet_prefill(),
        "Issue 2: New Project Allocation": test_issue_2_new_project_allocation(),
        "Issue 3: WBS Percentage Updates": test_issue_3_wbs_percentage(),
        "Issue 6: AI Actions": test_issue_6_ai_actions()
    }
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = 0
    failed = 0
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed} passed, {failed} failed out of {len(results)} tests")
    
    if failed == 0:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the output above.")

if __name__ == "__main__":
    main()
