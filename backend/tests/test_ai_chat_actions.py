"""
Test AI Chat Execute-Action Feature - Iteration 15
Tests the new inline action execution feature including:
- POST /api/ai/chat/execute-action with set_project_lead action
- POST /api/ai/chat/execute-action with create_allocation action
- POST /api/ai/chat/execute-action with add_risk action
- POST /api/ai/chat/execute-action with update_project_status action
- Verify project_lead_id is optional (existing projects without lead don't crash)
- GET /api/projects returns all projects for admin even without project_lead_id
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "don@ddconsult.tech"
SUPER_ADMIN_PASSWORD = "Welcome123!"

# Test data IDs (from database)
AMRIT_RESOURCE_ID = "698c7799eea263b28c2715af"  # Amrit
ASKDD_PROJECT_ID = "698c7799eea263b28c2715b3"  # ASKDD Chatbot
ELLERSTON_PROJECT_ID = "698c7799eea263b28c2715b4"  # Ellerston Digitisation (no lead)
WEBSITE_PROJECT_ID = "698c7799eea263b28c2715b5"  # Website Redesign


class TestExecuteActionBackend:
    """AI Chat Execute-Action backend API tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for super admin"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get auth headers"""
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_01_login_super_admin(self):
        """Test super admin login works"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == SUPER_ADMIN_EMAIL
        print(f"✓ Super admin login successful: {SUPER_ADMIN_EMAIL}")
    
    def test_02_execute_set_project_lead(self, auth_headers):
        """Test execute-action with set_project_lead action"""
        action = {
            "action": "set_project_lead",
            "project_id": ELLERSTON_PROJECT_ID,
            "resource_id": AMRIT_RESOURCE_ID,
            "description": "Set Amrit as lead for Ellerston Digitisation"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/ai/chat/execute-action",
            json=action,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Execute action failed: {response.text}"
        data = response.json()
        
        assert data["success"] == True, f"Action should succeed: {data}"
        assert "message" in data
        print(f"✓ set_project_lead action executed: {data['message']}")
        
        # Verify the project lead was actually set
        response = requests.get(
            f"{BASE_URL}/api/projects/{ELLERSTON_PROJECT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        project = response.json()
        assert project["project_lead_id"] == AMRIT_RESOURCE_ID, "Project lead should be updated"
        print(f"✓ Verified project lead is now Amrit")
    
    def test_03_execute_create_allocation(self, auth_headers):
        """Test execute-action with create_allocation action"""
        start_date = datetime.now().strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        action = {
            "action": "create_allocation",
            "resource_id": AMRIT_RESOURCE_ID,
            "project_id": WEBSITE_PROJECT_ID,
            "percentage": 50,
            "start_date": start_date,
            "end_date": end_date,
            "description": "Assign Amrit to Website Redesign at 50%"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/ai/chat/execute-action",
            json=action,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Execute action failed: {response.text}"
        data = response.json()
        
        assert data["success"] == True, f"Action should succeed: {data}"
        assert "id" in data, "Should return allocation ID"
        print(f"✓ create_allocation action executed: {data['message']}, id: {data['id']}")
        
        # Store allocation ID for cleanup
        TestExecuteActionBackend.created_allocation_id = data["id"]
    
    def test_04_execute_add_risk(self, auth_headers):
        """Test execute-action with add_risk action"""
        action = {
            "action": "add_risk",
            "project_id": ASKDD_PROJECT_ID,
            "description": "TEST_RISK: Potential delay due to resource constraints",
            "impact": "High",
            "probability": "Medium",
            "summary": "Resource constraint risk"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/ai/chat/execute-action",
            json=action,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Execute action failed: {response.text}"
        data = response.json()
        
        assert data["success"] == True, f"Action should succeed: {data}"
        assert "id" in data, "Should return risk ID"
        print(f"✓ add_risk action executed: {data['message']}, id: {data['id']}")
        
        # Store risk ID for cleanup
        TestExecuteActionBackend.created_risk_id = data["id"]
    
    def test_05_execute_update_project_status(self, auth_headers):
        """Test execute-action with update_project_status action"""
        action = {
            "action": "update_project_status",
            "project_id": WEBSITE_PROJECT_ID,
            "status": "Active",
            "description": "Update Website Redesign status to Active"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/ai/chat/execute-action",
            json=action,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Execute action failed: {response.text}"
        data = response.json()
        
        assert data["success"] == True, f"Action should succeed: {data}"
        print(f"✓ update_project_status action executed: {data['message']}")
        
        # Verify the status was updated
        response = requests.get(
            f"{BASE_URL}/api/projects/{WEBSITE_PROJECT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        project = response.json()
        assert project["status"] == "Active", "Project status should be Active"
        print(f"✓ Verified project status is Active")
    
    def test_06_execute_unknown_action(self, auth_headers):
        """Test execute-action with unknown action type"""
        action = {
            "action": "unknown_action",
            "project_id": ASKDD_PROJECT_ID
        }
        
        response = requests.post(
            f"{BASE_URL}/api/ai/chat/execute-action",
            json=action,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Request should not fail: {response.text}"
        data = response.json()
        
        assert data["success"] == False, "Unknown action should fail"
        assert "Unknown action" in data["message"]
        print(f"✓ Unknown action correctly rejected: {data['message']}")
    
    def test_07_projects_without_lead_dont_crash(self, auth_headers):
        """Test that GET /api/projects returns all projects even without project_lead_id"""
        response = requests.get(
            f"{BASE_URL}/api/projects",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get projects failed: {response.text}"
        projects = response.json()
        
        assert isinstance(projects, list), "Response should be a list"
        assert len(projects) > 0, "Should have projects"
        
        # Count projects with and without leads
        with_lead = sum(1 for p in projects if p.get("project_lead_id"))
        without_lead = sum(1 for p in projects if not p.get("project_lead_id"))
        
        print(f"✓ GET /api/projects returns {len(projects)} projects")
        print(f"  - With lead: {with_lead}")
        print(f"  - Without lead: {without_lead}")
        
        # Verify structure - project_lead_id should be optional
        for p in projects:
            assert "id" in p, "Project should have id"
            assert "name" in p, "Project should have name"
            # project_lead_id can be null/None - this is the key test
    
    def test_08_execute_action_without_auth(self):
        """Test that execute-action requires authentication"""
        action = {
            "action": "set_project_lead",
            "project_id": ASKDD_PROJECT_ID,
            "resource_id": AMRIT_RESOURCE_ID
        }
        
        response = requests.post(
            f"{BASE_URL}/api/ai/chat/execute-action",
            json=action
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Execute-action correctly requires authentication")
    
    def test_09_cleanup_test_data(self, auth_headers):
        """Cleanup test-created data"""
        # Delete created allocation
        alloc_id = getattr(TestExecuteActionBackend, 'created_allocation_id', None)
        if alloc_id:
            response = requests.delete(
                f"{BASE_URL}/api/allocations/{alloc_id}",
                headers=auth_headers
            )
            if response.status_code == 200:
                print(f"✓ Cleaned up test allocation: {alloc_id}")
        
        # Reset project lead on Ellerston (set back to null)
        response = requests.put(
            f"{BASE_URL}/api/projects/{ELLERSTON_PROJECT_ID}",
            json={"project_lead_id": None},
            headers=auth_headers
        )
        if response.status_code == 200:
            print(f"✓ Reset Ellerston project lead to null")
        
        print("✓ Test cleanup completed")


class TestAIChatWithActions:
    """Test AI Chat that returns action blocks"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authentication token for super admin"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_chat_analysis_query(self, auth_headers):
        """Test sending an analysis query to AI chat"""
        response = requests.post(
            f"{BASE_URL}/api/ai/chat",
            json={"message": "Which projects are at risk?", "session_id": None},
            headers=auth_headers,
            timeout=30
        )
        assert response.status_code == 200, f"Chat failed: {response.text}"
        data = response.json()
        
        assert "session_id" in data
        assert "response" in data
        assert len(data["response"]) > 10, "AI should provide analysis"
        
        print(f"✓ AI analysis query successful")
        print(f"  Response preview: {data['response'][:150]}...")
    
    def test_chat_action_query(self, auth_headers):
        """Test sending an action query to AI chat (may or may not return action block)"""
        response = requests.post(
            f"{BASE_URL}/api/ai/chat",
            json={"message": "Set Amrit as lead for ASKDD Chatbot project", "session_id": None},
            headers=auth_headers,
            timeout=30
        )
        assert response.status_code == 200, f"Chat failed: {response.text}"
        data = response.json()
        
        assert "session_id" in data
        assert "response" in data
        
        # Check if response contains action block
        if "```action" in data["response"]:
            print(f"✓ AI returned action block in response")
        else:
            print(f"✓ AI responded (no action block - AI decides based on context)")
        
        print(f"  Response preview: {data['response'][:200]}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
