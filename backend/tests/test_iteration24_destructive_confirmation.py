"""
Iteration 24 — Destructive Action Confirmation & manage_phases Merge Mode
=========================================================================
Tests the two new features:

1. remove_allocation + delete_wbs_task require confirmation token for
   non-super_admin admin users.
2. manage_phases defaults to merge (upsert) mode — existing phases not in
   payload are preserved. mode='replace' restores old full-replace behaviour.

Also covers:
- Super-admin bypasses destructive confirmation entirely.
- build_actions_prompt marks these two actions [destructive].
- Regression: delete_project / delete_risk still gate on confirmation for admin.
- Regression: update_project / create_resource execute immediately (non-destructive).
- /api/health endpoint healthy.

Implementation notes
--------------------
* Motor (async MongoDB) requires a PERSISTENT asyncio event loop — using
  asyncio.run() multiple times in the same session closes/reopens the loop
  and invalidates Motor's connection pool. We manage a module-level loop via
  _run() / _LOOP so every coroutine runs on the same (never-closed) loop.
* admin@test.com was promoted to super_admin in iteration 19. We create a
  temporary 'testadmin_iter24@test.com' (role=admin) for HTTP tests that need
  to exercise the confirmation gate.
"""
from __future__ import annotations

import asyncio
import sys
import uuid
import requests
import pytest
from bson import ObjectId
from datetime import datetime, timezone

# ─── backend path so imports resolve ──────────────────────────────────────────
sys.path.insert(0, "/app/backend")

# ─── persistent event loop (Motor needs the same loop for the whole session) ──
_LOOP: asyncio.AbstractEventLoop = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)


def _run(coro):
    """Run a coroutine on the module-level persistent loop."""
    return _LOOP.run_until_complete(coro)


# ─── backend imports (after loop is set) ──────────────────────────────────────
from database import (
    allocations_collection,
    wbs_tasks_collection,
    projects_collection,
    risks_collection,
    pending_actions_collection,
    users_collection,
)
from auth.dependencies import get_password_hash
from services.ai_action_registry import dispatch_action, build_actions_prompt, ACTIONS

BASE_URL = "http://localhost:8001"
TIMEOUT = 20

# ── User dicts passed directly to dispatch_action ────────────────────────────
# These are plain dicts — dispatch_action checks role, not the DB
ADMIN_USER = {"email": "testadmin_iter24@test.com", "role": "admin"}
SUPER_ADMIN_USER = {"email": "don@ddconsult.tech", "role": "super_admin"}


# ─────────────────────────────────────────────────────────────────────────────
# Module-level setup: ensure the temp admin user exists in the DB
# ─────────────────────────────────────────────────────────────────────────────

async def _ensure_temp_admin():
    existing = await users_collection.find_one({"email": ADMIN_USER["email"]})
    if not existing:
        await users_collection.insert_one({
            "email": ADMIN_USER["email"],
            "password_hash": get_password_hash("TestAdmin123!"),
            "role": "admin",
            "allowed_project_ids": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })


async def _cleanup_temp_admin():
    await users_collection.delete_one({"email": ADMIN_USER["email"]})


def setup_module(module):
    _run(_ensure_temp_admin())


def teardown_module(module):
    _run(_cleanup_temp_admin())
    # Clean up any leftover pending tokens from our test user
    _run(pending_actions_collection.delete_many({"user_email": ADMIN_USER["email"]}))


# ─────────────────────────────────────────────────────────────────────────────
# HTTP helpers
# ─────────────────────────────────────────────────────────────────────────────

def _login(email: str, password: str) -> str:
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


def _hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def temp_admin_token():
    """Token for the temp admin@iter24 user (role=admin, NOT super_admin)."""
    return _login(ADMIN_USER["email"], "TestAdmin123!")


@pytest.fixture(scope="module")
def super_admin_token():
    return _login("don@ddconsult.tech", "Welcome123!")


