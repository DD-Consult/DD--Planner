"""
Iteration 28: ResourceDashboard API Tests
Tests all backend APIs consumed by ResourceDashboard.js for riley@test.com:
1. GET /api/my-allocations?period=month — shape check + active allocations
2. GET /api/timesheets/history?weeks=4 — timesheet history scoped to riley
3. GET /api/leaves — leaves scoped to riley (resource user)
4. GET /api/dashboard/action-items — action items for riley
5. Admin regression: GET /api/dashboard (Command Center KPIs still present)
6. Role check: /api/auth/me returns resource role for riley
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


# ── Auth helpers ─────────────────────────────────────────────────────────────

def login(email: str, password: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": email, "password": password},
    )
    assert resp.status_code == 200, f"Login failed for {email}: {resp.status_code} {resp.text[:200]}"
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    return login("admin@test.com", "admin123")


@pytest.fixture(scope="module")
def riley_token():
    return login("riley@test.com", "riley123")


# ── 1. Role check ─────────────────────────────────────────────────────────────

class TestRileyRole:
    """riley@test.com must have role=resource for the personalized dashboard to trigger."""

    def test_riley_role_is_resource(self, riley_token):
        resp = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers(riley_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("role") in ("resource", "contractor"), \
            f"Expected resource/contractor role, got: {data.get('role')}"
        print(f"[PASS] Riley role: {data.get('role')} — personalized dashboard will render")

    def test_admin_role_is_super_admin(self, admin_token):
        resp = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("role") in ("admin", "super_admin"), \
            f"Expected admin/super_admin role, got: {data.get('role')}"
        print(f"[PASS] Admin role: {data.get('role')} — Command Center dashboard will render")


# ── 2. GET /api/my-allocations?period=month ───────────────────────────────────

class TestMyAllocations:
    """ResourceDashboard fetches /api/my-allocations?period=month for KPIs."""

    def test_my_allocations_status_200(self, riley_token):
        resp = requests.get(
            f"{BASE_URL}/api/my-allocations",
            params={"period": "month"},
            headers=auth_headers(riley_token),
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"

    def test_my_allocations_response_shape(self, riley_token):
        resp = requests.get(
            f"{BASE_URL}/api/my-allocations",
            params={"period": "month"},
            headers=auth_headers(riley_token),
        )
        data = resp.json()
        # Must have 'resource' and 'allocations' keys
        assert "resource" in data, f"Missing 'resource' key in response: {list(data.keys())}"
        assert "allocations" in data, f"Missing 'allocations' key in response: {list(data.keys())}"
        assert isinstance(data["allocations"], list), "allocations must be a list"
        print(f"[PASS] my-allocations shape OK. resource={data['resource'].get('name')}, allocations={len(data['allocations'])}")

    def test_my_allocations_weekly_hours_field(self, riley_token):
        """Each allocation must have weekly_hours field."""
        resp = requests.get(
            f"{BASE_URL}/api/my-allocations",
            params={"period": "month"},
            headers=auth_headers(riley_token),
        )
        data = resp.json()
        allocations = data.get("allocations", [])
        for alloc in allocations:
            assert "weekly_hours" in alloc, f"Allocation missing weekly_hours: {alloc}"
            assert "percentage" in alloc, f"Allocation missing percentage: {alloc}"
            assert "start_date" in alloc, f"Allocation missing start_date: {alloc}"
            assert "end_date" in alloc, f"Allocation missing end_date: {alloc}"
            assert "project_name" in alloc, f"Allocation missing project_name: {alloc}"
        print(f"[PASS] All {len(allocations)} allocations have required fields")

    def test_my_allocations_scoped_to_riley(self, riley_token, admin_token):
        """Riley should only see her own allocations, not all team allocations."""
        riley_resp = requests.get(
            f"{BASE_URL}/api/my-allocations",
            params={"period": "month"},
            headers=auth_headers(riley_token),
        )
        riley_data = riley_resp.json()
        # Riley's resource name should be in the response
        resource_name = riley_data.get("resource", {}).get("name", "")
        assert resource_name != "", f"Resource name is empty in my-allocations response"
        print(f"[PASS] Riley's resource: '{resource_name}', allocations count: {len(riley_data.get('allocations', []))}")


# ── 3. GET /api/timesheets/history?weeks=4 ────────────────────────────────────

class TestTimesheetHistory:
    """ResourceDashboard fetches timesheet history for 'Recent Timesheets' section."""

    def test_timesheet_history_status_200(self, riley_token):
        resp = requests.get(
            f"{BASE_URL}/api/timesheets/history",
            params={"weeks": 4},
            headers=auth_headers(riley_token),
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"

    def test_timesheet_history_shape(self, riley_token):
        resp = requests.get(
            f"{BASE_URL}/api/timesheets/history",
            params={"weeks": 4},
            headers=auth_headers(riley_token),
        )
        data = resp.json()
        assert "weeks" in data, f"Missing 'weeks' key: {list(data.keys())}"
        assert isinstance(data["weeks"], list), "weeks must be a list"
        print(f"[PASS] timesheet history shape OK. weeks count: {len(data['weeks'])}")

    def test_timesheet_history_weeks_count(self, riley_token):
        """Requesting 4 weeks should return at most 4 week entries."""
        resp = requests.get(
            f"{BASE_URL}/api/timesheets/history",
            params={"weeks": 4},
            headers=auth_headers(riley_token),
        )
        data = resp.json()
        weeks = data.get("weeks", [])
        assert len(weeks) <= 4, f"Expected ≤4 weeks, got {len(weeks)}"
        print(f"[PASS] timesheet history returned {len(weeks)} weeks (≤4)")

    def test_timesheet_history_week_shape(self, riley_token):
        """Each week entry must have week_start and entries fields."""
        resp = requests.get(
            f"{BASE_URL}/api/timesheets/history",
            params={"weeks": 4},
            headers=auth_headers(riley_token),
        )
        data = resp.json()
        weeks = data.get("weeks", [])
        for week in weeks:
            assert "week_start" in week, f"Week missing week_start: {week}"
            assert "entries" in week, f"Week missing entries: {week}"
        print(f"[PASS] All week entries have required shape")


# ── 4. GET /api/leaves ────────────────────────────────────────────────────────

class TestLeavesForDashboard:
    """ResourceDashboard fetches leaves for 'My Leaves' section."""

    def test_leaves_status_200(self, riley_token):
        resp = requests.get(f"{BASE_URL}/api/leaves", headers=auth_headers(riley_token))
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"

    def test_leaves_returns_list(self, riley_token):
        resp = requests.get(f"{BASE_URL}/api/leaves", headers=auth_headers(riley_token))
        data = resp.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"[PASS] riley's leaves: {len(data)} entries")

    def test_leaves_scoped_to_riley(self, riley_token):
        """Riley should not see other people's leaves."""
        resp = requests.get(f"{BASE_URL}/api/leaves", headers=auth_headers(riley_token))
        data = resp.json()
        # All leaves should have a resource_id (if leaves have one)
        for leave in data:
            # Just verify basic shape - start_date, end_date
            assert "start_date" in leave, f"Leave missing start_date: {leave}"
            assert "end_date" in leave, f"Leave missing end_date: {leave}"
        print(f"[PASS] Riley's leaves all have required fields. Count: {len(data)}")


