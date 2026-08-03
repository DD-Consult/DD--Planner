"""Tests for WBS access control - project leads (resource role) should be
allowed to perform WBS write operations on projects they lead.

Setup requires the following test users pre-configured in the DB:
  - don@ddconsult.tech  (super_admin)                     password: @Ddplanner2026
  - dhruti@ddconsult.tech (resource, leads project ServAI) password: Test@2026
  - akshaya@ddconsult.tech (resource, NOT lead of ServAI)  password: Test@2026
"""
import os
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

# Project lead by Dhruti (resource role) - ServAI
LEAD_PROJECT_ID = "696430ac4970d0cc2c6b42d5"

ADMIN = ("don@ddconsult.tech", "@Ddplanner2026")
LEAD = ("dhruti@ddconsult.tech", "Test@2026")
NON_LEAD = ("akshaya@ddconsult.tech", "Test@2026")


def _login(email, password):
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": email, "password": password},
    )
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def admin_token():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def lead_token():
    return _login(*LEAD)


@pytest.fixture(scope="module")
def non_lead_token():
    return _login(*NON_LEAD)


# Track created task ids to clean up
_created_task_ids = []


@pytest.fixture(scope="module", autouse=True)
def cleanup(admin_token):
    yield
    for tid in _created_task_ids:
        try:
            requests.delete(f"{BASE_URL}/api/wbs/tasks/{tid}", headers=_hdr(admin_token))
        except Exception:
            pass


# ---------------------------------------------------------------
# 1) Lead can CREATE
# ---------------------------------------------------------------
def test_lead_can_create_wbs_task(lead_token):
    payload = {
        "name": "TEST_Lead_Create_Task",
        "phase_name": "Discovery",
        "estimated_hours": 4,
        "status": "todo",
        "priority": "medium",
    }
    r = requests.post(
        f"{BASE_URL}/api/projects/{LEAD_PROJECT_ID}/wbs/tasks",
        json=payload,
        headers=_hdr(lead_token),
    )
    assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text}"
    data = r.json()
    assert data.get("name") == "TEST_Lead_Create_Task"
    assert "id" in data
    _created_task_ids.append(data["id"])


# ---------------------------------------------------------------
# 2) Lead can UPDATE
# ---------------------------------------------------------------
def test_lead_can_update_wbs_task(lead_token):
    # Create then update
    c = requests.post(
        f"{BASE_URL}/api/projects/{LEAD_PROJECT_ID}/wbs/tasks",
        json={"name": "TEST_Lead_Update_Task", "estimated_hours": 2},
        headers=_hdr(lead_token),
    )
    assert c.status_code == 200, c.text
    tid = c.json()["id"]
    _created_task_ids.append(tid)

    r = requests.put(
        f"{BASE_URL}/api/wbs/tasks/{tid}",
        json={"name": "TEST_Lead_Update_Task_Renamed"},
        headers=_hdr(lead_token),
    )
    assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text}"
    assert r.json().get("name") == "TEST_Lead_Update_Task_Renamed"


# ---------------------------------------------------------------
# 3) Lead can DELETE
# ---------------------------------------------------------------
def test_lead_can_delete_wbs_task(lead_token):
    c = requests.post(
        f"{BASE_URL}/api/projects/{LEAD_PROJECT_ID}/wbs/tasks",
        json={"name": "TEST_Lead_Delete_Task", "estimated_hours": 1},
        headers=_hdr(lead_token),
    )
    assert c.status_code == 200, c.text
    tid = c.json()["id"]

    r = requests.delete(f"{BASE_URL}/api/wbs/tasks/{tid}", headers=_hdr(lead_token))
    assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text}"


# ---------------------------------------------------------------
# 4) Non-lead resource forbidden
# ---------------------------------------------------------------
def test_non_lead_cannot_create_wbs_task(non_lead_token):
    r = requests.post(
        f"{BASE_URL}/api/projects/{LEAD_PROJECT_ID}/wbs/tasks",
        json={"name": "TEST_Nonlead_Task", "estimated_hours": 1},
        headers=_hdr(non_lead_token),
    )
    assert r.status_code == 403, f"Expected 403 got {r.status_code}: {r.text}"