@pytest.fixture(scope="module")
def projects_map(temp_admin_token):
    r = requests.get(f"{BASE_URL}/api/projects", headers=_hdr(temp_admin_token), timeout=15)
    assert r.status_code == 200
    return {p["name"]: p["id"] for p in r.json()}


# ─────────────────────────────────────────────────────────────────────────────
# Async DB helpers for test setup / teardown
# ─────────────────────────────────────────────────────────────────────────────

async def _create_test_allocation() -> str:
    """Insert a minimal test allocation. Returns allocation _id as str."""
    doc = {
        "resource_id": "000000000000000000000001",
        "project_id": "000000000000000000000002",
        "percentage": 50,
        "start_date": datetime(2026, 1, 1),
        "end_date": datetime(2026, 6, 30),
        "allocation_type": "percentage",
        "_TEST_iter24": True,
    }
    r = await allocations_collection.insert_one(doc)
    return str(r.inserted_id)


async def _cleanup_allocation(aid: str):
    await allocations_collection.delete_one({"_id": ObjectId(aid)})


async def _create_test_wbs_task() -> str:
    """Insert a minimal WBS task. Returns task _id as str."""
    doc = {
        "project_id": "000000000000000000000003",
        "name": f"TEST_iter24_WBS_{uuid.uuid4().hex[:6]}",
        "status": "todo",
        "estimated_hours": 8,
        "_TEST_iter24": True,
    }
    r = await wbs_tasks_collection.insert_one(doc)
    return str(r.inserted_id)


async def _cleanup_wbs_task(tid: str):
    await wbs_tasks_collection.delete_one({"_id": ObjectId(tid)})


async def _create_test_project_with_phases(phases: list) -> str:
    """Insert a test project with given phases. Returns _id as str."""
    doc = {
        "name": f"TEST_iter24_MP_{uuid.uuid4().hex[:6]}",
        "client_name": "Test Client",
        "status": "Active",
        "budgeted_hours": 300,
        "phases": [dict(ph) for ph in phases],
        "_TEST_iter24": True,
    }
    r = await projects_collection.insert_one(doc)
    return str(r.inserted_id)


async def _cleanup_project(pid: str):
    await projects_collection.delete_one({"_id": ObjectId(pid)})


async def _get_project_phases(pid: str) -> list:
    p = await projects_collection.find_one({"_id": ObjectId(pid)})
    return p.get("phases", []) if p else []


# Shared 3-phase template
PHASES_ALPHA_BETA_GAMMA = [
    {"id": "phase-alpha", "name": "Alpha", "status": "Active", "budgeted_hours": 100},
    {"id": "phase-beta",  "name": "Beta",  "status": "Not Started", "budgeted_hours": 50},
    {"id": "phase-gamma", "name": "Gamma", "status": "Not Started", "budgeted_hours": 80},
]


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 1: Confirmation flow — remove_allocation (direct dispatch_action calls)
# ═════════════════════════════════════════════════════════════════════════════

