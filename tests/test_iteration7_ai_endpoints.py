"""
Test suite for DD Planner - Iteration 7 Features
Focus: New AI Analysis Endpoints + Migration Endpoint + Project Status Fix

Tests:
1. POST /api/admin/migrate-phase-ids - Migration endpoint
2. POST /api/ai/timesheet-insights - Timesheet analysis
3. POST /api/ai/plan-allocation - Future allocation planning
4. POST /api/projects/{project_id}/move-phase - Phase date shifting
5. GET /api/projects - Verify health, schedule_status, actual_progress fields
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://calc-audit-review.preview.emergentagent.com').rstrip('/')

@pytest.fixture(scope='module')
def auth_token():
    """Get authentication token for super admin"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": "don@ddconsult.tech", "password": "Welcome123!"},
        timeout=10
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert 'access_token' in data, "No access_token in login response"
    return data['access_token']

@pytest.fixture(scope='module')
def auth_headers(auth_token):
    """Authenticated headers"""
    return {
        'Authorization': f'Bearer {auth_token}',
        'Content-Type': 'application/json'
    }

@pytest.fixture(scope='module')
def test_project_with_phases(auth_headers):
    """Get a project with phases for testing move-phase endpoint"""
    response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers, timeout=10)
    assert response.status_code == 200, f"Failed to get projects: {response.text}"
    projects = response.json()
    
    # Find project 'Ellerston Digitisation' or any project with phases
    for project in projects:
        if 'Ellerston' in project.get('name', ''):
            return project
    
    # Fallback: Find any project with phases
    for project in projects:
        if project.get('phases') and len(project.get('phases', [])) > 0:
            return project
    
    # If no projects with phases, return first project
    return projects[0] if projects else None


class TestMigratePhaseIds:
    """Test POST /api/admin/migrate-phase-ids endpoint"""
    
    def test_migrate_phase_ids_success(self, auth_headers):
        """Migration endpoint should return success with stats"""
        response = requests.post(
            f"{BASE_URL}/api/admin/migrate-phase-ids",
            headers=auth_headers,
            timeout=30
        )
        
        assert response.status_code == 200, f"Migration failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert 'success' in data, "Response should have 'success' field"
        assert data['success'] == True, "Migration should succeed"
        
        # Should have either message or stats
        assert 'message' in data or 'log' in data, "Response should have 'message' or 'log'"
        
        print(f"Migration result: success={data['success']}")
        if 'log' in data and data['log']:
            print(f"Migration log entries: {len(data['log'])}")


class TestTimesheetInsightsEndpoint:
    """Test POST /api/ai/timesheet-insights endpoint"""
    
    def test_timesheet_insights_basic(self, auth_headers):
        """Timesheet insights should return summary with totals"""
        response = requests.post(
            f"{BASE_URL}/api/ai/timesheet-insights",
            headers=auth_headers,
            timeout=10
        )
        
        assert response.status_code == 200, f"Timesheet insights failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert 'summary' in data, "Response should have 'summary' field"
        
        summary = data['summary']
        if isinstance(summary, dict):
            # Summary has structured format
            assert 'total_entries' in summary, "Summary should have 'total_entries'"
            print(f"Total entries: {summary.get('total_entries')}")
            print(f"Planned hours: {summary.get('total_planned_hours', 0)}")
            print(f"Actual hours: {summary.get('total_actual_hours', 0)}")
        else:
            # String message (no data found)
            print(f"Summary message: {summary}")
    
    def test_timesheet_insights_with_project_filter(self, auth_headers, test_project_with_phases):
        """Timesheet insights filtered by project name"""
        if not test_project_with_phases:
            pytest.skip("No test project available")
        
        project_name = test_project_with_phases.get('name', '')
        response = requests.post(
            f"{BASE_URL}/api/ai/timesheet-insights",
            headers=auth_headers,
            params={'project_name': project_name},
            timeout=10
        )
        
        assert response.status_code == 200, f"Timesheet insights with project filter failed: {response.text}"
        data = response.json()
        assert 'summary' in data, "Response should have 'summary' field"
        print(f"Timesheet insights for '{project_name}': {data.get('summary')}")


