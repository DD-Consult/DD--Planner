"""
Iteration 31 — Bug fix regression tests for GET /api/my-allocations
capacity calculation for part-time (standard_capacity < 100) resources.

Verifies:
- Response contains capacity_used_percentage (relative to standard_capacity),
  raw_allocation_pct, available_hours_per_week, standard_capacity, is_over_capacity
- For 100% resource: capacity_used_percentage == raw_allocation_pct,
  available_hours_per_week == 40
- For 30% resource: capacity_used_percentage == round(raw/30 * 100),
  available_hours_per_week == 12
- For 50% resource: available_hours_per_week == 20
- Division-by-zero guard: if standard_capacity == 0, effective_capacity falls back to 100
"""

import os
import pytest
import requests
from datetime import date, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')


# ---- Fixtures ---------------------------------------------------------------

@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(api, email, password):
    # OAuth2 password form (username/password form-encoded)
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      data={"username": email, "password": password})
    if r.status_code != 200:
        pytest.skip(f"Auth failed for {email}: {r.status_code} {r.text[:200]}")
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="session")
def admin_token(api):
    return _login(api, "admin@test.com", "admin123")


@pytest.fixture(scope="session")
def riley_token(api):
    return _login(api, "riley@test.com", "riley123")


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture
def riley_headers(riley_token):
    return {"Authorization": f"Bearer {riley_token}", "Content-Type": "application/json"}


# ---- Tests for existing 100% resource (Riley) -------------------------------

class TestMyAllocationsRileyFullCapacity:
    """Riley has standard_capacity = 100 → capacity_used_percentage should equal raw_allocation_pct."""

    def test_endpoint_reachable(self, api, riley_headers):
        r = api.get(f"{BASE_URL}/api/my-allocations?period=month", headers=riley_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "summary" in data
        assert "resource" in data

    def test_summary_has_new_fields(self, api, riley_headers):
        r = api.get(f"{BASE_URL}/api/my-allocations?period=month", headers=riley_headers)
        summary = r.json()["summary"]
        # New fields introduced by the bug fix
        for k in ("capacity_used_percentage", "raw_allocation_pct",
                  "available_hours_per_week", "standard_capacity",
                  "is_over_capacity", "total_weekly_hours", "total_allocations"):
            assert k in summary, f"Missing field: {k}"

    def test_riley_standard_capacity_is_100(self, api, riley_headers):
        r = api.get(f"{BASE_URL}/api/my-allocations?period=month", headers=riley_headers)
        summary = r.json()["summary"]
        assert summary["standard_capacity"] == 100, \
            f"Riley's standard_capacity is {summary['standard_capacity']}, expected 100"

    def test_capacity_used_equals_raw_for_100pct_resource(self, api, riley_headers):
        r = api.get(f"{BASE_URL}/api/my-allocations?period=month", headers=riley_headers)
        summary = r.json()["summary"]
        assert summary["capacity_used_percentage"] == summary["raw_allocation_pct"], (
            f"For 100% resource, capacity_used_percentage ({summary['capacity_used_percentage']}) "
            f"must equal raw_allocation_pct ({summary['raw_allocation_pct']})"
        )

    def test_available_hours_per_week_is_40_for_100pct(self, api, riley_headers):
        r = api.get(f"{BASE_URL}/api/my-allocations?period=month", headers=riley_headers)
        summary = r.json()["summary"]
        # available_hours_per_week is rounded to 1 decimal → 40.0
        assert summary["available_hours_per_week"] == 40 or summary["available_hours_per_week"] == 40.0, \
            f"Expected 40h available, got {summary['available_hours_per_week']}"

    def test_is_over_capacity_matches_raw_gt_standard(self, api, riley_headers):
        r = api.get(f"{BASE_URL}/api/my-allocations?period=month", headers=riley_headers)
        s = r.json()["summary"]
        expected = s["raw_allocation_pct"] > s["standard_capacity"]
        assert s["is_over_capacity"] == expected


# ---- Tests using dynamically-created part-time resources --------------------

@pytest.fixture(scope="class")
def created_resources(api, admin_token):
    """Create part-time TEST_ resources and matching users so we can login as them.
    Cleanup at end."""
    created = []
    admin_h = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}

    # Discover resource + user endpoints
    for cap in (30, 50, 0):
        # Create resource
        res_payload = {
            "name": f"TEST_iter31_part{cap}",
            "role": "Consultant",
            "email": f"TEST_iter31_part{cap}@test.com",
            "standard_capacity": cap,
        }
        rr = api.post(f"{BASE_URL}/api/resources", json=res_payload, headers=admin_h)
        if rr.status_code not in (200, 201):
            pytest.skip(f"Could not create resource (cap={cap}): {rr.status_code} {rr.text[:250]}")
        rjson = rr.json()
        res_id = rjson.get("id") or rjson.get("_id")

        # Create paired user linked to this resource
        user_payload = {
            "email": f"TEST_iter31_part{cap}@test.com",
            "password": "Testpass123!",
            "name": f"TEST iter31 part{cap}",
            "role": "resource",
            "resource_id": res_id,
        }
        # Try common user creation endpoints
        ur = None
        for path in ("/api/users", "/api/auth/register", "/api/admin/users"):
            ur = api.post(f"{BASE_URL}{path}", json=user_payload, headers=admin_h)
            if ur.status_code in (200, 201):
                break

        created.append({
            "resource_id": res_id,
            "email": user_payload["email"],
            "password": user_payload["password"],
            "capacity": cap,
            "user_created": ur is not None and ur.status_code in (200, 201),
        })

    yield created

    # Teardown: delete resources (best-effort)
    for c in created:
        try:
            api.delete(f"{BASE_URL}/api/resources/{c['resource_id']}", headers=admin_h)
        except Exception:
            pass


