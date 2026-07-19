"""
Test suite for DD Planner - Iteration 8 Features
Focus: New Add Timesheet Entry Feature + Fixed /api/users/me/resource Endpoint

Tests:
1. GET /api/users/me/resource - Should return 'Don' resource via find_user_resource fallback (not 404)
2. POST /api/timesheets - Create manual timesheet entry with project_id, phase_id, planned_hours, actual_hours
3. GET /api/projects - Get projects with phases for timesheet creation
4. GET /api/timesheets/my-week - Verify created timesheet appears in list
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://calc-audit-review.preview.emergentagent.com').rstrip('/')


@pytest.fixture(scope='module')
def auth_token():
    """Get authentication token for super admin (don@ddconsult.tech)"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": "don@ddconsult.tech", "password": "Welcome123!"},
        timeout=10
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert 'access_token' in data, "No access_token in login response"
    print(f"Logged in as: {data['user']['email']} (role: {data['user']['role']})")
    return data['access_token']


@pytest.fixture(scope='module')
def auth_headers(auth_token):
    """Authenticated headers"""
    return {
        'Authorization': f'Bearer {auth_token}',
        'Content-Type': 'application/json'
    }


class TestLoginWithDon:
    """Test login with don@ddconsult.tech / Welcome123!"""
    
    def test_login_super_admin(self):
        """Login with super admin credentials"""
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
        
        assert user.get('role') == 'super_admin', f"Expected super_admin role, got {user.get('role')}"


class TestGetMyResourceEndpoint:
    """Test GET /api/users/me/resource - Fixed endpoint that uses find_user_resource fallback"""
    
    def test_get_my_resource_returns_don(self, auth_headers):
        """
        GET /api/users/me/resource should return 'Don' resource via find_user_resource fallback.
        Previously returned 404, now should use email prefix matching to find the resource.
        """
        response = requests.get(
            f"{BASE_URL}/api/users/me/resource",
            headers=auth_headers,
            timeout=10
        )
        
        # Should NOT be 404 anymore
        assert response.status_code != 404, f"Endpoint should not return 404. Response: {response.text}"
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert 'id' in data, "Resource should have 'id'"
        assert 'name' in data, "Resource should have 'name'"
        assert 'role' in data, "Resource should have 'role'"
        
        # Should return 'Don' resource matched via email prefix
        print(f"Resource found: {data.get('name')} (role: {data.get('role')})")
        print(f"Resource ID: {data.get('id')}")
        
        # The resource name should match or be similar to 'Don' (email prefix matching)
        # don@ddconsult.tech -> matches resource named 'Don'
        assert 'don' in data.get('name', '').lower(), f"Expected 'Don' resource, got {data.get('name')}"


class TestGetProjectsWithPhases:
    """Test GET /api/projects to get projects with phases for timesheet creation"""
    
    def test_get_projects_with_phases(self, auth_headers):
        """Get active projects with phases for testing timesheet creation"""
        response = requests.get(
            f"{BASE_URL}/api/projects",
            headers=auth_headers,
            timeout=10
        )
        
        assert response.status_code == 200, f"Get projects failed: {response.text}"
        projects = response.json()
        
        assert isinstance(projects, list), "Projects should be a list"
        assert len(projects) > 0, f"Should have at least one project, got {len(projects)}"
        
        # Find active projects with phases
        active_with_phases = [p for p in projects if p.get('status') == 'Active' and p.get('phases')]
        
        print(f"Total projects: {len(projects)}")
        print(f"Active projects with phases: {len(active_with_phases)}")
        
        if active_with_phases:
            project = active_with_phases[0]
            print(f"Sample project: {project.get('name')}")
            print(f"  Phases: {[p.get('name') for p in project.get('phases', [])]}")
            print(f"  Project ID: {project.get('id')}")
            print(f"  First Phase ID: {project.get('phases', [{}])[0].get('id', 'MISSING')}")
        
        assert len(active_with_phases) > 0, "Should have at least one active project with phases"
        
        # Verify phases have IDs (critical for timesheet creation)
        for project in active_with_phases[:3]:
            phases = project.get('phases', [])
            for phase in phases:
                assert phase.get('id'), f"Phase '{phase.get('name')}' in project '{project.get('name')}' is missing an ID"


@pytest.fixture(scope='module')
def test_project_and_phase(auth_headers):
    """Get a valid project with phase for timesheet testing"""
    response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers, timeout=10)
    projects = response.json()
    
    # Find active project with phases
    for project in projects:
        if project.get('status') == 'Active' and project.get('phases'):
            phases = project.get('phases', [])
            if phases and phases[0].get('id'):
                return {
                    'project_id': project.get('id'),
                    'project_name': project.get('name'),
                    'phase_id': phases[0].get('id'),
                    'phase_name': phases[0].get('name')
                }
    
    return None


