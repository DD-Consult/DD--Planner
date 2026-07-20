"""
Iteration 25 — Agentic Features Test Suite
=========================================
Tests for 4 new agentic features:
  a) Agent Memory CRUD (/api/ai/memory)
  b) Project-scoped memories (/api/ai/memory/project/{project_id})
  c) Health Monitor (/api/ai/health-monitor/run, /api/ai/health-monitor/report)
  d) Execute Plan (/api/ai/chat/execute-plan)
  e) AI Actions: save_memory, run_health_check via dispatch_action
  f) Specialist Agent Detection (unit test via sys.path import)
  g) Backend health regression
"""
import pytest
import requests
import os
import sys
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ──────────────────────────────────────────────────────────────────────────
# Credentials
# ──────────────────────────────────────────────────────────────────────────
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "admin123"
RESOURCE_EMAIL = "riley@test.com"
RESOURCE_PASS = "riley123"


# ──────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ──────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    """Obtain JWT token for the super-admin (OAuth2 form-encoded login)."""
    resp = requests.post(f"{BASE_URL}/api/auth/login",
                         data={"username": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json().get("access_token") or resp.json().get("token")


@pytest.fixture(scope="module")
def resource_token():
    """Obtain JWT token for the resource user (riley) - OAuth2 form-encoded."""
    resp = requests.post(f"{BASE_URL}/api/auth/login",
                         data={"username": RESOURCE_EMAIL, "password": RESOURCE_PASS})
    assert resp.status_code == 200, f"Resource login failed: {resp.text}"
    return resp.json().get("access_token") or resp.json().get("token")


@pytest.fixture(scope="module")
def admin_session(admin_token):
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def resource_session(resource_token):
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {resource_token}", "Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def first_project_id(admin_session):
    """Grab a real project id for project-scoped memory tests."""
    resp = admin_session.get(f"{BASE_URL}/api/projects")
    assert resp.status_code == 200
    projects = resp.json()
    assert projects, "No projects found in DB — need at least one"
    return str(projects[0]["id"])


# ──────────────────────────────────────────────────────────────────────────
# Test Group 1 — Backend health (regression)
# ──────────────────────────────────────────────────────────────────────────

class TestHealthRegression:
    """Smoke test — backend must be healthy."""

    def test_health_endpoint(self):
        resp = requests.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200, f"Health check failed: {resp.text}"
        data = resp.json()
        assert data.get("status") == "healthy", f"Unexpected health status: {data}"
        print("PASS: /api/health is healthy")


# ──────────────────────────────────────────────────────────────────────────
# Test Group 2 — Specialist Agent Detection (pure unit test via import)
# ──────────────────────────────────────────────────────────────────────────

class TestSpecialistDetection:
    """Test detect_specialist logic directly (no HTTP needed)."""

    @classmethod
    def setup_class(cls):
        sys.path.insert(0, "/app/backend")

    def test_resource_trigger(self):
        from services.specialist_agents import detect_specialist
        result = detect_specialist("@resource who is available?")
        assert result == "resource", f"Expected 'resource', got '{result}'"
        print("PASS: @resource trigger detected")

    def test_budget_trigger(self):
        from services.specialist_agents import detect_specialist
        result = detect_specialist("@budget show me burn rate")
        assert result == "budget", f"Expected 'budget', got '{result}'"
        print("PASS: @budget trigger detected")

    def test_risk_trigger(self):
        from services.specialist_agents import detect_specialist
        result = detect_specialist("@risk what risks need mitigation?")
        assert result == "risk", f"Expected 'risk', got '{result}'"
        print("PASS: @risk trigger detected")

    def test_schedule_trigger(self):
        from services.specialist_agents import detect_specialist
        result = detect_specialist("@schedule what projects are late?")
        assert result == "schedule", f"Expected 'schedule', got '{result}'"
        print("PASS: @schedule trigger detected")

    def test_no_trigger_returns_none(self):
        from services.specialist_agents import detect_specialist
        result = detect_specialist("What is the status of Project Alpha?")
        assert result is None, f"Expected None, got '{result}'"
        print("PASS: no trigger returns None")

    def test_get_specialist_header_nonempty(self):
        from services.specialist_agents import get_specialist_header
        for key in ("resource", "budget", "risk", "schedule"):
            header = get_specialist_header(key)
            assert len(header) > 20, f"Header for '{key}' is too short"
        print("PASS: all specialist headers are non-empty")


# ──────────────────────────────────────────────────────────────────────────
# Test Group 3 — AI Memory CRUD
# ──────────────────────────────────────────────────────────────────────────

class TestAIMemoryCRUD:
    """Full CRUD lifecycle for the ai_memory collection."""
    _created_id = None

    def test_create_global_memory(self, admin_session):
        """POST /api/ai/memory — creates a global memory."""
        payload = {
            "title": "TEST_iter25 Global Memory",
            "content": "Team agreed: all projects use 60/40 discovery/build split.",
            "scope": "global",
            "category": "decision",
        }
        resp = admin_session.post(f"{BASE_URL}/api/ai/memory", json=payload)
        assert resp.status_code == 200, f"Create memory failed: {resp.text}"
        data = resp.json()
        assert "id" in data, f"Missing 'id' in response: {data}"
        assert data.get("title") == payload["title"]
        assert data.get("scope") == "global"
        assert data.get("active") is True
        TestAIMemoryCRUD._created_id = data["id"]
        print(f"PASS: Created global memory id={TestAIMemoryCRUD._created_id}")

    def test_list_memories_includes_created(self, admin_session):
        """GET /api/ai/memory — created memory should appear."""
        resp = admin_session.get(f"{BASE_URL}/api/ai/memory")
        assert resp.status_code == 200, f"List memories failed: {resp.text}"
        data = resp.json()
        assert isinstance(data, list), "Expected list response"
        ids = [m.get("id") for m in data]
        assert TestAIMemoryCRUD._created_id in ids, (
            f"Created memory {TestAIMemoryCRUD._created_id} not in list"
        )
        print(f"PASS: Memory list contains created entry ({len(data)} total)")

    def test_update_memory(self, admin_session):
        """PUT /api/ai/memory/{id} — updates the memory content."""
        mid = TestAIMemoryCRUD._created_id
        assert mid, "No memory id to update"
        payload = {"content": "Updated: use 70/30 split for fixed-price projects."}
        resp = admin_session.put(f"{BASE_URL}/api/ai/memory/{mid}", json=payload)
        assert resp.status_code == 200, f"Update memory failed: {resp.text}"
        data = resp.json()
        assert "updated" in data.get("message", "").lower() or "memory" in data.get("message", "").lower(), \
            f"Unexpected update response: {data}"
        print("PASS: Memory updated successfully")

    def test_delete_memory_soft(self, admin_session):
        """DELETE /api/ai/memory/{id} — soft-deletes (active=False)."""
        mid = TestAIMemoryCRUD._created_id
        assert mid, "No memory id to delete"
        resp = admin_session.delete(f"{BASE_URL}/api/ai/memory/{mid}")
        assert resp.status_code == 200, f"Delete memory failed: {resp.text}"
        data = resp.json()
        assert "deleted" in data.get("message", "").lower() or "memory" in data.get("message", "").lower(), \
            f"Unexpected delete response: {data}"
        print("PASS: Memory soft-deleted")

    def test_deleted_memory_not_in_list(self, admin_session):
        """GET /api/ai/memory — soft-deleted memory must NOT appear."""
        mid = TestAIMemoryCRUD._created_id
        resp = admin_session.get(f"{BASE_URL}/api/ai/memory")
        assert resp.status_code == 200
        ids = [m.get("id") for m in resp.json()]
        assert mid not in ids, f"Soft-deleted memory {mid} still appears in list"
        print("PASS: Soft-deleted memory excluded from list")

    def test_create_memory_missing_title_400(self, admin_session):
        """POST /api/ai/memory — missing title should return 400."""
        resp = admin_session.post(f"{BASE_URL}/api/ai/memory", json={"content": "orphan content"})
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        print("PASS: Missing title returns 400")

    def test_create_memory_invalid_scope_400(self, admin_session):
        """POST /api/ai/memory — invalid scope should return 400."""
        resp = admin_session.post(f"{BASE_URL}/api/ai/memory", json={
            "title": "TEST bad scope", "content": "test", "scope": "universe"
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        print("PASS: Invalid scope returns 400")

    def test_update_nonexistent_memory_404(self, admin_session):
        """PUT /api/ai/memory/{fake_id} — should return 404."""
        resp = admin_session.put(f"{BASE_URL}/api/ai/memory/000000000000000000000000",
                                 json={"content": "ghost"})
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("PASS: Update nonexistent memory returns 404")

    def test_resource_user_can_create_memory(self, resource_session):
        """Any authenticated user can create a memory (not admin-only)."""
        payload = {
            "title": "TEST_iter25_resource_memory",
            "content": "Resource user note for testing.",
            "scope": "global",
            "category": "note",
        }
        resp = resource_session.post(f"{BASE_URL}/api/ai/memory", json=payload)
        assert resp.status_code == 200, f"Resource user create memory failed: {resp.text}"
        data = resp.json()
        mid = data.get("id")
        # cleanup
        if mid:
            resource_session.delete(f"{BASE_URL}/api/ai/memory/{mid}")
        print("PASS: Resource user can create memory (endpoint is accessible to all auth users)")


# ──────────────────────────────────────────────────────────────────────────
# Test Group 4 — Project-scoped memories
# ──────────────────────────────────────────────────────────────────────────

class TestProjectMemories:
    """GET /api/ai/memory/project/{project_id} returns global + project memories."""
    _proj_mem_id = None
    _global_mem_id = None

    def test_setup_memories(self, admin_session, first_project_id):
        """Create one global + one project-scoped memory for fixture project."""
        pid = first_project_id
        # project-scoped
        r1 = admin_session.post(f"{BASE_URL}/api/ai/memory", json={
            "title": "TEST_iter25_project_scope",
            "content": "Project-specific preference.",
            "scope": "project",
            "project_id": pid,
            "category": "preference",
        })
        assert r1.status_code == 200, f"Project memory creation failed: {r1.text}"
        TestProjectMemories._proj_mem_id = r1.json().get("id")

        # global
        r2 = admin_session.post(f"{BASE_URL}/api/ai/memory", json={
            "title": "TEST_iter25_global_scope2",
            "content": "Global preference for all projects.",
            "scope": "global",
            "category": "preference",
        })
        assert r2.status_code == 200, f"Global memory creation failed: {r2.text}"
        TestProjectMemories._global_mem_id = r2.json().get("id")
        print(f"PASS: Setup memories — project={TestProjectMemories._proj_mem_id}, global={TestProjectMemories._global_mem_id}")

    def test_project_memory_endpoint_returns_both(self, admin_session, first_project_id):
        """GET /api/ai/memory/project/{pid} should include both global and project memories."""
        pid = first_project_id
        resp = admin_session.get(f"{BASE_URL}/api/ai/memory/project/{pid}")
        assert resp.status_code == 200, f"Project memories GET failed: {resp.text}"
        data = resp.json()
        assert isinstance(data, list), "Expected list response"
        ids = [m.get("id") for m in data]
        assert TestProjectMemories._proj_mem_id in ids, \
            f"Project-scoped memory {TestProjectMemories._proj_mem_id} not returned"
        assert TestProjectMemories._global_mem_id in ids, \
            f"Global memory {TestProjectMemories._global_mem_id} not returned"
        # Verify scopes in returned data
        scopes = {m.get("id"): m.get("scope") for m in data}
        assert scopes.get(TestProjectMemories._proj_mem_id) == "project"
        assert scopes.get(TestProjectMemories._global_mem_id) == "global"
        print(f"PASS: project/{pid} returns {len(data)} memories (global + project)")

    def test_cleanup_project_memories(self, admin_session):
        """Cleanup test memories."""
        for mid in [TestProjectMemories._proj_mem_id, TestProjectMemories._global_mem_id]:
            if mid:
                admin_session.delete(f"{BASE_URL}/api/ai/memory/{mid}")
        print("PASS: Cleanup done")


# ──────────────────────────────────────────────────────────────────────────
# Test Group 5 — Health Monitor
# ──────────────────────────────────────────────────────────────────────────

class TestHealthMonitor:
    """POST /api/ai/health-monitor/run and GET /api/ai/health-monitor/report."""

    def test_run_health_monitor_admin(self, admin_session):
        """Admin can run health monitor — returns findings."""
        resp = admin_session.post(f"{BASE_URL}/api/ai/health-monitor/run")
        assert resp.status_code == 200, f"Health monitor run failed: {resp.text}"
        data = resp.json()
        # Verify response structure
        assert "overall_health" in data, f"Missing 'overall_health': {data}"
        assert "summary" in data, f"Missing 'summary': {data}"
        assert "findings" in data, f"Missing 'findings': {data}"
        assert isinstance(data["findings"], list), "findings must be a list"
        assert data["overall_health"] in ("Healthy", "At Risk", "Critical"), \
            f"Unexpected overall_health: {data['overall_health']}"
        summary = data["summary"]
        assert "total_findings" in summary
        assert "critical" in summary
        assert "high" in summary
        print(f"PASS: Health monitor run — overall_health={data['overall_health']}, "
              f"total_findings={data['summary']['total_findings']}")

    def test_run_health_monitor_non_admin_403(self, resource_session):
        """Non-admin user should get 403 when running health monitor."""
        resp = resource_session.post(f"{BASE_URL}/api/ai/health-monitor/run")
        assert resp.status_code == 403, f"Expected 403 for resource user, got {resp.status_code}: {resp.text}"
        print("PASS: Non-admin gets 403 on health monitor run")

    def test_get_health_report_after_run(self, admin_session):
        """GET /api/ai/health-monitor/report — should return the saved report."""
        resp = admin_session.get(f"{BASE_URL}/api/ai/health-monitor/report")
        assert resp.status_code == 200, f"Get health report failed: {resp.text}"
        data = resp.json()
        # Either it's a real report with findings, or the no-report placeholder
        if "message" in data and "no health report" in data["message"].lower():
            pytest.skip("No health report saved yet — run health monitor first")
        assert "overall_health" in data or "findings" in data, \
            f"Unexpected health report shape: {data}"
        print(f"PASS: Health report retrieved — keys={list(data.keys())}")

    def test_health_report_non_admin_403(self, resource_session):
        """Non-admin user should get 403 on GET health report."""
        resp = resource_session.get(f"{BASE_URL}/api/ai/health-monitor/report")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
        print("PASS: Non-admin gets 403 on health report GET")

    def test_findings_have_required_fields(self, admin_session):
        """Each finding must have type, severity, message fields."""
        resp = admin_session.post(f"{BASE_URL}/api/ai/health-monitor/run")
        assert resp.status_code == 200
        findings = resp.json().get("findings", [])
        for f in findings:
            assert "type" in f, f"Finding missing 'type': {f}"
            assert "severity" in f, f"Finding missing 'severity': {f}"
            assert "message" in f, f"Finding missing 'message': {f}"
            assert f["severity"] in ("critical", "high", "medium", "low"), \
                f"Unexpected severity: {f['severity']}"
        print(f"PASS: All {len(findings)} findings have required fields")


# ──────────────────────────────────────────────────────────────────────────
# Test Group 6 — Execute Plan
# ──────────────────────────────────────────────────────────────────────────

class TestExecutePlan:
    """POST /api/ai/chat/execute-plan — multi-step sequential execution."""

    def test_execute_plan_empty_steps_400(self, admin_session):
        """Empty steps list should return 400."""
        resp = admin_session.post(f"{BASE_URL}/api/ai/chat/execute-plan", json={"steps": []})
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        print("PASS: Empty steps returns 400")

    def test_execute_plan_too_many_steps_400(self, admin_session):
        """More than 20 steps should return 400."""
        steps = [{"action": "get_project_info"} for _ in range(21)]
        resp = admin_session.post(f"{BASE_URL}/api/ai/chat/execute-plan", json={"steps": steps})
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        print("PASS: >20 steps returns 400")

    def test_execute_plan_non_admin_403(self, resource_session):
        """Non-admin should get 403."""
        resp = resource_session.post(f"{BASE_URL}/api/ai/chat/execute-plan", json={
            "steps": [{"action": "save_memory", "title": "test", "content": "test"}]
        })
        assert resp.status_code == 403, f"Expected 403 for resource user, got {resp.status_code}"
        print("PASS: Non-admin gets 403 on execute-plan")

    def test_execute_plan_single_valid_step(self, admin_session):
        """Execute a single save_memory step — should succeed."""
        resp = admin_session.post(f"{BASE_URL}/api/ai/chat/execute-plan", json={
            "steps": [{
                "action": "save_memory",
                "title": "TEST_iter25_plan_exec",
                "content": "Executed via plan executor in iter25 testing.",
                "scope": "global",
                "category": "note",
            }],
            "stop_on_error": True,
        })
        assert resp.status_code == 200, f"Execute plan failed: {resp.text}"
        data = resp.json()
        assert "results" in data, f"Missing 'results': {data}"
        assert "success_count" in data
        assert "total_steps" in data
        assert data["total_steps"] == 1
        assert data["executed_steps"] >= 1
        results = data["results"]
        assert len(results) == 1
        step_res = results[0]
        assert step_res.get("step") == 1
        assert step_res.get("action") == "save_memory"
        # The save_memory action should succeed
        assert step_res.get("success") is True, \
            f"save_memory step failed: {step_res.get('message')}"
        print(f"PASS: Single step plan executed — success_count={data['success_count']}")

    def test_execute_plan_multi_step(self, admin_session):
        """Execute a 2-step plan — both should succeed."""
        resp = admin_session.post(f"{BASE_URL}/api/ai/chat/execute-plan", json={
            "steps": [
                {
                    "action": "save_memory",
                    "title": "TEST_iter25_step1",
                    "content": "Step 1 memory.",
                    "scope": "global",
                    "category": "note",
                },
                {
                    "action": "save_memory",
                    "title": "TEST_iter25_step2",
                    "content": "Step 2 memory.",
                    "scope": "global",
                    "category": "note",
                },
            ]
        })
        assert resp.status_code == 200, f"Multi-step plan failed: {resp.text}"
        data = resp.json()
        assert data["total_steps"] == 2
        assert data["executed_steps"] == 2
        results = data["results"]
        for i, r in enumerate(results):
            assert r["step"] == i + 1
        print(f"PASS: Multi-step plan executed — success_count={data['success_count']}/2")

    def test_execute_plan_stop_on_error(self, admin_session):
        """A bad step with stop_on_error=True should halt execution."""
        resp = admin_session.post(f"{BASE_URL}/api/ai/chat/execute-plan", json={
            "steps": [
                {"action": "delete_project", "project_id": "000000000000000000000000"},
                {"action": "save_memory", "title": "TEST_should_not_run", "content": "x"},
            ],
            "stop_on_error": True,
        })
        assert resp.status_code == 200, f"Execute plan request failed: {resp.text}"
        data = resp.json()
        # First step fails (project not found), second should NOT run
        results = data["results"]
        assert len(results) == 1, f"Expected only 1 result (stop_on_error), got {len(results)}"
        assert results[0]["success"] is False
        print("PASS: stop_on_error halts execution after first failure")

    def test_execute_plan_no_stop_on_error(self, admin_session):
        """With stop_on_error=False, all steps run even if one fails."""
        resp = admin_session.post(f"{BASE_URL}/api/ai/chat/execute-plan", json={
            "steps": [
                {"action": "delete_project", "project_id": "000000000000000000000000"},
                {"action": "save_memory", "title": "TEST_iter25_should_run", "content": "runs after failure"},
            ],
            "stop_on_error": False,
        })
        assert resp.status_code == 200, f"Execute plan request failed: {resp.text}"
        data = resp.json()
        assert data["executed_steps"] == 2, \
            f"Expected 2 executed steps (no_stop_on_error), got {data['executed_steps']}"
        print("PASS: stop_on_error=False allows all steps to run")


# ──────────────────────────────────────────────────────────────────────────
# Test Group 7 — AI Actions via dispatch_action
# ──────────────────────────────────────────────────────────────────────────

class TestAIActionsDispatch:
    """Test save_memory and run_health_check via /api/ai/chat/execute-action."""

    def test_save_memory_via_dispatch(self, admin_session):
        """save_memory action creates a memory entry in ai_memory collection."""
        payload = {
            "action": "save_memory",
            "title": "TEST_iter25_dispatch_memory",
            "content": "Decision: use three-amigo reviews before each sprint.",
            "scope": "global",
            "category": "decision",
        }
        resp = admin_session.post(f"{BASE_URL}/api/ai/chat/execute-action", json=payload)
        assert resp.status_code == 200, f"save_memory dispatch failed: {resp.text}"
        data = resp.json()
        assert data.get("success") is True, f"save_memory returned not-success: {data}"
        assert "id" in data or "saved" in data.get("message", "").lower() or "memory" in data.get("message", "").lower(), \
            f"Unexpected save_memory response: {data}"
        # Verify it appears in memory list
        list_resp = admin_session.get(f"{BASE_URL}/api/ai/memory")
        assert list_resp.status_code == 200
        titles = [m.get("title") for m in list_resp.json()]
        assert "TEST_iter25_dispatch_memory" in titles, "Memory not found in list after save_memory dispatch"
        # cleanup
        for m in list_resp.json():
            if m.get("title") == "TEST_iter25_dispatch_memory":
                admin_session.delete(f"{BASE_URL}/api/ai/memory/{m['id']}")
        print("PASS: save_memory action creates DB entry and is retrievable")

    def test_run_health_check_via_dispatch(self, admin_session):
        """run_health_check action returns health findings summary."""
        payload = {"action": "run_health_check"}
        resp = admin_session.post(f"{BASE_URL}/api/ai/chat/execute-action", json=payload)
        assert resp.status_code == 200, f"run_health_check dispatch failed: {resp.text}"
        data = resp.json()
        assert data.get("success") is True, f"run_health_check returned not-success: {data}"
        assert "overall_health" in data, f"Missing 'overall_health' in response: {data}"
        assert "findings" in data, f"Missing 'findings' in response: {data}"
        assert "summary" in data, f"Missing 'summary' in response: {data}"
        print(f"PASS: run_health_check action returns health={data.get('overall_health')}")

    def test_save_memory_missing_fields(self, admin_session):
        """save_memory without required fields returns success=False (not HTTP 4xx)."""
        payload = {"action": "save_memory", "title": "", "content": ""}
        resp = admin_session.post(f"{BASE_URL}/api/ai/chat/execute-action", json=payload)
        assert resp.status_code == 200, f"Expected 200 with success=False, got {resp.status_code}"
        data = resp.json()
        assert data.get("success") is False, \
            f"Expected success=False for missing fields, got: {data}"
        print("PASS: save_memory with missing fields returns success=False")


# ──────────────────────────────────────────────────────────────────────────
# Test Group 8 — Action Registry Size Check
# ──────────────────────────────────────────────────────────────────────────

class TestActionRegistry:
    """Verify the action registry has the expected 35 actions including new ones."""

    def test_action_registry_count(self):
        """Check that save_memory and run_health_check are registered."""
        sys.path.insert(0, "/app/backend")
        from services.ai_action_registry import ACTIONS
        action_names = set(ACTIONS.keys())
        assert "save_memory" in action_names, f"save_memory not in registry: {action_names}"
        assert "run_health_check" in action_names, f"run_health_check not in registry: {action_names}"
        # Should have ~35 actions now
        assert len(action_names) >= 33, \
            f"Expected at least 33 registered actions, got {len(action_names)}: {sorted(action_names)}"
        print(f"PASS: Action registry has {len(action_names)} actions including save_memory and run_health_check")


# ──────────────────────────────────────────────────────────────────────────
# Test Group 9 — Regression: Previous endpoints still work
# ──────────────────────────────────────────────────────────────────────────

class TestRegression:
    """Key endpoints from previous iterations still functional."""

    def test_projects_list(self, admin_session):
        resp = admin_session.get(f"{BASE_URL}/api/projects")
        assert resp.status_code == 200, f"Projects list failed: {resp.text}"
        assert isinstance(resp.json(), list)
        print(f"PASS: /api/projects returns {len(resp.json())} projects")

    def test_resources_list(self, admin_session):
        resp = admin_session.get(f"{BASE_URL}/api/resources")
        assert resp.status_code == 200, f"Resources list failed: {resp.text}"
        assert isinstance(resp.json(), list)
        print(f"PASS: /api/resources returns {len(resp.json())} resources")

    def test_ai_chat_session_creation(self, admin_session):
        """POST /api/ai/chat — new session creates and returns session_id."""
        resp = admin_session.post(f"{BASE_URL}/api/ai/chat", json={
            "message": "Hello, how many active projects are there?",
            "session_id": None,
        })
        assert resp.status_code == 200, f"AI chat failed: {resp.text}"
        data = resp.json()
        assert "session_id" in data, f"Missing session_id in chat response: {data}"
        print("PASS: /api/ai/chat creates new session and responds")

    def test_allocations_list(self, admin_session):
        resp = admin_session.get(f"{BASE_URL}/api/allocations")
        assert resp.status_code == 200, f"Allocations list failed: {resp.text}"
        print(f"PASS: /api/allocations returns {len(resp.json())} allocations")
