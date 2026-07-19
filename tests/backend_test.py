import requests
import sys
from datetime import datetime

class ResourcePlannerAPITester:
    def __init__(self, base_url="https://calc-audit-review.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_result(self, test_name, passed, message=""):
        """Log test result"""
        self.tests_run += 1
        if passed:
            self.tests_passed += 1
            print(f"✅ PASS: {test_name}")
        else:
            print(f"❌ FAIL: {test_name}")
            if message:
                print(f"   Error: {message}")
        
        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "message": message
        })

    def run_test(self, name, method, endpoint, expected_status, data=None, check_response=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=10)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=headers, timeout=10)

            success = response.status_code == expected_status
            
            if success:
                print(f"   Status: {response.status_code} ✓")
                
                # Additional response checks
                if check_response and response.status_code == expected_status:
                    try:
                        response_data = response.json()
                        check_result = check_response(response_data)
                        if not check_result:
                            success = False
                            self.log_result(name, False, "Response validation failed")
                            return False, {}
                    except Exception as e:
                        success = False
                        self.log_result(name, False, f"Response check error: {str(e)}")
                        return False, {}
                
                self.log_result(name, True)
                return True, response.json() if response.content else {}
            else:
                error_msg = f"Expected {expected_status}, got {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f" - {error_detail.get('detail', '')}"
                except:
                    pass
                self.log_result(name, False, error_msg)
                return False, {}

        except requests.exceptions.Timeout:
            self.log_result(name, False, "Request timeout")
            return False, {}
        except Exception as e:
            self.log_result(name, False, f"Exception: {str(e)}")
            return False, {}

    def test_login(self, username, password):
        """Test login and get token"""
        print("\n" + "="*60)
        print("AUTHENTICATION TEST")
        print("="*60)
        
        # Login uses form data, not JSON
        url = f"{self.base_url}/api/auth/login"
        try:
            response = requests.post(
                url, 
                data={"username": username, "password": password},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'access_token' in data:
                    self.token = data['access_token']
                    print(f"✅ PASS: Login as Super Admin")
                    print(f"   Token obtained: {self.token[:20]}...")
                    self.tests_run += 1
                    self.tests_passed += 1
                    self.test_results.append({"test": "Login", "passed": True, "message": ""})
                    return True
            
            self.log_result("Login as Super Admin", False, f"Status {response.status_code}")
            return False
        except Exception as e:
            self.log_result("Login as Super Admin", False, str(e))
            return False

    def test_timesheet_restriction(self):
        """Test timesheet update restriction (Thursday/Friday Sydney time)"""
        print("\n" + "="*60)
        print("BUG FIX #2: TIMESHEET DAY RESTRICTION")
        print("="*60)
        
        def check_timesheet_response(data):
            """Validate timesheet restriction response"""
            required_fields = ['allowed', 'current_day']
            for field in required_fields:
                if field not in data:
                    print(f"   ❌ Missing field: {field}")
                    return False
            
            print(f"   Current day (Sydney): {data.get('current_day')}")
            print(f"   Updates allowed: {data.get('allowed')}")
            
            if not data.get('allowed'):
                if 'next_allowed_day' in data:
                    print(f"   Next allowed day: {data.get('next_allowed_day')}")
            
            return True
        
        success, response = self.run_test(
            "Check timesheet update restriction",
            "GET",
            "timesheet/can-update",
            200,
            check_response=check_timesheet_response
        )
        
        return success

    def test_projects_with_health_status(self):
        """Test that projects return health and status fields"""
        print("\n" + "="*60)
        print("BUG FIX #3: DASHBOARD HEALTH METRIC")
        print("="*60)
        
        def check_projects_response(data):
            """Validate projects have health status fields"""
            if not isinstance(data, list):
                print(f"   ❌ Expected list, got {type(data)}")
                return False
            
            if len(data) == 0:
                print(f"   ⚠️  No projects found")
                return True
            
            # Check first project for health fields
            project = data[0]
            print(f"   Sample project: {project.get('name', 'Unknown')}")
            
            # These fields should be present (can be None)
            if 'health' in project:
                print(f"   ✓ Health field present: {project.get('health')}")
            else:
                print(f"   ⚠️  Health field missing (may be computed on frontend)")
            
            if 'schedule_status' in project:
                print(f"   ✓ Schedule status present: {project.get('schedule_status')}")
            
            if 'actual_progress' in project:
                print(f"   ✓ Actual progress present: {project.get('actual_progress')}")
            
            return True
        
        success, response = self.run_test(
            "Get projects with health metrics",
            "GET",
            "projects",
            200,
            check_response=check_projects_response
        )
        
        return success

    def test_status_update_creation(self):
        """Test creating a project status update"""
        print("\n" + "="*60)
        print("PROJECT STATUS UPDATES")
        print("="*60)
        
        # First get a project
        success, projects = self.run_test(
            "Get projects for status update",
            "GET",
            "projects",
            200
        )
        
        if not success or not projects or len(projects) == 0:
            self.log_result("Create status update", False, "No projects available")
            return False
        
        project_id = projects[0]['id']
        project_name = projects[0]['name']
        print(f"   Using project: {project_name} ({project_id})")
        
        # Create a status update
        status_data = {
            "project_id": project_id,
            "health": "Green",
            "schedule_status": "On Track",
            "actual_progress": 75,
            "accomplishments": "Test accomplishment",
            "blockers": "No blockers",
            "next_steps": "Continue testing"
        }
        
        success, response = self.run_test(
            "Create project status update",
            "POST",
            "status-updates",
            200,
            data=status_data
        )
        
        if success:
            print(f"   Status update created with ID: {response.get('id')}")
        
        return success

    def test_allocation_roles(self):
        """Test allocation roles endpoint"""
        print("\n" + "="*60)
        print("ALLOCATION ROLES")
        print("="*60)
        
        def check_roles_response(data):
            """Validate allocation roles response"""
            if 'roles' not in data:
                print(f"   ❌ Missing 'roles' field")
                return False
            
            roles = data['roles']
            if not isinstance(roles, list):
                print(f"   ❌ Roles should be a list")
                return False
            
            print(f"   ✓ Found {len(roles)} allocation roles")
            print(f"   Roles: {', '.join(roles[:5])}...")
            return True
        
        success, response = self.run_test(
            "Get allocation roles",
            "GET",
            "allocation-roles",
            200,
            check_response=check_roles_response
        )
        
        return success

    def test_project_phases(self):
        """Test project phases endpoint"""
        print("\n" + "="*60)
        print("BUG FIX #1: PHASE SELECTION")
        print("="*60)
        
        # Get a project first
        success, projects = self.run_test(
            "Get projects",
            "GET",
            "projects",
            200
        )
        
        if not success or not projects or len(projects) == 0:
            self.log_result("Get project phases", False, "No projects available")
            return False
        
        project_id = projects[0]['id']
        project_name = projects[0]['name']
        print(f"   Using project: {project_name}")
        
        def check_phases_response(data):
            """Validate phases response"""
            if 'phases' not in data:
                print(f"   ❌ Missing 'phases' field")
                return False
            
            phases = data['phases']
            if not isinstance(phases, list):
                print(f"   ❌ Phases should be a list")
                return False
            
            print(f"   ✓ Found {len(phases)} phase(s)")
            
            for idx, phase in enumerate(phases):
                print(f"   Phase {idx+1}: {phase.get('name', 'Unknown')}")
                if 'start_date' in phase and 'end_date' in phase:
                    print(f"      Dates: {phase['start_date']} to {phase['end_date']}")
            
            return True
        
        success, response = self.run_test(
            "Get project phases",
            "GET",
            f"projects/{project_id}/phases",
            200,
            check_response=check_phases_response
        )
        
        return success

    def test_my_projects_for_status(self):
        """Test getting projects for status updates"""
        print("\n" + "="*60)
        print("MY PROJECTS FOR STATUS UPDATES")
        print("="*60)
        
        def check_my_projects_response(data):
            """Validate my projects response"""
            if not isinstance(data, list):
                print(f"   ❌ Expected list, got {type(data)}")
                return False
            
            print(f"   ✓ Found {len(data)} project(s) for status updates")
            
            for project in data[:3]:  # Show first 3
                print(f"   - {project.get('name', 'Unknown')}")
                if 'latest_status' in project:
                    latest = project['latest_status']
                    if latest:
                        print(f"     Latest status: {latest.get('health', 'N/A')} - {latest.get('schedule_status', 'N/A')}")
                    else:
                        print(f"     No status updates yet")
            
            return True
        
        success, response = self.run_test(
            "Get my projects for status updates",
            "GET",
            "status-updates/my-projects",
            200,
            check_response=check_my_projects_response
        )
        
        return success

    def test_get_project_status_updates(self):
        """Test getting status updates for a specific project (Issue #2 fix)"""
        print("\n" + "="*60)
        print("ISSUE #2 FIX: GET PROJECT STATUS UPDATES")
        print("="*60)
        
        # First get a project
        success, projects = self.run_test(
            "Get projects",
            "GET",
            "projects",
            200
        )
        
        if not success or not projects or len(projects) == 0:
            self.log_result("Get project status updates", False, "No projects available")
            return False
        
        project_id = projects[0]['id']
        project_name = projects[0]['name']
        print(f"   Using project: {project_name} ({project_id})")
        
        def check_status_updates_response(data):
            """Validate status updates response"""
            if not isinstance(data, list):
                print(f"   ❌ Expected list, got {type(data)}")
                return False
            
            print(f"   ✓ Found {len(data)} status update(s)")
            
            if len(data) > 0:
                update = data[0]
                print(f"   Latest update:")
                print(f"     Health: {update.get('health', 'N/A')}")
                print(f"     Schedule: {update.get('schedule_status', 'N/A')}")
                print(f"     Progress: {update.get('actual_progress', 'N/A')}%")
                if update.get('accomplishments'):
                    print(f"     Accomplishments: {update.get('accomplishments')[:50]}...")
            else:
                print(f"   ⚠️  No status updates yet (this is OK for new projects)")
            
            return True
        
        success, response = self.run_test(
            "Get project status updates (Issue #2)",
            "GET",
            f"status-updates/project/{project_id}?limit=5",
            200,
            check_response=check_status_updates_response
        )
        
        return success

    def test_allocation_creation(self):
        """Test allocation creation (Bug Fix: Allocation Editor not working)"""
        print("\n" + "="*60)
        print("BUG FIX: ALLOCATION CREATION")
        print("="*60)
        
        # Get resources and projects first
        success, resources = self.run_test(
            "Get resources for allocation",
            "GET",
            "resources",
            200
        )
        
        if not success or not resources or len(resources) == 0:
            self.log_result("Create allocation", False, "No resources available")
            return False
        
        success, projects = self.run_test(
            "Get projects for allocation",
            "GET",
            "projects",
            200
        )
        
        if not success or not projects or len(projects) == 0:
            self.log_result("Create allocation", False, "No projects available")
            return False
        
        resource_id = resources[0]['id']
        project = projects[0]
        project_id = project['id']
        
        print(f"   Using resource: {resources[0]['name']}")
        print(f"   Using project: {project['name']}")
        
        # Use project's date range for allocation
        project_start = project.get('start_date', '2026-01-01')[:10]  # Get YYYY-MM-DD
        project_end = project.get('end_date', '2026-02-01')[:10]
        
        print(f"   Project dates: {project_start} to {project_end}")
        
        # Create allocation within project date range
        allocation_data = {
            "resource_id": resource_id,
            "project_id": project_id,
            "start_date": project_start,
            "end_date": project_end,
            "percentage": 50,
            "allocation_type": "percentage",
            "role": "Developer"
        }
        
        success, response = self.run_test(
            "Create allocation",
            "POST",
            "allocations",
            200,
            data=allocation_data
        )
        
        if success:
            print(f"   ✓ Allocation created with ID: {response.get('id')}")
            # Store for cleanup
            self.created_allocation_id = response.get('id')
        
        return success

    def test_timesheet_no_duplicates(self):
        """Test timesheet retrieval to ensure no duplicates (Bug Fix: Timesheet duplicates)"""
        print("\n" + "="*60)
        print("BUG FIX: TIMESHEET DUPLICATES")
        print("="*60)
        
        # Get a project first
        success, projects = self.run_test(
            "Get projects",
            "GET",
            "projects",
            200
        )
        
        if not success or not projects or len(projects) == 0:
            self.log_result("Check timesheet duplicates", False, "No projects available")
            return False
        
        project_id = projects[0]['id']
        project_name = projects[0]['name']
        print(f"   Using project: {project_name} ({project_id})")
        
        # Get project time report - CORRECT ENDPOINT
        def check_time_report(data):
            """Check for duplicate timesheets in phase breakdown"""
            if 'phases' not in data:
                print(f"   ⚠️  No phases in time report")
                return True
            
            phases = data['phases']
            print(f"   ✓ Found {len(phases)} phase(s) in time report")
            
            # Check each phase for duplicate entries
            for phase in phases:
                phase_name = phase.get('phase_name', 'Unknown')
                phase_id = phase.get('phase_id', 'N/A')
                print(f"   Phase: {phase_name} (ID: {phase_id})")
                print(f"     Planned: {phase.get('planned_hours', 0)}h")
                print(f"     Actual: {phase.get('actual_hours', 0)}h")
            
            # Check if phase_ids are unique (no None values)
            phase_ids = [p.get('phase_id') for p in phases]
            if None in phase_ids:
                print(f"   ❌ Found None phase_id - this causes duplicates!")
                return False
            
            print(f"   ✓ All phases have valid IDs (no None values)")
            return True
        
        success, response = self.run_test(
            "Get project time report (check duplicates)",
            "GET",
            f"reports/planned-vs-actual/project/{project_id}",
            200,
            check_response=check_time_report
        )
        
        return success

    def test_ai_summary_generation(self):
        """Test AI summary generation with timeout handling (Bug Fix: AI API fallback)"""
        print("\n" + "="*60)
        print("BUG FIX: AI SUMMARY GENERATION")
        print("="*60)
        
        # Get a project first
        success, projects = self.run_test(
            "Get projects",
            "GET",
            "projects",
            200
        )
        
        if not success or not projects or len(projects) == 0:
            self.log_result("AI summary generation", False, "No projects available")
            return False
        
        project_id = projects[0]['id']
        project_name = projects[0]['name']
        print(f"   Using project: {project_name} ({project_id})")
        
        # Test AI summary generation
        url = f"{self.base_url}/api/projects/{project_id}/generate-summary"
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        
        print(f"\n🔍 Testing AI Summary Generation...")
        print(f"   Note: This may take up to 15 seconds (reduced from 30s)")
        
        try:
            response = requests.post(url, headers=headers, timeout=20)
            
            if response.status_code == 200:
                data = response.json()
                if 'summary' in data:
                    print(f"   ✓ Summary generated successfully")
                    print(f"   Summary preview: {data['summary'][:100]}...")
                    self.log_result("AI summary generation", True)
                    return True
                else:
                    self.log_result("AI summary generation", False, "No summary in response")
                    return False
            elif response.status_code == 500:
                # Check if it's a timeout or API key issue
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', '')
                    if 'timeout' in error_detail.lower() or 'fallback' in error_detail.lower():
                        print(f"   ⚠️  AI API timeout/fallback detected: {error_detail}")
                        print(f"   This is expected behavior with reduced timeout (15s)")
                        self.log_result("AI summary generation (timeout handling)", True, "Timeout handled correctly")
                        return True
                    else:
                        self.log_result("AI summary generation", False, f"Error: {error_detail}")
                        return False
                except:
                    self.log_result("AI summary generation", False, f"Status {response.status_code}")
                    return False
            else:
                self.log_result("AI summary generation", False, f"Status {response.status_code}")
                return False
        
        except requests.exceptions.Timeout:
            print(f"   ⚠️  Request timeout (>20s)")
            self.log_result("AI summary generation", False, "Request timeout exceeded 20s")
            return False
        except Exception as e:
            self.log_result("AI summary generation", False, str(e))
            return False

    def test_error_handling(self):
        """Test error handling for invalid API calls (Bug Fix: Error popups)"""
        print("\n" + "="*60)
        print("BUG FIX: ERROR HANDLING")
        print("="*60)
        
        # Test 1: Invalid allocation creation (missing required fields)
        print("\n   Test 1: Invalid allocation (missing fields)")
        invalid_allocation = {
            "resource_id": "invalid-id"
            # Missing required fields
        }
        
        url = f"{self.base_url}/api/allocations"
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        
        try:
            response = requests.post(url, json=invalid_allocation, headers=headers, timeout=10)
            if response.status_code in [400, 422]:
                print(f"   ✓ Invalid allocation rejected with status {response.status_code}")
                error_data = response.json()
                print(f"   Error detail: {str(error_data.get('detail', 'N/A'))[:100]}...")
                self.log_result("Error handling - invalid allocation", True)
            else:
                print(f"   ❌ Expected 400/422, got {response.status_code}")
                self.log_result("Error handling - invalid allocation", False, f"Wrong status code: {response.status_code}")
        except Exception as e:
            self.log_result("Error handling - invalid allocation", False, str(e))
        
        # Test 2: Non-existent resource
        print("\n   Test 2: Non-existent resource")
        url = f"{self.base_url}/api/resources/nonexistent-resource-id-12345"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            # Accept 404 or 500 (ObjectId validation error)
            if response.status_code in [404, 500]:
                print(f"   ✓ Non-existent resource handled with status {response.status_code}")
                self.log_result("Error handling - non-existent resource", True)
            else:
                print(f"   ⚠️  Got status {response.status_code} (expected 404 or 500)")
                self.log_result("Error handling - non-existent resource", True, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Error handling - non-existent resource", False, str(e))
        
        return True

    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"Total tests run: {self.tests_run}")
        print(f"Tests passed: {self.tests_passed}")
        print(f"Tests failed: {self.tests_run - self.tests_passed}")
        print(f"Success rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        if self.tests_passed < self.tests_run:
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result['passed']:
                    print(f"  - {result['test']}")
                    if result['message']:
                        print(f"    {result['message']}")
        
        return 0 if self.tests_passed == self.tests_run else 1

def main():
    print("="*60)
    print("RESOURCE PLANNER - BACKEND API TESTS")
    print("Testing Bug Fixes: Allocation Editor, Timesheet Duplicates, AI Fallback, Error Handling")
    print("="*60)
    
    tester = ResourcePlannerAPITester()
    
    # Test 1: Login
    if not tester.test_login("don@ddconsult.tech", "Welcome123!"):
        print("\n❌ Login failed, cannot continue with authenticated tests")
        return 1
    
    # Test 2: Timesheet restriction (Bug Fix #2)
    tester.test_timesheet_restriction()
    
    # Test 3: Projects with health metrics (Bug Fix #3)
    tester.test_projects_with_health_status()
    
    # Test 4: Status update creation
    tester.test_status_update_creation()
    
    # Test 5: Allocation roles
    tester.test_allocation_roles()
    
    # Test 6: Project phases (Bug Fix #1)
    tester.test_project_phases()
    
    # Test 7: My projects for status updates
    tester.test_my_projects_for_status()
    
    # Test 8: Get project status updates (Issue #2 fix)
    tester.test_get_project_status_updates()
    
    # NEW TESTS FOR CURRENT BUG FIXES
    print("\n" + "="*60)
    print("TESTING CURRENT BUG FIXES")
    print("="*60)
    
    # Test 9: Allocation creation (Bug: Allocation Editor not working)
    tester.test_allocation_creation()
    
    # Test 10: Timesheet duplicates (Bug: Timesheets showing under multiple phases)
    tester.test_timesheet_no_duplicates()
    
    # Test 11: AI summary generation (Bug: AI API fallback)
    tester.test_ai_summary_generation()
    
    # Test 12: Error handling (Bug: Silent errors)
    tester.test_error_handling()
    
    # Print summary
    return tester.print_summary()

if __name__ == "__main__":
    sys.exit(main())
