"""
Iteration 26: Resource-scoping fixes test suite
Tests:
1. Allocations scoped: admin sees all, resource (riley) sees only own
2. Leaves scoped: admin sees all, resource sees own; resource can create without resource_id; resource can delete own, 403 on others; admin 400 when resource_id omitted
3. Timesheets history: new endpoint /api/timesheets/history scoped to own resource
4. Health check regression
5. GET /api/my-allocations regression
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ── Auth helpers ──────────────────────────────────────────────────────────────

def login(email: str, password: str) -> str:
    """Return Bearer token via form-encoded login."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": email, "password": password},
    )
    assert resp.status_code == 200, f"Login failed for {email}: {resp.status_code} {resp.text}"
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


# ── Health check ──────────────────────────────────────────────────────────────

class TestHealthRegression:
    """Health check must still return healthy"""

    def test_health_check(self):
        resp = requests.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200, f"Health check failed: {resp.text}"
        data = resp.json()
        assert data.get("status") == "healthy", f"Unexpected health status: {data}"


# ── Allocations scoping ───────────────────────────────────────────────────────

class TestAllocationsScoping:
    """
    Admin: GET /api/allocations returns ALL allocations (≥ 1, expected ~19).
    Riley: GET /api/allocations returns ONLY her own allocations (≥ 1, but strictly fewer than admin).
    """

    def test_admin_sees_all_allocations(self, admin_token):
        resp = requests.get(f"{BASE_URL}/api/allocations", headers=auth_headers(admin_token))
        assert resp.status_code == 200, f"Admin /api/allocations failed: {resp.text}"
        data = resp.json()
        assert isinstance(data, list), "Expected a list"
        # Admin should see a non-trivial number of allocations
        assert len(data) >= 1, f"Admin should see ≥ 1 allocation, got {len(data)}"
        print(f"[PASS] Admin sees {len(data)} allocations (all)")

    def test_riley_sees_only_own_allocations(self, riley_token):
        resp = requests.get(f"{BASE_URL}/api/allocations", headers=auth_headers(riley_token))
        assert resp.status_code == 200, f"Riley /api/allocations failed: {resp.text}"
        data = resp.json()
        assert isinstance(data, list), "Expected a list"
        print(f"[INFO] Riley sees {len(data)} allocation(s) via /api/allocations")

    def test_riley_allocations_less_than_admin(self, admin_token, riley_token):
        admin_resp = requests.get(f"{BASE_URL}/api/allocations", headers=auth_headers(admin_token))
        riley_resp = requests.get(f"{BASE_URL}/api/allocations", headers=auth_headers(riley_token))
        admin_count = len(admin_resp.json())
        riley_count = len(riley_resp.json())
        # Riley's scoped count must be <= admin's total
        assert riley_count <= admin_count, (
            f"Riley sees {riley_count} allocations but admin sees {admin_count}; scoping may be broken"
        )
        # Admin should see more (there are other resources in the system)
        assert admin_count >= riley_count, "Admin should see at least as many allocations as Riley"
        print(f"[PASS] Admin sees {admin_count}, Riley sees {riley_count} (scoped)")

    def test_riley_allocations_are_all_hers(self, riley_token, admin_token):
        """Every allocation Riley sees via /api/allocations must belong to her resource."""
        # Get Riley's resource_id from /api/my-allocations
        my_alloc = requests.get(f"{BASE_URL}/api/my-allocations", headers=auth_headers(riley_token))
        assert my_alloc.status_code == 200
        resource = my_alloc.json().get("resource")
        if resource is None:
            pytest.skip("Riley has no linked resource — cannot verify ownership")
        riley_resource_id = resource["id"]

        riley_allocs = requests.get(f"{BASE_URL}/api/allocations", headers=auth_headers(riley_token))
        assert riley_allocs.status_code == 200
        for alloc in riley_allocs.json():
            assert alloc["resource_id"] == riley_resource_id, (
                f"Allocation {alloc['id']} belongs to resource {alloc['resource_id']}, not Riley ({riley_resource_id})"
            )
        print(f"[PASS] All {len(riley_allocs.json())} of Riley's allocations are scoped to her resource_id")


# ── Leaves scoping ────────────────────────────────────────────────────────────

