"""Backend tests for PUT /api/timesheets/{id} — resource inline edit of Draft entries."""
import os
import pytest
import requests
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://allocation-tracker-5.preview.emergentagent.com').rstrip('/')

RILEY = {"email": "riley@test.com", "password": "riley123"}
ADMIN = {"email": "admin@test.com", "password": "admin123"}


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      data={"username": creds["email"], "password": creds["password"]}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    j = r.json()
    return j.get("access_token") or j.get("token")


@pytest.fixture(scope="module")
def riley_headers():
    return {"Authorization": f"Bearer {_login(RILEY)}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_login(ADMIN)}", "Content-Type": "application/json"}


def _current_week():
    today = datetime.utcnow().date()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)
    return monday.isoformat(), friday.isoformat()


def test_login_riley(riley_headers):
    assert riley_headers["Authorization"].startswith("Bearer ")


def test_riley_can_update_own_draft(riley_headers):
    """Create a draft entry via autofill/create, then update it via PUT."""
    week_start, week_end = _current_week()

    # Try autofill first
    r = requests.post(f"{BASE_URL}/api/timesheets/auto-fill",
                      params={"week_start": week_start}, headers=riley_headers, timeout=30)
    print(f"autofill: {r.status_code} {r.text[:200]}")

    # Fetch history to find a draft entry
    r = requests.get(f"{BASE_URL}/api/timesheets/history", params={"weeks": 1}, headers=riley_headers, timeout=30)
    assert r.status_code == 200, r.text
    weeks = r.json().get("weeks", [])
    draft_entry = None
    for w in weeks:
        if w.get("week_start") == week_start:
            for e in w.get("entries", []):
                if e.get("status") == "Draft":
                    draft_entry = e
                    break
    
    if not draft_entry:
        # Need to create one - get an allocation
        r = requests.get(f"{BASE_URL}/api/my-allocations?period=month", headers=riley_headers, timeout=30)
        assert r.status_code == 200
        allocs_data = r.json()
        resource = allocs_data.get("resource", {})
        allocs = allocs_data.get("allocations", [])
        if not allocs:
            pytest.skip("Riley has no allocations - can't create entry")
        alloc = allocs[0]
        # Get project phases
        r = requests.get(f"{BASE_URL}/api/projects/{alloc['project_id']}", headers=riley_headers, timeout=30)
        assert r.status_code == 200
        # Riley's allocation is out of current week; use a project that has phases
        proj_id = "6a5d4ac2ad5ecf8fe70d55b4"  # Data Migration
        phase_id = "96de4e86-cb8d-4ed3-8229-b97913b40cc5"
        payload = {
            "resource_id": resource["id"],
            "project_id": proj_id,
            "phase_id": phase_id,
            "week_start_date": week_start,
            "week_end_date": week_end,
            "planned_hours": 5,
            "actual_hours": 5,
            "notes": "TEST_pytest_entry",
            "status": "Draft",
        }
        r = requests.post(f"{BASE_URL}/api/timesheets", json=payload, headers=riley_headers, timeout=30)
        assert r.status_code in (200, 201), f"create failed: {r.status_code} {r.text}"
        draft_entry = r.json()

    entry_id = draft_entry["id"]
    print(f"Draft entry id: {entry_id}, planned={draft_entry.get('planned_hours')}, actual={draft_entry.get('actual_hours')}")

    # Update it
    upd = {"planned_hours": 3.5, "actual_hours": 5, "notes": "TEST_updated_via_pytest"}
    r = requests.put(f"{BASE_URL}/api/timesheets/{entry_id}", json=upd, headers=riley_headers, timeout=30)
    assert r.status_code == 200, f"update failed: {r.status_code} {r.text}"
    updated = r.json()
    assert updated["actual_hours"] == 5, updated
    assert updated["notes"] == "TEST_updated_via_pytest"
    # FIX verification: planned_hours must now persist (TimesheetUpdate schema field added)
    assert updated["planned_hours"] == 3.5, f"planned_hours not persisted: {updated}"
    # variance = actual - planned = 5 - 3.5 = 1.5
    assert updated["variance_hours"] == 1.5, f"variance not recalculated: {updated}"

    # Verify persistence via GET history
    r = requests.get(f"{BASE_URL}/api/timesheets/history?weeks=1", headers=riley_headers, timeout=30)
    assert r.status_code == 200
    found = False
    for w in r.json().get("weeks", []):
        for e in w.get("entries", []):
            if e.get("id") == entry_id:
                assert e["actual_hours"] == 5
                assert e["planned_hours"] == 3.5, f"planned_hours not persisted in GET: {e}"
                assert e["variance_hours"] == 1.5
                found = True
    assert found, "updated entry not found in history"

    # Test 2: planned=8 & actual=6 → variance=-2
    upd2 = {"planned_hours": 8, "actual_hours": 6}
    r = requests.put(f"{BASE_URL}/api/timesheets/{entry_id}", json=upd2, headers=riley_headers, timeout=30)
    assert r.status_code == 200
    u2 = r.json()
    assert u2["planned_hours"] == 8
    assert u2["actual_hours"] == 6
    assert u2["variance_hours"] == -2, f"expected -2, got {u2['variance_hours']}"

    # Test 3: update only actual_hours - variance should recalc using existing planned=8
    upd3 = {"actual_hours": 10}
    r = requests.put(f"{BASE_URL}/api/timesheets/{entry_id}", json=upd3, headers=riley_headers, timeout=30)
    assert r.status_code == 200
    u3 = r.json()
    assert u3["planned_hours"] == 8, "planned should be unchanged"
    assert u3["actual_hours"] == 10
    assert u3["variance_hours"] == 2, f"variance regression on actual-only update: {u3}"

    # Test 4: update only notes - variance should NOT recalc; prior values preserved
    prior_variance = u3["variance_hours"]
    upd4 = {"notes": "TEST_notes_only"}
    r = requests.put(f"{BASE_URL}/api/timesheets/{entry_id}", json=upd4, headers=riley_headers, timeout=30)
    assert r.status_code == 200
    u4 = r.json()
    assert u4["notes"] == "TEST_notes_only"
    assert u4["planned_hours"] == 8
    assert u4["actual_hours"] == 10
    assert u4["variance_hours"] == prior_variance, f"variance mutated on notes-only update: {u4}"


