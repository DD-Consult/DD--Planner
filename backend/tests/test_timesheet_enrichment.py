"""Backend tests for iteration 46: verify TimesheetResponse enrichment fields
(project_name, client_name, phase_name, resource_name) are returned by
/api/timesheets/my-week and that regression fields are preserved.
"""
import os
from datetime import date, timedelta
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
# Fallback: read frontend env
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

RILEY_EMAIL = "riley@test.com"
RILEY_PASSWORD = "riley123"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

DATA_MIGRATION_PROJECT_ID = "6a5d4ac2ad5ecf8fe70d55b4"
DATA_MIGRATION_PHASE_ID = "96de4e86-cb8d-4ed3-8229-b97913b40cc5"


def _login(email, password):
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


def _current_monday():
    today = date.today()
    return today - timedelta(days=today.weekday())


@pytest.fixture(scope="module")
def riley_token():
    return _login(RILEY_EMAIL, RILEY_PASSWORD)


@pytest.fixture(scope="module")
def riley_headers(riley_token):
    return {"Authorization": f"Bearer {riley_token}"}


@pytest.fixture(scope="module")
def riley_resource_id(riley_headers):
    r = requests.get(f"{BASE_URL}/api/resources", headers=riley_headers, timeout=15)
    assert r.status_code == 200
    resources = r.json()
    for res in resources:
        if "riley" in (res.get("name") or "").lower() or "riley" in (res.get("email") or "").lower():
            return res["id"]
    pytest.skip("Riley resource not found")