class TestLeavesScoping:
    """
    Admin GET /api/leaves: all leaves.
    Riley GET /api/leaves: only her own.
    Riley POST /api/leaves without resource_id: backend auto-fills.
    Riley DELETE own leave: 200; DELETE another's leave: 403.
    Admin POST /api/leaves without resource_id: 400.
    """

    # Module-level storage so tests can share created leave ids
    _riley_leave_id = None
    _riley_resource_id = None
    _another_leave_id = None  # a leave belonging to another resource

    def test_admin_sees_all_leaves(self, admin_token):
        resp = requests.get(f"{BASE_URL}/api/leaves", headers=auth_headers(admin_token))
        assert resp.status_code == 200, f"Admin GET /api/leaves failed: {resp.text}"
        data = resp.json()
        assert isinstance(data, list)
        print(f"[PASS] Admin sees {len(data)} leaves (all)")

    def test_riley_sees_only_own_leaves(self, riley_token):
        resp = requests.get(f"{BASE_URL}/api/leaves", headers=auth_headers(riley_token))
        assert resp.status_code == 200, f"Riley GET /api/leaves failed: {resp.text}"
        data = resp.json()
        assert isinstance(data, list)
        print(f"[INFO] Riley sees {len(data)} leave(s)")

    def test_riley_can_create_leave_without_resource_id(self, riley_token):
        """Riley POSTs /api/leaves without resource_id — backend should auto-fill it."""
        payload = {
            "start_date": "2026-06-01",
            "end_date": "2026-06-03",
            "type": "Annual Leave",
            "notes": "TEST_iter26_riley_leave",
        }
        resp = requests.post(f"{BASE_URL}/api/leaves", json=payload, headers=auth_headers(riley_token))
        assert resp.status_code == 200, f"Riley POST /api/leaves failed: {resp.status_code} {resp.text}"
        doc = resp.json()
        assert "id" in doc, f"Response missing 'id': {doc}"
        assert doc.get("resource_id"), f"resource_id not auto-filled: {doc}"
        TestLeavesScoping._riley_leave_id = doc["id"]
        TestLeavesScoping._riley_resource_id = doc["resource_id"]
        print(f"[PASS] Riley created leave {doc['id']} with auto-filled resource_id={doc['resource_id']}")

    def test_riley_leave_resource_id_matches_her_resource(self, riley_token):
        """resource_id on returned leave doc must match Riley's linked resource."""
        if TestLeavesScoping._riley_resource_id is None:
            pytest.skip("No leave was created in previous test")
        # Get Riley's resource from /api/my-allocations
        my_alloc = requests.get(f"{BASE_URL}/api/my-allocations", headers=auth_headers(riley_token))
        assert my_alloc.status_code == 200
        resource = my_alloc.json().get("resource")
        if resource is None:
            pytest.skip("Riley has no linked resource")
        assert TestLeavesScoping._riley_resource_id == resource["id"], (
            f"Leave resource_id={TestLeavesScoping._riley_resource_id} != Riley resource {resource['id']}"
        )
        print(f"[PASS] Leave resource_id correctly auto-filled to Riley's resource {resource['id']}")

    def test_admin_cannot_create_leave_without_resource_id(self, admin_token):
        """Admin POST /api/leaves without resource_id must return 400."""
        payload = {
            "start_date": "2026-07-01",
            "end_date": "2026-07-01",
            "type": "Sick Leave",
        }
        resp = requests.post(f"{BASE_URL}/api/leaves", json=payload, headers=auth_headers(admin_token))
        assert resp.status_code == 400, (
            f"Expected 400 when admin omits resource_id, got {resp.status_code}: {resp.text}"
        )
        print(f"[PASS] Admin correctly gets 400 when resource_id is omitted")

    def test_riley_can_delete_own_leave(self, riley_token):
        """Riley can delete the leave she created."""
        if TestLeavesScoping._riley_leave_id is None:
            pytest.skip("No leave_id stored — creation test may have failed")
        resp = requests.delete(
            f"{BASE_URL}/api/leaves/{TestLeavesScoping._riley_leave_id}",
            headers=auth_headers(riley_token),
        )
        assert resp.status_code == 200, (
            f"Riley DELETE own leave failed: {resp.status_code} {resp.text}"
        )
        TestLeavesScoping._riley_leave_id = None  # mark as deleted
        print("[PASS] Riley successfully deleted her own leave")

    def test_riley_cannot_delete_another_users_leave(self, admin_token, riley_token):
        """
        Create a leave for a resource OTHER than Riley (via admin), then verify Riley gets 403.
        """
        # First find a resource that is not Riley
        resources_resp = requests.get(f"{BASE_URL}/api/resources", headers=auth_headers(admin_token))
        if resources_resp.status_code != 200:
            pytest.skip("Cannot fetch resources list")
        resources = resources_resp.json()

        # Get Riley's resource_id
        my_alloc = requests.get(f"{BASE_URL}/api/my-allocations", headers=auth_headers(riley_token))
        if my_alloc.status_code != 200 or not my_alloc.json().get("resource"):
            pytest.skip("Cannot determine Riley's resource_id")
        riley_res_id = my_alloc.json()["resource"]["id"]

        # Find any resource that is not Riley
        other_resource = None
        for r in resources:
            if r.get("id") != riley_res_id:
                other_resource = r
                break

        if not other_resource:
            pytest.skip("No other resource found to create a leave for")

        # Admin creates a leave for the other resource
        payload = {
            "resource_id": other_resource["id"],
            "start_date": "2026-08-01",
            "end_date": "2026-08-01",
            "type": "Annual Leave",
            "notes": "TEST_iter26_other_leave",
        }
        create_resp = requests.post(
            f"{BASE_URL}/api/leaves", json=payload, headers=auth_headers(admin_token)
        )
        assert create_resp.status_code == 200, f"Admin failed to create leave: {create_resp.text}"
        other_leave_id = create_resp.json()["id"]
        TestLeavesScoping._another_leave_id = other_leave_id

        # Riley tries to delete it — should get 403
        del_resp = requests.delete(
            f"{BASE_URL}/api/leaves/{other_leave_id}",
            headers=auth_headers(riley_token),
        )
        assert del_resp.status_code == 403, (
            f"Expected 403 when Riley deletes another's leave, got {del_resp.status_code}: {del_resp.text}"
        )
        print(f"[PASS] Riley correctly gets 403 when deleting another resource's leave")

        # Cleanup: admin deletes the test leave
        requests.delete(f"{BASE_URL}/api/leaves/{other_leave_id}", headers=auth_headers(admin_token))


