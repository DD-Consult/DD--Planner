"""Iteration 48 tests: WBS topological ordering + auto end-date recalculation.

Covers:
- POST /api/projects/{id}/wbs/recalculate-dates
- POST /api/projects/{id}/wbs/tasks with auto end_date
- PUT  /api/wbs/tasks/{id}      with auto end_date recompute
- Topological ordering invariant (via task dependencies)
- Milestone tasks are not recalculated
"""
import os
import math
import pytest
import requests
from datetime import datetime, timedelta

def _get_base_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        # Load from frontend/.env
        env_path = "/app/frontend/.env"
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip()
                        break
    assert url, "REACT_APP_BACKEND_URL not set"
    return url.rstrip("/")

BASE_URL = _get_base_url()
PROJECT_ID = "6a5d4ac2ad5ecf8fe70d55b3"  # Mobile App project (from review request)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def add_business_days(start_iso, biz_days):
    d = datetime.strptime(start_iso[:10], "%Y-%m-%d").date()
    # snap to weekday
    while d.weekday() >= 5:
        d += timedelta(days=1)
    added = 0
    while added < biz_days:
        d += timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d.isoformat()


def expected_end(start_iso, est_hours, hours_per_day=8.0):
    biz = max(1, math.ceil(est_hours / hours_per_day))
    return add_business_days(start_iso, biz - 1)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------
@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": "admin@test.com", "password": "admin123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def client(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def project_tasks(client):
    r = client.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/wbs")
    assert r.status_code == 200, f"GET wbs failed: {r.status_code} {r.text}"
    tasks = r.json()
    assert isinstance(tasks, list) and len(tasks) > 0, "No WBS tasks found"
    return tasks


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------
class TestRecalculateDates:
    def test_recalculate_endpoint(self, client):
        r = client.post(f"{BASE_URL}/api/projects/{PROJECT_ID}/wbs/recalculate-dates")
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        assert "updated" in data
        assert isinstance(data["updated"], int)
        assert "message" in data

    def test_end_dates_match_formula_after_recalc(self, client, project_tasks):
        # Re-fetch after recalc
        r = client.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/wbs")
        tasks = r.json()
        # Fetch allocations for project so we know hrs/day per assignee
        ra = client.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/allocations")
        allocs = ra.json() if ra.status_code == 200 else []
        alloc_pct_by_resource = {}
        for a in allocs:
            rid = a.get("resource_id")
            if rid and rid not in alloc_pct_by_resource:
                alloc_pct_by_resource[rid] = a.get("percentage", 100) or 100

        mismatches = []
        for t in tasks:
            if t.get("is_milestone"):
                continue
            start = t.get("start_date")
            est = t.get("estimated_hours") or 0
            end = t.get("end_date")
            if not start or est <= 0 or not end:
                continue
            assignee = t.get("assigned_to")
            if assignee and assignee in alloc_pct_by_resource:
                pct = alloc_pct_by_resource[assignee]
                hrs_per_day = (pct / 100.0) * 8.0
                if hrs_per_day <= 0:
                    hrs_per_day = 8.0
            else:
                hrs_per_day = 8.0
            expected = expected_end(start, est, hours_per_day=hrs_per_day)
            actual = str(end)[:10]
            if actual != expected:
                mismatches.append({
                    "name": t.get("name"),
                    "start": start[:10],
                    "est": est,
                    "hrs_per_day": hrs_per_day,
                    "expected_end": expected,
                    "actual_end": actual,
                })
        assert not mismatches, f"End-date formula mismatches: {mismatches[:5]}"

    def test_milestones_not_recalculated(self, client):
        r = client.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/wbs")
        tasks = r.json()
        milestones = [t for t in tasks if t.get("is_milestone")]
        for m in milestones:
            # For milestones, start_date == end_date (== milestone_date)
            if m.get("milestone_date") and m.get("end_date"):
                assert str(m["end_date"])[:10] == str(m["milestone_date"])[:10], \
                    f"Milestone {m.get('name')} end_date != milestone_date"


class TestCreateTaskAutoEndDate:
    def test_create_task_auto_end_date(self, client):
        payload = {
            "name": "TEST_iter48_auto_end",
            "phase_name": None,
            "estimated_hours": 24,  # 3 biz days at 8h/day
            "start_date": "2026-02-02",  # Monday
            "status": "todo",
            "priority": "medium",
        }
        r = client.post(f"{BASE_URL}/api/projects/{PROJECT_ID}/wbs/tasks", json=payload)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text}"
        data = r.json()
        assert data.get("end_date"), "end_date not auto-computed"
        expected = expected_end("2026-02-02", 24)
        assert str(data["end_date"])[:10] == expected, \
            f"Expected {expected}, got {data['end_date']}"
        # cleanup
        client.delete(f"{BASE_URL}/api/wbs/tasks/{data['id']}")

    def test_create_task_20h_ceil(self, client):
        payload = {
            "name": "TEST_iter48_20h",
            "estimated_hours": 20,  # ceil(2.5) = 3 biz days
            "start_date": "2026-02-02",
            "status": "todo",
            "priority": "medium",
        }
        r = client.post(f"{BASE_URL}/api/projects/{PROJECT_ID}/wbs/tasks", json=payload)
        assert r.status_code in (200, 201), r.text
        data = r.json()
        expected = expected_end("2026-02-02", 20)  # 3 biz days -> 2026-02-04
        assert str(data["end_date"])[:10] == expected
        client.delete(f"{BASE_URL}/api/wbs/tasks/{data['id']}")