class TestRemoveAllocationConfirmation:
    """remove_allocation is_destructive=True → non-super_admin admin must confirm."""

    def test_no_token_returns_needs_confirmation(self):
        """Admin without confirm_token must receive needs_confirmation=True."""
        aid = _run(_create_test_allocation())
        try:
            action = {"action": "remove_allocation", "allocation_id": aid}
            result = _run(dispatch_action(action, ADMIN_USER))

            print(f"\n[remove_allocation no-token] result: {result}")
            assert result.get("success") is False, f"Expected success=False, got {result}"
            assert result.get("needs_confirmation") is True, (
                f"Expected needs_confirmation=True, got {result}"
            )
            token = result.get("confirm_token")
            assert token and len(token) > 0, f"Expected a confirm_token, got {result}"
            assert result.get("action_name") == "remove_allocation", (
                f"Expected action_name='remove_allocation', got {result}"
            )
            # Allocation must still exist (not deleted before confirmation)
            still_there = _run(allocations_collection.find_one({"_id": ObjectId(aid)}))
            assert still_there is not None, "Allocation was deleted before confirmation!"
            # Cleanup the issued token
            _run(pending_actions_collection.delete_one({"token": token}))
        finally:
            _run(_cleanup_allocation(aid))

    def test_valid_token_executes_deletion(self):
        """Admin with a valid confirm_token → allocation deleted successfully."""
        aid = _run(_create_test_allocation())
        try:
            action = {"action": "remove_allocation", "allocation_id": aid}
            # Step 1 — get token
            first = _run(dispatch_action(action, ADMIN_USER))
            assert first.get("needs_confirmation") is True, f"Step 1 failed: {first}"
            token = first["confirm_token"]

            # Step 2 — confirm
            action_confirmed = {**action, "confirm_token": token}
            result = _run(dispatch_action(action_confirmed, ADMIN_USER))

            print(f"\n[remove_allocation with-token] result: {result}")
            assert result.get("success") is True, (
                f"Expected success=True after providing token, got {result}"
            )
            # Allocation must now be gone
            gone = _run(allocations_collection.find_one({"_id": ObjectId(aid)}))
            assert gone is None, "Allocation still exists after confirmed deletion!"
        finally:
            _run(_cleanup_allocation(aid))

    def test_invalid_token_rejected_and_data_safe(self):
        """A bogus confirm_token must be rejected; allocation must survive."""
        aid = _run(_create_test_allocation())
        try:
            action = {
                "action": "remove_allocation",
                "allocation_id": aid,
                "confirm_token": "deadbeef",
            }
            result = _run(dispatch_action(action, ADMIN_USER))
            print(f"\n[remove_allocation invalid-token] result: {result}")
            assert result.get("success") is False, (
                f"Expected failure on bad token, got {result}"
            )
            still = _run(allocations_collection.find_one({"_id": ObjectId(aid)}))
            assert still is not None, "Allocation deleted despite invalid token!"
        finally:
            _run(_cleanup_allocation(aid))

    def test_super_admin_bypasses_confirmation(self):
        """Super-admin executes remove_allocation immediately without confirm_token."""
        aid = _run(_create_test_allocation())
        try:
            action = {"action": "remove_allocation", "allocation_id": aid}
            result = _run(dispatch_action(action, SUPER_ADMIN_USER))

            print(f"\n[remove_allocation super-admin] result: {result}")
            assert result.get("success") is True, (
                f"Super-admin should bypass confirmation and succeed, got {result}"
            )
            assert not result.get("needs_confirmation"), (
                f"Super-admin must NOT need confirmation, got {result}"
            )
            gone = _run(allocations_collection.find_one({"_id": ObjectId(aid)}))
            assert gone is None, "Allocation still exists after super-admin deletion!"
        finally:
            _run(_cleanup_allocation(aid))


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 2: Confirmation flow — delete_wbs_task (direct dispatch_action calls)
# ═════════════════════════════════════════════════════════════════════════════

