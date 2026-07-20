"""
Iteration 22 — Resource lifecycle (deactivate/reactivate/delete) + user
disable/enable/delete + AI action guards + capacity report exclusion.

Uses http://localhost:8001 per review-request (external preview URL is
hibernated). Credentials: admin@test.com/admin123 (super_admin),
riley@test.com/riley123.
"""
import os
import time
import pytest
import requests
from datetime import date, datetime, timedelta

BASE_URL = os.environ.get("TEST_BACKEND_URL", "http://localhost:8001")

ADMIN_EMAIL = "admin@test.com"
ADMIN_PW = "admin123"
RILEY_EMAIL = "riley@test.com"
RILEY_PW = "riley123"


# ─────────────────── helpers ─────────────────── #
def login(email: str, password: str) -> str:
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def admin_token():
    return login(ADMIN_EMAIL, ADMIN_PW)


@pytest.fixture(scope="module")
def any_project_id(admin_token):
    r = requests.get(f"{BASE_URL}/api/projects", headers=auth(admin_token))
    assert r.status_code == 200
    projs = r.json()
    assert projs, "no projects available"
    return projs[0]["id"]


# ─────────────────── LIFECYCLE ─────────────────── #
class TestResourceLifecycle:
    """Full deactivate/reactivate/delete flow."""

    def test_full_lifecycle(self, admin_token, any_project_id):
        # 1) CREATE resource
        r = requests.post(
            f"{BASE_URL}/api/resources",
            headers=auth(admin_token),
            json={"name": "TEST_Lifecycle_Resource", "role": "Tester", "standard_capacity": 100},
        )
        assert r.status_code == 200, r.text
        res_id = r.json()["id"]
        assert r.json().get("active") is True

        try:
            # 2) Add an allocation → gives it history
            today = date.today()
            payload = {
                "resource_id": res_id,
                "project_id": any_project_id,
                "percentage": 25,
                "allocation_type": "percentage",
                "start_date": today.isoformat(),
                "end_date": (today + timedelta(days=30)).isoformat(),
                "role": "Tester",
            }
            r = requests.post(f"{BASE_URL}/api/allocations", headers=auth(admin_token), json=payload)
            assert r.status_code == 200, r.text
            alloc_id = r.json()["id"]

            # 3) DELETE with history → 409
            r = requests.delete(f"{BASE_URL}/api/resources/{res_id}", headers=auth(admin_token))
            assert r.status_code == 409, f"expected 409 got {r.status_code}: {r.text}"
            assert "history" in r.json()["detail"].lower()

            # 4) DEACTIVATE
            r = requests.post(f"{BASE_URL}/api/resources/{res_id}/deactivate", headers=auth(admin_token))
            assert r.status_code == 200
            body = r.json()
            assert body["success"] is True
            assert "deactivated" in body["message"].lower()

            # 5) GET /api/resources → active:false
            r = requests.get(f"{BASE_URL}/api/resources", headers=auth(admin_token))
            got = next((x for x in r.json() if x["id"] == res_id), None)
            assert got and got.get("active") is False

            # 6) POST new allocation → 400 deactivated
            r = requests.post(f"{BASE_URL}/api/allocations", headers=auth(admin_token), json=payload)
            assert r.status_code == 400
            assert "deactivat" in r.json()["detail"].lower()

            # 7) REACTIVATE
            r = requests.post(f"{BASE_URL}/api/resources/{res_id}/reactivate", headers=auth(admin_token))
            assert r.status_code == 200 and r.json()["success"] is True

            r = requests.get(f"{BASE_URL}/api/resources", headers=auth(admin_token))
            got = next((x for x in r.json() if x["id"] == res_id), None)
            assert got and got.get("active") is True

            # 8) Manually delete allocation (via API) then DELETE resource → 200
            requests.delete(f"{BASE_URL}/api/allocations/{alloc_id}", headers=auth(admin_token))
            r = requests.delete(f"{BASE_URL}/api/resources/{res_id}", headers=auth(admin_token))
            assert r.status_code == 200, r.text
            res_id = None  # marker: cleaned up
        finally:
            if res_id:
                # best-effort cleanup
                requests.delete(f"{BASE_URL}/api/allocations/{alloc_id}", headers=auth(admin_token))
                requests.delete(f"{BASE_URL}/api/resources/{res_id}", headers=auth(admin_token))


