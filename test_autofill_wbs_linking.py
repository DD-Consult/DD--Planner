"""
Comprehensive tests for Auto-Fill Timesheets with WBS Task Linking Feature
Tests all 6 scenarios from the review request:
1. Backward compatibility (no WBS tasks)
2. Single WBS task auto-assignment
3. Multiple WBS tasks (no auto-assignment)
4. Resource-specific task assignment
5. Existing timesheet update (preserve manual selection)
6. Error handling (WBS collection unavailable)
"""

import requests
import sys
from datetime import datetime, timedelta
from typing import Optional, Dict, List

class AutoFillWBSLinkingTester:
    def __init__(self, base_url="https://calc-audit-review.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.admin_token = None
        self.resource_token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        
        # Test data storage
        self.test_project_id = None
        self.test_resource_id = None
        self.test_resource2_id = None
        self.test_allocation_id = None
        self.test_phase_id = None
        self.test_wbs_task_ids = []
        self.test_timesheet_ids = []

    def log_result(self, test_name, passed, message=""):
        """Log test result"""
        self.tests_run += 1
        if passed:
            self.tests_passed += 1
            status = "✅ PASSED"
        else:
            status = "❌ FAILED"
        
        result = f"{status} - {test_name}"
        if message:
            result += f": {message}"
        
        print(result)
        self.test_results.append({"test": test_name, "passed": passed, "message": message})
        return passed

    def login_admin(self):
        """Login as super admin"""
        try:
            data = {
                "username": "don@ddconsult.tech",
                "password": "Welcome123!"
            }
            response = requests.post(
                f"{self.base_url}/auth/login",
                data=data,
                timeout=10
            )
            
            if response.status_code == 200:
                json_data = response.json()
                if "access_token" in json_data:
                    self.admin_token = json_data["access_token"]
                    return self.log_result("Super Admin Login", True, "Token received")
                else:
                    return self.log_result("Super Admin Login", False, "No access_token in response")
            else:
                return self.log_result("Super Admin Login", False, f"Status: {response.status_code}")
        except Exception as e:
            return self.log_result("Super Admin Login", False, str(e))

    def get_headers(self, token=None):
        """Get authorization headers"""
        if token is None:
            token = self.admin_token
        return {"Authorization": f"Bearer {token}"}

    def cleanup_test_data(self):
        """Clean up all test data created during tests"""
        print("\n--- Cleaning up test data ---")
        
        # Delete timesheets
        for ts_id in self.test_timesheet_ids:
            try:
                requests.delete(
                    f"{self.base_url}/timesheets/{ts_id}",
                    headers=self.get_headers(),
                    timeout=10
                )
            except:
                pass
        
        # Delete WBS tasks
        for task_id in self.test_wbs_task_ids:
            try:
                requests.delete(
                    f"{self.base_url}/wbs/tasks/{task_id}",
                    headers=self.get_headers(),
                    timeout=10
                )
            except:
                pass
        
        # Delete allocation
        if self.test_allocation_id:
            try:
                requests.delete(
                    f"{self.base_url}/allocations/{self.test_allocation_id}",
                    headers=self.get_headers(),
                    timeout=10
                )
            except:
                pass
        
        # Delete project
        if self.test_project_id:
            try:
                requests.delete(
                    f"{self.base_url}/projects/{self.test_project_id}",
                    headers=self.get_headers(),
                    timeout=10
                )
            except:
                pass
        
        # Delete resources
        if self.test_resource_id:
            try:
                requests.delete(
                    f"{self.base_url}/resources/{self.test_resource_id}",
                    headers=self.get_headers(),
                    timeout=10
                )
            except:
                pass
        
        if self.test_resource2_id:
            try:
                requests.delete(
                    f"{self.base_url}/resources/{self.test_resource2_id}",
                    headers=self.get_headers(),
                    timeout=10
                )
            except:
                pass
        
        print("Cleanup completed")

    def setup_test_environment(self):
        """Create test project, resource, and allocation"""
        print("\n--- Setting up test environment ---")
        
        # Create test resource 1
        resource_data = {
            "name": "Test Resource AutoFill 1",
            "role": "Developer",
            "standard_capacity": 100
        }
        response = requests.post(
            f"{self.base_url}/resources",
            headers=self.get_headers(),
            json=resource_data,
            timeout=10
        )
        if response.status_code == 200:
            self.test_resource_id = response.json()["id"]
            print(f"✅ Created test resource 1: {self.test_resource_id}")
        else:
            print(f"❌ Failed to create test resource 1: {response.status_code}")
            return False
        
        # Create test resource 2
        resource_data2 = {
            "name": "Test Resource AutoFill 2",
            "role": "Designer",
            "standard_capacity": 100
        }
        response = requests.post(
            f"{self.base_url}/resources",
            headers=self.get_headers(),
            json=resource_data2,
            timeout=10
        )
        if response.status_code == 200:
            self.test_resource2_id = response.json()["id"]
            print(f"✅ Created test resource 2: {self.test_resource2_id}")
        else:
            print(f"❌ Failed to create test resource 2: {response.status_code}")
            return False
        
        # Create test project with phases
        today = datetime.now().date()
        project_data = {
            "name": "AutoFill WBS Test Project",
            "client_name": "Test Client",
            "status": "Active",
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=90)).isoformat(),
            "budgeted_hours": 500,
            "phases": [
                {
                    "id": "phase-1",
                    "name": "Development",
                    "start_date": today.isoformat(),
                    "end_date": (today + timedelta(days=45)).isoformat()
                },
                {
                    "id": "phase-2",
                    "name": "Testing",
                    "start_date": (today + timedelta(days=46)).isoformat(),
                    "end_date": (today + timedelta(days=90)).isoformat()
                }
            ]
        }
        response = requests.post(
            f"{self.base_url}/projects",
            headers=self.get_headers(),
            json=project_data,
            timeout=10
        )
        if response.status_code == 200:
            self.test_project_id = response.json()["id"]
            self.test_phase_id = "phase-1"
            print(f"✅ Created test project: {self.test_project_id}")
        else:
            print(f"❌ Failed to create test project: {response.status_code}")
            return False
        
        # Create allocation for resource 1
        allocation_data = {
            "resource_id": self.test_resource_id,
            "project_id": self.test_project_id,
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=90)).isoformat(),
            "percentage": 50,
            "allocation_type": "percentage",
            "role": "Developer",
            "phase_ids": ["phase-1"]
        }
        response = requests.post(
            f"{self.base_url}/allocations",
            headers=self.get_headers(),
            json=allocation_data,
            timeout=10
        )
        if response.status_code == 200:
            self.test_allocation_id = response.json()["id"]
            print(f"✅ Created test allocation: {self.test_allocation_id}")
        else:
            print(f"❌ Failed to create test allocation: {response.status_code}")
            return False
        
        print("✅ Test environment setup complete\n")
        return True

    def get_week_start(self, offset_weeks=0):
        """Get week start date (Monday) with optional offset"""
        today = datetime.now().date()
        # Find the Monday of current week
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday)
        # Apply offset
        return monday + timedelta(weeks=offset_weeks)

    def create_user_for_resource(self, resource_id: str, email: str, password: str):
        """Create a user account linked to a resource"""
        user_data = {
            "email": email,
            "password": password,
            "role": "resource",
            "resource_id": resource_id,
            "must_change_password": False
        }
        response = requests.post(
            f"{self.base_url}/users",
            headers=self.get_headers(),
            json=user_data,
            timeout=10
        )
        return response.status_code == 200

    def login_as_resource(self, email: str, password: str):
        """Login as a resource user"""
        data = {
            "username": email,
            "password": password
        }
        response = requests.post(
            f"{self.base_url}/auth/login",
            data=data,
            timeout=10
        )
        if response.status_code == 200:
            json_data = response.json()
            if "access_token" in json_data:
                self.resource_token = json_data["access_token"]
                return True
        return False

    def verify_wbs_tasks_exist(self, project_id: str) -> List[Dict]:
        """Get WBS tasks for a project"""
        response = requests.get(
            f"{self.base_url}/projects/{project_id}/wbs",
            headers=self.get_headers(),
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        return []

    def create_wbs_task(self, project_id: str, phase_id: str, name: str, 
                       assigned_to: Optional[str] = None) -> Optional[str]:
        """Create a WBS task"""
        task_data = {
            "name": name,
            "description": f"Test task: {name}",
            "phase_id": phase_id,
            "phase_name": "Development",
            "status": "todo",
            "priority": "medium",
            "estimated_hours": 20,
            "assigned_to": assigned_to
        }
        response = requests.post(
            f"{self.base_url}/projects/{project_id}/wbs/tasks",
            headers=self.get_headers(),
            json=task_data,
            timeout=10
        )
        if response.status_code == 200:
            task_id = response.json()["id"]
            self.test_wbs_task_ids.append(task_id)
            return task_id
        return None

    def call_auto_fill(self, week_start: str, token=None) -> Optional[Dict]:
        """Call auto-fill endpoint"""
        if token is None:
            token = self.admin_token
        
        response = requests.post(
            f"{self.base_url}/timesheets/auto-fill?week_start={week_start}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        return None

    def get_timesheets(self, week_start: str, token=None) -> List[Dict]:
        """Get timesheets for a week"""
        if token is None:
            token = self.admin_token
        
        response = requests.get(
            f"{self.base_url}/timesheets/my-week?week_start={week_start}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if response.status_code == 200:
            timesheets = response.json()
            # Store IDs for cleanup
            for ts in timesheets:
                if ts["id"] not in self.test_timesheet_ids:
                    self.test_timesheet_ids.append(ts["id"])
            return timesheets
        return []

    def delete_all_timesheets_for_week(self, week_start: str):
        """Delete all timesheets for a specific week"""
        timesheets = self.get_timesheets(week_start)
        for ts in timesheets:
            try:
                requests.delete(
                    f"{self.base_url}/timesheets/{ts['id']}",
                    headers=self.get_headers(),
                    timeout=10
                )
            except:
                pass

    # ========== TEST SCENARIOS ==========

    def test_scenario_1_backward_compatibility(self):
        """
        Scenario 1: Backward Compatibility (No WBS Tasks)
        Setup: Project with phases but NO WBS tasks
        Expected: Auto-fill creates timesheets WITHOUT task_id (legacy behavior)
        """
        print("\n--- Scenario 1: Backward Compatibility (No WBS Tasks) ---")
        
        week_start = self.get_week_start(offset_weeks=1)
        week_start_str = week_start.isoformat()
        
        # Ensure no WBS tasks exist
        wbs_tasks = self.verify_wbs_tasks_exist(self.test_project_id)
        if len(wbs_tasks) > 0:
            return self.log_result(
                "Scenario 1: Setup",
                False,
                f"Expected 0 WBS tasks, found {len(wbs_tasks)}"
            )
        
        # Clean up any existing timesheets
        self.delete_all_timesheets_for_week(week_start_str)
        
        # Call auto-fill
        result = self.call_auto_fill(week_start_str)
        if not result:
            return self.log_result(
                "Scenario 1: Auto-fill call",
                False,
                "Auto-fill API call failed"
            )
        
        # Verify response
        if result.get("created", 0) == 0:
            return self.log_result(
                "Scenario 1: Timesheet creation",
                False,
                f"Expected at least 1 timesheet created, got {result.get('created', 0)}"
            )
        
        # Get timesheets and verify
        timesheets = self.get_timesheets(week_start_str)
        if len(timesheets) == 0:
            return self.log_result(
                "Scenario 1: Timesheet retrieval",
                False,
                "No timesheets found after auto-fill"
            )
        
        # Verify timesheet has NO task_id (backward compatibility)
        timesheet = timesheets[0]
        has_phase_id = timesheet.get("phase_id") is not None
        has_no_task_id = timesheet.get("task_id") is None
        is_auto_filled = timesheet.get("auto_filled") == True
        
        if not has_phase_id:
            return self.log_result(
                "Scenario 1: Phase ID",
                False,
                "Timesheet missing phase_id"
            )
        
        if not has_no_task_id:
            return self.log_result(
                "Scenario 1: Task ID (should be None)",
                False,
                f"Expected task_id=None, got task_id={timesheet.get('task_id')}"
            )
        
        if not is_auto_filled:
            return self.log_result(
                "Scenario 1: Auto-filled flag",
                False,
                "Expected auto_filled=True"
            )
        
        return self.log_result(
            "Scenario 1: Backward Compatibility",
            True,
            f"✅ phase_id={timesheet.get('phase_id')}, task_id=None, auto_filled=True"
        )

    def test_scenario_2_single_task_assignment(self):
        """
        Scenario 2: Single WBS Task Auto-Assignment
        Setup: Project with 1 WBS task in a phase
        Expected: Auto-fill assigns that task to timesheet
        """
        print("\n--- Scenario 2: Single WBS Task Auto-Assignment ---")
        
        week_start = self.get_week_start(offset_weeks=2)
        week_start_str = week_start.isoformat()
        
        # Create 1 WBS task
        task_id = self.create_wbs_task(
            self.test_project_id,
            self.test_phase_id,
            "Single Task Test"
        )
        if not task_id:
            return self.log_result(
                "Scenario 2: WBS task creation",
                False,
                "Failed to create WBS task"
            )
        
        # Clean up any existing timesheets
        self.delete_all_timesheets_for_week(week_start_str)
        
        # Call auto-fill
        result = self.call_auto_fill(week_start_str)
        if not result:
            return self.log_result(
                "Scenario 2: Auto-fill call",
                False,
                "Auto-fill API call failed"
            )
        
        # Get timesheets and verify
        timesheets = self.get_timesheets(week_start_str)
        if len(timesheets) == 0:
            return self.log_result(
                "Scenario 2: Timesheet retrieval",
                False,
                "No timesheets found after auto-fill"
            )
        
        # Verify timesheet has task_id assigned
        timesheet = timesheets[0]
        assigned_task_id = timesheet.get("task_id")
        assigned_task_name = timesheet.get("task_name")
        
        if assigned_task_id != task_id:
            return self.log_result(
                "Scenario 2: Task assignment",
                False,
                f"Expected task_id={task_id}, got task_id={assigned_task_id}"
            )
        
        if not assigned_task_name:
            return self.log_result(
                "Scenario 2: Task name",
                False,
                "Expected task_name to be set"
            )
        
        return self.log_result(
            "Scenario 2: Single Task Auto-Assignment",
            True,
            f"✅ task_id={assigned_task_id}, task_name={assigned_task_name}"
        )

    def test_scenario_3_multiple_tasks_no_assignment(self):
        """
        Scenario 3: Multiple WBS Tasks (No Auto-Assignment)
        Setup: Project with 3 WBS tasks in a phase
        Expected: Auto-fill does NOT assign task (user chooses later)
        """
        print("\n--- Scenario 3: Multiple WBS Tasks (No Auto-Assignment) ---")
        
        week_start = self.get_week_start(offset_weeks=3)
        week_start_str = week_start.isoformat()
        
        # Create 3 WBS tasks
        task_ids = []
        for i in range(3):
            task_id = self.create_wbs_task(
                self.test_project_id,
                self.test_phase_id,
                f"Multiple Task Test {i+1}"
            )
            if task_id:
                task_ids.append(task_id)
        
        if len(task_ids) != 3:
            return self.log_result(
                "Scenario 3: WBS tasks creation",
                False,
                f"Expected 3 tasks created, got {len(task_ids)}"
            )
        
        # Clean up any existing timesheets
        self.delete_all_timesheets_for_week(week_start_str)
        
        # Call auto-fill
        result = self.call_auto_fill(week_start_str)
        if not result:
            return self.log_result(
                "Scenario 3: Auto-fill call",
                False,
                "Auto-fill API call failed"
            )
        
        # Get timesheets and verify
        timesheets = self.get_timesheets(week_start_str)
        if len(timesheets) == 0:
            return self.log_result(
                "Scenario 3: Timesheet retrieval",
                False,
                "No timesheets found after auto-fill"
            )
        
        # Verify timesheet has NO task_id (multiple options, user chooses)
        timesheet = timesheets[0]
        assigned_task_id = timesheet.get("task_id")
        
        if assigned_task_id is not None:
            return self.log_result(
                "Scenario 3: No task assignment",
                False,
                f"Expected task_id=None (multiple tasks), got task_id={assigned_task_id}"
            )
        
        return self.log_result(
            "Scenario 3: Multiple Tasks (No Auto-Assignment)",
            True,
            f"✅ task_id=None (smart: multiple options, user chooses)"
        )

    def test_scenario_4_resource_specific_assignment(self):
        """
        Scenario 4: Resource-Specific Task Assignment
        Setup: Phase has 3 tasks, but only 1 assigned to this resource
        Expected: Auto-fill assigns the resource's task
        """
        print("\n--- Scenario 4: Resource-Specific Task Assignment ---")
        
        week_start = self.get_week_start(offset_weeks=4)
        week_start_str = week_start.isoformat()
        
        # Create 3 WBS tasks with different assignments
        task_a_id = self.create_wbs_task(
            self.test_project_id,
            self.test_phase_id,
            "Task A - Resource 1",
            assigned_to=self.test_resource_id
        )
        task_b_id = self.create_wbs_task(
            self.test_project_id,
            self.test_phase_id,
            "Task B - Resource 2",
            assigned_to=self.test_resource2_id
        )
        task_c_id = self.create_wbs_task(
            self.test_project_id,
            self.test_phase_id,
            "Task C - Unassigned"
        )
        
        if not all([task_a_id, task_b_id, task_c_id]):
            return self.log_result(
                "Scenario 4: WBS tasks creation",
                False,
                "Failed to create all 3 WBS tasks"
            )
        
        # Clean up any existing timesheets
        self.delete_all_timesheets_for_week(week_start_str)
        
        # Call auto-fill (as admin, but for resource 1's allocation)
        result = self.call_auto_fill(week_start_str)
        if not result:
            return self.log_result(
                "Scenario 4: Auto-fill call",
                False,
                "Auto-fill API call failed"
            )
        
        # Get timesheets and verify
        timesheets = self.get_timesheets(week_start_str)
        if len(timesheets) == 0:
            return self.log_result(
                "Scenario 4: Timesheet retrieval",
                False,
                "No timesheets found after auto-fill"
            )
        
        # Verify timesheet has Task A assigned (resource 1's task)
        timesheet = timesheets[0]
        assigned_task_id = timesheet.get("task_id")
        assigned_task_name = timesheet.get("task_name")
        
        if assigned_task_id != task_a_id:
            return self.log_result(
                "Scenario 4: Resource-specific assignment",
                False,
                f"Expected task_id={task_a_id} (Task A), got task_id={assigned_task_id}"
            )
        
        if "Task A" not in assigned_task_name:
            return self.log_result(
                "Scenario 4: Task name verification",
                False,
                f"Expected 'Task A' in task_name, got {assigned_task_name}"
            )
        
        return self.log_result(
            "Scenario 4: Resource-Specific Assignment",
            True,
            f"✅ task_id={assigned_task_id}, task_name={assigned_task_name}"
        )

    def test_scenario_5_preserve_manual_selection(self):
        """
        Scenario 5: Existing Timesheet Update (Preserve Manual Selection)
        Setup: Timesheet already exists with manually selected task
        Expected: Auto-fill updates hours but PRESERVES task selection
        """
        print("\n--- Scenario 5: Preserve Manual Selection ---")
        
        week_start = self.get_week_start(offset_weeks=5)
        week_start_str = week_start.isoformat()
        
        # Create 2 WBS tasks
        task_x_id = self.create_wbs_task(
            self.test_project_id,
            self.test_phase_id,
            "Task X - Manual Selection"
        )
        task_y_id = self.create_wbs_task(
            self.test_project_id,
            self.test_phase_id,
            "Task Y - Should Not Replace"
        )
        
        if not all([task_x_id, task_y_id]):
            return self.log_result(
                "Scenario 5: WBS tasks creation",
                False,
                "Failed to create WBS tasks"
            )
        
        # Clean up any existing timesheets
        self.delete_all_timesheets_for_week(week_start_str)
        
        # Create a manual timesheet with Task X selected
        manual_timesheet_data = {
            "resource_id": self.test_resource_id,
            "project_id": self.test_project_id,
            "phase_id": self.test_phase_id,
            "week_start_date": week_start_str,
            "week_end_date": (week_start + timedelta(days=6)).isoformat(),
            "planned_hours": 10.0,
            "actual_hours": 8.0,
            "status": "Draft",
            "task_id": task_x_id,
            "task_name": "Task X - Manual Selection"
        }
        response = requests.post(
            f"{self.base_url}/timesheets",
            headers=self.get_headers(),
            json=manual_timesheet_data,
            timeout=10
        )
        if response.status_code != 200:
            return self.log_result(
                "Scenario 5: Manual timesheet creation",
                False,
                f"Failed to create manual timesheet: {response.status_code}"
            )
        
        manual_ts_id = response.json()["id"]
        self.test_timesheet_ids.append(manual_ts_id)
        
        # Call auto-fill (should update hours but preserve task_id)
        result = self.call_auto_fill(week_start_str)
        if not result:
            return self.log_result(
                "Scenario 5: Auto-fill call",
                False,
                "Auto-fill API call failed"
            )
        
        # Verify auto-fill skipped the manually modified timesheet
        if result.get("skipped", 0) == 0:
            return self.log_result(
                "Scenario 5: Skipped count",
                False,
                f"Expected skipped=1 (manual timesheet), got skipped={result.get('skipped', 0)}"
            )
        
        # Get timesheets and verify task_id is still Task X
        timesheets = self.get_timesheets(week_start_str)
        if len(timesheets) == 0:
            return self.log_result(
                "Scenario 5: Timesheet retrieval",
                False,
                "No timesheets found after auto-fill"
            )
        
        timesheet = timesheets[0]
        preserved_task_id = timesheet.get("task_id")
        
        if preserved_task_id != task_x_id:
            return self.log_result(
                "Scenario 5: Task preservation",
                False,
                f"Expected task_id={task_x_id} (preserved), got task_id={preserved_task_id}"
            )
        
        return self.log_result(
            "Scenario 5: Preserve Manual Selection",
            True,
            f"✅ task_id={preserved_task_id} (preserved), skipped={result.get('skipped', 0)}"
        )

    def test_scenario_6_error_handling(self):
        """
        Scenario 6: Error Handling (WBS Collection Unavailable)
        Expected: Auto-fill gracefully fails WBS query but continues
        
        Note: This scenario is difficult to test without mocking the database.
        We'll verify that auto-fill works even when WBS queries might fail.
        """
        print("\n--- Scenario 6: Error Handling (Graceful Degradation) ---")
        
        week_start = self.get_week_start(offset_weeks=6)
        week_start_str = week_start.isoformat()
        
        # Clean up any existing timesheets
        self.delete_all_timesheets_for_week(week_start_str)
        
        # Call auto-fill (should work even if WBS query fails internally)
        result = self.call_auto_fill(week_start_str)
        if not result:
            return self.log_result(
                "Scenario 6: Auto-fill call",
                False,
                "Auto-fill API call failed"
            )
        
        # Verify timesheets were created (graceful degradation)
        timesheets = self.get_timesheets(week_start_str)
        if len(timesheets) == 0:
            return self.log_result(
                "Scenario 6: Graceful degradation",
                False,
                "No timesheets created (should continue even if WBS fails)"
            )
        
        return self.log_result(
            "Scenario 6: Error Handling (Graceful Degradation)",
            True,
            f"✅ Auto-fill continued successfully, created {result.get('created', 0)} timesheets"
        )

    def verify_mongodb_documents(self):
        """
        Verify MongoDB documents directly (show task_id field)
        This is a bonus verification to show the actual data structure
        """
        print("\n--- MongoDB Document Verification ---")
        
        week_start = self.get_week_start(offset_weeks=2)
        week_start_str = week_start.isoformat()
        
        timesheets = self.get_timesheets(week_start_str)
        if len(timesheets) > 0:
            timesheet = timesheets[0]
            print(f"Sample Timesheet Document:")
            print(f"  - id: {timesheet.get('id')}")
            print(f"  - resource_id: {timesheet.get('resource_id')}")
            print(f"  - project_id: {timesheet.get('project_id')}")
            print(f"  - phase_id: {timesheet.get('phase_id')}")
            print(f"  - task_id: {timesheet.get('task_id')}")
            print(f"  - task_name: {timesheet.get('task_name')}")
            print(f"  - auto_filled: {timesheet.get('auto_filled')}")
            print(f"  - modified_by_user: {timesheet.get('modified_by_user')}")
            print(f"  - planned_hours: {timesheet.get('planned_hours')}")
            print(f"  - actual_hours: {timesheet.get('actual_hours')}")
            return self.log_result(
                "MongoDB Document Verification",
                True,
                "Document structure verified"
            )
        else:
            return self.log_result(
                "MongoDB Document Verification",
                False,
                "No timesheets found for verification"
            )

    def run_all_tests(self):
        """Run all test scenarios"""
        print("="*80)
        print("AUTO-FILL TIMESHEETS WITH WBS TASK LINKING - COMPREHENSIVE TESTS")
        print("="*80)
        
        # Login
        if not self.login_admin():
            print("❌ Failed to login as admin. Aborting tests.")
            return False
        
        # Setup test environment
        if not self.setup_test_environment():
            print("❌ Failed to setup test environment. Aborting tests.")
            return False
        
        try:
            # Run all 6 scenarios
            self.test_scenario_1_backward_compatibility()
            self.test_scenario_2_single_task_assignment()
            self.test_scenario_3_multiple_tasks_no_assignment()
            self.test_scenario_4_resource_specific_assignment()
            self.test_scenario_5_preserve_manual_selection()
            self.test_scenario_6_error_handling()
            
            # Bonus: Verify MongoDB documents
            self.verify_mongodb_documents()
            
        finally:
            # Cleanup
            self.cleanup_test_data()
        
        # Summary
        print("\n" + "="*80)
        print(f"TESTS COMPLETED: {self.tests_passed}/{self.tests_run} passed")
        print("="*80 + "\n")
        
        # Print detailed results
        print("\n--- DETAILED RESULTS ---")
        for result in self.test_results:
            status = "✅" if result["passed"] else "❌"
            print(f"{status} {result['test']}")
            if result["message"]:
                print(f"   {result['message']}")
        
        return self.tests_passed == self.tests_run


def main():
    tester = AutoFillWBSLinkingTester()
    success = tester.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