class TestDeleteWbsTaskConfirmation:
    """delete_wbs_task is_destructive=True → non-super_admin admin must confirm."""

    def test_no_token_returns_needs_confirmation(self):
        """Admin without confirm_token receives needs_confirmation=True."""
        tid = _run(_create_test_wbs_task())
        try:
            action = {"action": "delete_wbs_task", "task_id": tid}
            result = _run(dispatch_action(action, ADMIN_USER))

            print(f"\n[delete_wbs_task no-token] result: {result}")
            assert result.get("success") is False, f"Expected success=False, got {result}"
            assert result.get("needs_confirmation") is True, (
                f"Expected needs_confirmation=True, got {result}"
            )
            token = result.get("confirm_token")
            assert token and len(token) > 0, f"Expected a confirm_token, got {result}"
            assert result.get("action_name") == "delete_wbs_task", (
                f"Expected action_name='delete_wbs_task', got {result}"
            )
            # Task must still exist
            still = _run(wbs_tasks_collection.find_one({"_id": ObjectId(tid)}))
            assert still is not None, "WBS task deleted before confirmation!"
            _run(pending_actions_collection.delete_one({"token": token}))
        finally:
            _run(_cleanup_wbs_task(tid))

    def test_valid_token_executes_deletion(self):
        """Admin with valid confirm_token → WBS task deleted."""
        tid = _run(_create_test_wbs_task())
        try:
            action = {"action": "delete_wbs_task", "task_id": tid}
            # Step 1
            first = _run(dispatch_action(action, ADMIN_USER))
            assert first.get("needs_confirmation") is True, f"Step 1 failed: {first}"
            token = first["confirm_token"]

            # Step 2 — confirm
            result = _run(dispatch_action({**action, "confirm_token": token}, ADMIN_USER))

            print(f"\n[delete_wbs_task with-token] result: {result}")
            assert result.get("success") is True, (
                f"Expected success=True after confirm, got {result}"
            )
            gone = _run(wbs_tasks_collection.find_one({"_id": ObjectId(tid)}))
            assert gone is None, "WBS task still present after confirmed deletion!"
        finally:
            _run(_cleanup_wbs_task(tid))

    def test_super_admin_bypasses_confirmation(self):
        """Super-admin deletes WBS task without confirmation token."""
        tid = _run(_create_test_wbs_task())
        try:
            action = {"action": "delete_wbs_task", "task_id": tid}
            result = _run(dispatch_action(action, SUPER_ADMIN_USER))

            print(f"\n[delete_wbs_task super-admin] result: {result}")
            assert result.get("success") is True, f"Super-admin bypass failed, got {result}"
            assert not result.get("needs_confirmation"), (
                f"Super-admin must NOT need confirmation, got {result}"
            )
            gone = _run(wbs_tasks_collection.find_one({"_id": ObjectId(tid)}))
            assert gone is None, "Task still present after super-admin deletion!"
        finally:
            _run(_cleanup_wbs_task(tid))


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 3: manage_phases — merge vs replace (direct handler + dispatch_action)
# ═════════════════════════════════════════════════════════════════════════════