def test_non_lead_cannot_update_wbs_task(non_lead_token, admin_token):
    # Admin creates a task so we have one to attempt update against
    c = requests.post(
        f"{BASE_URL}/api/projects/{LEAD_PROJECT_ID}/wbs/tasks",
        json={"name": "TEST_Admin_Task_For_Nonlead_Update", "estimated_hours": 1},
        headers=_hdr(admin_token),
    )
    assert c.status_code == 200, c.text
    tid = c.json()["id"]
    _created_task_ids.append(tid)

    r = requests.put(
        f"{BASE_URL}/api/wbs/tasks/{tid}",
        json={"name": "hacked"},
        headers=_hdr(non_lead_token),
    )
    assert r.status_code == 403, f"Expected 403 got {r.status_code}: {r.text}"


def test_non_lead_cannot_delete_wbs_task(non_lead_token, admin_token):
    c = requests.post(
        f"{BASE_URL}/api/projects/{LEAD_PROJECT_ID}/wbs/tasks",
        json={"name": "TEST_Admin_Task_For_Nonlead_Delete", "estimated_hours": 1},
        headers=_hdr(admin_token),
    )
    assert c.status_code == 200, c.text
    tid = c.json()["id"]
    _created_task_ids.append(tid)

    r = requests.delete(f"{BASE_URL}/api/wbs/tasks/{tid}", headers=_hdr(non_lead_token))
    assert r.status_code == 403, f"Expected 403 got {r.status_code}: {r.text}"


# ---------------------------------------------------------------
# 5) Admin regression
# ---------------------------------------------------------------
def test_admin_can_create_wbs_task(admin_token):
    r = requests.post(
        f"{BASE_URL}/api/projects/{LEAD_PROJECT_ID}/wbs/tasks",
        json={"name": "TEST_Admin_Create_Task", "estimated_hours": 1},
        headers=_hdr(admin_token),
    )
    assert r.status_code == 200, r.text
    _created_task_ids.append(r.json()["id"])


# ---------------------------------------------------------------
# 6) Project-scoped write endpoints for leads
# ---------------------------------------------------------------
def test_lead_can_recalculate_dates(lead_token):
    r = requests.post(
        f"{BASE_URL}/api/projects/{LEAD_PROJECT_ID}/wbs/recalculate-dates",
        headers=_hdr(lead_token),
    )
    assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text}"


def test_lead_can_set_baseline(lead_token):
    r = requests.post(
        f"{BASE_URL}/api/projects/{LEAD_PROJECT_ID}/wbs/set-baseline",
        headers=_hdr(lead_token),
    )
    assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text}"


def test_lead_can_sync_dates_from_wbs(lead_token):
    r = requests.post(
        f"{BASE_URL}/api/projects/{LEAD_PROJECT_ID}/sync-dates-from-wbs",
        headers=_hdr(lead_token),
    )
    # 200 (synced) or 400 (no dated tasks) both mean auth passed; 403 would be the bug.
    assert r.status_code in (200, 400), f"Expected 200/400 got {r.status_code}: {r.text}"
    assert r.status_code != 403


def test_non_lead_cannot_recalculate_dates(non_lead_token):
    r = requests.post(
        f"{BASE_URL}/api/projects/{LEAD_PROJECT_ID}/wbs/recalculate-dates",
        headers=_hdr(non_lead_token),
    )
    assert r.status_code == 403, f"Expected 403 got {r.status_code}: {r.text}"


# ---------------------------------------------------------------
# 7) Milestone complete + set-baseline (task-level) as lead
# ---------------------------------------------------------------
def test_lead_can_complete_milestone_and_set_task_baseline(lead_token):
    # Create milestone
    c = requests.post(
        f"{BASE_URL}/api/projects/{LEAD_PROJECT_ID}/wbs/tasks",
        json={
            "name": "TEST_Lead_Milestone",
            "is_milestone": True,
            "milestone_date": "2026-06-01",
        },
        headers=_hdr(lead_token),
    )
    assert c.status_code == 200, c.text
    tid = c.json()["id"]
    _created_task_ids.append(tid)

    # Complete milestone
    r = requests.patch(
        f"{BASE_URL}/api/wbs/tasks/{tid}/complete-milestone?completed=true",
        headers=_hdr(lead_token),
    )
    assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text}"

    # Task-level set baseline
    r2 = requests.post(
        f"{BASE_URL}/api/wbs/tasks/{tid}/set-baseline",
        headers=_hdr(lead_token),
    )
    assert r2.status_code == 200, f"Expected 200 got {r2.status_code}: {r2.text}"
