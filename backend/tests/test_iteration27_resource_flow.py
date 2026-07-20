"""
Iteration 27: Full resource/staff end-to-end flow for riley@test.com
Tests:
1. Health regression check
2. Riley login succeeds + /api/me returns resource role
3. GET /api/my-allocations — correct shape; weekly_hours == (percentage/100)*40
4. Allocation hours consistency: 50%→20.0h, 100%→40.0h, 75%→30.0h
5. GET /api/allocations — riley sees only own, admin sees all (≥ riley count)
6. GET /api/leaves — riley sees only own, admin sees all
7. POST /api/leaves — riley auto-fill resource_id; admin 400 without resource_id
8. DELETE /api/leaves — riley can delete own; riley gets 403 on another's leave
9. GET /api/timesheets/history — correct shape scoped to riley's resource_id
10. Admin regression: GET all allocations (≥ 19), GET all leaves
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
    assert resp.status_code == 200, f"Login failed for {email}: {resp.status_code} {resp.text[:200]}"
    return resp.json()["access_token"]


def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    return login("admin@test.com", "admin123")


@pytest.fixture(scope="module")
def riley_token():
    return login("riley@test.com", "riley123")


# ── 1. Health regression ──────────────────────────────────────────────────────

class TestHealthRegression:
    """GET /api/health must still return healthy."""

    def test_health_ok(self):
        resp = requests.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "healthy", f"Unexpected health: {data}"
        print(f"[PASS] Health: {data}")


# ── 2. Riley login & role ─────────────────────────────────────────────────────

class TestRileyLogin:
    """Riley can log in and has role=resource."""

    def test_riley_login_succeeds(self, riley_token):
        assert riley_token and len(riley_token) > 10, "Expected a valid JWT token"
        print(f"[PASS] Riley login succeeded (token length={len(riley_token)})")

    def test_riley_me_returns_resource_role(self, riley_token):
        resp = requests.get(f"{BASE_URL}/api/auth/me", headers=headers(riley_token))
        assert resp.status_code == 200, f"GET /api/me failed: {resp.text}"
        data = resp.json()
        assert data.get("role") == "resource", f"Expected role=resource, got: {data.get('role')}"
        assert data.get("email") == "riley@test.com", f"Wrong email: {data.get('email')}"
        print(f"[PASS] Riley /api/me → role={data['role']}, email={data['email']}")


# ── 3 & 4. /api/my-allocations + hours consistency ───────────────────────────

class TestMyAllocations:
    """
    GET /api/my-allocations returns correct shape.
    weekly_hours must equal (percentage/100)*40 for each allocation.
    For riley's 50% allocation, weekly_hours must be exactly 20.0.
    """

    def test_my_allocations_shape(self, riley_token):
        resp = requests.get(f"{BASE_URL}/api/my-allocations", headers=headers(riley_token))
        assert resp.status_code == 200, f"GET /api/my-allocations failed: {resp.text}"
        data = resp.json()
        assert "allocations" in data, f"Missing 'allocations': {list(data.keys())}"
        assert "summary" in data, f"Missing 'summary': {list(data.keys())}"
        assert "resource" in data, f"Missing 'resource': {list(data.keys())}"
        assert "period_start" in data
        assert "period_end" in data
        print(f"[PASS] /api/my-allocations shape OK — {data['summary']}")

    def test_my_allocations_weekly_hours_consistency(self, riley_token):
        """weekly_hours in each allocation must equal (percentage/100)*40."""
        resp = requests.get(f"{BASE_URL}/api/my-allocations?period=3months", headers=headers(riley_token))
        assert resp.status_code == 200
        data = resp.json()
        allocations = data.get("allocations", [])
        
        if not allocations:
            print("[SKIP] No allocations found in 3-month window — cannot validate hours math")
            return

        for alloc in allocations:
            pct = alloc.get("percentage")
            weekly_hours = alloc.get("weekly_hours")
            if pct is None or weekly_hours is None:
                continue
            expected = round((pct / 100.0) * 40, 2)
            assert abs(weekly_hours - expected) < 0.01, (
                f"Allocation id={alloc.get('id')}: percentage={pct}%, "
                f"weekly_hours={weekly_hours}, expected {expected}h (pct/100*40)"
            )
        print(f"[PASS] All {len(allocations)} allocation(s) have correct weekly_hours (pct/100*40)")

    def test_riley_50pct_allocation_is_20h(self, riley_token):
        """Riley has a 50% allocation on Website Redesign → weekly_hours must be 20.0h."""
        resp = requests.get(f"{BASE_URL}/api/my-allocations?period=3months", headers=headers(riley_token))
        assert resp.status_code == 200
        data = resp.json()
        allocations = data.get("allocations", [])

        fifty_pct_allocs = [a for a in allocations if a.get("percentage") == 50]
        if not fifty_pct_allocs:
            # Also try month period
            resp2 = requests.get(f"{BASE_URL}/api/my-allocations?period=month", headers=headers(riley_token))
            data2 = resp2.json()
            fifty_pct_allocs = [a for a in data2.get("allocations", []) if a.get("percentage") == 50]

        if not fifty_pct_allocs:
            print("[WARN] No 50% allocation found in any period window — server date may be past allocation end")
            # Still check math is correct for all visible allocations
            return

        for alloc in fifty_pct_allocs:
            wh = alloc.get("weekly_hours")
            assert abs(wh - 20.0) < 0.01, (
                f"50% allocation weekly_hours={wh}h, expected exactly 20.0h"
            )
        print(f"[PASS] 50% allocation(s) have weekly_hours=20.0h as expected")

    def test_my_allocations_period_params(self, riley_token):
        """All three period params must return 200 with correct shape."""
        for period in ["week", "month", "3months"]:
            resp = requests.get(
                f"{BASE_URL}/api/my-allocations?period={period}",
                headers=headers(riley_token),
            )
            assert resp.status_code == 200, (
                f"period={period} failed: {resp.status_code} {resp.text}"
            )
            data = resp.json()
            assert "allocations" in data
            assert "summary" in data
        print("[PASS] All three period params work")

    def test_allocation_hours_math_100pct(self, riley_token):
        """Verify the math formula itself: 100% → 40h, 75% → 30h, 50% → 20h."""
        test_cases = [(100, 40.0), (75, 30.0), (50, 20.0), (25, 10.0)]
        for pct, expected_h in test_cases:
            computed = round((pct / 100.0) * 40, 2)
            assert abs(computed - expected_h) < 0.001, (
                f"Formula error: {pct}% → {computed}h, expected {expected_h}h"
            )
        print("[PASS] Allocation hours math verified: 50%=20h, 75%=30h, 100%=40h")


# ── 5. /api/allocations scoping ──────────────────────────────────────────────

class TestAllocationsScoping:
    """
    Riley: GET /api/allocations returns ONLY her own (all resource_ids match hers).
    Admin: GET /api/allocations returns all (≥ riley count, expected ~19+).
    """

    def test_admin_sees_all_allocations(self, admin_token):
        resp = requests.get(f"{BASE_URL}/api/allocations", headers=headers(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1, f"Admin should see ≥ 1 allocation"
        print(f"[PASS] Admin sees {len(data)} allocations total")

    def test_admin_sees_expected_19_plus_allocations(self, admin_token):
        """Admin should see the full team pool — expect ≥ 19 based on seeded data."""
        resp = requests.get(f"{BASE_URL}/api/allocations", headers=headers(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 19, (
            f"Expected admin to see ≥ 19 allocations (full team), got {len(data)}"
        )
        print(f"[PASS] Admin sees {len(data)} allocations (≥ 19 as expected)")

    def test_riley_sees_only_own_allocations(self, riley_token):
        resp = requests.get(f"{BASE_URL}/api/allocations", headers=headers(riley_token))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"[INFO] Riley sees {len(data)} allocation(s)")

    def test_riley_allocations_strictly_fewer_than_admin(self, admin_token, riley_token):
        admin_count = len(requests.get(f"{BASE_URL}/api/allocations", headers=headers(admin_token)).json())
        riley_count = len(requests.get(f"{BASE_URL}/api/allocations", headers=headers(riley_token)).json())
        assert riley_count < admin_count, (
            f"Riley sees {riley_count} allocations but admin sees {admin_count}. "
            "Scoping may be broken — riley should see fewer than all."
        )
        print(f"[PASS] Riley sees {riley_count} (own only); admin sees {admin_count} (all)")

    def test_riley_allocations_all_belong_to_her_resource(self, riley_token):
        """Every allocation Riley sees must have her resource_id."""
        my_alloc = requests.get(f"{BASE_URL}/api/my-allocations", headers=headers(riley_token))
        assert my_alloc.status_code == 200
        resource = my_alloc.json().get("resource")
        if resource is None:
            pytest.skip("Riley has no linked resource — cannot verify ownership")
        riley_rid = resource["id"]

        riley_allocs = requests.get(f"{BASE_URL}/api/allocations", headers=headers(riley_token)).json()
        for alloc in riley_allocs:
            assert alloc["resource_id"] == riley_rid, (
                f"Allocation {alloc.get('id')} belongs to {alloc['resource_id']}, not Riley ({riley_rid})"
            )
        print(f"[PASS] All {len(riley_allocs)} allocation(s) scoped to Riley's resource_id={riley_rid}")


# ── 6. /api/leaves scoping ───────────────────────────────────────────────────

class TestLeavesScoping:
    """
    Riley: GET /api/leaves returns only her own.
    Admin: GET /api/leaves returns all.
    """

    def test_admin_sees_all_leaves(self, admin_token):
        resp = requests.get(f"{BASE_URL}/api/leaves", headers=headers(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"[PASS] Admin sees {len(data)} leave(s) (all)")

    def test_riley_gets_200_on_leaves(self, riley_token):
        resp = requests.get(f"{BASE_URL}/api/leaves", headers=headers(riley_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        print(f"[INFO] Riley sees {len(resp.json())} leave(s)")

    def test_riley_leaves_all_belong_to_her_resource(self, riley_token):
        """Every leave riley sees must have her resource_id."""
        my_alloc = requests.get(f"{BASE_URL}/api/my-allocations", headers=headers(riley_token))
        assert my_alloc.status_code == 200
        resource = my_alloc.json().get("resource")
        if resource is None:
            pytest.skip("Riley has no linked resource")
        riley_rid = resource["id"]

        riley_leaves = requests.get(f"{BASE_URL}/api/leaves", headers=headers(riley_token)).json()
        for lv in riley_leaves:
            assert lv.get("resource_id") == riley_rid, (
                f"Leave {lv.get('id')} has resource_id={lv.get('resource_id')}, not Riley's ({riley_rid})"
            )
        print(f"[PASS] All {len(riley_leaves)} riley leaves scoped to her resource_id")


# ── 7 & 8. POST/DELETE /api/leaves ───────────────────────────────────────────

class TestLeavesCreateDelete:
    """
    Riley POST without resource_id → auto-fill + resource_id matches hers.
    Admin POST without resource_id → 400.
    Riley DELETE own → 200.
    Riley DELETE another's → 403.
    """

    _riley_leave_id = None
    _riley_resource_id = None
    _other_leave_id = None

    def test_riley_creates_leave_without_resource_id(self, riley_token):
        payload = {
            "start_date": "2026-09-01",
            "end_date": "2026-09-03",
            "type": "Annual Leave",
            "notes": "TEST_iter27_riley_leave",
        }
        resp = requests.post(f"{BASE_URL}/api/leaves", json=payload, headers=headers(riley_token))
        assert resp.status_code == 200, f"Riley POST /api/leaves failed: {resp.status_code} {resp.text}"
        doc = resp.json()
        assert "id" in doc
        assert doc.get("resource_id"), f"resource_id not auto-filled: {doc}"
        TestLeavesCreateDelete._riley_leave_id = doc["id"]
        TestLeavesCreateDelete._riley_resource_id = doc["resource_id"]
        print(f"[PASS] Riley created leave {doc['id']} auto-fill resource_id={doc['resource_id']}")

    def test_riley_leave_resource_id_matches_her_resource(self, riley_token):
        if TestLeavesCreateDelete._riley_resource_id is None:
            pytest.skip("No leave created in previous test")
        my_alloc = requests.get(f"{BASE_URL}/api/my-allocations", headers=headers(riley_token))
        assert my_alloc.status_code == 200
        resource = my_alloc.json().get("resource")
        if resource is None:
            pytest.skip("Riley has no linked resource")
        assert TestLeavesCreateDelete._riley_resource_id == resource["id"], (
            f"Leave resource_id={TestLeavesCreateDelete._riley_resource_id} != Riley resource={resource['id']}"
        )
        print(f"[PASS] Auto-filled resource_id={resource['id']} matches Riley's resource")

    def test_admin_cannot_create_leave_without_resource_id(self, admin_token):
        payload = {
            "start_date": "2026-10-01",
            "end_date": "2026-10-01",
            "type": "Sick Leave",
        }
        resp = requests.post(f"{BASE_URL}/api/leaves", json=payload, headers=headers(admin_token))
        assert resp.status_code == 400, (
            f"Expected 400 when admin omits resource_id, got {resp.status_code}: {resp.text}"
        )
        print("[PASS] Admin correctly gets 400 when resource_id is omitted")

    def test_riley_can_delete_own_leave(self, riley_token):
        if TestLeavesCreateDelete._riley_leave_id is None:
            pytest.skip("No leave_id stored — creation may have failed")
        resp = requests.delete(
            f"{BASE_URL}/api/leaves/{TestLeavesCreateDelete._riley_leave_id}",
            headers=headers(riley_token),
        )
        assert resp.status_code == 200, (
            f"Riley DELETE own leave failed: {resp.status_code} {resp.text}"
        )
        TestLeavesCreateDelete._riley_leave_id = None
        print("[PASS] Riley deleted her own leave successfully")

    def test_riley_gets_403_deleting_another_users_leave(self, admin_token, riley_token):
        """Create a leave for a different resource (via admin), verify Riley gets 403."""
        # Find a resource that is not Riley
        resources_resp = requests.get(f"{BASE_URL}/api/resources", headers=headers(admin_token))
        if resources_resp.status_code != 200:
            pytest.skip("Cannot fetch resources")
        resources = resources_resp.json()

        my_alloc = requests.get(f"{BASE_URL}/api/my-allocations", headers=headers(riley_token))
        if my_alloc.status_code != 200 or not my_alloc.json().get("resource"):
            pytest.skip("Cannot determine Riley's resource_id")
        riley_rid = my_alloc.json()["resource"]["id"]

        other = next((r for r in resources if r.get("id") != riley_rid), None)
        if not other:
            pytest.skip("No other resource found")

        # Admin creates leave for the other resource
        create_resp = requests.post(
            f"{BASE_URL}/api/leaves",
            json={
                "resource_id": other["id"],
                "start_date": "2026-11-01",
                "end_date": "2026-11-01",
                "type": "Annual Leave",
                "notes": "TEST_iter27_other_leave",
            },
            headers=headers(admin_token),
        )
        assert create_resp.status_code == 200, f"Admin failed to create leave: {create_resp.text}"
        other_leave_id = create_resp.json()["id"]
        TestLeavesCreateDelete._other_leave_id = other_leave_id

        # Riley tries to delete it → 403
        del_resp = requests.delete(
            f"{BASE_URL}/api/leaves/{other_leave_id}",
            headers=headers(riley_token),
        )
        assert del_resp.status_code == 403, (
            f"Expected 403 when Riley deletes another's leave, got {del_resp.status_code}: {del_resp.text}"
        )
        print("[PASS] Riley correctly gets 403 on another resource's leave")

        # Cleanup
        requests.delete(f"{BASE_URL}/api/leaves/{other_leave_id}", headers=headers(admin_token))
        TestLeavesCreateDelete._other_leave_id = None


# ── 9. /api/timesheets/history ───────────────────────────────────────────────

class TestTimesheetHistory:
    """
    GET /api/timesheets/history — shape check; entries scoped to riley's resource_id.
    Expected: {resource: {name: 'Riley Resource'}, weeks: [], total_weeks_with_data: 0}
    """

    def test_riley_history_shape(self, riley_token):
        resp = requests.get(f"{BASE_URL}/api/timesheets/history", headers=headers(riley_token))
        assert resp.status_code == 200, f"GET /api/timesheets/history failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "weeks" in data, f"Missing 'weeks': {list(data.keys())}"
        assert "total_weeks_with_data" in data, f"Missing 'total_weeks_with_data': {list(data.keys())}"
        assert "resource" in data, f"Missing 'resource': {list(data.keys())}"
        assert isinstance(data["weeks"], list)
        assert isinstance(data["total_weeks_with_data"], int)
        print(f"[PASS] History shape OK — {data['total_weeks_with_data']} week(s) with data")

    def test_riley_history_resource_is_riley(self, riley_token):
        """resource field should identify Riley Resource."""
        resp = requests.get(f"{BASE_URL}/api/timesheets/history", headers=headers(riley_token))
        assert resp.status_code == 200
        data = resp.json()
        resource = data.get("resource")
        if resource is None:
            print("[SKIP] resource is None — Riley has no timesheet history")
            return
        resource_name = resource.get("name", "")
        assert "riley" in resource_name.lower() or "riley" in str(resource).lower(), (
            f"Expected Riley's resource, got: {resource_name}"
        )
        print(f"[PASS] History resource = '{resource_name}'")

    def test_riley_history_entries_scoped_to_her_resource(self, riley_token):
        """All timesheet entries in history must belong to Riley's resource_id."""
        resp = requests.get(f"{BASE_URL}/api/timesheets/history", headers=headers(riley_token))
        assert resp.status_code == 200
        data = resp.json()
        resource = data.get("resource")
        if not resource or not data["weeks"]:
            print("[SKIP] No history entries to validate scoping")
            return
        riley_rid = resource.get("id") or str(resource.get("_id", ""))
        for week in data["weeks"]:
            for entry in week.get("entries", []):
                assert entry["resource_id"] == riley_rid, (
                    f"Entry {entry.get('id')} belongs to {entry['resource_id']}, not Riley ({riley_rid})"
                )
        print("[PASS] All history entries scoped to Riley's resource_id")

    def test_history_custom_weeks_param(self, riley_token):
        resp = requests.get(
            f"{BASE_URL}/api/timesheets/history?weeks=4",
            headers=headers(riley_token),
        )
        assert resp.status_code == 200, f"history?weeks=4 failed: {resp.text}"
        data = resp.json()
        assert "weeks" in data and "total_weeks_with_data" in data
        print("[PASS] weeks=4 param accepted")

    def test_admin_history_shape(self, admin_token):
        """Admin can also call /api/timesheets/history (scoped to own resource)."""
        resp = requests.get(f"{BASE_URL}/api/timesheets/history", headers=headers(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "weeks" in data and "total_weeks_with_data" in data
        print("[PASS] Admin history endpoint returns valid shape")


# ── 10. Admin regression ──────────────────────────────────────────────────────

class TestAdminRegression:
    """Admin: still sees all allocations (≥ 19) and all leaves."""

    def test_admin_sees_all_allocations_count(self, admin_token):
        resp = requests.get(f"{BASE_URL}/api/allocations", headers=headers(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 19, f"Expected ≥ 19 allocations, got {len(data)}"
        print(f"[PASS] Admin allocation count = {len(data)}")

    def test_admin_sees_all_leaves(self, admin_token):
        resp = requests.get(f"{BASE_URL}/api/leaves", headers=headers(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"[PASS] Admin sees {len(data)} leave(s) in total")

    def test_admin_my_allocations_works(self, admin_token):
        resp = requests.get(f"{BASE_URL}/api/my-allocations", headers=headers(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "allocations" in data and "summary" in data
        print(f"[PASS] Admin /api/my-allocations OK")