class TestManagePhases:
    """manage_phases merge (default) and replace modes."""

    def test_merge_default_preserves_other_phases(self):
        """Sending only 'Alpha' update (no mode) must keep Beta and Gamma intact."""
        from services.ai_actions_extended import _h_manage_phases

        pid = _run(_create_test_project_with_phases(PHASES_ALPHA_BETA_GAMMA))
        try:
            action = {
                "action": "manage_phases",
                "project_id": pid,
                "phases": [
                    {"id": "phase-alpha", "name": "Alpha", "status": "Completed", "budgeted_hours": 120}
                ],
                # mode not specified → defaults to 'merge'
            }
            result = _run(_h_manage_phases(action, ADMIN_USER))
            print(f"\n[manage_phases merge default] result: {result}")
            assert result.get("success") is True, f"manage_phases failed: {result}"

            phases = _run(_get_project_phases(pid))
            phase_names = {ph["name"] for ph in phases}
            print(f"  phases after: {phase_names}")

            assert "Alpha" in phase_names, "Alpha missing after merge"
            assert "Beta" in phase_names, "Beta removed — should be preserved!"
            assert "Gamma" in phase_names, "Gamma removed — should be preserved!"
            assert len(phases) == 3, f"Expected 3 phases, got {len(phases)}: {phase_names}"

            alpha = next(ph for ph in phases if ph["name"] == "Alpha")
            assert alpha["status"] == "Completed", f"Alpha status not updated: {alpha}"
            assert alpha.get("budgeted_hours") == 120, f"Alpha hours not updated: {alpha}"
        finally:
            _run(_cleanup_project(pid))

    def test_merge_explicit_preserves_others(self):
        """Explicit mode='merge' keeps phases not in payload."""
        from services.ai_actions_extended import _h_manage_phases

        pid = _run(_create_test_project_with_phases(PHASES_ALPHA_BETA_GAMMA))
        try:
            action = {
                "action": "manage_phases",
                "project_id": pid,
                "phases": [{"id": "phase-beta", "name": "Beta", "status": "Active"}],
                "mode": "merge",
            }
            result = _run(_h_manage_phases(action, ADMIN_USER))
            assert result.get("success") is True

            phases = _run(_get_project_phases(pid))
            names = {ph["name"] for ph in phases}
            assert "Alpha" in names and "Beta" in names and "Gamma" in names, (
                f"Phases lost on explicit merge: {names}"
            )
            beta = next(ph for ph in phases if ph["name"] == "Beta")
            assert beta["status"] == "Active", f"Beta status not updated: {beta}"
        finally:
            _run(_cleanup_project(pid))

    def test_replace_mode_discards_existing(self):
        """mode='replace' must discard Alpha/Beta/Gamma and use only supplied phases."""
        from services.ai_actions_extended import _h_manage_phases

        pid = _run(_create_test_project_with_phases(PHASES_ALPHA_BETA_GAMMA))
        try:
            action = {
                "action": "manage_phases",
                "project_id": pid,
                "phases": [{"name": "OnlyPhase", "status": "Not Started", "budgeted_hours": 200}],
                "mode": "replace",
            }
            result = _run(_h_manage_phases(action, ADMIN_USER))
            print(f"\n[manage_phases replace] result: {result}")
            assert result.get("success") is True

            phases = _run(_get_project_phases(pid))
            names = [ph["name"] for ph in phases]
            print(f"  phases after replace: {names}")

            assert len(phases) == 1, f"Expected 1 phase after replace, got {len(phases)}: {names}"
            assert phases[0]["name"] == "OnlyPhase"
            assert "Alpha" not in names, "Alpha not removed in replace mode!"
            assert "Beta" not in names, "Beta not removed in replace mode!"
            assert "Gamma" not in names, "Gamma not removed in replace mode!"
        finally:
            _run(_cleanup_project(pid))

    def test_merge_adds_new_phase_without_removing_existing(self):
        """Merge with a brand-new phase name → adds to list, keeps all 3 original phases."""
        from services.ai_actions_extended import _h_manage_phases

        pid = _run(_create_test_project_with_phases(PHASES_ALPHA_BETA_GAMMA))
        try:
            action = {
                "action": "manage_phases",
                "project_id": pid,
                "phases": [{"name": "Delta", "status": "Not Started", "budgeted_hours": 60}],
                # merge mode is default
            }
            result = _run(_h_manage_phases(action, ADMIN_USER))
            print(f"\n[manage_phases merge add-new] result: {result}")
            assert result.get("success") is True

            phases = _run(_get_project_phases(pid))
            names = {ph["name"] for ph in phases}
            print(f"  phases after add: {names}")

            assert "Alpha" in names, "Alpha removed on merge-add!"
            assert "Beta" in names, "Beta removed on merge-add!"
            assert "Gamma" in names, "Gamma removed on merge-add!"
            assert "Delta" in names, "New 'Delta' phase not added!"
            assert len(phases) == 4, f"Expected 4 phases, got {len(phases)}: {names}"
        finally:
            _run(_cleanup_project(pid))

    def test_merge_via_dispatch_action_no_confirmation_needed(self):
        """manage_phases through dispatch_action: non-destructive → executes immediately."""
        pid = _run(_create_test_project_with_phases([
            {"id": "p1", "name": "Planning", "status": "Not Started", "budgeted_hours": 40}
        ]))
        try:
            action = {
                "action": "manage_phases",
                "project_id": pid,
                "phases": [{"name": "Execution", "status": "Not Started", "budgeted_hours": 120}],
            }
            result = _run(dispatch_action(action, ADMIN_USER))
            print(f"\n[manage_phases via dispatch] result: {result}")
            assert result.get("success") is True, f"Expected success via dispatch, got {result}"
            assert not result.get("needs_confirmation"), (
                f"manage_phases must NOT require confirmation, got {result}"
            )
            phases = _run(_get_project_phases(pid))
            names = {ph["name"] for ph in phases}
            assert "Planning" in names, "Planning phase was removed (merge should preserve it)"
            assert "Execution" in names, "Execution phase not added"
        finally:
            _run(_cleanup_project(pid))


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 4: build_actions_prompt — [destructive] labels
# ═════════════════════════════════════════════════════════════════════════════