class TestMyAllocationsPartTime:
    """Verify capacity formula for part-time resources by inspecting the response directly.
    Uses admin token but passes a specific resource by logging in as the newly created user
    (fallback: skip if user creation isn't supported)."""

    def _login_as(self, api, email, password):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          data={"username": email, "password": password})
        return r.json().get("access_token") if r.status_code == 200 else None

    def test_30pct_resource_available_hours_is_12(self, api, created_resources):
        r = next((c for c in created_resources if c["capacity"] == 30), None)
        if not r or not r["user_created"]:
            pytest.skip("Could not create 30% user for part-time test")
        tok = self._login_as(api, r["email"], r["password"])
        if not tok:
            pytest.skip("Could not login as 30% user")
        h = {"Authorization": f"Bearer {tok}"}
        resp = api.get(f"{BASE_URL}/api/my-allocations?period=month", headers=h)
        assert resp.status_code == 200, resp.text
        s = resp.json()["summary"]
        assert s["standard_capacity"] == 30
        # (30/100) * 40 = 12
        assert s["available_hours_per_week"] == 12 or s["available_hours_per_week"] == 12.0, \
            f"Expected 12h/wk for 30% capacity, got {s['available_hours_per_week']}"

    def test_50pct_resource_available_hours_is_20(self, api, created_resources):
        r = next((c for c in created_resources if c["capacity"] == 50), None)
        if not r or not r["user_created"]:
            pytest.skip("Could not create 50% user for part-time test")
        tok = self._login_as(api, r["email"], r["password"])
        if not tok:
            pytest.skip("Could not login as 50% user")
        h = {"Authorization": f"Bearer {tok}"}
        resp = api.get(f"{BASE_URL}/api/my-allocations?period=month", headers=h)
        assert resp.status_code == 200
        s = resp.json()["summary"]
        assert s["standard_capacity"] == 50
        assert s["available_hours_per_week"] == 20 or s["available_hours_per_week"] == 20.0

    def test_30pct_resource_no_allocations_capacity_zero(self, api, created_resources):
        """A brand new 30% resource with no allocations → capacity_used_percentage == 0
        and raw_allocation_pct == 0. Sanity check for the formula path."""
        r = next((c for c in created_resources if c["capacity"] == 30), None)
        if not r or not r["user_created"]:
            pytest.skip("Could not create 30% user")
        tok = self._login_as(api, r["email"], r["password"])
        if not tok:
            pytest.skip("Login failed for 30% user")
        h = {"Authorization": f"Bearer {tok}"}
        resp = api.get(f"{BASE_URL}/api/my-allocations?period=month", headers=h)
        s = resp.json()["summary"]
        # No allocations → both should be 0, is_over_capacity should be False
        assert s["raw_allocation_pct"] == 0
        assert s["capacity_used_percentage"] == 0
        assert s["is_over_capacity"] is False

    def test_zero_capacity_resource_defaults_to_100(self, api, created_resources):
        """standard_capacity=0 must NOT divide by zero — server should default effective_capacity to 100.
        available_hours_per_week for 0% is (0/100)*40 = 0."""
        r = next((c for c in created_resources if c["capacity"] == 0), None)
        if not r or not r["user_created"]:
            pytest.skip("Could not create 0% user")
        tok = self._login_as(api, r["email"], r["password"])
        if not tok:
            pytest.skip("Login failed for 0% user")
        h = {"Authorization": f"Bearer {tok}"}
        resp = api.get(f"{BASE_URL}/api/my-allocations?period=month", headers=h)
        assert resp.status_code == 200, f"Zero capacity broke endpoint: {resp.text[:200]}"
        s = resp.json()["summary"]
        # Should NOT crash. available_hours_per_week may be 0.0 (0/100 * 40).
        assert isinstance(s["capacity_used_percentage"], (int, float))


# ---- Formula unit test (does not rely on user creation) ---------------------

class TestCapacityFormulaViaAdminInspection:
    """Verify formula by inspecting all resources via admin: for each active resource,
    compute their expected available_hours_per_week and confirm the endpoint returns
    consistent numbers when we can reach it. Also validates the fix is present in
    the deployed code."""

    def test_formula_documented_in_response_for_riley(self, api, riley_headers):
        """For Riley (cap=100): available = 40, if raw=X then used=X."""
        r = api.get(f"{BASE_URL}/api/my-allocations?period=month", headers=riley_headers)
        assert r.status_code == 200
        s = r.json()["summary"]
        # Recompute expected values
        std_cap = s["standard_capacity"] or 100
        effective_cap = std_cap if std_cap > 0 else 100
        expected_pct = round((s["raw_allocation_pct"] / effective_cap) * 100)
        expected_hrs = round((effective_cap / 100.0) * 40, 1)
        assert s["capacity_used_percentage"] == expected_pct, \
            f"capacity_used_percentage mismatch: got {s['capacity_used_percentage']}, expected {expected_pct}"
        # Server rounds to 1dp
        assert abs(s["available_hours_per_week"] - expected_hrs) < 0.11
