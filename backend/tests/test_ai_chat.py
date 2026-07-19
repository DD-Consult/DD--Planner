"""
Test AI Chat Agent Feature - Iteration 14
Tests the new AI chatbot slide-out panel feature including:
- POST /api/ai/chat - Send chat message
- GET /api/ai/chat/sessions - Get user's chat sessions
- GET /api/ai/chat/sessions/{id} - Get specific session with messages
- DELETE /api/ai/chat/sessions/{id} - Delete a session
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from iteration 13
SUPER_ADMIN_EMAIL = "don@ddconsult.tech"
SUPER_ADMIN_PASSWORD = "Welcome123!"
RESOURCE_EMAIL = "henry@ddconsult.tech"
RESOURCE_PASSWORD = "Welcome123!"


class TestAIChatBackend:
    """AI Chat Agent backend API tests"""
    
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
        return {"Authorization": f"Bearer {auth_token}"}
    
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
        assert data["user"]["role"] == "super_admin"
        print(f"✓ Super admin login successful: {SUPER_ADMIN_EMAIL}")
    
    def test_02_send_chat_message_new_session(self, auth_headers):
        """Test sending a chat message creates a new session"""
        response = requests.post(
            f"{BASE_URL}/api/ai/chat",
            json={"message": "Which projects are at risk?", "session_id": None},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Chat failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "session_id" in data, "Response should contain session_id"
        assert "response" in data, "Response should contain AI response"
        assert "message_count" in data, "Response should contain message_count"
        
        # Verify message count (should be 2: user + assistant)
        assert data["message_count"] >= 2, f"Expected at least 2 messages, got {data['message_count']}"
        
        # Verify AI response is not empty
        assert len(data["response"]) > 10, "AI response should not be empty"
        
        print(f"✓ Chat message sent, session_id: {data['session_id']}")
        print(f"  AI Response preview: {data['response'][:100]}...")
        
        # Store session_id for later tests
        TestAIChatBackend.created_session_id = data["session_id"]
    
    def test_03_send_followup_message(self, auth_headers):
        """Test sending a follow-up message to existing session (multi-turn)"""
        session_id = getattr(TestAIChatBackend, 'created_session_id', None)
        assert session_id, "No session_id from previous test"
        
        response = requests.post(
            f"{BASE_URL}/api/ai/chat",
            json={"message": "Tell me more about the first one", "session_id": session_id},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Follow-up chat failed: {response.text}"
        data = response.json()
        
        # Verify same session is used
        assert data["session_id"] == session_id, "Should use same session"
        
        # Verify message count increased (should be 4 now: 2 user + 2 assistant)
        assert data["message_count"] >= 4, f"Expected at least 4 messages, got {data['message_count']}"
        
        print(f"✓ Follow-up message sent, message_count: {data['message_count']}")
        print(f"  AI Response preview: {data['response'][:100]}...")
    
    def test_04_get_chat_sessions(self, auth_headers):
        """Test getting user's chat sessions list"""
        response = requests.get(
            f"{BASE_URL}/api/ai/chat/sessions",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get sessions failed: {response.text}"
        data = response.json()
        
        # Should be a list
        assert isinstance(data, list), "Response should be a list"
        
        # Should have at least one session (from previous tests)
        assert len(data) >= 1, "Should have at least one session"
        
        # Verify session structure
        session = data[0]
        assert "id" in session, "Session should have id"
        assert "user_email" in session, "Session should have user_email"
        assert "created_at" in session, "Session should have created_at"
        
        print(f"✓ Got {len(data)} chat sessions")
    
    def test_05_get_specific_session(self, auth_headers):
        """Test getting a specific session with full message history"""
        session_id = getattr(TestAIChatBackend, 'created_session_id', None)
        assert session_id, "No session_id from previous test"
        
        response = requests.get(
            f"{BASE_URL}/api/ai/chat/sessions/{session_id}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get session failed: {response.text}"
        data = response.json()
        
        # Verify session structure
        assert "id" in data, "Session should have id"
        assert "messages" in data, "Session should have messages"
        assert "user_email" in data, "Session should have user_email"
        
        # Verify messages
        messages = data["messages"]
        assert isinstance(messages, list), "Messages should be a list"
        assert len(messages) >= 4, f"Expected at least 4 messages, got {len(messages)}"
        
        # Verify message structure
        for msg in messages:
            assert "role" in msg, "Message should have role"
            assert "content" in msg, "Message should have content"
            assert msg["role"] in ["user", "assistant"], f"Invalid role: {msg['role']}"
        
        print(f"✓ Got session with {len(messages)} messages")
    
    def test_06_delete_session(self, auth_headers):
        """Test deleting a chat session"""
        session_id = getattr(TestAIChatBackend, 'created_session_id', None)
        assert session_id, "No session_id from previous test"
        
        response = requests.delete(
            f"{BASE_URL}/api/ai/chat/sessions/{session_id}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Delete session failed: {response.text}"
        data = response.json()
        assert "message" in data, "Response should have message"
        
        print(f"✓ Session deleted: {session_id}")
        
        # Verify session is gone
        response = requests.get(
            f"{BASE_URL}/api/ai/chat/sessions/{session_id}",
            headers=auth_headers
        )
        assert response.status_code == 404, "Deleted session should return 404"
        print("✓ Verified session no longer exists")
    
    def test_07_chat_without_auth(self):
        """Test that chat requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/ai/chat",
            json={"message": "Hello", "session_id": None}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Chat correctly requires authentication")
    
    def test_08_get_sessions_without_auth(self):
        """Test that getting sessions requires authentication"""
        response = requests.get(f"{BASE_URL}/api/ai/chat/sessions")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Get sessions correctly requires authentication")


class TestResourceUserChat:
    """Test that resource users can also use chat"""
    
    @pytest.fixture(scope="class")
    def resource_auth_headers(self):
        """Get authentication token for resource user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": RESOURCE_EMAIL, "password": RESOURCE_PASSWORD}
        )
        # Try alternate password if first fails
        if response.status_code != 200:
            response = requests.post(
                f"{BASE_URL}/api/auth/login",
                data={"username": RESOURCE_EMAIL, "password": "Welcome123!New"}
            )
        assert response.status_code == 200, f"Resource login failed: {response.text}"
        return {"Authorization": f"Bearer {response.json()['access_token']}"}
    
    def test_resource_user_can_chat(self, resource_auth_headers):
        """Test that resource users can use the chat feature"""
        response = requests.post(
            f"{BASE_URL}/api/ai/chat",
            json={"message": "What projects am I assigned to?", "session_id": None},
            headers=resource_auth_headers
        )
        assert response.status_code == 200, f"Resource user chat failed: {response.text}"
        data = response.json()
        
        assert "session_id" in data
        assert "response" in data
        assert len(data["response"]) > 10
        
        print(f"✓ Resource user can use chat")
        print(f"  AI Response preview: {data['response'][:100]}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