class TestBuildActionsPrompt:
    """AI system prompt must label remove_allocation and delete_wbs_task as [destructive]."""

    def _lines_for(self, action_name: str) -> list:
        return [ln for ln in build_actions_prompt().split("\n") if action_name in ln]

    def test_remove_allocation_marked_destructive_in_prompt(self):
        lines = self._lines_for("remove_allocation")
        print(f"\n[prompt] remove_allocation lines: {lines}")
        assert lines, "remove_allocation missing from build_actions_prompt output"
        assert "[destructive]" in lines[0], (
            f"remove_allocation not marked [destructive] in prompt: {lines[0]}"
        )

    def test_delete_wbs_task_marked_destructive_in_prompt(self):
        lines = self._lines_for("delete_wbs_task")
        print(f"\n[prompt] delete_wbs_task lines: {lines}")
        assert lines, "delete_wbs_task missing from build_actions_prompt output"
        assert "[destructive]" in lines[0], (
            f"delete_wbs_task not marked [destructive] in prompt: {lines[0]}"
        )

    def test_update_project_not_marked_destructive(self):
        """update_project is non-destructive — must NOT show [destructive]."""
        lines = self._lines_for("update_project")
        assert lines, "update_project missing from prompt"
        assert "[destructive]" not in lines[0], (
            f"update_project incorrectly marked as destructive: {lines[0]}"
        )

    def test_registry_flags_are_correct(self):
        """Direct registry check: is_destructive flag on correct entries."""
        assert ACTIONS["remove_allocation"]["is_destructive"] is True
        assert ACTIONS["delete_wbs_task"]["is_destructive"] is True
        assert ACTIONS["update_project"]["is_destructive"] is False
        assert ACTIONS["manage_phases"]["is_destructive"] is False
        assert ACTIONS["delete_project"]["is_destructive"] is True
        assert ACTIONS["delete_risk"]["is_destructive"] is True


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 5: Regression — existing destructive actions gate on confirmation (HTTP)
# ═════════════════════════════════════════════════════════════════════════════

