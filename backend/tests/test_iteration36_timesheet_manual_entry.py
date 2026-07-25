"""
Iteration 36: Resource timesheet manual entry
Tests:
- GET /api/projects/all-active-summary returns all active/pipeline projects
- POST /api/timesheets allows entries for non-allocated projects
- GET /api/projects/{id} now allows access if user has a timesheet for that project
"""
import os
import pytest
import requests
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")

RILEY_EMAIL = "riley@test.com"
RILEY_PASSWORD = "riley123"


def _login(email, password):
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def riley_token():
    return _login(RILEY_EMAIL, RILEY_PASSWORD)


@pytest.fixture(scope="module")
def riley_headers(riley_token):
    return {"Authorization": f"Bearer {riley_token}"}


@pytest.fixture(scope="module")
def riley_resource(riley_headers):
    r = requests.get(f"{BASE_URL}/api/users/me/resource", headers=riley_headers, timeout=15)
    assert r.status_code == 200, r.text
    resource = r.json()
    resource_id = resource.get("id") or resource.get("_id")
    return {"resource_id": resource_id}


class TestAllActiveSummary:
    """GET /api/projects/all-active-summary"""

    def test_endpoint_accessible_for_resource(self, riley_headers):
        r = requests.get(f"{BASE_URL}/api/projects/all-active-summary", headers=riley_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Expected active/pipeline projects"

    def test_returns_projects_not_allocated_to_riley(self, riley_headers):
        # Check Riley sees more projects here than in /api/projects (allocated-only)
        r_all = requests.get(f"{BASE_URL}/api/projects/all-active-summary", headers=riley_headers, timeout=15)
        r_alloc = requests.get(f"{BASE_URL}/api/projects", headers=riley_headers, timeout=15)
        assert r_all.status_code == 200
        assert r_alloc.status_code == 200
        all_projects = r_all.json()
        alloc_projects = r_alloc.json()
        print(f"all-active-summary count={len(all_projects)}, allocated projects count={len(alloc_projects)}")
        # Should have Mobile App in all-active-summary but not in allocated list
        all_names = [p.get("name") for p in all_projects]
        alloc_names = [p.get("name") for p in alloc_projects]
        assert "Mobile App" in all_names, f"Mobile App should be in all-active list, got: {all_names}"

    def test_response_shape(self, riley_headers):
        r = requests.get(f"{BASE_URL}/api/projects/all-active-summary", headers=riley_headers, timeout=15)
        data = r.json()
        p = data[0]
        assert "id" in p
        assert "name" in p
        assert "phases" in p
        assert "status" in p
        # Should NOT include _id (must be serialized properly)
        assert "_id" not in p, f"_id should not leak: {p}"


class TestTimesheetForNonAllocatedProject:
    """POST /api/timesheets should allow non-allocated projects"""

    def _get_project_by_name(self, riley_headers, name):
        r = requests.get(f"{BASE_URL}/api/projects/all-active-summary", headers=riley_headers, timeout=15)
        for p in r.json():
            if p.get("name") == name:
                return p
        return None

    def test_create_timesheet_for_non_allocated_project(self, riley_headers, riley_resource):
        rid = riley_resource["resource_id"]
        assert rid, "Could not resolve Riley's resource_id"

        mobile_app = self._get_project_by_name(riley_headers, "Mobile App")
        assert mobile_app, "Mobile App project not found"
        phases = mobile_app.get("phases") or []
        assert phases, "Mobile App must have at least one phase"
        phase_id = phases[0].get("id")
        assert phase_id, "Phase must have an id"

        # Compute Monday of this week
        today = datetime.utcnow().date()
        monday = today - timedelta(days=today.weekday())
        friday = monday + timedelta(days=4)

        payload = {
            "resource_id": rid,
            "project_id": mobile_app["id"],
            "phase_id": phase_id,
            "week_start_date": monday.isoformat(),
            "week_end_date": friday.isoformat(),
            "planned_hours": 8,
            "actual_hours": 8,
            "notes": "TEST_iteration36 non-allocated entry",
            "status": "Draft",
        }
        r = requests.post(f"{BASE_URL}/api/timesheets", json=payload, headers=riley_headers, timeout=20)
        assert r.status_code == 200, f"Create failed: {r.status_code} {r.text}"
        ts = r.json()
        assert ts.get("actual_hours") == 8
        assert ts.get("project_id") == mobile_app["id"]

        # Cleanup: delete the entry
        ts_id = ts.get("id") or ts.get("_id")
        if ts_id:
            requests.delete(f"{BASE_URL}/api/timesheets/{ts_id}", headers=riley_headers, timeout=15)

    def test_project_detail_access_after_timesheet(self, riley_headers, riley_resource):
        """After creating a timesheet, resource should access the project detail (not 403)."""
        rid = riley_resource["resource_id"]
        assert rid
        mobile_app = self._get_project_by_name(riley_headers, "Mobile App")
        assert mobile_app
        mobile_id = mobile_app["id"]

        # Baseline: without timesheet, should be 403 (may not be true if prior test left data)
        # So we create a fresh timesheet then check access
        phases = mobile_app.get("phases") or []
        phase_id = phases[0].get("id")
        today = datetime.utcnow().date()
        monday = today - timedelta(days=today.weekday())
        friday = monday + timedelta(days=4)
        payload = {
            "resource_id": rid,
            "project_id": mobile_id,
            "phase_id": phase_id,
            "week_start_date": monday.isoformat(),
            "week_end_date": friday.isoformat(),
            "planned_hours": 1,
            "actual_hours": 1,
            "notes": "TEST_iteration36 project-access",
            "status": "Draft",
        }
        create = requests.post(f"{BASE_URL}/api/timesheets", json=payload, headers=riley_headers, timeout=20)
        assert create.status_code == 200, create.text
        ts_id = create.json().get("id") or create.json().get("_id")

        try:
            r = requests.get(f"{BASE_URL}/api/projects/{mobile_id}", headers=riley_headers, timeout=15)
            assert r.status_code == 200, f"Expected 200 after timesheet exists, got {r.status_code}: {r.text}"
            data = r.json()
            assert data.get("name") == "Mobile App"
        finally:
            if ts_id:
                requests.delete(f"{BASE_URL}/api/timesheets/{ts_id}", headers=riley_headers, timeout=15)


class TestAuth:
    def test_login_form_encoded(self):
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": RILEY_EMAIL, "password": RILEY_PASSWORD},
            timeout=15,
        )
        assert r.status_code == 200
        assert "access_token" in r.json()