class TestDeactivationSideEffects:
    """Future allocs deleted, running alloc end_date trimmed to today."""

    def test_side_effects(self, admin_token, any_project_id):
        r = requests.post(
            f"{BASE_URL}/api/resources",
            headers=auth(admin_token),
            json={"name": "TEST_SideEffects", "role": "Dev", "standard_capacity": 100},
        )
        res_id = r.json()["id"]
        today = date.today()
        future_start = today + timedelta(days=10)
        future_end = today + timedelta(days=20)
        running_start = today - timedelta(days=5)
        running_end = today + timedelta(days=30)

        try:
            # future
            r = requests.post(f"{BASE_URL}/api/allocations", headers=auth(admin_token), json={
                "resource_id": res_id, "project_id": any_project_id, "percentage": 10,
                "allocation_type": "percentage",
                "start_date": future_start.isoformat(), "end_date": future_end.isoformat(),
                "role": "Dev",
            })
            assert r.status_code == 200, r.text
            future_id = r.json()["id"]
            # running
            r = requests.post(f"{BASE_URL}/api/allocations", headers=auth(admin_token), json={
                "resource_id": res_id, "project_id": any_project_id, "percentage": 20,
                "allocation_type": "percentage",
                "start_date": running_start.isoformat(), "end_date": running_end.isoformat(),
                "role": "Dev",
            })
            assert r.status_code == 200, r.text
            running_id = r.json()["id"]

            # deactivate
            r = requests.post(f"{BASE_URL}/api/resources/{res_id}/deactivate", headers=auth(admin_token))
            assert r.status_code == 200

            all_allocs = requests.get(f"{BASE_URL}/api/allocations", headers=auth(admin_token)).json()
            future_still = next((a for a in all_allocs if a["id"] == future_id), None)
            running_still = next((a for a in all_allocs if a["id"] == running_id), None)
            assert future_still is None, "future allocation should be deleted"
            assert running_still is not None, "running allocation should be preserved"
            # end_date trimmed to today
            end_str = running_still["end_date"][:10]
            assert end_str == today.isoformat(), f"expected end trimmed to {today}, got {end_str}"
        finally:
            # cleanup
            allocs = requests.get(f"{BASE_URL}/api/allocations", headers=auth(admin_token)).json()
            for a in allocs:
                if a.get("resource_id") == res_id:
                    requests.delete(f"{BASE_URL}/api/allocations/{a['id']}", headers=auth(admin_token))
            requests.delete(f"{BASE_URL}/api/resources/{res_id}", headers=auth(admin_token))