class TestEnrichmentFields:
    """Verify TimesheetResponse now includes project_name/client_name/phase_name."""

    def test_my_week_returns_enriched_fields(self, riley_headers):
        monday = _current_monday().isoformat()
        r = requests.get(
            f"{BASE_URL}/api/timesheets/my-week",
            params={"week_start": monday},
            headers=riley_headers,
            timeout=15,
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        # /my-week may return either a list or an object with 'entries'
        entries = payload if isinstance(payload, list) else payload.get("entries", [])
        assert isinstance(entries, list)

        if not entries:
            pytest.skip("No timesheet entries for current week")

        for e in entries:
            # All 4 enrichment keys must be present in schema (Optional but declared)
            assert "project_name" in e, f"project_name missing: {e}"
            assert "client_name" in e, f"client_name missing: {e}"
            assert "phase_name" in e, f"phase_name missing: {e}"
            assert "resource_name" in e, f"resource_name missing: {e}"

            # None of them should be the literal 'Unknown Project' / 'Unknown Client'
            assert e.get("project_name") not in (None, "", "Unknown Project"), (
                f"Bug: project_name not enriched: {e}"
            )
            assert e.get("client_name") not in (None, "", "Unknown Client"), (
                f"Bug: client_name not enriched: {e}"
            )

    def test_my_week_regression_fields_preserved(self, riley_headers):
        monday = _current_monday().isoformat()
        r = requests.get(
            f"{BASE_URL}/api/timesheets/my-week",
            params={"week_start": monday},
            headers=riley_headers,
            timeout=15,
        )
        assert r.status_code == 200
        payload = r.json()
        entries = payload if isinstance(payload, list) else payload.get("entries", [])
        if not entries:
            pytest.skip("No entries to validate")
        required = [
            "id", "resource_id", "project_id", "week_start_date", "week_end_date",
            "planned_hours", "actual_hours", "variance_hours", "status", "created_at",
        ]
        for e in entries:
            for k in required:
                assert k in e, f"regression: field {k} missing from {e}"


class TestUnknownProjectRepro:
    """Create a timesheet for Riley on Data Migration (NOT allocated) and verify
    the /my-week response enriches project_name to the real value, NOT 'Unknown'.
    """

    def test_create_entry_on_unallocated_project_and_verify_enrichment(
        self, riley_headers, riley_resource_id
    ):
        monday = _current_monday()
        payload = {
            "resource_id": riley_resource_id,
            "project_id": DATA_MIGRATION_PROJECT_ID,
            "phase_id": DATA_MIGRATION_PHASE_ID,
            "week_start_date": monday.isoformat(),
            "week_end_date": (monday + timedelta(days=6)).isoformat(),
            "planned_hours": 4,
            "actual_hours": 0,
            "notes": "TEST_iteration46_enrichment",
            "status": "Draft",
        }
        r = requests.post(
            f"{BASE_URL}/api/timesheets", json=payload, headers=riley_headers, timeout=15
        )
        # It's OK if it already exists (409/400) — we only need one entry
        created_id = None
        if r.status_code in (200, 201):
            created_id = r.json().get("id")
        else:
            print(f"Create returned {r.status_code}: {r.text[:200]}")

        try:
            # Now fetch my-week and locate the Data Migration entry
            r2 = requests.get(
                f"{BASE_URL}/api/timesheets/my-week",
                params={"week_start": monday.isoformat()},
                headers=riley_headers,
                timeout=15,
            )
            assert r2.status_code == 200, r2.text
            payload2 = r2.json()
            entries = payload2 if isinstance(payload2, list) else payload2.get("entries", [])
            dm = [e for e in entries if e.get("project_id") == DATA_MIGRATION_PROJECT_ID]
            if not dm:
                pytest.skip("Data Migration entry not present in my-week response")
            entry = dm[0]
            assert entry.get("project_name") and entry["project_name"] != "Unknown Project", (
                f"Bug NOT fixed. Got project_name={entry.get('project_name')!r}"
            )
            assert entry.get("client_name") and entry["client_name"] != "Unknown Client", (
                f"Bug NOT fixed. Got client_name={entry.get('client_name')!r}"
            )
            print(
                f"Enriched OK -> project_name={entry.get('project_name')!r}, "
                f"client_name={entry.get('client_name')!r}, "
                f"phase_name={entry.get('phase_name')!r}"
            )
        finally:
            if created_id:
                requests.delete(
                    f"{BASE_URL}/api/timesheets/{created_id}",
                    headers=riley_headers,
                    timeout=15,
                )


class TestSubmitWeekEndpoint:
    """Verify POST /api/timesheets/submit-week responds according to the Thu/Fri policy."""

    def test_submit_week_responds(self, riley_headers):
        monday = _current_monday().isoformat()
        r = requests.post(
            f"{BASE_URL}/api/timesheets/submit-week",
            params={"week_start": monday},
            headers=riley_headers,
            timeout=15,
        )
        # Acceptable outcomes:
        #  200 -> submitted (if Thu-Mon Sydney window)
        #  403 -> gated by policy (correct behavior on other days)
        #  400 -> no draft entries to submit (acceptable)
        assert r.status_code in (200, 400, 403), f"unexpected {r.status_code}: {r.text}"
        print(f"submit-week status={r.status_code} body={r.text[:200]}")


class TestPlannedHoursRegression:
    """iter45 regression — PUT /api/timesheets/{id} persists planned_hours."""

    def test_update_planned_hours_persists(self, riley_headers, riley_resource_id):
        monday = _current_monday()
        # Get any existing draft entry for riley
        r = requests.get(
            f"{BASE_URL}/api/timesheets/my-week",
            params={"week_start": monday.isoformat()},
            headers=riley_headers,
            timeout=15,
        )
        entries = r.json() if isinstance(r.json(), list) else r.json().get("entries", [])
        draft = next((e for e in entries if e.get("status") == "Draft"), None)
        if not draft:
            pytest.skip("No draft entry to update")
        eid = draft["id"]
        new_val = (draft.get("planned_hours") or 0) + 1
        u = requests.put(
            f"{BASE_URL}/api/timesheets/{eid}",
            json={"planned_hours": new_val},
            headers=riley_headers,
            timeout=15,
        )
        assert u.status_code == 200, u.text
        # verify
        r2 = requests.get(
            f"{BASE_URL}/api/timesheets/my-week",
            params={"week_start": monday.isoformat()},
            headers=riley_headers,
            timeout=15,
        )
        entries2 = r2.json() if isinstance(r2.json(), list) else r2.json().get("entries", [])
        updated = next((e for e in entries2 if e["id"] == eid), None)
        assert updated and float(updated["planned_hours"]) == float(new_val)