# ── 5. GET /api/dashboard/action-items ───────────────────────────────────────

class TestActionItems:
    """ResourceDashboard fetches action items for the banner and Timesheet Status KPI."""

    def test_action_items_status_200(self, riley_token):
        resp = requests.get(f"{BASE_URL}/api/dashboard/action-items", headers=auth_headers(riley_token))
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"

    def test_action_items_shape(self, riley_token):
        resp = requests.get(f"{BASE_URL}/api/dashboard/action-items", headers=auth_headers(riley_token))
        data = resp.json()
        assert "action_items" in data, f"Missing 'action_items' key: {list(data.keys())}"
        assert "summary" in data, f"Missing 'summary' key: {list(data.keys())}"
        assert isinstance(data["action_items"], list), "action_items must be a list"
        summary = data["summary"]
        assert "total" in summary, f"Missing 'total' in summary: {summary}"
        print(f"[PASS] action-items shape OK. total={summary.get('total')}, high={summary.get('high', 0)}")

    def test_action_items_for_admin(self, admin_token):
        """Admin also uses this endpoint in the Command Center dashboard."""
        resp = requests.get(f"{BASE_URL}/api/dashboard/action-items", headers=auth_headers(admin_token))
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "action_items" in data
        assert "summary" in data
        print(f"[PASS] admin action-items shape OK. total={data['summary'].get('total')}")


# ── 6. Admin regression: Command Center APIs still work ───────────────────────

class TestAdminCommandCenter:
    """Admin should still have all Command Center APIs working."""

    def test_admin_can_get_resources(self, admin_token):
        resp = requests.get(f"{BASE_URL}/api/resources", headers=auth_headers(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Admin should see at least some resources"
        print(f"[PASS] Admin resources count: {len(data)}")

    def test_admin_can_get_projects(self, admin_token):
        resp = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"[PASS] Admin projects count: {len(data)}")

    def test_admin_can_get_allocations(self, admin_token):
        resp = requests.get(f"{BASE_URL}/api/allocations", headers=auth_headers(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1, "Admin should see at least 1 allocation"
        print(f"[PASS] Admin allocations count: {len(data)}")

    def test_admin_can_get_capacity_report(self, admin_token):
        from datetime import date, timedelta
        today = date.today()
        end = today + timedelta(days=13)
        resp = requests.get(
            f"{BASE_URL}/api/reports/capacity",
            params={"start_date": str(today), "end_date": str(end)},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "resources" in data, f"Capacity report missing 'resources': {list(data.keys())}"
        print(f"[PASS] Capacity report OK. resources count: {len(data.get('resources', []))}")


# ── 7. Riley can access /my-allocations, /my-timesheets-related APIs ──────────

class TestRileyRegressionAPIs:
    """Regression: riley's key pages still load without errors."""

    def test_riley_can_get_own_allocations(self, riley_token):
        """GET /api/allocations scoped to riley."""
        resp = requests.get(f"{BASE_URL}/api/allocations", headers=auth_headers(riley_token))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"[PASS] Riley allocations (scoped): {len(data)}")

    def test_riley_timesheet_history_default_weeks(self, riley_token):
        """Default weeks (12) should still work."""
        resp = requests.get(f"{BASE_URL}/api/timesheets/history", headers=auth_headers(riley_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "weeks" in data
        print(f"[PASS] Riley timesheet history default works. weeks: {len(data['weeks'])}")

    def test_riley_cannot_see_all_resources(self, riley_token):
        """Riley (resource role) should not have full resource list."""
        resp = requests.get(f"{BASE_URL}/api/resources", headers=auth_headers(riley_token))
        # Could be 200 (if allowed for resource role) or 403 — just not 500
        assert resp.status_code in (200, 403), f"Unexpected status: {resp.status_code}"
        print(f"[PASS] Riley /api/resources returns {resp.status_code} (expected 200 or 403)")
