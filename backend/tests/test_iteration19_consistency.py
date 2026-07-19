"""
Iteration 19 – Canonical calculation layer end-to-end tests.

Validates that the app-wide standard of 40 hours/week is applied consistently
across budget-health, budget-reconciliation, allocation validation and
"my-allocations" for percentage and hours allocations, that WBS totals use
leaf-only aggregation, that auto-fill respects phase overlap and holiday
deduction and that the insights service reads timesheet actuals.

The tests intentionally hit the running service via HTTP so they exercise
the exact code path a client would.  BASE_URL is taken from the
REACT_APP_BACKEND_URL environment variable when present but falls back to
localhost:8001 because the external preview URL may be hibernated.
"""
from __future__ import annotations

import datetime as _dt
import os
import subprocess
import uuid
from typing import Any, Dict, List, Optional

import pytest
import requests


BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")
ADMIN_USER = "admin@test.com"
ADMIN_PASS = "admin123"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login() -> str:
    """OAuth2 form-encoded login returning bearer token."""
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": ADMIN_USER, "password": ADMIN_PASS},
        timeout=30,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:400]}"
    tok = r.json().get("access_token")
    assert tok, f"No access_token in login response: {r.json()}"
    return tok


@pytest.fixture(scope="session")
def token() -> str:
    return _login()