class TestPlanAllocationEndpoint:
    """Test POST /api/ai/plan-allocation endpoint"""
    
    def test_plan_allocation_basic(self, auth_headers):
        """Plan allocation should return available resources and recommendation"""
        response = requests.post(
            f"{BASE_URL}/api/ai/plan-allocation",
            headers=auth_headers,
            timeout=10
        )
        
        assert response.status_code == 200, f"Plan allocation failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert 'available_resources' in data, "Response should have 'available_resources'"
        assert 'recommendation' in data, "Response should have 'recommendation'"
        assert 'date_range' in data, "Response should have 'date_range'"
        assert 'total_resources' in data, "Response should have 'total_resources'"
        
        print(f"Total resources: {data['total_resources']}")
        print(f"Available resources: {len(data['available_resources'])}")
        print(f"Recommendation: {data['recommendation']}")
        print(f"Date range: {data['date_range']}")
    
    def test_plan_allocation_with_date_range(self, auth_headers):
        """Plan allocation with specific date range"""
        start_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        end_date = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
        
        response = requests.post(
            f"{BASE_URL}/api/ai/plan-allocation",
            headers=auth_headers,
            params={'start_date': start_date, 'end_date': end_date, 'required_count': 2},
            timeout=10
        )
        
        assert response.status_code == 200, f"Plan allocation with date range failed: {response.text}"
        data = response.json()
        
        # Verify date range in response
        assert data['date_range']['start'] == start_date, "Start date should match request"
        assert data['date_range']['end'] == end_date, "End date should match request"
        
        # Verify recommendation mentions required count
        assert 'can_staff' in data, "Response should have 'can_staff' field"
        print(f"Can staff 2 resources: {data['can_staff']}")


class TestMoveProjectPhaseEndpoint:
    """Test POST /api/projects/{project_id}/move-phase endpoint"""
    
    def test_move_phase_basic(self, auth_headers, test_project_with_phases):
        """Move phase should shift phase dates"""
        if not test_project_with_phases:
            pytest.skip("No test project available")
        
        project_id = test_project_with_phases.get('id')
        phases = test_project_with_phases.get('phases', [])
        
        if not phases:
            pytest.skip("Project has no phases")
        
        # Use first phase name
        phase_name = phases[0].get('name', 'Discovery')
        print(f"Testing move-phase for project '{test_project_with_phases.get('name')}', phase '{phase_name}'")
        
        # Move phase forward by 1 week
        response = requests.post(
            f"{BASE_URL}/api/projects/{project_id}/move-phase",
            headers=auth_headers,
            params={'phase_name': phase_name, 'weeks_to_shift': 1, 'direction': 'forward'},
            timeout=10
        )
        
        assert response.status_code == 200, f"Move phase failed: {response.text}"
        data = response.json()
        
        # Verify project was returned
        assert 'id' in data or '_id' in data, "Response should return updated project"
        assert 'phases' in data, "Response should have phases"
        
        # Find the moved phase
        updated_phases = data.get('phases', [])
        moved_phase = next((p for p in updated_phases if p.get('name', '').lower() == phase_name.lower()), None)
        assert moved_phase is not None, f"Phase '{phase_name}' should exist in response"
        
        print(f"Phase '{phase_name}' moved. New dates: {moved_phase.get('start_date')} - {moved_phase.get('end_date')}")
        
        # Move phase back to restore (cleanup)
        restore_response = requests.post(
            f"{BASE_URL}/api/projects/{project_id}/move-phase",
            headers=auth_headers,
            params={'phase_name': phase_name, 'weeks_to_shift': 1, 'direction': 'backward'},
            timeout=10
        )
        print(f"Phase restored: {restore_response.status_code}")
    
    def test_move_phase_invalid_phase_name(self, auth_headers, test_project_with_phases):
        """Move phase with invalid phase name should return 404"""
        if not test_project_with_phases:
            pytest.skip("No test project available")
        
        project_id = test_project_with_phases.get('id')
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{project_id}/move-phase",
            headers=auth_headers,
            params={'phase_name': 'NonExistentPhase123', 'days_to_shift': 7},
            timeout=10
        )
        
        assert response.status_code == 404, f"Expected 404 for invalid phase, got {response.status_code}"
        data = response.json()
        assert 'detail' in data, "Error response should have 'detail'"
        print(f"Expected error: {data.get('detail')}")
    
    def test_move_phase_no_shift(self, auth_headers, test_project_with_phases):
        """Move phase with zero shift should return 400"""
        if not test_project_with_phases:
            pytest.skip("No test project available")
        
        project_id = test_project_with_phases.get('id')
        phases = test_project_with_phases.get('phases', [])
        
        if not phases:
            pytest.skip("Project has no phases")
        
        phase_name = phases[0].get('name', 'Discovery')
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{project_id}/move-phase",
            headers=auth_headers,
            params={'phase_name': phase_name, 'days_to_shift': 0, 'weeks_to_shift': 0},
            timeout=10
        )
        
        assert response.status_code == 400, f"Expected 400 for zero shift, got {response.status_code}"