class TestRegressionDestructiveHTTP:
    """delete_project and delete_risk must still require confirmation for a regular admin."""

    def test_delete_project_needs_confirmation_for_admin(self, temp_admin_token, projects_map):
        """delete_project without confirm_token → needs_confirmation (admin user)."""
        pid = projects_map.get("Mobile App") or list(projects_map.values())[0]
        r = requests.post(
            f"{BASE_URL}/api/ai/chat/execute-action",
            headers=_hdr(temp_admin_token),
            json={"action": "delete_project", "project_id": pid},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"Unexpected HTTP error: {r.status_code} {r.text}"
        body = r.json()
        print(f"\n[delete_project regression] body: {body}")
        assert body.get("needs_confirmation") is True, (
            f"delete_project must require confirmation for admin, got: {body}"
        )
        assert body.get("confirm_token"), "No confirm_token issued"
        # Project must still exist
        check = requests.get(f"{BASE_URL}/api/projects/{pid}", headers=_hdr(temp_admin_token), timeout=10)
        assert check.status_code == 200, "Project disappeared despite no confirmation!"
        # Cleanup token
        _run(pending_actions_collection.delete_one({"token": body["confirm_token"]}))

    def test_delete_risk_needs_confirmation_for_admin(self, temp_admin_token, projects_map):
        """delete_risk without confirm_token → needs_confirmation (admin user)."""
        # Create a test risk via REST endpoint
        pid = projects_map.get("Mobile App") or list(projects_map.values())[0]
        cr = requests.post(
            f"{BASE_URL}/api/projects/{pid}/risks",
            headers=_hdr(temp_admin_token),
            json={
                "description": "TEST_iter24_regression_delete_risk",
                "impact": "Low",
                "probability": "Low",
                "category": "Schedule",
                "status": "Active",
            },
            timeout=TIMEOUT,
        )
        assert cr.status_code in (200, 201), f"Risk creation failed: {cr.status_code} {cr.text}"
        risk_id = cr.json().get("id")
        assert risk_id, f"No risk id in response: {cr.json()}"

        try:
            # Attempt to delete via AI action (no confirm_token)
            r = requests.post(
                f"{BASE_URL}/api/ai/chat/execute-action",
                headers=_hdr(temp_admin_token),
                json={"action": "delete_risk", "risk_id": risk_id},
                timeout=TIMEOUT,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            print(f"\n[delete_risk regression] body: {body}")
            assert body.get("needs_confirmation") is True, (
                f"delete_risk must require confirmation for admin, got: {body}"
            )
            token = body.get("confirm_token")
            assert token, "No confirm_token returned"
            # Cleanup pending token
            _run(pending_actions_collection.delete_one({"token": token}))
        finally:
            # Cleanup the test risk via REST (even if above test flow changed it)
            requests.delete(
                f"{BASE_URL}/api/projects/{pid}/risks/{risk_id}",
                headers=_hdr(temp_admin_token),
                timeout=10,
            )


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 6: Regression — non-destructive actions execute immediately (HTTP)
# ═════════════════════════════════════════════════════════════════════════════

class TestRegressionNonDestructiveHTTP:
    """Non-destructive registry actions execute immediately — no confirmation gate."""

    def test_update_project_executes_immediately(self, temp_admin_token, projects_map):
        pid = projects_map.get("Website Redesign") or list(projects_map.values())[0]
        orig = requests.get(f"{BASE_URL}/api/projects/{pid}", headers=_hdr(temp_admin_token), timeout=10).json()

        r = requests.post(
            f"{BASE_URL}/api/ai/chat/execute-action",
            headers=_hdr(temp_admin_token),
            json={"action": "update_project", "project_id": pid, "client_name": "TEST_iter24_client"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        print(f"\n[update_project non-destructive] body: {body}")
        assert not body.get("needs_confirmation"), (
            f"update_project should NOT need confirmation, got: {body}"
        )
        assert body.get("success") is True, f"update_project failed: {body}"

        # Restore original client name
        requests.post(
            f"{BASE_URL}/api/ai/chat/execute-action",
            headers=_hdr(temp_admin_token),
            json={"action": "update_project", "project_id": pid, "client_name": orig.get("client_name", "")},
            timeout=TIMEOUT,
        )

    def test_create_resource_executes_immediately(self, temp_admin_token):
        """create_resource is non-destructive → executes without confirmation."""
        r = requests.post(
            f"{BASE_URL}/api/ai/chat/execute-action",
            headers=_hdr(temp_admin_token),
            json={"action": "create_resource", "name": "TEST_iter24_resource", "role": "Tester"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        print(f"\n[create_resource non-destructive] body: {body}")
        assert not body.get("needs_confirmation"), (
            f"create_resource should NOT need confirmation, got: {body}"
        )
        assert body.get("success") is True, f"create_resource failed: {body}"

        # Cleanup
        resources = requests.get(f"{BASE_URL}/api/resources", headers=_hdr(temp_admin_token), timeout=10).json()
        for res in resources:
            if res.get("name") == "TEST_iter24_resource":
                requests.delete(f"{BASE_URL}/api/resources/{res['id']}", headers=_hdr(temp_admin_token), timeout=10)


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 7: Health endpoint + smoke
# ═════════════════════════════════════════════════════════════════════════════

class TestHealth:
    def test_health_endpoint_ok(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert r.status_code == 200, f"/api/health returned {r.status_code}: {r.text}"
        print(f"\n[health] {r.json()}")

    def test_remove_allocation_in_registry(self):
        assert "remove_allocation" in ACTIONS
        assert ACTIONS["remove_allocation"]["is_destructive"] is True

    def test_delete_wbs_task_in_registry(self):
        assert "delete_wbs_task" in ACTIONS
        assert ACTIONS["delete_wbs_task"]["is_destructive"] is True