@pytest.fixture(scope="session")
def H(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _run_mongo(js: str) -> None:
    subprocess.run(
        ["mongosh", "--quiet", "project_planner", "--eval", js],
        capture_output=True,
        check=False,
    )


def _next_monday(offset_weeks: int = 1) -> _dt.date:
    today = _dt.date.today()
    delta = (7 - today.weekday()) % 7 or 7
    return today + _dt.timedelta(days=delta + 7 * (offset_weeks - 1))


def _fmt(d: _dt.date) -> str:
    return d.isoformat()


# ---------------------------------------------------------------------------
# Sanity / login smoke
# ---------------------------------------------------------------------------


class TestSanity:
    def test_login(self, token: str):
        assert isinstance(token, str) and len(token) > 10

    def test_projects_list(self, H):
        r = requests.get(f"{BASE_URL}/api/projects", headers=H, timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# CONSISTENCY TESTS 1-3 & WBS Leaf-only, Insights (via one shared project)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="class")
def consistency_env(H):
    """Create resource + 4-week project with 2 phases + percentage allocation."""
    # far future window to avoid clashing with existing data
    start = _dt.date(2027, 6, 7)  # Monday
    end = _dt.date(2027, 7, 2)  # Friday, 4 weeks / 20 biz days
    phase_a_end = _dt.date(2027, 6, 18)  # 2 weeks
    phase_b_start = _dt.date(2027, 6, 21)  # 2 weeks

    ctx: Dict[str, Any] = {
        "start": start,
        "end": end,
        "resource_ids": [],
        "project_id": None,
        "wbs_task_ids": [],
    }

    # resource 1
    r1 = requests.post(
        f"{BASE_URL}/api/resources",
        json={"name": f"TEST_ConsistencyR1_{uuid.uuid4().hex[:6]}", "role": "Developer"},
        headers=H,
        timeout=30,
    )
    assert r1.status_code in (200, 201), r1.text[:300]
    rid1 = r1.json().get("id") or str(r1.json().get("_id"))
    ctx["resource_ids"].append(rid1)

    # project
    proj_payload = {
        "name": f"TEST_Consistency_{uuid.uuid4().hex[:6]}",
        "client_name": "TEST_ACME",
        "status": "Active",
        "start_date": _fmt(start),
        "end_date": _fmt(end),
        "budgeted_hours": 400,
        "phases": [
            {"id": "ph1", "name": "Phase 1", "start_date": _fmt(start),
             "end_date": _fmt(phase_a_end), "budgeted_hours": 200},
            {"id": "ph2", "name": "Phase 2", "start_date": _fmt(phase_b_start),
             "end_date": _fmt(end), "budgeted_hours": 200},
        ],
    }
    pr = requests.post(f"{BASE_URL}/api/projects", json=proj_payload, headers=H, timeout=30)
    assert pr.status_code in (200, 201), pr.text[:400]
    pid = pr.json().get("id") or str(pr.json().get("_id"))
    ctx["project_id"] = pid

    # 50% allocation for full 4 weeks
    a1 = requests.post(
        f"{BASE_URL}/api/allocations",
        json={
            "resource_id": rid1,
            "project_id": pid,
            "start_date": _fmt(start),
            "end_date": _fmt(end),
            "percentage": 50,
            "allocation_type": "percentage",
        },
        headers=H,
        timeout=30,
    )
    assert a1.status_code in (200, 201), a1.text[:300]

    yield ctx

    # Cleanup
    try:
        requests.delete(f"{BASE_URL}/api/projects/{pid}", headers=H, timeout=30)
    except Exception:
        pass
    for rid in ctx["resource_ids"]:
        try:
            requests.delete(f"{BASE_URL}/api/resources/{rid}", headers=H, timeout=30)
        except Exception:
            pass


class TestConsistency:
    """Tests 1-3 – project + phase + hours-type allocation agreement."""

    def test_1_project_allocated_agrees_everywhere(self, H, consistency_env):
        pid = consistency_env["project_id"]
        rid = consistency_env["resource_ids"][0]
        start = consistency_env["start"]
        end = consistency_env["end"]

        bh = requests.get(f"{BASE_URL}/api/projects/{pid}/budget-health", headers=H).json()
        rec = requests.get(f"{BASE_URL}/api/projects/{pid}/budget-reconciliation", headers=H).json()
        val = requests.post(
            f"{BASE_URL}/api/allocations/validate",
            json={
                "project_id": pid,
                "resource_id": rid,
                "start_date": _fmt(start),
                "end_date": _fmt(end),
                "percentage": 10,
                "allocation_type": "percentage",
            },
            headers=H,
        ).json()

        bh_alloc = bh.get("allocated_hours")
        rec_alloc = (rec.get("totals") or {}).get("allocated")
        val_alloc = val.get("current_allocated_hours")

        assert bh_alloc == 80.0, f"budget-health.allocated_hours != 80 (got {bh_alloc}); resp={bh}"
        assert rec_alloc == 80.0, f"budget-reconciliation.totals.allocated != 80 (got {rec_alloc}); resp={rec}"
        assert val_alloc == 80.0, f"validate.current_allocated_hours != 80 (got {val_alloc}); resp={val}"

        # validate new_allocation_hours for 10% x 20 biz days x 8h = 16
        assert val.get("new_allocation_hours") == 16.0, (
            f"validate.new_allocation_hours != 16 (got {val.get('new_allocation_hours')})"
        )

    def test_2_phase_level_no_double_counting(self, H, consistency_env):
        pid = consistency_env["project_id"]
        bh = requests.get(f"{BASE_URL}/api/projects/{pid}/budget-health", headers=H).json()
        rec = requests.get(f"{BASE_URL}/api/projects/{pid}/budget-reconciliation", headers=H).json()

        # budget-health phase_breakdown
        phases_bh = bh.get("phase_breakdown") or []
        assert len(phases_bh) == 2, f"expected 2 phases, got {phases_bh}"
        for ph in phases_bh:
            assert ph["allocated_hours"] == 40.0, (
                f"phase {ph.get('phase_name')} allocated != 40 (got {ph.get('allocated_hours')})"
            )
        assert sum(p["allocated_hours"] for p in phases_bh) == 80.0

        # budget-reconciliation phases
        phases_rec = rec.get("phases") or []
        assert len(phases_rec) == 2, f"expected 2 phases in reconciliation, got {phases_rec}"
        for ph in phases_rec:
            assert ph.get("allocated") == 40.0, (
                f"reconciliation phase {ph.get('name')} allocated != 40 (got {ph.get('allocated')})"
            )

    def test_3_hours_allocation_adds_total(self, H, consistency_env):
        pid = consistency_env["project_id"]

        # Second resource with hours-type allocation over first 2 weeks (40h flat)
        r2 = requests.post(
            f"{BASE_URL}/api/resources",
            json={"name": f"TEST_HoursR_{uuid.uuid4().hex[:6]}", "role": "QA"},
            headers=H,
        )
        assert r2.status_code in (200, 201), r2.text[:200]
        rid2 = r2.json().get("id") or str(r2.json().get("_id"))
        consistency_env["resource_ids"].append(rid2)

        start = consistency_env["start"]
        two_weeks_end = start + _dt.timedelta(days=11)  # 10 biz days

        a2 = requests.post(
            f"{BASE_URL}/api/allocations",
            json={
                "resource_id": rid2,
                "project_id": pid,
                "start_date": _fmt(start),
                "end_date": _fmt(two_weeks_end),
                "hours": 40,
                "allocation_type": "hours",
            },
            headers=H,
        )
        assert a2.status_code in (200, 201), a2.text[:400]

        bh = requests.get(f"{BASE_URL}/api/projects/{pid}/budget-health", headers=H).json()
        rec = requests.get(f"{BASE_URL}/api/projects/{pid}/budget-reconciliation", headers=H).json()

        assert bh.get("allocated_hours") == 120.0, (
            f"expected 120 after +40h hours-type alloc, got {bh.get('allocated_hours')}"
        )
        rec_alloc = (rec.get("totals") or {}).get("allocated")
        assert rec_alloc == 120.0, f"reconciliation total allocated != 120, got {rec_alloc}"


# ---------------------------------------------------------------------------
# CONSISTENCY TEST 4 – My-allocations uses 40h/week
# ---------------------------------------------------------------------------


class TestMyAllocationsWeekly:
    def test_4_my_allocations_weekly_hours_40h(self, H):
        # Create resource, link admin user to it, 50% allocation covering today+13 days
        rname = f"TEST_MyAllocR_{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{BASE_URL}/api/resources",
                          json={"name": rname, "role": "Developer"}, headers=H).json()
        rid = r.get("id") or str(r.get("_id"))
        assert rid

        today = _dt.date.today()
        end = today + _dt.timedelta(days=14)
        a = requests.post(
            f"{BASE_URL}/api/allocations",
            json={
                "resource_id": rid,
                "project_id": None,  # will fill below
                "start_date": _fmt(today),
                "end_date": _fmt(end),
                "percentage": 50,
                "allocation_type": "percentage",
            },
            headers=H,
        )
        # Some backends require project_id: create a throwaway project if so
        aid = None
        pid = None
        if a.status_code not in (200, 201):
            pr = requests.post(
                f"{BASE_URL}/api/projects",
                json={
                    "name": f"TEST_MyAllocProj_{uuid.uuid4().hex[:6]}",
                    "client_name": "TEST",
                    "status": "Active",
                    "start_date": _fmt(today),
                    "end_date": _fmt(end),
                    "budgeted_hours": 40,
                },
                headers=H,
            ).json()
            pid = pr.get("id") or str(pr.get("_id"))
            a = requests.post(
                f"{BASE_URL}/api/allocations",
                json={
                    "resource_id": rid,
                    "project_id": pid,
                    "start_date": _fmt(today),
                    "end_date": _fmt(end),
                    "percentage": 50,
                    "allocation_type": "percentage",
                },
                headers=H,
            )
        assert a.status_code in (200, 201), a.text[:300]
        aid = a.json().get("id") or str(a.json().get("_id"))

        # Link admin user -> resource via mongo (route not exposed)
        _run_mongo(
            f'db.users.updateOne({{email:"{ADMIN_USER}"}}, {{$set:{{resource_id:"{rid}"}}}})'
        )
        try:
            resp = requests.get(f"{BASE_URL}/api/my-allocations?period=week", headers=H)
            assert resp.status_code == 200, resp.text[:300]
            data = resp.json()
            # Locate the freshly-created allocation
            allocs = data.get("allocations") or []
            match = next((x for x in allocs if x.get("id") == aid), None)
            assert match is not None, f"created allocation not found; allocs={allocs}"
            assert match["weekly_hours"] == 20.0, (
                f"expected weekly_hours=20.0 (50% of 40h), got {match['weekly_hours']}"
            )
        finally:
            _run_mongo(
                f'db.users.updateOne({{email:"{ADMIN_USER}"}}, {{$unset:{{resource_id:""}}}})'
            )
            try:
                requests.delete(f"{BASE_URL}/api/allocations/{aid}", headers=H)
            except Exception:
                pass
            if pid:
                requests.delete(f"{BASE_URL}/api/projects/{pid}", headers=H)
            requests.delete(f"{BASE_URL}/api/resources/{rid}", headers=H)


# ---------------------------------------------------------------------------
# AUTO-FILL TEST – phase-aware + holiday deduction
# ---------------------------------------------------------------------------


class TestAutoFill:
    def test_autofill_phase_aware_and_holiday(self, H):
        monday = _next_monday(1)
        friday = monday + _dt.timedelta(days=4)
        phase_a_end = monday + _dt.timedelta(days=11)
        phase_b_start = monday + _dt.timedelta(days=14)
        phase_b_end = monday + _dt.timedelta(days=25)

        rid = requests.post(
            f"{BASE_URL}/api/resources",
            json={"name": f"TEST_AF_{uuid.uuid4().hex[:6]}", "role": "Developer"},
            headers=H,
        ).json()
        rid = rid.get("id") or str(rid.get("_id"))

        proj = requests.post(
            f"{BASE_URL}/api/projects",
            json={
                "name": f"TEST_AutoFill_{uuid.uuid4().hex[:6]}",
                "client_name": "TEST_ACME",
                "status": "Active",
                "start_date": _fmt(monday),
                "end_date": _fmt(phase_b_end),
                "budgeted_hours": 300,
                "phases": [
                    {"id": "pa", "name": "Build", "start_date": _fmt(monday),
                     "end_date": _fmt(phase_a_end)},
                    {"id": "pb", "name": "Test", "start_date": _fmt(phase_b_start),
                     "end_date": _fmt(phase_b_end)},
                ],
            },
            headers=H,
        ).json()
        pid = proj.get("id") or str(proj.get("_id"))

        alloc = requests.post(
            f"{BASE_URL}/api/allocations",
            json={
                "resource_id": rid,
                "project_id": pid,
                "start_date": _fmt(monday),
                "end_date": _fmt(phase_b_end),
                "percentage": 50,
                "allocation_type": "percentage",
                "phase_names": ["Build", "Test"],
                "phase_allocations": [
                    {"phase_id": "pa", "percentage": 80},
                    {"phase_id": "pb", "percentage": 20},
                ],
            },
            headers=H,
        )
        assert alloc.status_code in (200, 201), alloc.text[:400]

        # Holiday on Monday
        hol = requests.post(
            f"{BASE_URL}/api/holidays",
            json={"name": "TEST_AF_Holiday", "date": _fmt(monday)},
            headers=H,
        )
        assert hol.status_code in (200, 201), hol.text[:200]

        # Link admin user to resource
        _run_mongo(
            f'db.users.updateOne({{email:"{ADMIN_USER}"}}, {{$set:{{resource_id:"{rid}"}}}})'
        )

        try:
            r = requests.post(
                f"{BASE_URL}/api/timesheets/auto-fill?week_start={_fmt(monday)}",
                headers=H,
                timeout=30,
            )
            assert r.status_code in (200, 201), r.text[:400]

            # Fetch created timesheets for the week for this project
            tss = requests.get(
                f"{BASE_URL}/api/timesheets/my-week?week_start={_fmt(monday)}",
                headers=H,
            ).json()
            ours = [t for t in tss if t.get("project_id") == pid]
            assert len(ours) == 1, (
                f"expected exactly 1 timesheet (only Build phase overlaps), got {len(ours)}: {ours}"
            )
            row = ours[0]
            assert row.get("phase_id") == "pa", f"expected phase pa, got {row.get('phase_id')}"
            # Expected: 80% * 40h * 4/5 (Mon holiday) = 25.6
            assert row["planned_hours"] == 25.6, (
                f"planned_hours expected 25.6, got {row.get('planned_hours')}"
            )
            assert row["actual_hours"] == 25.6, (
                f"actual_hours should default to planned (25.6), got {row.get('actual_hours')}"
            )
        finally:
            # Cleanup: unlink user, delete timesheets, holiday, project, resource
            _run_mongo(
                f'db.users.updateOne({{email:"{ADMIN_USER}"}}, {{$unset:{{resource_id:""}}}})'
            )
            try:
                tss = requests.get(
                    f"{BASE_URL}/api/timesheets/my-week?week_start={_fmt(monday)}",
                    headers=H,
                ).json()
                for t in tss:
                    if t.get("project_id") == pid:
                        requests.delete(f"{BASE_URL}/api/timesheets/{t['id']}", headers=H)
            except Exception:
                pass
            try:
                hols = requests.get(f"{BASE_URL}/api/holidays", headers=H).json()
                for h in hols:
                    if h.get("name") == "TEST_AF_Holiday":
                        requests.delete(f"{BASE_URL}/api/holidays/{h['id']}", headers=H)
            except Exception:
                pass
            requests.delete(f"{BASE_URL}/api/projects/{pid}", headers=H)
            requests.delete(f"{BASE_URL}/api/resources/{rid}", headers=H)


# ---------------------------------------------------------------------------
# WBS LEAF-ONLY TEST
# ---------------------------------------------------------------------------


class TestWbsLeafOnly:
    def test_wbs_leaf_only(self, H):
        # Build a tiny project with 1 parent + 1 child WBS task (leaf 20h)
        start = _dt.date(2027, 8, 2)
        end = _dt.date(2027, 8, 27)
        proj = requests.post(
            f"{BASE_URL}/api/projects",
            json={
                "name": f"TEST_WBS_{uuid.uuid4().hex[:6]}",
                "client_name": "TEST",
                "status": "Active",
                "start_date": _fmt(start),
                "end_date": _fmt(end),
                "budgeted_hours": 100,
                "phases": [
                    {"id": "phw", "name": "Main", "start_date": _fmt(start),
                     "end_date": _fmt(end), "budgeted_hours": 100},
                ],
            },
            headers=H,
        ).json()
        pid = proj.get("id") or str(proj.get("_id"))

        parent = requests.post(
            f"{BASE_URL}/api/projects/{pid}/wbs/tasks",
            json={
                "name": "TEST_ParentTask",
                "phase_id": "phw",
                "phase_name": "Main",
                "estimated_hours": 20,
                "start_date": _fmt(start),
                "end_date": _fmt(end),
            },
            headers=H,
        )
        assert parent.status_code in (200, 201), parent.text[:400]
        parent_id = parent.json()["id"]

        child = requests.post(
            f"{BASE_URL}/api/projects/{pid}/wbs/tasks",
            json={
                "name": "TEST_ChildTask",
                "phase_id": "phw",
                "phase_name": "Main",
                "parent_id": parent_id,
                "estimated_hours": 20,
                "start_date": _fmt(start),
                "end_date": _fmt(end),
            },
            headers=H,
        )
        assert child.status_code in (200, 201), child.text[:400]

        try:
            bstat = requests.get(
                f"{BASE_URL}/api/projects/{pid}/wbs/budget-status", headers=H
            ).json()
            proj_full = requests.get(f"{BASE_URL}/api/projects/{pid}", headers=H).json()
            rec = requests.get(
                f"{BASE_URL}/api/projects/{pid}/budget-reconciliation", headers=H
            ).json()

            total_wbs = bstat.get("total_wbs_hours") or bstat.get("total_estimated_hours")
            assert total_wbs == 20, f"total_wbs_hours expected 20 (leaf-only), got {total_wbs}; resp={bstat}"

            wbs_summary = proj_full.get("wbs_summary") or {}
            assert wbs_summary.get("total_estimated_hours") == 20, (
                f"project.wbs_summary.total_estimated_hours expected 20, got {wbs_summary}"
            )

            rec_est = (rec.get("totals") or {}).get("estimated")
            assert rec_est == 20, f"reconciliation.totals.estimated expected 20, got {rec_est}"
        finally:
            requests.delete(f"{BASE_URL}/api/projects/{pid}", headers=H)


# ---------------------------------------------------------------------------
# INSIGHTS FIX TEST
# ---------------------------------------------------------------------------


class TestInsights:
    def test_insights_reads_actuals(self, H):
        # Create project with an approved-style timesheet with actual_hours > 0
        start = _dt.date.today() - _dt.timedelta(days=14)
        end = _dt.date.today() + _dt.timedelta(days=14)
        proj = requests.post(
            f"{BASE_URL}/api/projects",
            json={
                "name": f"TEST_Insights_{uuid.uuid4().hex[:6]}",
                "client_name": "TEST",
                "status": "Active",
                "start_date": _fmt(start),
                "end_date": _fmt(end),
                "budgeted_hours": 80,
                "phases": [
                    {"id": "phi", "name": "PhaseI", "start_date": _fmt(start),
                     "end_date": _fmt(end), "budgeted_hours": 80},
                ],
            },
            headers=H,
        ).json()
        pid = proj.get("id") or str(proj.get("_id"))

        r = requests.post(
            f"{BASE_URL}/api/resources",
            json={"name": f"TEST_Ins_{uuid.uuid4().hex[:6]}", "role": "Dev"},
            headers=H,
        ).json()
        rid = r.get("id") or str(r.get("_id"))

        # Manually insert a submitted/draft timesheet with actual_hours=12 via mongo
        # so the insights aggregation exercises the new "no status filter" path.
        week_start = _fmt(_dt.date.today() - _dt.timedelta(days=_dt.date.today().weekday()))
        js = (
            'db.timesheets.insertOne({'
            f'id:"TEST_TS_{uuid.uuid4().hex[:8]}",'
            f'project_id:"{pid}",resource_id:"{rid}",'
            f'week_start:"{week_start}","phase_id":"phi",'
            'planned_hours:20,actual_hours:12,status:"draft",'
            'auto_filled:false})'
        )
        _run_mongo(js)

        try:
            pred = requests.get(
                f"{BASE_URL}/api/insights/project/{pid}/predictions", headers=H
            )
            assert pred.status_code == 200, pred.text[:400]
            body = pred.json()
            bp = body.get("budget_prediction") or {}
            assert bp.get("current_actual", 0) > 0, (
                f"budget_prediction.current_actual should read timesheet actuals; got {bp}"
            )

            hs = requests.get(
                f"{BASE_URL}/api/insights/project/{pid}/health-score", headers=H
            )
            assert hs.status_code == 200, hs.text[:400]
            hs_body = hs.json()
            # The budget dimension should mention actuals as a % of budget.  12/80 = 15% used.
            budget_dim = (hs_body.get("dimensions") or {}).get("budget") or {}
            detail = str(budget_dim.get("detail", "")).lower()
            assert "%" in detail and "used" in detail, (
                f"health-score budget dimension does not reflect actuals: {budget_dim}"
            )
            # Extract percent used and verify it is > 0 (i.e. actuals were considered)
            import re as _re
            m = _re.search(r"(\d+)\s*%\s*used", detail)
            pct_used = int(m.group(1)) if m else 0
            assert pct_used > 0, (
                f"health-score budget %used == 0 despite actuals present: {budget_dim}"
            )
        finally:
            _run_mongo(f'db.timesheets.deleteMany({{project_id:"{pid}"}})')
            requests.delete(f"{BASE_URL}/api/projects/{pid}", headers=H)
            requests.delete(f"{BASE_URL}/api/resources/{rid}", headers=H)


# ---------------------------------------------------------------------------
# REGRESSION – basic CRUD & aggregation endpoints
# ---------------------------------------------------------------------------


class TestRegression:
    def test_projects_list(self, H):
        r = requests.get(f"{BASE_URL}/api/projects", headers=H)
        assert r.status_code == 200

    def test_allocations_list(self, H):
        r = requests.get(f"{BASE_URL}/api/allocations", headers=H)
        assert r.status_code == 200

    def test_capacity_report(self, H):
        # Actual endpoint: /api/reports/capacity?start_date&end_date
        today = _dt.date.today()
        start = today - _dt.timedelta(days=today.weekday())
        end = start + _dt.timedelta(days=27)
        r = requests.get(
            f"{BASE_URL}/api/reports/capacity",
            params={"start_date": _fmt(start), "end_date": _fmt(end)},
            headers=H,
        )
        assert r.status_code == 200, r.text[:300]

    def test_portfolio(self, H):
        r = requests.get(f"{BASE_URL}/api/portfolio", headers=H)
        assert r.status_code == 200, r.text[:400]
        data = r.json()
        projects = data.get("projects", data if isinstance(data, list) else [])
        # Each project should include baseline_hours computed
        missing = [p for p in projects if "baseline_hours" not in p]
        assert not missing, (
            f"portfolio: {len(missing)} projects missing baseline_hours field"
        )

    def test_planned_vs_actual(self, H):
        # Pick any existing project
        pr = requests.get(f"{BASE_URL}/api/projects", headers=H).json()
        if not pr:
            pytest.skip("no projects to test planned-vs-actual against")
        pid = pr[0].get("id") or str(pr[0].get("_id"))
        r = requests.get(
            f"{BASE_URL}/api/reports/planned-vs-actual/project/{pid}", headers=H
        )
        assert r.status_code == 200, r.text[:400]