class TestLinkedUserAutoDisable:
    """Deactivating a resource with a linked user auto-disables login."""

    def test_linked_user(self, admin_token):
        # riley IS linked to Riley Resource in seed data. We test on riley.
        # 1) find riley's resource
        r = requests.get(f"{BASE_URL}/api/resources", headers=auth(admin_token))
        riley_res = next((x for x in r.json() if "riley" in x["name"].lower()), None)
        assert riley_res, "Riley resource not found in seed data"
        rid = riley_res["id"]

        try:
            # 2) deactivate
            r = requests.post(f"{BASE_URL}/api/resources/{rid}/deactivate", headers=auth(admin_token))
            assert r.status_code == 200
            assert r.json().get("users_disabled", 0) >= 1

            # 3) riley login → 403
            r = requests.post(
                f"{BASE_URL}/api/auth/login",
                data={"username": RILEY_EMAIL, "password": RILEY_PW},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text}"
            assert "disabled" in r.text.lower()
        finally:
            # 4) reactivate — riley login must work again
            requests.post(f"{BASE_URL}/api/resources/{rid}/reactivate", headers=auth(admin_token))
            r = requests.post(
                f"{BASE_URL}/api/auth/login",
                data={"username": RILEY_EMAIL, "password": RILEY_PW},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            assert r.status_code == 200, f"post-reactivate login failed: {r.text}"


# ─────────────────── USER DISABLE/ENABLE + SESSION INVALIDATION ─────────────────── #
class TestUserDisableEnable:
    def test_disable_invalidates_existing_token_and_login(self, admin_token):
        # 1) find riley user
        users = requests.get(f"{BASE_URL}/api/admin/users", headers=auth(admin_token)).json()
        riley = next((u for u in users if u["email"] == RILEY_EMAIL), None)
        assert riley, "riley user not found"
        rid = riley["id"]

        # get a valid riley token BEFORE disabling
        riley_token = login(RILEY_EMAIL, RILEY_PW)

        try:
            # 2) disable riley
            r = requests.put(
                f"{BASE_URL}/api/admin/users/{rid}/status?disabled=true",
                headers=auth(admin_token),
            )
            assert r.status_code == 200, r.text

            # 3) existing riley token → /auth/me → 403
            r = requests.get(f"{BASE_URL}/api/auth/me", headers=auth(riley_token))
            assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text}"

            # 4) fresh login → 403
            r = requests.post(
                f"{BASE_URL}/api/auth/login",
                data={"username": RILEY_EMAIL, "password": RILEY_PW},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            assert r.status_code == 403
        finally:
            # re-enable riley
            r = requests.put(
                f"{BASE_URL}/api/admin/users/{rid}/status?disabled=false",
                headers=auth(admin_token),
            )
            assert r.status_code == 200
            # final: login works
            r = requests.post(
                f"{BASE_URL}/api/auth/login",
                data={"username": RILEY_EMAIL, "password": RILEY_PW},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            assert r.status_code == 200, f"riley login not restored: {r.text}"


class TestUserGuards:
    def test_cannot_disable_self(self, admin_token):
        me = requests.get(f"{BASE_URL}/api/auth/me", headers=auth(admin_token)).json()
        r = requests.put(
            f"{BASE_URL}/api/admin/users/{me['id']}/status?disabled=true",
            headers=auth(admin_token),
        )
        assert r.status_code == 400
        assert "own" in r.json()["detail"].lower()

    def test_cannot_delete_self(self, admin_token):
        me = requests.get(f"{BASE_URL}/api/auth/me", headers=auth(admin_token)).json()
        r = requests.delete(
            f"{BASE_URL}/api/admin/users/{me['id']}",
            headers=auth(admin_token),
        )
        assert r.status_code == 400
        assert "own" in r.json()["detail"].lower()

    def test_plain_admin_cannot_disable_super_admin(self, admin_token):
        """Create a plain 'admin', login as it, then try to disable admin@test.com (super_admin)."""
        # create user via AI create_user action (super_admin path). But simpler:
        # POST /api/auth/register requires admin — admin@test.com is super_admin so OK.
        temp_email = "test_plain_admin@test.com"
        temp_pw = "AdminPass123!"
        # ensure clean start
        users = requests.get(f"{BASE_URL}/api/admin/users", headers=auth(admin_token)).json()
        existing = next((u for u in users if u["email"] == temp_email), None)
        if existing:
            requests.delete(f"{BASE_URL}/api/admin/users/{existing['id']}", headers=auth(admin_token))

        r = requests.post(
            f"{BASE_URL}/api/auth/register",
            headers=auth(admin_token),
            json={
                "email": temp_email,
                "password": temp_pw,
                "role": "admin",
                "allowed_project_ids": [],
            },
        )
        assert r.status_code == 200, r.text
        temp_id = r.json()["id"]

        try:
            plain_admin_token = login(temp_email, temp_pw)
            # find super_admin id (admin@test.com)
            me = requests.get(f"{BASE_URL}/api/auth/me", headers=auth(admin_token)).json()
            super_id = me["id"]
            # plain admin attempts to disable super_admin
            r = requests.put(
                f"{BASE_URL}/api/admin/users/{super_id}/status?disabled=true",
                headers=auth(plain_admin_token),
            )
            assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text}"
            assert "super admin" in r.json()["detail"].lower()
        finally:
            requests.delete(f"{BASE_URL}/api/admin/users/{temp_id}", headers=auth(admin_token))


class TestUserDelete:
    def test_create_and_delete_throwaway(self, admin_token):
        temp_email = "test_throwaway@test.com"
        # ensure clean start
        users = requests.get(f"{BASE_URL}/api/admin/users", headers=auth(admin_token)).json()
        existing = next((u for u in users if u["email"] == temp_email), None)
        if existing:
            requests.delete(f"{BASE_URL}/api/admin/users/{existing['id']}", headers=auth(admin_token))

        r = requests.post(
            f"{BASE_URL}/api/auth/register",
            headers=auth(admin_token),
            json={
                "email": temp_email, "password": "Pass1234!",
                "role": "resource", "allowed_project_ids": [],
            },
        )
        assert r.status_code == 200
        tid = r.json()["id"]
        # DELETE
        r = requests.delete(f"{BASE_URL}/api/admin/users/{tid}", headers=auth(admin_token))
        assert r.status_code == 200
        # verify gone
        users = requests.get(f"{BASE_URL}/api/admin/users", headers=auth(admin_token)).json()
        assert not any(u["id"] == tid for u in users)


# ─────────────────── CAPACITY REPORT EXCLUSION ─────────────────── #
class TestCapacityExclusion:
    def test_deactivated_not_in_report(self, admin_token, any_project_id):
        r = requests.post(
            f"{BASE_URL}/api/resources",
            headers=auth(admin_token),
            json={"name": "TEST_CapExclude", "role": "Dev", "standard_capacity": 100},
        )
        res_id = r.json()["id"]
        try:
            today = date.today()
            # deactivate
            requests.post(f"{BASE_URL}/api/resources/{res_id}/deactivate", headers=auth(admin_token))
            # capacity report - use /api/reports/capacity
            r = requests.get(
                f"{BASE_URL}/api/reports/capacity",
                params={"start_date": today.isoformat(), "end_date": (today + timedelta(days=7)).isoformat()},
                headers=auth(admin_token),
            )
            assert r.status_code == 200, r.text
            resources_list = r.json().get("resources", [])
            ids = [x["resource_id"] for x in resources_list]
            assert res_id not in ids, "deactivated resource should NOT be in capacity report"
        finally:
            requests.delete(f"{BASE_URL}/api/resources/{res_id}", headers=auth(admin_token))


# ─────────────────── AI ACTIONS ─────────────────── #
class TestAIActions:
    def test_delete_resource_with_history_fails(self, admin_token, any_project_id):
        """Regression: BUG discovered — AI _h_delete_resource does NOT check
        project_lead_id. Uses a fresh resource with an allocation to trigger
        the alloc-count check (which IS implemented). Also asserts (currently
        failing) that a resource that is a project lead cannot be deleted via AI.
        """
        # Case A: resource with allocation (should fail with 'deactivate' message)
        r = requests.post(
            f"{BASE_URL}/api/resources",
            headers=auth(admin_token),
            json={"name": "TEST_AIHistDelA", "role": "Dev"},
        )
        rid_a = r.json()["id"]
        today = date.today()
        alloc_resp = requests.post(f"{BASE_URL}/api/allocations", headers=auth(admin_token), json={
            "resource_id": rid_a, "project_id": any_project_id, "percentage": 20,
            "allocation_type": "percentage",
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=5)).isoformat(),
            "role": "Dev",
        })
        assert alloc_resp.status_code == 200, alloc_resp.text
        alloc_id_a = alloc_resp.json()["id"]
        try:
            r = requests.post(
                f"{BASE_URL}/api/ai/chat/execute-action",
                headers=auth(admin_token),
                json={"action": "delete_resource", "resource_id": rid_a},
            )
            assert r.status_code == 200
            body = r.json()
            assert body.get("success") is False, f"expected failure got {body}"
            assert "deactivate" in body.get("message", "").lower()
        finally:
            requests.delete(f"{BASE_URL}/api/allocations/{alloc_id_a}", headers=auth(admin_token))
            requests.delete(f"{BASE_URL}/api/resources/{rid_a}", headers=auth(admin_token))

    def test_delete_resource_that_is_project_lead_should_fail(self, admin_token, any_project_id):
        """BUG: AI _h_delete_resource does not check project_lead_id — REST endpoint does.
        This test currently FAILS (asserts the expected correct behavior).
        Reproduces the incident where Riley Resource was auto-deleted despite being lead."""
        # create a resource then assign as project lead
        r = requests.post(
            f"{BASE_URL}/api/resources",
            headers=auth(admin_token),
            json={"name": "TEST_AILead_Delete", "role": "PM"},
        )
        rid = r.json()["id"]
        # set as project lead
        r_upd = requests.put(f"{BASE_URL}/api/projects/{any_project_id}",
                             headers=auth(admin_token),
                             json={"project_lead_id": rid})
        assert r_upd.status_code == 200, r_upd.text
        try:
            r = requests.post(
                f"{BASE_URL}/api/ai/chat/execute-action",
                headers=auth(admin_token),
                json={"action": "delete_resource", "resource_id": rid},
            )
            body = r.json()
            # EXPECTED: success:False, message mentions lead/history/deactivate
            # ACTUAL (bug): success:True — resource deleted anyway.
            assert body.get("success") is False, (
                f"BUG: AI delete_resource ignored project_lead_id guard. Response: {body}"
            )
        finally:
            # unset lead + delete
            requests.put(f"{BASE_URL}/api/projects/{any_project_id}",
                         headers=auth(admin_token),
                         json={"project_lead_id": None})
            requests.delete(f"{BASE_URL}/api/resources/{rid}", headers=auth(admin_token))

    def test_deactivate_and_reactivate_via_ai(self, admin_token):
        # create test resource
        r = requests.post(
            f"{BASE_URL}/api/resources",
            headers=auth(admin_token),
            json={"name": "TEST_AI_Lifecycle", "role": "Dev", "standard_capacity": 100},
        )
        res_id = r.json()["id"]
        try:
            # As super_admin, destructive actions execute directly (no confirm token)
            r = requests.post(
                f"{BASE_URL}/api/ai/chat/execute-action",
                headers=auth(admin_token),
                json={"action": "deactivate_resource", "resource_id": res_id},
            )
            assert r.status_code == 200
            body = r.json()
            # super_admin bypasses confirmation -> should succeed directly
            assert body.get("success") is True, f"deactivate_resource failed: {body}"

            # reactivate (not destructive) — executes directly
            r = requests.post(
                f"{BASE_URL}/api/ai/chat/execute-action",
                headers=auth(admin_token),
                json={"action": "reactivate_resource", "resource_id": res_id},
            )
            assert r.status_code == 200
            assert r.json().get("success") is True
        finally:
            requests.delete(f"{BASE_URL}/api/resources/{res_id}", headers=auth(admin_token))

    def test_deactivate_confirmation_flow_as_plain_admin(self, admin_token):
        """Non-super admin should get needs_confirmation for destructive deactivate."""
        # setup: create a plain admin + throwaway resource
        temp_email = "test_ai_confirm_admin@test.com"
        temp_pw = "AdminPass123!"
        users = requests.get(f"{BASE_URL}/api/admin/users", headers=auth(admin_token)).json()
        existing = next((u for u in users if u["email"] == temp_email), None)
        if existing:
            requests.delete(f"{BASE_URL}/api/admin/users/{existing['id']}", headers=auth(admin_token))

        r = requests.post(
            f"{BASE_URL}/api/auth/register",
            headers=auth(admin_token),
            json={"email": temp_email, "password": temp_pw, "role": "admin", "allowed_project_ids": []},
        )
        assert r.status_code == 200
        temp_uid = r.json()["id"]

        r = requests.post(
            f"{BASE_URL}/api/resources",
            headers=auth(admin_token),
            json={"name": "TEST_AI_Confirm", "role": "Dev"},
        )
        res_id = r.json()["id"]

        try:
            plain_admin_token = login(temp_email, temp_pw)
            # first request → needs_confirmation
            r = requests.post(
                f"{BASE_URL}/api/ai/chat/execute-action",
                headers=auth(plain_admin_token),
                json={"action": "deactivate_resource", "resource_id": res_id},
            )
            assert r.status_code == 200
            body = r.json()
            assert body.get("needs_confirmation") is True, f"expected needs_confirmation, got {body}"
            token = body.get("confirm_token")
            assert token, "no confirm_token returned"

            # confirmed request → executes
            r = requests.post(
                f"{BASE_URL}/api/ai/chat/execute-action",
                headers=auth(plain_admin_token),
                json={"action": "deactivate_resource", "resource_id": res_id, "confirm_token": token},
            )
            assert r.status_code == 200
            assert r.json().get("success") is True, f"confirm-execute failed: {r.json()}"
        finally:
            requests.delete(f"{BASE_URL}/api/resources/{res_id}", headers=auth(admin_token))
            requests.delete(f"{BASE_URL}/api/admin/users/{temp_uid}", headers=auth(admin_token))