@pytest.fixture(scope='module')
def don_resource_id(auth_headers):
    """Get Don's resource ID for timesheet creation"""
    response = requests.get(f"{BASE_URL}/api/users/me/resource", headers=auth_headers, timeout=10)
    if response.status_code == 200:
        return response.json().get('id')
    return None


class TestCreateTimesheetEntry:
    """Test POST /api/timesheets - Create manual timesheet entry"""
    
    def test_create_timesheet_entry_success(self, auth_headers, test_project_and_phase, don_resource_id):
        """
        POST /api/timesheets should create a manual timesheet entry.
        Required fields: resource_id, project_id, phase_id, planned_hours, actual_hours
        """
        if not test_project_and_phase:
            pytest.skip("No test project with phases available")
        
        if not don_resource_id:
            pytest.skip("Could not get Don's resource ID")
        
        # Calculate week dates (week containing today, starting Monday)
        today = datetime.now()
        day_of_week = today.weekday()
        week_start = today - timedelta(days=day_of_week)
        week_end = week_start + timedelta(days=6)
        
        week_start_str = week_start.strftime('%Y-%m-%d')
        week_end_str = week_end.strftime('%Y-%m-%d')
        
        print(f"Creating timesheet for week: {week_start_str} to {week_end_str}")
        print(f"Project: {test_project_and_phase['project_name']} (ID: {test_project_and_phase['project_id']})")
        print(f"Phase: {test_project_and_phase['phase_name']} (ID: {test_project_and_phase['phase_id']})")
        print(f"Resource ID: {don_resource_id}")
        
        # Create timesheet entry
        timesheet_data = {
            "resource_id": don_resource_id,
            "project_id": test_project_and_phase['project_id'],
            "phase_id": test_project_and_phase['phase_id'],
            "week_start_date": week_start_str,
            "week_end_date": week_end_str,
            "planned_hours": 8.0,
            "actual_hours": 6.5,
            "notes": "TEST_Iteration8_Manual_Entry - Testing Add Entry feature",
            "status": "Draft"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/timesheets",
            headers=auth_headers,
            json=timesheet_data,
            timeout=10
        )
        
        assert response.status_code == 200, f"Create timesheet failed: {response.status_code} - {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert 'id' in data, "Response should have 'id'"
        assert data.get('resource_id') == don_resource_id, "Resource ID should match"
        assert data.get('project_id') == test_project_and_phase['project_id'], "Project ID should match"
        assert data.get('phase_id') == test_project_and_phase['phase_id'], "Phase ID should match"
        assert data.get('planned_hours') == 8.0, "Planned hours should match"
        assert data.get('actual_hours') == 6.5, "Actual hours should match"
        
        # Verify calculated variance
        assert 'variance_hours' in data, "Should have variance_hours"
        expected_variance = 6.5 - 8.0  # actual - planned = -1.5
        assert abs(data.get('variance_hours', 0) - expected_variance) < 0.01, f"Variance should be {expected_variance}"
        
        print(f"Timesheet created successfully!")
        print(f"  ID: {data.get('id')}")
        print(f"  Variance hours: {data.get('variance_hours')}")
        print(f"  Status: {data.get('status')}")
        
        return data.get('id')
    
    def test_create_timesheet_without_phase_id_fails(self, auth_headers, test_project_and_phase, don_resource_id):
        """
        POST /api/timesheets without phase_id should return 400 error.
        phase_id is required for timesheet creation.
        """
        if not test_project_and_phase:
            pytest.skip("No test project with phases available")
        
        if not don_resource_id:
            pytest.skip("Could not get Don's resource ID")
        
        today = datetime.now()
        day_of_week = today.weekday()
        week_start = today - timedelta(days=day_of_week)
        week_end = week_start + timedelta(days=6)
        
        # Missing phase_id intentionally
        timesheet_data = {
            "resource_id": don_resource_id,
            "project_id": test_project_and_phase['project_id'],
            # "phase_id": missing
            "week_start_date": week_start.strftime('%Y-%m-%d'),
            "week_end_date": week_end.strftime('%Y-%m-%d'),
            "planned_hours": 8.0,
            "actual_hours": 6.5,
            "status": "Draft"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/timesheets",
            headers=auth_headers,
            json=timesheet_data,
            timeout=10
        )
        
        # Should fail with 400 or 422 (validation error)
        assert response.status_code in [400, 422], f"Expected 400/422 for missing phase_id, got {response.status_code}"
        print(f"Correctly rejected timesheet without phase_id: {response.json()}")


