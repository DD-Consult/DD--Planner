"""
Iteration 32 tests:
1) allocation_weekly_hours respects standard_capacity
   - 50% capacity resource at 100% allocation => 20h/wk
   - 100% capacity resource unchanged (100% => 40h/wk, 50% => 20h/wk)
2) create_allocation with allocation_type='hours' computes the correct percentage
   based on resource standard_capacity + biz days over the range.
3) my-allocations weekly_hours reflects standard_capacity.
"""

import os
import pytest
import requests
from datetime import date, timedelta

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    # fallback: read from frontend/.env
    try:
        with open("/app/frontend/.env", "r") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not configured")


BASE_URL = _load_backend_url()

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

TEST_PREFIX = "TEST_iter32_"


# ------- Utility functions imported directly -------
def test_utils_allocation_weekly_hours_respects_capacity():
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path("/app/backend")))
    from utils import allocation_weekly_hours

    # 100% capacity resource - unchanged
    assert allocation_weekly_hours({"percentage": 100}, 100) == 40.0
    assert allocation_weekly_hours({"percentage": 50}, 100) == 20.0
    assert allocation_weekly_hours({"percentage": 25}, 100) == 10.0

    # 50% capacity resource
    # 100% alloc = 20h/wk (bug fix), 50% alloc = 10h/wk
    assert allocation_weekly_hours({"percentage": 100}, 50) == 20.0
    assert allocation_weekly_hours({"percentage": 50}, 50) == 10.0

    # 30% capacity resource
    # 100% alloc = 12h/wk
    assert allocation_weekly_hours({"percentage": 100}, 30) == 12.0

    # Zero/None capacity defaults to 100
    assert allocation_weekly_hours({"percentage": 100}, 0) == 40.0
    assert allocation_weekly_hours({"percentage": 100}, None) == 40.0


# ------- Fixtures -------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def test_project(admin_headers):
    """Create a project with a wide date range and get one back."""
    # Reuse an existing project so we do not accidentally break seed data.
    r = requests.get(f"{BASE_URL}/api/projects", headers=admin_headers, timeout=15)
    assert r.status_code == 200
    projects = r.json()
    # Pick a project with widest date range
    candidates = [p for p in projects if p.get("start_date") and p.get("end_date")]
    assert candidates, "No projects with dates found"
    proj = max(candidates, key=lambda p: (p["end_date"], p["start_date"]))
    return proj


@pytest.fixture(scope="module")
def half_capacity_resource(admin_headers):
    """Create a resource with standard_capacity=50 (part-time)."""
    payload = {
        "name": f"{TEST_PREFIX}HalfCap",
        "email": f"{TEST_PREFIX.lower()}halfcap@test.com",
        "role": "Developer",
        "standard_capacity": 50,
    }
    r = requests.post(f"{BASE_URL}/api/resources", json=payload, headers=admin_headers, timeout=15)
    assert r.status_code in (200, 201), f"resource create failed: {r.status_code} {r.text}"
    resource = r.json()
    yield resource
    # Cleanup
    try:
        requests.delete(f"{BASE_URL}/api/resources/{resource['id']}", headers=admin_headers, timeout=15)
    except Exception:
        pass


@pytest.fixture(scope="module")
def created_allocs_registry():
    """Registry so we can delete at teardown."""
    ids = []
    yield ids


@pytest.fixture(scope="module", autouse=True)
def cleanup_allocs(admin_headers, created_allocs_registry):
    yield
    for aid in created_allocs_registry:
        try:
            requests.delete(f"{BASE_URL}/api/allocations/{aid}", headers=admin_headers, timeout=15)
        except Exception:
            pass


# ------- Tests -------

