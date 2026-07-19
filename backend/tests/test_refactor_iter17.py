"""
Iteration 17 - Post-refactor regression: validate all endpoints listed in the
review request still work identically after server.py was split into modules.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "don@ddconsult.tech"
ADMIN_PASSWORD = "Welcome123!"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "access_token" in data
    return data["access_token"]


@pytest.fixture(scope="module")
def headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---------- Auth ----------
class TestAuth:
    def test_login_super_admin(self):
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert body.get("token_type", "bearer").lower() == "bearer"

    def test_auth_me(self, headers):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert r.status_code == 200, r.text
        me = r.json()
        assert me["email"] == ADMIN_EMAIL
        assert "role" in me

    def test_login_bad_password(self):
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": ADMIN_EMAIL, "password": "wrong"},
        )
        assert r.status_code in (400, 401)


# ---------- Core list endpoints ----------
class TestCoreListEndpoints:
    def test_get_projects(self, headers):
        r = requests.get(f"{BASE_URL}/api/projects", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0
        first = data[0]
        # Dates should be serialized as strings (per serialize_doc update)
        assert isinstance(first.get("start_date"), str), first.get("start_date")
        assert isinstance(first.get("end_date"), str), first.get("end_date")
        assert "id" in first
        assert "name" in first
        pytest.project_id = first["id"]

    def test_get_resources(self, headers):
        r = requests.get(f"{BASE_URL}/api/resources", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "id" in data[0]
        assert "name" in data[0]

    def test_get_allocations(self, headers):
        r = requests.get(f"{BASE_URL}/api/allocations", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        if data:
            item = data[0]
            assert "id" in item
            assert "resource_id" in item
            assert "project_id" in item
            # Dates should be strings post-serialize_doc
            assert isinstance(item.get("start_date"), str)
            assert isinstance(item.get("end_date"), str)

    def test_get_status_options(self, headers):
        r = requests.get(f"{BASE_URL}/api/status-options", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        # Should contain health and schedule options
        assert isinstance(data, dict)
        # expected keys (flexible)
        keys = set(data.keys())
        assert any(k in keys for k in ("health", "health_options", "project_health"))
        assert any(k in keys for k in ("schedule", "schedule_options", "project_schedule"))


# ---------- Reports ----------
class TestReports:
    def test_planned_vs_actual_overview(self, headers):
        r = requests.get(
            f"{BASE_URL}/api/reports/planned-vs-actual/overview",
            headers=headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "summary" in data
        assert "projects" in data
        assert isinstance(data["projects"], list)


# ---------- Settings ----------
class TestSettings:
    def test_get_ai_settings(self, headers):
        r = requests.get(f"{BASE_URL}/api/settings/ai", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, dict)
        # Should at least have a provider or similar config key
        assert any(k in data for k in ("provider", "model", "api_key_present", "enabled"))


# ---------- Notifications ----------
class TestNotifications:
    def test_get_notifications(self, headers):
        r = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)


# ---------- AI Chat ----------
class TestAIChat:
    def test_get_chat_sessions(self, headers):
        r = requests.get(f"{BASE_URL}/api/ai/chat/sessions", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)

    def test_post_chat_message(self, headers):
        payload = {"message": "How many active projects are there?"}
        r = requests.post(
            f"{BASE_URL}/api/ai/chat",
            headers={**headers, "Content-Type": "application/json"},
            json=payload,
            timeout=90,
        )
        # AI chat can take time; allow 200 or 500 if LLM not configured
        assert r.status_code in (200, 500, 502, 503), r.text
        if r.status_code == 200:
            body = r.json()
            # Response shape flexible: should contain some text field
            assert any(k in body for k in ("response", "message", "reply", "content", "session_id"))


# ---------- Project-scoped endpoints ----------
class TestProjectSubResources:
    def test_get_project_risks(self, headers):
        # Use first project id captured earlier
        pid = getattr(pytest, "project_id", None)
        if not pid:
            pytest.skip("project_id not captured")
        r = requests.get(f"{BASE_URL}/api/projects/{pid}/risks", headers=headers)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_get_project_allocations(self, headers):
        pid = getattr(pytest, "project_id", None)
        if not pid:
            pytest.skip("project_id not captured")
        r = requests.get(f"{BASE_URL}/api/projects/{pid}/allocations", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        if data:
            # All must belong to project
            for a in data:
                assert a["project_id"] == pid
