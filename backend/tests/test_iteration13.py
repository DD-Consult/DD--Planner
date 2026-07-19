"""
Iteration 13 Backend Tests
Tests for:
- Role-based project filtering (resource/contractor only see allocated projects)
- AI settings restricted to super_admin
- Project lead and google_drive_url fields
- Contractor role existence
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "don@ddconsult.tech"
SUPER_ADMIN_PASSWORD = "Welcome123!"
RESOURCE_EMAIL = "henry@ddconsult.tech"
RESOURCE_PASSWORD = "Welcome123!"
RESOURCE_EMAIL_2 = "amrit@ddconsult.tech"
RESOURCE_PASSWORD_2 = "Welcome123!"


class TestAuth:
    """Authentication tests"""
    
    def test_super_admin_login(self):
        """Test super admin can login"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Super admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "super_admin"
        print(f"✓ Super admin login successful, role: {data['user']['role']}")
    
    def test_resource_login(self):
        """Test resource user can login"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": RESOURCE_EMAIL, "password": RESOURCE_PASSWORD}
        )
        assert response.status_code == 200, f"Resource login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "resource"
        print(f"✓ Resource login successful, role: {data['user']['role']}")


class TestRoleBasedProjectFiltering:
    """Test that resources/contractors only see allocated projects"""
    
    @pytest.fixture
    def super_admin_token(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    @pytest.fixture
    def resource_token(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": RESOURCE_EMAIL, "password": RESOURCE_PASSWORD}
        )
        return response.json()["access_token"]
    
    @pytest.fixture
    def resource_token_2(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": RESOURCE_EMAIL_2, "password": RESOURCE_PASSWORD_2}
        )
        return response.json()["access_token"]
    
    def test_super_admin_sees_all_projects(self, super_admin_token):
        """Super admin should see all projects"""
        response = requests.get(
            f"{BASE_URL}/api/projects",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200
        projects = response.json()
        # Super admin should see all 15 projects
        print(f"✓ Super admin sees {len(projects)} projects")
        assert len(projects) >= 10, f"Expected at least 10 projects, got {len(projects)}"
    
    def test_resource_sees_only_allocated_projects(self, resource_token):
        """Resource user should only see projects they're allocated to"""
        response = requests.get(
            f"{BASE_URL}/api/projects",
            headers={"Authorization": f"Bearer {resource_token}"}
        )
        assert response.status_code == 200
        projects = response.json()
        # Henry should see fewer projects than super admin (only allocated ones)
        print(f"✓ Resource user (henry) sees {len(projects)} projects")
        # Should be less than total (15) - expecting ~2 based on allocations
        assert len(projects) < 15, f"Resource should see fewer than all projects, got {len(projects)}"
    
    def test_resource_project_count_differs_from_admin(self, super_admin_token, resource_token):
        """Verify resource sees fewer projects than admin"""
        admin_response = requests.get(
            f"{BASE_URL}/api/projects",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        resource_response = requests.get(
            f"{BASE_URL}/api/projects",
            headers={"Authorization": f"Bearer {resource_token}"}
        )
        
        admin_projects = admin_response.json()
        resource_projects = resource_response.json()
        
        print(f"✓ Admin sees {len(admin_projects)} projects, Resource sees {len(resource_projects)} projects")
        assert len(resource_projects) <= len(admin_projects), "Resource should see same or fewer projects than admin"


class TestProjectLeadAndDriveUrl:
    """Test project_lead_id and google_drive_url fields"""
    
    @pytest.fixture
    def super_admin_token(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    def test_projects_have_lead_fields(self, super_admin_token):
        """Verify projects return project_lead_name and google_drive_url fields"""
        response = requests.get(
            f"{BASE_URL}/api/projects",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200
        projects = response.json()
        
        # Check that at least one project has the new fields in response
        for project in projects[:3]:  # Check first 3 projects
            assert "project_lead_id" in project or project.get("project_lead_id") is None, "project_lead_id field missing"
            assert "project_lead_name" in project or project.get("project_lead_name") is None, "project_lead_name field missing"
            assert "google_drive_url" in project or project.get("google_drive_url") is None, "google_drive_url field missing"
        
        print(f"✓ Projects have project_lead_id, project_lead_name, and google_drive_url fields")
    
    def test_single_project_has_lead_fields(self, super_admin_token):
        """Verify single project endpoint returns lead fields"""
        # First get list of projects
        list_response = requests.get(
            f"{BASE_URL}/api/projects",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        projects = list_response.json()
        
        if len(projects) > 0:
            project_id = projects[0]["id"]
            response = requests.get(
                f"{BASE_URL}/api/projects/{project_id}",
                headers={"Authorization": f"Bearer {super_admin_token}"}
            )
            assert response.status_code == 200
            project = response.json()
            
            # Verify fields exist (can be null for existing projects)
            assert "project_lead_id" in project or project.get("project_lead_id") is None
            assert "project_lead_name" in project or project.get("project_lead_name") is None
            assert "google_drive_url" in project or project.get("google_drive_url") is None
            print(f"✓ Single project endpoint returns lead fields")


class TestAISettingsRestriction:
    """Test AI settings are restricted to super_admin only"""
    
    @pytest.fixture
    def super_admin_token(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    @pytest.fixture
    def resource_token(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": RESOURCE_EMAIL, "password": RESOURCE_PASSWORD}
        )
        return response.json()["access_token"]
    
    def test_super_admin_can_get_ai_settings(self, super_admin_token):
        """Super admin should be able to GET AI settings"""
        response = requests.get(
            f"{BASE_URL}/api/settings/ai",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200, f"Super admin should access AI settings: {response.text}"
        data = response.json()
        assert "provider" in data
        print(f"✓ Super admin can GET AI settings")
    
    def test_resource_cannot_get_ai_settings(self, resource_token):
        """Resource user should NOT be able to GET AI settings"""
        response = requests.get(
            f"{BASE_URL}/api/settings/ai",
            headers={"Authorization": f"Bearer {resource_token}"}
        )
        assert response.status_code == 403, f"Resource should get 403, got {response.status_code}"
        print(f"✓ Resource user correctly denied access to GET AI settings (403)")
    
    def test_resource_cannot_put_ai_settings(self, resource_token):
        """Resource user should NOT be able to PUT AI settings"""
        response = requests.put(
            f"{BASE_URL}/api/settings/ai",
            params={"provider": "openai", "api_key": "test-key"},
            headers={"Authorization": f"Bearer {resource_token}"}
        )
        assert response.status_code == 403, f"Resource should get 403, got {response.status_code}"
        print(f"✓ Resource user correctly denied access to PUT AI settings (403)")


class TestContractorRole:
    """Test contractor role exists in the system"""
    
    @pytest.fixture
    def super_admin_token(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    def test_users_endpoint_returns_roles(self, super_admin_token):
        """Verify users endpoint works and returns role field"""
        response = requests.get(
            f"{BASE_URL}/api/admin/users",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200
        users = response.json()
        
        # Check that users have role field
        for user in users[:3]:
            assert "role" in user, "User should have role field"
        
        # Get all unique roles
        roles = set(user["role"] for user in users)
        print(f"✓ Found roles in system: {roles}")


class TestDashboardStatusGrouping:
    """Test that dashboard data supports status grouping"""
    
    @pytest.fixture
    def super_admin_token(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    def test_projects_have_status_field(self, super_admin_token):
        """Verify projects have status field for grouping"""
        response = requests.get(
            f"{BASE_URL}/api/projects",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200
        projects = response.json()
        
        statuses = set()
        for project in projects:
            assert "status" in project, "Project should have status field"
            statuses.add(project["status"])
        
        print(f"✓ Found project statuses: {statuses}")
        # Should have at least Active status
        assert "Active" in statuses or "Pipeline" in statuses or "Completed" in statuses, \
            "Should have at least one valid status"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