class TestCreateAllocationHoursMode:
    """Create allocation with allocation_type='hours' — backend should compute percentage."""

    def test_hours_allocation_100_capacity(self, admin_headers, test_project, created_allocs_registry):
        # Find a 100% capacity resource
        r = requests.get(f"{BASE_URL}/api/resources", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        full_res = next(
            (x for x in r.json() if (x.get("standard_capacity") or 100) == 100 and x.get("active") is not False),
            None,
        )
        assert full_res, "No 100% capacity resource found"

        # Project date range
        start = test_project["start_date"][:10]
        end_full = test_project["end_date"][:10]

        # Use a 5-day (1 week, Mon-Fri) window if possible
        s = date.fromisoformat(start)
        # snap to Monday
        while s.weekday() != 0:
            s = s + timedelta(days=1)
        e = s + timedelta(days=4)  # Fri
        # ensure within project bounds
        proj_end = date.fromisoformat(end_full)
        if e > proj_end:
            pytest.skip("Project too short for test window")

        payload = {
            "project_id": test_project["id"],
            "resource_id": full_res["id"],
            "start_date": s.isoformat(),
            "end_date": e.isoformat(),
            "allocation_type": "hours",
            "hours": 40,
            "percentage": 0,  # will be computed
        }
        resp = requests.post(f"{BASE_URL}/api/allocations", json=payload, headers=admin_headers, timeout=15)
        assert resp.status_code == 200, f"POST failed: {resp.status_code} {resp.text}"
        alloc = resp.json()
        created_allocs_registry.append(alloc["id"])

        # 40 hours over 5 biz days on a 100% resource:
        # available = 5 * (100/100) * 8 = 40 hours
        # percentage = round(40/40 * 100) = 100
        assert alloc["percentage"] == 100, f"expected 100%, got {alloc['percentage']}"

    def test_hours_allocation_50_capacity(self, admin_headers, test_project, half_capacity_resource, created_allocs_registry):
        # Use a 5-day (Mon-Fri) window inside project range
        start = test_project["start_date"][:10]
        end_full = test_project["end_date"][:10]
        s = date.fromisoformat(start)
        while s.weekday() != 0:
            s = s + timedelta(days=1)
        e = s + timedelta(days=4)
        if e > date.fromisoformat(end_full):
            pytest.skip("Project too short")

        payload = {
            "project_id": test_project["id"],
            "resource_id": half_capacity_resource["id"],
            "start_date": s.isoformat(),
            "end_date": e.isoformat(),
            "allocation_type": "hours",
            "hours": 20,   # for a 50% resource, 20 hours over 5 biz days = 100% alloc
            "percentage": 0,
        }
        resp = requests.post(f"{BASE_URL}/api/allocations", json=payload, headers=admin_headers, timeout=15)
        assert resp.status_code == 200, f"POST failed: {resp.status_code} {resp.text}"
        alloc = resp.json()
        created_allocs_registry.append(alloc["id"])

        # available = 5 * (50/100) * 8 = 20 hours; percentage = round(20/20*100) = 100
        assert alloc["percentage"] == 100, f"expected 100%, got {alloc['percentage']}"

    def test_hours_allocation_50_capacity_partial(self, admin_headers, test_project, half_capacity_resource, created_allocs_registry):
        start = test_project["start_date"][:10]
        end_full = test_project["end_date"][:10]
        s = date.fromisoformat(start)
        while s.weekday() != 0:
            s = s + timedelta(days=1)
        # use a different week to avoid overlap
        s = s + timedelta(days=7)
        e = s + timedelta(days=4)
        if e > date.fromisoformat(end_full):
            pytest.skip("Project too short")

        payload = {
            "project_id": test_project["id"],
            "resource_id": half_capacity_resource["id"],
            "start_date": s.isoformat(),
            "end_date": e.isoformat(),
            "allocation_type": "hours",
            "hours": 10,   # 10/20 = 50%
            "percentage": 0,
        }
        resp = requests.post(f"{BASE_URL}/api/allocations", json=payload, headers=admin_headers, timeout=15)
        assert resp.status_code == 200, f"POST failed: {resp.status_code} {resp.text}"
        alloc = resp.json()
        created_allocs_registry.append(alloc["id"])

        assert alloc["percentage"] == 50, f"expected 50%, got {alloc['percentage']}"


class TestMyAllocationsWeeklyHoursRespectsCapacity:
    """Verify GET /api/my-allocations weekly_hours = pct% * cap% * 40."""

    def test_admin_my_allocations_response_shape(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/my-allocations?period=month", headers=admin_headers, timeout=15)
        # admin might not have linked resource; endpoint must still return 200
        assert r.status_code == 200
        data = r.json()
        assert "summary" in data
        assert "allocations" in data

    def test_riley_100pct_weekly_hours(self):
        # Riley = 100% resource; behavior unchanged
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": "riley@test.com", "password": "riley123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        if r.status_code != 200:
            pytest.skip(f"Riley login failed: {r.status_code} {r.text}")
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/my-allocations?period=month", headers=headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        std_cap = data["resource"]["standard_capacity"]
        assert std_cap == 100
        # For each allocation entry, weekly_hours = pct/100 * 1.0 * 40 (assuming percentage type)
        for a in data["allocations"]:
            if a.get("allocation_type", "percentage") == "percentage":
                expected = round((a["percentage"] / 100.0) * 40.0, 2)
                assert abs(a["weekly_hours"] - expected) < 0.01, \
                    f"weekly_hours mismatch: got {a['weekly_hours']}, expected {expected}"


# Optional: sanity check the utility compute_allocation_hours also respects capacity
def test_utils_compute_allocation_hours_respects_capacity():
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path("/app/backend")))
    from utils import compute_allocation_hours
    # 100% alloc, 50% capacity, 5 biz days (Mon-Fri)
    alloc = {
        "start_date": date(2026, 1, 5),  # Monday
        "end_date": date(2026, 1, 9),    # Friday
        "percentage": 100,
        "allocation_type": "percentage",
    }
    # weekly_hours = 20; biz/5 = 1 → 20 total
    assert compute_allocation_hours(alloc, standard_capacity=50) == 20.0
    # same alloc on 100% capacity → 40h
    assert compute_allocation_hours(alloc, standard_capacity=100) == 40.0