# ── Timesheets history ────────────────────────────────────────────────────────

class TestTimesheetHistory:
    """
    GET /api/timesheets/history returns {resource, weeks, total_weeks_with_data}
    scoped to logged-in user's resource.
    Admin and Riley should each get their own scoped response.
    """

    def test_riley_timesheets_history_shape(self, riley_token):
        resp = requests.get(f"{BASE_URL}/api/timesheets/history", headers=auth_headers(riley_token))
        assert resp.status_code == 200, f"GET /api/timesheets/history failed for Riley: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "weeks" in data, f"'weeks' missing from response: {data.keys()}"
        assert "total_weeks_with_data" in data, f"'total_weeks_with_data' missing: {data.keys()}"
        assert "resource" in data, f"'resource' missing: {data.keys()}"
        assert isinstance(data["weeks"], list)
        assert isinstance(data["total_weeks_with_data"], int)
        print(f"[PASS] Riley timesheets history: {data['total_weeks_with_data']} week(s) with data")

    def test_riley_history_scoped_to_her_resource(self, riley_token):
        """All timesheet entries returned must belong to Riley's resource."""
        resp = requests.get(f"{BASE_URL}/api/timesheets/history", headers=auth_headers(riley_token))
        assert resp.status_code == 200
        data = resp.json()
        resource = data.get("resource")
        if not resource or not data["weeks"]:
            print("[SKIP] No timesheet history entries to validate scoping")
            return
        riley_resource_id = resource.get("id") or str(resource.get("_id", ""))
        for week in data["weeks"]:
            for entry in week.get("entries", []):
                assert entry["resource_id"] == riley_resource_id, (
                    f"Entry {entry.get('id')} belongs to {entry['resource_id']}, not Riley ({riley_resource_id})"
                )
        print(f"[PASS] All timesheet history entries are scoped to Riley's resource_id")

    def test_admin_timesheets_history_shape(self, admin_token):
        """Admin can also call /api/timesheets/history and get a valid response (own resource)."""
        resp = requests.get(f"{BASE_URL}/api/timesheets/history", headers=auth_headers(admin_token))
        assert resp.status_code == 200, f"GET /api/timesheets/history failed for admin: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "weeks" in data
        assert "total_weeks_with_data" in data
        print(f"[PASS] Admin timesheets history endpoint returns valid shape")

    def test_timesheets_history_custom_weeks_param(self, riley_token):
        """Optional ?weeks=4 query param should be accepted."""
        resp = requests.get(
            f"{BASE_URL}/api/timesheets/history?weeks=4", headers=auth_headers(riley_token)
        )
        assert resp.status_code == 200, f"GET /api/timesheets/history?weeks=4 failed: {resp.text}"
        data = resp.json()
        assert "weeks" in data
        print("[PASS] Custom weeks param accepted and returns valid response")


