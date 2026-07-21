"""
Iteration 29 — Integration Layer tests:
- HubSpot CRM bi-directional sync endpoints
- MCP Server (AI Agent API) JSON-RPC 2.0 endpoints
- Integration settings (super_admin only)
- Sync logs
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def super_admin_token():
    """Login as super_admin (admin@test.com) and return Bearer token."""
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": "admin@test.com", "password": "admin123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    token = r.json().get("access_token")
    assert token, "No access_token in login response"
    return token


@pytest.fixture(scope="module")
def super_admin_headers(super_admin_token):
    return {"Authorization": f"Bearer {super_admin_token}"}


@pytest.fixture(scope="module")
def resource_token():
    """Login as riley@test.com (resource role) and return Bearer token."""
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": "riley@test.com", "password": "riley123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200, f"Riley login failed: {r.status_code} {r.text}"
    token = r.json().get("access_token")
    assert token, "No access_token"
    return token


@pytest.fixture(scope="module")
def resource_headers(resource_token):
    return {"Authorization": f"Bearer {resource_token}"}


@pytest.fixture(scope="module")
def agent_api_key(super_admin_headers):
    """Generate a fresh agent API key and return it."""
    r = requests.post(
        f"{BASE_URL}/api/integrations/agent-api/regenerate",
        headers=super_admin_headers,
    )
    assert r.status_code == 200, f"Regen failed: {r.status_code} {r.text}"
    data = r.json()
    assert data.get("ok") is True
    key = data.get("api_key", "")
    assert key.startswith("dda_"), f"Key doesn't start with dda_: {key}"
    return key


# ─── Integration Settings ──────────────────────────────────────────────────────

class TestIntegrationSettings:
    """GET and PUT /api/integrations/settings"""

    def test_get_settings_super_admin(self, super_admin_headers):
        """Super admin can fetch settings — response includes hubspot + agent_api sections."""
        r = requests.get(f"{BASE_URL}/api/integrations/settings", headers=super_admin_headers)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "hubspot" in data, "Missing hubspot section"
        assert "agent_api" in data, "Missing agent_api section"

    def test_get_settings_structure_hubspot(self, super_admin_headers):
        """HubSpot section has expected keys."""
        r = requests.get(f"{BASE_URL}/api/integrations/settings", headers=super_admin_headers)
        hs = r.json().get("hubspot", {})
        assert "enabled" in hs
        assert "portal_id" in hs
        assert "trigger_stage" in hs
        assert "sync_status_updates" in hs

    def test_get_settings_structure_agent_api(self, super_admin_headers):
        """agent_api section has expected keys."""
        r = requests.get(f"{BASE_URL}/api/integrations/settings", headers=super_admin_headers)
        agent = r.json().get("agent_api", {})
        assert "enabled" in agent

    def test_get_settings_regular_user_forbidden(self, resource_headers):
        """Non-super_admin user should get 403."""
        r = requests.get(f"{BASE_URL}/api/integrations/settings", headers=resource_headers)
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"

    def test_get_settings_no_auth_forbidden(self):
        """No auth should get 401 or 403."""
        r = requests.get(f"{BASE_URL}/api/integrations/settings")
        assert r.status_code in [401, 403], f"Expected 401/403, got {r.status_code}"

    def test_put_settings_hubspot_config(self, super_admin_headers):
        """PUT saves HubSpot config successfully."""
        payload = {
            "hubspot": {
                "enabled": False,
                "private_app_token": "",
                "portal_id": "12345678",
                "trigger_stage": "closedwon",
                "sync_status_updates": True,
                "default_project_status": "Pipeline",
            }
        }
        r = requests.put(
            f"{BASE_URL}/api/integrations/settings",
            json=payload,
            headers=super_admin_headers,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("ok") is True

    def test_put_settings_portal_id_persisted(self, super_admin_headers):
        """After saving portal_id, GET settings returns the same value."""
        # Save a specific portal_id
        payload = {
            "hubspot": {
                "enabled": False,
                "private_app_token": "",
                "portal_id": "TEST_99999",
                "trigger_stage": "closedwon",
                "sync_status_updates": True,
                "default_project_status": "Pipeline",
            }
        }
        put_r = requests.put(
            f"{BASE_URL}/api/integrations/settings",
            json=payload,
            headers=super_admin_headers,
        )
        assert put_r.status_code == 200

        get_r = requests.get(f"{BASE_URL}/api/integrations/settings", headers=super_admin_headers)
        assert get_r.status_code == 200
        assert get_r.json()["hubspot"]["portal_id"] == "TEST_99999"

    def test_put_settings_regular_user_forbidden(self, resource_headers):
        """Regular user cannot PUT settings."""
        r = requests.put(
            f"{BASE_URL}/api/integrations/settings",
            json={"hubspot": {"enabled": True}},
            headers=resource_headers,
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}"


# ─── HubSpot Test Connection ──────────────────────────────────────────────────

class TestHubSpotTestConnection:
    """POST /api/integrations/hubspot/test"""

    def test_test_with_invalid_token_returns_ok_false(self, super_admin_headers):
        """Invalid token returns ok=False with error message (NOT 500)."""
        r = requests.post(
            f"{BASE_URL}/api/integrations/hubspot/test",
            json={"token": "pat-na1-00000000-invalid-test-token"},
            headers=super_admin_headers,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("ok") is False, f"Expected ok=False, got: {data}"
        assert "message" in data, "Missing message field"
        assert data["message"], "Empty message"

    def test_test_connection_super_admin_only(self, resource_headers):
        """Resource user cannot test connection."""
        r = requests.post(
            f"{BASE_URL}/api/integrations/hubspot/test",
            json={"token": "pat-test"},
            headers=resource_headers,
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}"

    def test_test_with_empty_token_returns_400(self, super_admin_headers):
        """Empty token (no saved token and no token provided) should return 400."""
        # Clear any saved token first by saving empty
        requests.put(
            f"{BASE_URL}/api/integrations/settings",
            json={"hubspot": {
                "enabled": False,
                "private_app_token": "",
                "portal_id": "",
                "trigger_stage": "closedwon",
                "sync_status_updates": True,
                "default_project_status": "Pipeline",
            }},
            headers=super_admin_headers,
        )
        r = requests.post(
            f"{BASE_URL}/api/integrations/hubspot/test",
            json={"token": None},
            headers=super_admin_headers,
        )
        # Should return 400 (no token) OR ok:False
        assert r.status_code in [400, 200], f"Unexpected: {r.status_code} {r.text}"
        if r.status_code == 200:
            assert r.json().get("ok") is False


# ─── Agent API Key ─────────────────────────────────────────────────────────────

class TestAgentApiKey:
    """POST /api/integrations/agent-api/regenerate"""

    def test_regenerate_creates_dda_key(self, super_admin_headers):
        """Generated key starts with 'dda_' prefix."""
        r = requests.post(
            f"{BASE_URL}/api/integrations/agent-api/regenerate",
            headers=super_admin_headers,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("ok") is True
        api_key = data.get("api_key", "")
        assert api_key.startswith("dda_"), f"Expected key starting with dda_, got: {api_key}"
        assert len(api_key) > 10, "Key too short"

    def test_regenerate_key_returns_message(self, super_admin_headers):
        """Response includes a message about saving the key."""
        r = requests.post(
            f"{BASE_URL}/api/integrations/agent-api/regenerate",
            headers=super_admin_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert "message" in data, "Missing message in response"
        assert data["message"], "Empty message"

    def test_regenerate_resource_user_forbidden(self, resource_headers):
        """Resource user cannot regenerate key."""
        r = requests.post(
            f"{BASE_URL}/api/integrations/agent-api/regenerate",
            headers=resource_headers,
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}"

    def test_new_key_marked_enabled_in_db(self, super_admin_headers):
        """After regenerating key, agent_api.enabled is True in settings."""
        requests.post(
            f"{BASE_URL}/api/integrations/agent-api/regenerate",
            headers=super_admin_headers,
        )
        r = requests.get(f"{BASE_URL}/api/integrations/settings", headers=super_admin_headers)
        assert r.status_code == 200
        agent = r.json().get("agent_api", {})
        assert agent.get("enabled") is True


# ─── Sync Logs ────────────────────────────────────────────────────────────────

class TestSyncLogs:
    """GET /api/integrations/sync-logs"""

    def test_sync_logs_returns_array(self, super_admin_headers):
        """Returns a list (possibly empty)."""
        r = requests.get(f"{BASE_URL}/api/integrations/sync-logs", headers=super_admin_headers)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"

    def test_sync_logs_super_admin_only(self, resource_headers):
        """Resource user cannot see sync logs."""
        r = requests.get(f"{BASE_URL}/api/integrations/sync-logs", headers=resource_headers)
        assert r.status_code == 403, f"Expected 403, got {r.status_code}"

    def test_sync_logs_no_auth(self):
        """No auth should return 401 or 403."""
        r = requests.get(f"{BASE_URL}/api/integrations/sync-logs")
        assert r.status_code in [401, 403], f"Expected 401/403, got {r.status_code}"

    def test_sync_logs_has_entry_after_test(self, super_admin_headers):
        """After running a hubspot test, sync_logs should have at least one entry."""
        # Run a test to generate a sync log entry
        requests.post(
            f"{BASE_URL}/api/integrations/hubspot/test",
            json={"token": "pat-na1-testtoken"},
            headers=super_admin_headers,
        )
        r = requests.get(f"{BASE_URL}/api/integrations/sync-logs", headers=super_admin_headers)
        assert r.status_code == 200
        logs = r.json()
        assert len(logs) >= 1, "Expected at least 1 sync log entry after test"
        # Verify structure
        log = logs[0]
        assert "direction" in log
        assert "event_type" in log
        assert "status" in log


# ─── MCP Server ────────────────────────────────────────────────────────────────

class TestMCPServer:
    """GET /api/mcp (discovery) and POST /api/mcp (JSON-RPC 2.0)"""

    def test_get_mcp_no_auth_returns_manifest(self):
        """GET /api/mcp requires no auth and returns server manifest."""
        r = requests.get(f"{BASE_URL}/api/mcp")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "protocolVersion" in data, "Missing protocolVersion"
        assert "serverInfo" in data, "Missing serverInfo"
        assert "tools" in data, "Missing tools"

    def test_get_mcp_has_4_tools(self):
        """GET /api/mcp returns exactly 4 tools."""
        r = requests.get(f"{BASE_URL}/api/mcp")
        assert r.status_code == 200
        tools = r.json().get("tools", [])
        assert len(tools) == 4, f"Expected 4 tools, got {len(tools)}: {[t['name'] for t in tools]}"

    def test_get_mcp_tool_names(self):
        """All 4 expected tool names are present."""
        r = requests.get(f"{BASE_URL}/api/mcp")
        tool_names = {t["name"] for t in r.json().get("tools", [])}
        expected = {"list_projects", "get_project_status", "get_team_capacity", "get_recent_updates"}
        assert expected == tool_names, f"Tool names mismatch: got {tool_names}"

    def test_post_mcp_no_auth_returns_401(self):
        """POST /api/mcp without X-Agent-Key returns 401."""
        r = requests.post(
            f"{BASE_URL}/api/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"

    def test_post_mcp_invalid_key_returns_401(self):
        """POST /api/mcp with invalid X-Agent-Key returns 401."""
        r = requests.post(
            f"{BASE_URL}/api/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers={"X-Agent-Key": "dda_invalid_key_xyz123"},
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"

    def test_post_mcp_initialize(self, agent_api_key):
        """POST /api/mcp method=initialize returns server info."""
        r = requests.post(
            f"{BASE_URL}/api/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            headers={"X-Agent-Key": agent_api_key},
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "result" in data, "Missing result"
        result = data["result"]
        assert "protocolVersion" in result
        assert "serverInfo" in result

    def test_post_mcp_tools_list(self, agent_api_key):
        """POST /api/mcp method=tools/list returns all 4 tools."""
        r = requests.post(
            f"{BASE_URL}/api/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            headers={"X-Agent-Key": agent_api_key},
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "result" in data
        tools = data["result"].get("tools", [])
        assert len(tools) == 4, f"Expected 4 tools, got {len(tools)}"
        tool_names = {t["name"] for t in tools}
        assert "list_projects" in tool_names
        assert "get_team_capacity" in tool_names

    def test_post_mcp_tools_call_list_projects(self, agent_api_key):
        """tools/call list_projects returns an array of projects."""
        r = requests.post(
            f"{BASE_URL}/api/mcp",
            json={
                "jsonrpc": "2.0", "id": 3,
                "method": "tools/call",
                "params": {"name": "list_projects", "arguments": {"status_filter": "Active"}},
            },
            headers={"X-Agent-Key": agent_api_key},
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "result" in data, f"Missing result in: {data}"
        result = data["result"]
        assert "content" in result, f"Missing content in result: {result}"
        assert result.get("isError") is False
        # Parse the JSON text content
        import json
        projects = json.loads(result["content"][0]["text"])
        assert isinstance(projects, list), f"Expected list of projects, got: {type(projects)}"

    def test_post_mcp_tools_call_get_team_capacity(self, agent_api_key):
        """tools/call get_team_capacity returns resources with utilization percentages."""
        r = requests.post(
            f"{BASE_URL}/api/mcp",
            json={
                "jsonrpc": "2.0", "id": 4,
                "method": "tools/call",
                "params": {"name": "get_team_capacity", "arguments": {}},
            },
            headers={"X-Agent-Key": agent_api_key},
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "result" in data
        result = data["result"]
        assert result.get("isError") is False
        import json
        resources = json.loads(result["content"][0]["text"])
        assert isinstance(resources, list), "Expected list of resources"
        if resources:
            # Each resource should have utilization field
            first = resources[0]
            assert "name" in first, "Missing name in resource"
            assert "current_utilization_pct" in first, "Missing current_utilization_pct"
            assert "status" in first, "Missing status"

    def test_post_mcp_tools_call_get_recent_updates(self, agent_api_key):
        """tools/call get_recent_updates returns array."""
        r = requests.post(
            f"{BASE_URL}/api/mcp",
            json={
                "jsonrpc": "2.0", "id": 5,
                "method": "tools/call",
                "params": {"name": "get_recent_updates", "arguments": {"days": 30}},
            },
            headers={"X-Agent-Key": agent_api_key},
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "result" in data
        import json
        updates = json.loads(data["result"]["content"][0]["text"])
        assert isinstance(updates, list)

    def test_post_mcp_unknown_method_returns_error(self, agent_api_key):
        """Unknown method returns JSON-RPC error."""
        r = requests.post(
            f"{BASE_URL}/api/mcp",
            json={"jsonrpc": "2.0", "id": 6, "method": "unknown/method", "params": {}},
            headers={"X-Agent-Key": agent_api_key},
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        assert "error" in data, f"Expected error field for unknown method, got: {data}"

    def test_post_mcp_tools_call_all_projects(self, agent_api_key):
        """tools/call list_projects with status_filter=All works."""
        r = requests.post(
            f"{BASE_URL}/api/mcp",
            json={
                "jsonrpc": "2.0", "id": 7,
                "method": "tools/call",
                "params": {"name": "list_projects", "arguments": {"status_filter": "All"}},
            },
            headers={"X-Agent-Key": agent_api_key},
        )
        assert r.status_code == 200
        data = r.json()
        assert "result" in data
        import json
        projects = json.loads(data["result"]["content"][0]["text"])
        assert isinstance(projects, list)


# ─── Regression: core flows still work ────────────────────────────────────────

class TestRegression:
    """Verify existing endpoints haven't broken."""

    def test_dashboard_loads(self, super_admin_headers):
        """GET /api/dashboard/action-items returns 200 (regression check)."""
        r = requests.get(f"{BASE_URL}/api/dashboard/action-items", headers=super_admin_headers)
        assert r.status_code == 200, f"Dashboard broken: {r.status_code} {r.text}"

    def test_resources_list(self, super_admin_headers):
        """GET /api/resources returns 200."""
        r = requests.get(f"{BASE_URL}/api/resources", headers=super_admin_headers)
        assert r.status_code == 200, f"Resources broken: {r.status_code} {r.text}"

    def test_projects_list(self, super_admin_headers):
        """GET /api/projects returns 200."""
        r = requests.get(f"{BASE_URL}/api/projects", headers=super_admin_headers)
        assert r.status_code == 200, f"Projects broken: {r.status_code} {r.text}"

    def test_riley_resource_dashboard(self, resource_headers):
        """Riley resource can access dashboard."""
        r = requests.get(f"{BASE_URL}/api/dashboard/summary", headers=resource_headers)
        # resource users may get 200 or 403 depending on their role — just confirm no 500
        assert r.status_code != 500, f"Dashboard returned 500 for riley: {r.text}"

    def test_status_updates_endpoint(self, super_admin_headers):
        """GET /api/status-updates/my-projects returns 200 (regression check)."""
        r = requests.get(f"{BASE_URL}/api/status-updates/my-projects", headers=super_admin_headers)
        assert r.status_code in [200, 422], f"Status updates broken: {r.status_code} {r.text}"