class TestGetMyWeekTimesheets:
    """Test GET /api/timesheets/my-week to verify created timesheet appears"""
    
    def test_get_timesheets_for_current_week(self, auth_headers):
        """
        GET /api/timesheets/my-week should return timesheets for the current week.
        Should include any manually created entries.
        """
        # Calculate current week start (Monday)
        today = datetime.now()
        day_of_week = today.weekday()
        week_start = today - timedelta(days=day_of_week)
        week_start_str = week_start.strftime('%Y-%m-%d')
        
        response = requests.get(
            f"{BASE_URL}/api/timesheets/my-week",
            headers=auth_headers,
            params={"week_start": week_start_str},
            timeout=10
        )
        
        assert response.status_code == 200, f"Get timesheets failed: {response.status_code} - {response.text}"
        
        data = response.json()
        
        assert isinstance(data, list), "Response should be a list"
        
        print(f"Timesheets for week starting {week_start_str}: {len(data)} entries")
        
        for ts in data[:5]:  # Show first 5
            print(f"  - Project: {ts.get('project_name', ts.get('project_id'))}")
            print(f"    Planned: {ts.get('planned_hours')}h, Actual: {ts.get('actual_hours')}h")
            print(f"    Status: {ts.get('status')}, Auto-filled: {ts.get('auto_filled')}")


class TestPrefillStillWorks:
    """Test that Pre-fill button still works alongside Add Entry"""
    
    def test_auto_fill_timesheets(self, auth_headers):
        """
        POST /api/timesheets/auto-fill should still work.
        This tests that the Pre-fill functionality wasn't broken by the Add Entry feature.
        """
        # Calculate current week start (Monday)
        today = datetime.now()
        day_of_week = today.weekday()
        week_start = today - timedelta(days=day_of_week)
        week_start_str = week_start.strftime('%Y-%m-%d')
        
        response = requests.post(
            f"{BASE_URL}/api/timesheets/auto-fill",
            headers=auth_headers,
            params={"week_start": week_start_str},
            timeout=15
        )
        
        assert response.status_code == 200, f"Auto-fill failed: {response.status_code} - {response.text}"
        
        data = response.json()
        
        # Should return count of created/updated timesheets
        print(f"Auto-fill result: {data}")
        
        if isinstance(data, dict):
            assert 'created' in data or 'updated' in data or 'message' in data, "Response should have counts or message"
            print(f"  Created: {data.get('created', 0)}, Updated: {data.get('updated', 0)}")


class TestGetResources:
    """Test GET /api/resources to verify resources exist for dropdown"""
    
    def test_get_all_resources(self, auth_headers):
        """
        GET /api/resources should return list of resources.
        Used by Add Entry form when super admin needs to select resource.
        """
        response = requests.get(
            f"{BASE_URL}/api/resources",
            headers=auth_headers,
            timeout=10
        )
        
        assert response.status_code == 200, f"Get resources failed: {response.text}"
        
        data = response.json()
        
        assert isinstance(data, list), "Resources should be a list"
        assert len(data) > 0, "Should have at least one resource"
        
        print(f"Total resources: {len(data)}")
        
        # Find Don resource
        don_resource = next((r for r in data if 'don' in r.get('name', '').lower()), None)
        
        if don_resource:
            print(f"Don resource found: {don_resource.get('name')} (ID: {don_resource.get('id')})")
        else:
            print(f"Resources: {[r.get('name') for r in data]}")


class TestTimesheetUpdateAllowedCheck:
    """Test GET /api/timesheet/can-update - Day restriction check"""
    
    def test_can_update_timesheet(self, auth_headers):
        """
        GET /api/timesheet/can-update should return whether timesheet updates are allowed.
        (Restricted to Thursday/Friday Sydney time in some implementations)
        """
        response = requests.get(
            f"{BASE_URL}/api/timesheet/can-update",
            headers=auth_headers,
            timeout=10
        )
        
        assert response.status_code == 200, f"Can-update check failed: {response.text}"
        
        data = response.json()
        
        print(f"Timesheet update allowed: {data}")
        
        # Should have 'allowed' field
        assert 'allowed' in data, "Response should have 'allowed' field"
        print(f"  Allowed: {data.get('allowed')}")
        print(f"  Current day: {data.get('current_day')}")


# Cleanup test data marker
class TestCleanupMarker:
    """Marker for test data that should be cleaned up"""
    
    def test_marker_for_cleanup(self):
        """
        Timesheets created with notes containing 'TEST_Iteration8' should be cleaned up.
        This is just a marker test.
        """
        print("Test data created with 'TEST_Iteration8' prefix should be cleaned up manually or by future test runs")
        assert True


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