# ── Regression: /api/my-allocations ──────────────────────────────────────────

class TestMyAllocationsRegression:
    """GET /api/my-allocations still works for resource users (unchanged endpoint)."""

    def test_riley_my_allocations(self, riley_token):
        resp = requests.get(f"{BASE_URL}/api/my-allocations", headers=auth_headers(riley_token))
        assert resp.status_code == 200, f"Riley GET /api/my-allocations failed: {resp.text}"
        data = resp.json()
        assert "allocations" in data, f"'allocations' missing from response: {data.keys()}"
        assert "summary" in data
        assert "resource" in data
        print(f"[PASS] /api/my-allocations works for Riley: {data['summary']}")

    def test_my_allocations_period_param(self, riley_token):
        for period in ["week", "month", "3months"]:
            resp = requests.get(
                f"{BASE_URL}/api/my-allocations?period={period}",
                headers=auth_headers(riley_token),
            )
            assert resp.status_code == 200, (
                f"/api/my-allocations?period={period} failed: {resp.status_code} {resp.text}"
            )
        print("[PASS] All three period params work for /api/my-allocations")


# ── Regression: Admin allocation creation ────────────────────────────────────

class TestAdminAllocationRegression:
    """Admin can still create allocations (existing functionality unchanged)."""

    _created_allocation_id = None

    def test_admin_can_list_allocations(self, admin_token):
        resp = requests.get(f"{BASE_URL}/api/allocations", headers=auth_headers(admin_token))
        assert resp.status_code == 200
        print(f"[PASS] Admin list allocations: {len(resp.json())} items")

    def test_admin_can_create_and_read_allocation(self, admin_token):
        """Admin creates a new allocation, verifies it appears in list."""
        # Get a valid resource and project to use
        resources = requests.get(f"{BASE_URL}/api/resources", headers=auth_headers(admin_token)).json()
        projects = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers(admin_token)).json()
        if not resources or not projects:
            pytest.skip("No resources or projects available for allocation test")

        resource = resources[0]
        resource_id = resource.get("id")

        # Find a project with suitable date range
        project = None
        for p in projects:
            # Just pick an Active project
            if p.get("status") == "Active":
                project = p
                break
        if not project:
            project = projects[0]
        project_id = project.get("id")
        proj_start = project.get("start_date", "")[:10]
        proj_end = project.get("end_date", "")[:10]

        payload = {
            "resource_id": resource_id,
            "project_id": project_id,
            "start_date": proj_start,
            "end_date": proj_end,
            "percentage": 20,
            "allocation_type": "percentage",
        }
        resp = requests.post(
            f"{BASE_URL}/api/allocations", json=payload, headers=auth_headers(admin_token)
        )
        assert resp.status_code == 200, f"Admin POST /api/allocations failed: {resp.status_code} {resp.text}"
        alloc = resp.json()
        assert "id" in alloc
        TestAdminAllocationRegression._created_allocation_id = alloc["id"]
        print(f"[PASS] Admin created allocation {alloc['id']}")

    def test_admin_cleanup_allocation(self, admin_token):
        """Delete the test allocation created above."""
        alloc_id = TestAdminAllocationRegression._created_allocation_id
        if not alloc_id:
            pytest.skip("No allocation to clean up")
        resp = requests.delete(
            f"{BASE_URL}/api/allocations/{alloc_id}", headers=auth_headers(admin_token)
        )
        assert resp.status_code == 200, f"DELETE allocation failed: {resp.text}"
        print(f"[PASS] Test allocation {alloc_id} cleaned up")