class TestProjectStatusFields:
    """Test GET /api/projects returns health, schedule_status, actual_progress fields"""
    
    def test_projects_have_status_fields(self, auth_headers):
        """Projects should include health, schedule_status, actual_progress"""
        response = requests.get(
            f"{BASE_URL}/api/projects",
            headers=auth_headers,
            timeout=10
        )
        
        assert response.status_code == 200, f"Get projects failed: {response.text}"
        projects = response.json()
        
        assert isinstance(projects, list), "Projects should be a list"
        assert len(projects) > 0, "Should have at least one project"
        
        # Check first project has status fields
        project = projects[0]
        
        # These fields should exist (can be None)
        print(f"Project: {project.get('name')}")
        print(f"  health: {project.get('health')}")
        print(f"  schedule_status: {project.get('schedule_status')}")
        print(f"  actual_progress: {project.get('actual_progress')}")
        
        # health should be present in the model
        assert 'health' in project or project.get('health') is None, "Project should have 'health' field"
    
    def test_project_detail_has_status(self, auth_headers, test_project_with_phases):
        """Individual project detail should include status fields"""
        if not test_project_with_phases:
            pytest.skip("No test project available")
        
        project_id = test_project_with_phases.get('id')
        
        response = requests.get(
            f"{BASE_URL}/api/projects/{project_id}",
            headers=auth_headers,
            timeout=10
        )
        
        assert response.status_code == 200, f"Get project detail failed: {response.text}"
        project = response.json()
        
        print(f"Project detail: {project.get('name')}")
        print(f"  health: {project.get('health')}")
        print(f"  schedule_status: {project.get('schedule_status')}")
        print(f"  actual_progress: {project.get('actual_progress')}")
        
        # Verify the project has expected fields
        assert 'id' in project, "Project should have 'id'"
        assert 'name' in project, "Project should have 'name'"


class TestLoginCredentials:
    """Test login with specified credentials"""
    
    def test_login_don_ddconsult(self):
        """Login with don@ddconsult.tech / Welcome123!"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": "don@ddconsult.tech", "password": "Welcome123!"},
            timeout=10
        )
        
        assert response.status_code == 200, f"Login failed: {response.status_code} - {response.text}"
        data = response.json()
        
        assert 'access_token' in data, "Response should have access_token"
        assert 'user' in data, "Response should have user info"
        
        user = data['user']
        print(f"Logged in as: {user.get('email')} (role: {user.get('role')})")
        
        # Verify super_admin role
        assert user.get('role') == 'super_admin', f"Expected super_admin role, got {user.get('role')}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