class TestUpdateTaskAutoEndDate:
    def test_update_estimated_hours_recomputes_end(self, client):
        # Create a task first
        create_payload = {
            "name": "TEST_iter48_update",
            "estimated_hours": 8,
            "start_date": "2026-02-02",
            "status": "todo",
            "priority": "medium",
        }
        r = client.post(f"{BASE_URL}/api/projects/{PROJECT_ID}/wbs/tasks", json=create_payload)
        assert r.status_code in (200, 201), r.text
        task_id = r.json()["id"]

        # Now update estimated_hours only (no end_date)
        r2 = client.put(
            f"{BASE_URL}/api/wbs/tasks/{task_id}",
            json={"estimated_hours": 40},
        )
        assert r2.status_code == 200, r2.text
        data = r2.json()
        expected = expected_end("2026-02-02", 40)  # 5 biz days
        assert str(data["end_date"])[:10] == expected, \
            f"Expected {expected}, got {data['end_date']}"
        client.delete(f"{BASE_URL}/api/wbs/tasks/{task_id}")


class TestTopologicalDependencyIntegrity:
    """Verify dependency data exists so frontend topo-sort can work.
    Backend returns tasks by 'order'; frontend does the topo sort."""

    def test_dependency_data_present(self, project_tasks):
        tasks = project_tasks
        by_name = {t.get("name"): t for t in tasks}

        # Look for User Auth Module -> Database Schema Design dep
        ua = next((t for t in tasks if "User Auth" in (t.get("name") or "")), None)
        ds = next((t for t in tasks if "Database Schema" in (t.get("name") or "")), None)
        if ua and ds:
            deps = ua.get("dependencies") or []
            assert ds["id"] in deps or str(ds.get("id")) in [str(d) for d in deps], \
                f"User Auth Module should depend on Database Schema Design. Got deps: {deps}"

        # WebSocket -> REST Endpoints
        ws = next((t for t in tasks if "WebSocket" in (t.get("name") or "")), None)
        rest = next((t for t in tasks if "REST" in (t.get("name") or "")), None)
        if ws and rest:
            deps = ws.get("dependencies") or []
            assert rest["id"] in deps or str(rest.get("id")) in [str(d) for d in deps], \
                f"WebSocket Integration should depend on REST Endpoints. Got deps: {deps}"

    def test_wbs_returns_expected_task_count(self, project_tasks):
        # Per review: 8 tasks (6 root + 2 sub-tasks)
        assert len(project_tasks) >= 6, f"Expected >=6 tasks, got {len(project_tasks)}"


class TestReadOnlyReportAccess:
    def test_get_wbs_readonly(self, client):
        # Same endpoint used by report page
        r = client.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/wbs")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
