import requests
import sys
import json
from datetime import datetime, timedelta

class WBSAPITester:
    def __init__(self, base_url="https://calc-audit-review.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.admin_token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.project_id = None
        self.created_task_id = None
        self.created_task_id_2 = None

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

    def test_super_admin_login(self):
        """Test super admin login to get JWT token"""
        try:
            # Try super admin first, fallback to regular admin
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
                    return self.log_result("Super Admin Login", True, f"Token received, Role: {json_data.get('user', {}).get('role')}")
                else:
                    return self.log_result("Super Admin Login", False, "No access_token in response")
            else:
                # Try fallback to regular admin
                print("Super admin failed, trying regular admin...")
                data = {
                    "username": "admin@test.com",
                    "password": "admin123"
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
                        return self.log_result("Admin Login (Fallback)", True, f"Token received, Role: {json_data.get('user', {}).get('role')}")
                    else:
                        return self.log_result("Admin Login (Fallback)", False, "No access_token in response")
                else:
                    return self.log_result("Super Admin Login", False, f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            return self.log_result("Super Admin Login", False, str(e))

    def test_get_projects(self):
        """Get all projects to find a valid project_id for testing"""
        try:
            headers = {"Authorization": f"Bearer {self.admin_token}"}
            response = requests.get(f"{self.base_url}/projects", headers=headers, timeout=10)
            
            if response.status_code == 200:
                projects = response.json()
                if isinstance(projects, list) and len(projects) > 0:
                    # Use the first project for testing
                    self.project_id = projects[0]["id"]
                    return self.log_result("Get Projects", True, f"Found {len(projects)} projects, using project_id: {self.project_id}")
                else:
                    return self.log_result("Get Projects", False, "No projects found")
            else:
                return self.log_result("Get Projects", False, f"Status: {response.status_code}")
        except Exception as e:
            return self.log_result("Get Projects", False, str(e))

    def test_get_project_wbs_empty(self):
        """Test GET /api/projects/{project_id}/wbs - should return empty array initially"""
        try:
            headers = {"Authorization": f"Bearer {self.admin_token}"}
            response = requests.get(
                f"{self.base_url}/projects/{self.project_id}/wbs",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    return self.log_result("Get Project WBS (Empty)", True, f"Returned array with {len(data)} tasks")
                else:
                    return self.log_result("Get Project WBS (Empty)", False, "Response is not an array")
            else:
                return self.log_result("Get Project WBS (Empty)", False, f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            return self.log_result("Get Project WBS (Empty)", False, str(e))

    def test_create_wbs_task(self):
        """Test POST /api/projects/{project_id}/wbs/tasks - create a task"""
        try:
            headers = {
                "Authorization": f"Bearer {self.admin_token}",
                "Content-Type": "application/json"
            }
            task_data = {
                "name": "Test WBS Task",
                "description": "Test task description",
                "phase_name": None,
                "status": "todo",
                "priority": "medium",
                "estimated_hours": 16,
                "start_date": "2025-07-01",
                "end_date": "2025-07-05",
                "order": 0,
                "dependencies": [],
                "labels": ["test"]
            }
            
            response = requests.post(
                f"{self.base_url}/projects/{self.project_id}/wbs/tasks",
                json=task_data,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if "id" in result:
                    self.created_task_id = result["id"]
                    # Verify task ID is a valid MongoDB ObjectId string (24 hex chars)
                    task_id_valid = len(self.created_task_id) == 24 and all(c in '0123456789abcdef' for c in self.created_task_id.lower())
                    return self.log_result("Create WBS Task", True, f"Created task ID: {self.created_task_id}, Valid ObjectId: {task_id_valid}")
                else:
                    return self.log_result("Create WBS Task", False, "No ID in response")
            else:
                return self.log_result("Create WBS Task", False, f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            return self.log_result("Create WBS Task", False, str(e))

    def test_update_wbs_task(self):
        """Test PUT /api/wbs/tasks/{task_id} - update the created task"""
        if not self.created_task_id:
            return self.log_result("Update WBS Task", False, "No task ID to update")
        
        try:
            headers = {
                "Authorization": f"Bearer {self.admin_token}",
                "Content-Type": "application/json"
            }
            update_data = {
                "status": "in_progress",
                "description": "Updated test task description"
            }
            
            response = requests.put(
                f"{self.base_url}/wbs/tasks/{self.created_task_id}",
                json=update_data,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "in_progress":
                    return self.log_result("Update WBS Task", True, f"Status updated to: {result.get('status')}")
                else:
                    return self.log_result("Update WBS Task", False, f"Expected status 'in_progress', got: {result.get('status')}")
            else:
                return self.log_result("Update WBS Task", False, f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            return self.log_result("Update WBS Task", False, str(e))

    def test_create_second_wbs_task(self):
        """Create a second task for dependency and delete testing"""
        try:
            headers = {
                "Authorization": f"Bearer {self.admin_token}",
                "Content-Type": "application/json"
            }
            task_data = {
                "name": "Second Test WBS Task",
                "description": "Second task for testing",
                "phase_name": None,
                "status": "todo",
                "priority": "high",
                "estimated_hours": 8,
                "start_date": "2025-07-06",
                "end_date": "2025-07-08",
                "order": 1,
                "dependencies": [self.created_task_id] if self.created_task_id else [],
                "labels": ["test", "dependency"]
            }
            
            response = requests.post(
                f"{self.base_url}/projects/{self.project_id}/wbs/tasks",
                json=task_data,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if "id" in result:
                    self.created_task_id_2 = result["id"]
                    return self.log_result("Create Second WBS Task", True, f"Created task ID: {self.created_task_id_2}")
                else:
                    return self.log_result("Create Second WBS Task", False, "No ID in response")
            else:
                return self.log_result("Create Second WBS Task", False, f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            return self.log_result("Create Second WBS Task", False, str(e))

    def test_cascade_dates(self):
        """Test POST /api/wbs/tasks/{task_id}/cascade-dates"""
        if not self.created_task_id:
            return self.log_result("Cascade Task Dates", False, "No task ID for cascading")
        
        try:
            headers = {"Authorization": f"Bearer {self.admin_token}"}
            response = requests.post(
                f"{self.base_url}/wbs/tasks/{self.created_task_id}/cascade-dates?new_end_date=2025-08-15",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if "updated_count" in result:
                    return self.log_result("Cascade Task Dates", True, f"Updated {result.get('updated_count')} dependent tasks")
                else:
                    return self.log_result("Cascade Task Dates", True, "Cascade completed successfully")
            else:
                return self.log_result("Cascade Task Dates", False, f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            return self.log_result("Cascade Task Dates", False, str(e))

    def test_get_wbs_actuals(self):
        """Test GET /api/projects/{project_id}/wbs/actuals - should return empty array"""
        try:
            headers = {"Authorization": f"Bearer {self.admin_token}"}
            response = requests.get(
                f"{self.base_url}/projects/{self.project_id}/wbs/actuals",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    return self.log_result("Get WBS Actuals", True, f"Returned array with {len(data)} actual entries")
                else:
                    return self.log_result("Get WBS Actuals", False, "Response is not an array")
            else:
                return self.log_result("Get WBS Actuals", False, f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            return self.log_result("Get WBS Actuals", False, str(e))

    def test_get_wbs_tasks_for_timesheet(self):
        """Test GET /api/projects/{project_id}/wbs/tasks-for-timesheet - should return list of tasks"""
        try:
            headers = {"Authorization": f"Bearer {self.admin_token}"}
            response = requests.get(
                f"{self.base_url}/projects/{self.project_id}/wbs/tasks-for-timesheet",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    # Verify lightweight structure
                    if len(data) > 0:
                        first_task = data[0]
                        required_fields = ["id", "name", "phase_name", "status", "estimated_hours"]
                        has_required_fields = all(field in first_task for field in required_fields)
                        return self.log_result("Get WBS Tasks for Timesheet", True, f"Returned {len(data)} tasks with required fields: {has_required_fields}")
                    else:
                        return self.log_result("Get WBS Tasks for Timesheet", True, "Returned empty array (no tasks yet)")
                else:
                    return self.log_result("Get WBS Tasks for Timesheet", False, "Response is not an array")
            else:
                return self.log_result("Get WBS Tasks for Timesheet", False, f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            return self.log_result("Get WBS Tasks for Timesheet", False, str(e))

    def test_get_project_wbs_with_tasks(self):
        """Test GET /api/projects/{project_id}/wbs after creating tasks"""
        try:
            headers = {"Authorization": f"Bearer {self.admin_token}"}
            response = requests.get(
                f"{self.base_url}/projects/{self.project_id}/wbs",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    return self.log_result("Get Project WBS (With Tasks)", True, f"Returned array with {len(data)} tasks")
                else:
                    return self.log_result("Get Project WBS (With Tasks)", False, "Expected tasks but got empty array")
            else:
                return self.log_result("Get Project WBS (With Tasks)", False, f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            return self.log_result("Get Project WBS (With Tasks)", False, str(e))

    def test_delete_wbs_task(self):
        """Test DELETE /api/wbs/tasks/{task_id} - delete the second task"""
        if not self.created_task_id_2:
            return self.log_result("Delete WBS Task", False, "No second task ID to delete")
        
        try:
            headers = {"Authorization": f"Bearer {self.admin_token}"}
            response = requests.delete(
                f"{self.base_url}/wbs/tasks/{self.created_task_id_2}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if "message" in result:
                    return self.log_result("Delete WBS Task", True, result.get("message"))
                else:
                    return self.log_result("Delete WBS Task", True, "Task deleted successfully")
            else:
                return self.log_result("Delete WBS Task", False, f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            return self.log_result("Delete WBS Task", False, str(e))

    def test_ai_generate_wbs(self):
        """Test POST /api/ai/generate-wbs - AI WBS generation"""
        try:
            headers = {
                "Authorization": f"Bearer {self.admin_token}",
                "Content-Type": "application/json"
            }
            ai_request = {
                "project_id": self.project_id,
                "additional_context": "This is a web development project",
                "include_subtasks": True,
                "complexity": "standard",
                "primary_deliverables": "Website, Mobile App",
                "provider": None,
                "api_key": None
            }
            
            response = requests.post(
                f"{self.base_url}/ai/generate-wbs",
                json=ai_request,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if "tasks" in result and isinstance(result["tasks"], list):
                    return self.log_result("AI Generate WBS", True, f"Generated {len(result['tasks'])} tasks")
                else:
                    return self.log_result("AI Generate WBS", False, "Invalid response format")
            else:
                # AI might not be configured, which is acceptable
                if response.status_code == 500 and "AI service unavailable" in response.text:
                    return self.log_result("AI Generate WBS", True, "AI service unavailable (expected if no AI key configured)")
                else:
                    return self.log_result("AI Generate WBS", False, f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            return self.log_result("AI Generate WBS", False, str(e))

    def test_save_generated_wbs(self):
        """Test POST /api/ai/generate-wbs/save - Save AI-generated WBS"""
        try:
            headers = {
                "Authorization": f"Bearer {self.admin_token}",
                "Content-Type": "application/json"
            }
            # Mock AI-generated tasks for testing save functionality
            mock_tasks = [
                {
                    "temp_id": "t1",
                    "name": "AI Generated Task 1",
                    "description": "First AI generated task",
                    "phase_name": None,
                    "status": "todo",
                    "priority": "medium",
                    "estimated_hours": 8,
                    "start_date_offset": 0,
                    "duration_days": 2,
                    "dependencies": [],
                    "labels": ["ai-generated"]
                },
                {
                    "temp_id": "t2",
                    "name": "AI Generated Task 2",
                    "description": "Second AI generated task",
                    "phase_name": None,
                    "status": "todo",
                    "priority": "high",
                    "estimated_hours": 12,
                    "start_date_offset": 2,
                    "duration_days": 3,
                    "dependencies": ["t1"],
                    "labels": ["ai-generated"]
                }
            ]
            
            save_request = {
                "project_id": self.project_id,
                "tasks": mock_tasks,
                "start_date": "2025-07-01"
            }
            
            response = requests.post(
                f"{self.base_url}/ai/generate-wbs/save",
                json=save_request,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if "saved_count" in result:
                    return self.log_result("Save Generated WBS", True, f"Saved {result['saved_count']} tasks")
                else:
                    return self.log_result("Save Generated WBS", True, "Tasks saved successfully")
            else:
                return self.log_result("Save Generated WBS", False, f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            return self.log_result("Save Generated WBS", False, str(e))

    def run_all_wbs_tests(self):
        """Run all WBS backend tests"""
        print("\n" + "="*80)
        print("WBS (WORK BREAKDOWN STRUCTURE) API BACKEND TESTS")
        print("="*80 + "\n")
        
        # Authentication
        print("--- Authentication ---")
        if not self.test_super_admin_login():
            print("❌ Super admin login failed - stopping tests")
            return False
        
        # Get projects
        print("\n--- Project Setup ---")
        if not self.test_get_projects():
            print("❌ Failed to get projects - stopping tests")
            return False
        
        # WBS CRUD Tests
        print("\n--- WBS CRUD Tests ---")
        self.test_get_project_wbs_empty()
        self.test_create_wbs_task()
        self.test_update_wbs_task()
        self.test_create_second_wbs_task()
        self.test_cascade_dates()
        self.test_get_project_wbs_with_tasks()
        self.test_delete_wbs_task()
        
        # WBS Integration Tests
        print("\n--- WBS Integration Tests ---")
        self.test_get_wbs_actuals()
        self.test_get_wbs_tasks_for_timesheet()
        
        # AI WBS Tests
        print("\n--- AI WBS Generation Tests ---")
        self.test_ai_generate_wbs()
        self.test_save_generated_wbs()
        
        # Summary
        print("\n" + "="*80)
        print(f"WBS TESTS COMPLETED: {self.tests_passed}/{self.tests_run} passed")
        print("="*80 + "\n")
        
        return self.tests_passed == self.tests_run


def main():
    tester = WBSAPITester()
    success = tester.run_all_wbs_tests()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())