def test_riley_cannot_update_submitted(riley_headers, admin_headers):
    """Find or admin-flip a timesheet to Submitted, then Riley PUT — expect 403."""
    # Look for existing Submitted/Approved via history first
    r = requests.get(f"{BASE_URL}/api/timesheets/history?weeks=12", headers=riley_headers, timeout=30)
    assert r.status_code == 200
    submitted_entry = None
    for w in r.json().get("weeks", []):
        for e in w.get("entries", []):
            if e.get("status") in ("Submitted", "Approved"):
                submitted_entry = e
                break
        if submitted_entry:
            break

    if not submitted_entry:
        # Try to flip one of Riley's Draft entries to Submitted via admin PUT
        draft_entry = None
        for w in r.json().get("weeks", []):
            for e in w.get("entries", []):
                if e.get("status") == "Draft":
                    draft_entry = e
                    break
            if draft_entry:
                break
        if not draft_entry:
            pytest.skip("No entries available")
        # Admin sets status to Submitted
        ar = requests.put(f"{BASE_URL}/api/timesheets/{draft_entry['id']}",
                          json={"status": "Submitted"}, headers=admin_headers, timeout=30)
        if ar.status_code != 200:
            pytest.skip(f"admin couldn't flip status: {ar.status_code} {ar.text}")
        submitted_entry = ar.json()

    upd = {"actual_hours": 99}
    r = requests.put(f"{BASE_URL}/api/timesheets/{submitted_entry['id']}", json=upd, headers=riley_headers, timeout=30)
    assert r.status_code in (400, 403), f"expected 403, got {r.status_code} {r.text}"

    # Restore back to Draft so subsequent runs don't fail
    requests.put(f"{BASE_URL}/api/timesheets/{submitted_entry['id']}",
                 json={"status": "Draft"}, headers=admin_headers, timeout=30)


def test_riley_cannot_update_others_entry(riley_headers, admin_headers):
    """Ensure a resource cannot update someone else's timesheet."""
    # Admin lists all timesheets, pick one not belonging to riley
    r = requests.get(f"{BASE_URL}/api/timesheets", headers=admin_headers, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"can't list all timesheets: {r.status_code}")
    all_ts = r.json()
    # Riley's resource id
    rr = requests.get(f"{BASE_URL}/api/my-allocations?period=month", headers=riley_headers, timeout=30)
    riley_res_id = rr.json().get("resource", {}).get("id")
    other = None
    for t in all_ts if isinstance(all_ts, list) else []:
        if t.get("resource_id") != riley_res_id:
            other = t
            break
    if not other:
        pytest.skip("no other resource timesheets found")

    r = requests.put(f"{BASE_URL}/api/timesheets/{other['id']}", json={"actual_hours": 1}, headers=riley_headers, timeout=30)
    assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text}"
