"""
Iteration 21 - Project Lead permissions (REST + AI chat) tests.

Coverage (backend only):
  1. REST allow: lead can PUT own project (budget update).
  2. REST deny: lead cannot PUT other project (403).
  3. Lead risks: create / update / delete for own project.
  4. Lead status updates: create + edit for own project.
  5. Lead reschedule: forward + backward for own project.
  6. AI action allow: lead add_risk on own project.
  7. AI action deny: lead add_risk on other project.
  8. AI action deny: non-whitelisted action (create_allocation) for lead.
  9. AI chat E2E: lead auto-creates a status update via natural language.
 10. Client still read-only via execute-action.
 11. Admin regression: admin PUT other project still 200.
 12. Non-lead resource still blocked: temporarily strip project_lead_id and re-test.
"""
import os
import time
import pytest
import requests
from pymongo import MongoClient
from bson import ObjectId

BASE_URL = "http://localhost:8001"
CHAT_TIMEOUT = 90

# Canonical IDs from problem statement
WEBSITE_REDESIGN_ID = "6a5d4ac2ad5ecf8fe70d55b2"   # riley leads
MOBILE_APP_ID = "6a5d4ac2ad5ecf8fe70d55b3"        # riley does NOT lead
RILEY_RESOURCE_ID = "6a5d78c7b9384e8caf2ecdba"

MONGO = MongoClient("mongodb://localhost:27017")
DB = MONGO.project_planner


# ────────────── helpers ──────────────
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


@pytest.fixture(scope="module")
def admin_token():
    return _login("admin@test.com", "admin123")


@pytest.fixture(scope="module")
def riley_token():
    return _login("riley@test.com", "riley123")


@pytest.fixture(scope="module")
def client_token():
    return _login("client@test.com", "client123")


@pytest.fixture(scope="module", autouse=True)
def ensure_lead_setup(admin_token):
    """Sanity: verify riley is lead of WR and NOT of MA before we start.
    Restore lead if a prior failed test wiped it out."""
    wr = DB.projects.find_one({"_id": ObjectId(WEBSITE_REDESIGN_ID)})
    assert wr is not None, "Website Redesign missing"
    if wr.get("project_lead_id") != RILEY_RESOURCE_ID:
        DB.projects.update_one(
            {"_id": ObjectId(WEBSITE_REDESIGN_ID)},
            {"$set": {"project_lead_id": RILEY_RESOURCE_ID}},
        )
    ma = DB.projects.find_one({"_id": ObjectId(MOBILE_APP_ID)})
    assert ma is not None, "Mobile App missing"
    # Mobile App must NOT have riley as lead
    if ma.get("project_lead_id") == RILEY_RESOURCE_ID:
        DB.projects.update_one(
            {"_id": ObjectId(MOBILE_APP_ID)},
            {"$unset": {"project_lead_id": ""}},
        )
    yield
    # Final restore
    DB.projects.update_one(
        {"_id": ObjectId(WEBSITE_REDESIGN_ID)},
        {"$set": {"project_lead_id": RILEY_RESOURCE_ID, "budgeted_hours": 0}},
    )


# ────────────── 1. REST allow ──────────────
class TestLeadRestAllow:
    def test_lead_can_update_own_project_budget(self, riley_token, admin_token):
        r = requests.put(
            f"{BASE_URL}/api/projects/{WEBSITE_REDESIGN_ID}",
            headers=_hdr(riley_token),
            json={"budgeted_hours": 250},
            timeout=15,
        )
        assert r.status_code == 200, f"Lead PUT should be 200; got {r.status_code} {r.text}"

        # Verify persistence via GET
        g = requests.get(
            f"{BASE_URL}/api/projects/{WEBSITE_REDESIGN_ID}",
            headers=_hdr(admin_token), timeout=15,
        )
        assert g.status_code == 200
        assert g.json().get("budgeted_hours") == 250, f"budget not persisted: {g.json()}"

        # Restore to 0
        r2 = requests.put(
            f"{BASE_URL}/api/projects/{WEBSITE_REDESIGN_ID}",
            headers=_hdr(admin_token),
            json={"budgeted_hours": 0},
            timeout=15,
        )
        assert r2.status_code == 200


# ────────────── 2. REST deny for other project ──────────────
class TestLeadRestDeny:
    def test_lead_cannot_update_other_project(self, riley_token, admin_token):
        # Snapshot Mobile App budget before
        before = requests.get(
            f"{BASE_URL}/api/projects/{MOBILE_APP_ID}",
            headers=_hdr(admin_token), timeout=15,
        ).json()
        before_budget = before.get("budgeted_hours", 0)

        r = requests.put(
            f"{BASE_URL}/api/projects/{MOBILE_APP_ID}",
            headers=_hdr(riley_token),
            json={"budgeted_hours": 999},
            timeout=15,
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"

        # Verify budget unchanged
        after = requests.get(
            f"{BASE_URL}/api/projects/{MOBILE_APP_ID}",
            headers=_hdr(admin_token), timeout=15,
        ).json()
        assert after.get("budgeted_hours", 0) == before_budget, (
            f"Mobile App budget changed! before={before_budget} after={after.get('budgeted_hours')}"
        )


# ────────────── 3. Lead risks ──────────────
class TestLeadRisks:
    def test_lead_can_create_update_delete_risk(self, riley_token):
        # CREATE
        r = requests.post(
            f"{BASE_URL}/api/projects/{WEBSITE_REDESIGN_ID}/risks",
            headers=_hdr(riley_token),
            json={
                "description": "QA lead risk",
                "impact": "Low",
                "probability": "Low",
                "skip_ai_polish": True,
            },
            timeout=20,
        )
        assert r.status_code == 200, f"Create risk failed: {r.status_code} {r.text}"
        risk = r.json()
        risk_id = risk["id"]
        assert risk["description"] == "QA lead risk"

        try:
            # UPDATE
            u = requests.put(
                f"{BASE_URL}/api/risks/{risk_id}",
                headers=_hdr(riley_token),
                json={"status": "Mitigated", "skip_ai_polish": True},
                timeout=20,
            )
            assert u.status_code == 200, f"Update risk failed: {u.status_code} {u.text}"
            assert u.json().get("status") == "Mitigated"

            # DELETE
            d = requests.delete(
                f"{BASE_URL}/api/risks/{risk_id}",
                headers=_hdr(riley_token),
                timeout=15,
            )
            assert d.status_code == 200, f"Delete risk failed: {d.status_code} {d.text}"

            # Verify gone
            gone = DB.risks.find_one({"_id": ObjectId(risk_id)})
            assert gone is None, "Risk still in DB after DELETE"
        finally:
            # safety cleanup
            try:
                DB.risks.delete_one({"_id": ObjectId(risk_id)})
            except Exception:
                pass


# ────────────── 4. Lead status updates ──────────────
class TestLeadStatusUpdates:
    def test_lead_can_create_and_edit_status_update(self, riley_token):
        r = requests.post(
            f"{BASE_URL}/api/status-updates",
            headers=_hdr(riley_token),
            json={
                "project_id": WEBSITE_REDESIGN_ID,
                "health": "Green",
                "schedule_status": "On Track",
                "accomplishments": "qa test",
                "next_steps": "qa",
            },
            timeout=30,
        )
        assert r.status_code == 200, f"Create status update failed: {r.status_code} {r.text}"
        su = r.json()
        su_id = su.get("id")
        assert su_id, f"No id in status update response: {su}"

        try:
            e = requests.put(
                f"{BASE_URL}/api/status-updates/{su_id}",
                headers=_hdr(riley_token),
                json={"accomplishments": "qa edited"},
                timeout=20,
            )
            assert e.status_code == 200, f"Edit status update failed: {e.status_code} {e.text}"
            assert e.json().get("accomplishments") == "qa edited"
        finally:
            # Cleanup - remove from DB directly (routes may not expose delete)
            try:
                DB.status_updates.delete_one({"_id": ObjectId(su_id)})
            except Exception:
                DB.status_updates.delete_one({"id": su_id})


# ────────────── 5. Lead reschedule ──────────────
class TestLeadReschedule:
    def test_lead_can_reschedule_own_project(self, riley_token, admin_token):
        # Snapshot dates
        before = requests.get(
            f"{BASE_URL}/api/projects/{WEBSITE_REDESIGN_ID}",
            headers=_hdr(admin_token), timeout=15,
        ).json()
        start_before = before.get("start_date")
        end_before = before.get("end_date")

        # forward
        r = requests.post(
            f"{BASE_URL}/api/projects/{WEBSITE_REDESIGN_ID}/reschedule",
            headers=_hdr(riley_token),
            json={"weeks_to_shift": 1, "shift_direction": "forward"},
            timeout=30,
        )
        assert r.status_code == 200, f"Reschedule forward failed: {r.status_code} {r.text}"

        # backward (restore)
        r2 = requests.post(
            f"{BASE_URL}/api/projects/{WEBSITE_REDESIGN_ID}/reschedule",
            headers=_hdr(riley_token),
            json={"weeks_to_shift": 1, "shift_direction": "backward"},
            timeout=30,
        )
        assert r2.status_code == 200, f"Reschedule backward failed: {r2.status_code} {r2.text}"

        # Verify dates back to original (or close - within a day)
        after = requests.get(
            f"{BASE_URL}/api/projects/{WEBSITE_REDESIGN_ID}",
            headers=_hdr(admin_token), timeout=15,
        ).json()
        assert after.get("start_date") == start_before, (
            f"start_date not restored: {start_before} → {after.get('start_date')}"
        )
        assert after.get("end_date") == end_before, (
            f"end_date not restored: {end_before} → {after.get('end_date')}"
        )


# ────────────── 6. AI action allow ──────────────
class TestLeadAiActionAllow:
    def test_lead_add_risk_via_execute_action(self, riley_token, admin_token):
        # Snapshot risk IDs before (AI may polish description, so match by new IDs)
        before_ids = {str(r["_id"]) for r in DB.risks.find({"project_id": WEBSITE_REDESIGN_ID})}

        r = requests.post(
            f"{BASE_URL}/api/ai/chat/execute-action",
            headers=_hdr(riley_token),
            json={
                "action": "add_risk",
                "project_id": WEBSITE_REDESIGN_ID,
                "description": "ai lead risk qa",
                "impact": "Low",
                "probability": "Low",
            },
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True, f"Lead AI action should succeed: {body}"

        # Locate any new risk(s) & clean up (description may be AI-polished)
        after_ids = {str(r["_id"]) for r in DB.risks.find({"project_id": WEBSITE_REDESIGN_ID})}
        new_ids = after_ids - before_ids
        assert new_ids, "No new risk persisted despite success=true"
        for rid in new_ids:
            DB.risks.delete_one({"_id": ObjectId(rid)})


# ────────────── 7. AI action deny (other project) ──────────────
class TestLeadAiActionDenyOtherProject:
    def test_lead_add_risk_on_other_project_denied(self, riley_token):
        r = requests.post(
            f"{BASE_URL}/api/ai/chat/execute-action",
            headers=_hdr(riley_token),
            json={
                "action": "add_risk",
                "project_id": MOBILE_APP_ID,
                "description": "ai lead risk qa OTHER",
                "impact": "Low",
                "probability": "Low",
            },
            timeout=30,
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("success") is False, f"Expected success=false, got {body}"
        msg = (body.get("message") or body.get("error") or "").lower()
        assert "admin access required" in msg, f"Expected 'Admin access required', got: {body}"

        # Verify no risk leaked into Mobile App
        assert DB.risks.find_one(
            {"project_id": MOBILE_APP_ID, "description": "ai lead risk qa OTHER"}
        ) is None, "Risk leaked into Mobile App"


# ────────────── 8. AI action deny (non-whitelisted action) ──────────────
class TestLeadAiActionDenyNonWhitelisted:
    def test_lead_create_allocation_denied(self, riley_token):
        r = requests.post(
            f"{BASE_URL}/api/ai/chat/execute-action",
            headers=_hdr(riley_token),
            json={
                "action": "create_allocation",
                "project_id": WEBSITE_REDESIGN_ID,
                "resource_id": RILEY_RESOURCE_ID,
                "percentage": 10,
                "start_date": "2026-07-01",
                "end_date": "2026-07-31",
            },
            timeout=30,
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("success") is False, (
            f"Lead should NOT be allowed create_allocation: {body}"
        )


# ────────────── 9. AI chat E2E ──────────────
class TestLeadAiChatE2E:
    def test_lead_chat_creates_status_update(self, riley_token):
        # Snapshot status updates count for the project
        before_ids = {str(s["_id"]) for s in DB.status_updates.find({"project_id": WEBSITE_REDESIGN_ID})}

        r = requests.post(
            f"{BASE_URL}/api/ai/chat",
            headers=_hdr(riley_token),
            json={
                "message": (
                    "submit a status update for Website Redesign: health green, on track, "
                    "we finished the homepage designs, no blockers, "
                    "next step is backend integration"
                )
            },
            timeout=CHAT_TIMEOUT,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        print(f"\n[LEAD CHAT E2E] auto_executed={body.get('auto_executed')} resp={(body.get('response') or '')[:400]}")

        ae = body.get("auto_executed")
        executed = bool(ae) and (
            ae is True or (isinstance(ae, dict) and ae.get("result", {}).get("success") is True)
            or (isinstance(ae, list) and any(
                (isinstance(x, dict) and x.get("result", {}).get("success") is True) for x in ae
            ))
        )
        assert executed, f"Expected auto_executed truthy indicating success: {body}"

        # Verify status update in DB
        after_ids = {str(s["_id"]) for s in DB.status_updates.find({"project_id": WEBSITE_REDESIGN_ID})}
        new_ids = after_ids - before_ids
        assert new_ids, "No new status update in DB after chat auto-execute"

        # Cleanup
        for sid in new_ids:
            DB.status_updates.delete_one({"_id": ObjectId(sid)})


# ────────────── 10. Client still read-only ──────────────
class TestClientReadOnly:
    def test_client_add_risk_still_denied(self, client_token):
        r = requests.post(
            f"{BASE_URL}/api/ai/chat/execute-action",
            headers=_hdr(client_token),
            json={
                "action": "add_risk",
                "project_id": WEBSITE_REDESIGN_ID,
                "description": "TEST_client_privilege_esc_iter21",
                "impact": "Low",
                "probability": "Low",
            },
            timeout=20,
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("success") is False, f"Client should be blocked: {body}"
        msg = (body.get("message") or body.get("error") or "").lower()
        assert "admin access required" in msg, f"Expected 'Admin access required': {body}"


# ────────────── 11. Admin regression ──────────────
class TestAdminRegression:
    def test_admin_can_still_update_any_project(self, admin_token):
        # Snapshot Mobile App budget
        before = requests.get(
            f"{BASE_URL}/api/projects/{MOBILE_APP_ID}",
            headers=_hdr(admin_token), timeout=15,
        ).json()
        before_budget = before.get("budgeted_hours", 0)

        r = requests.put(
            f"{BASE_URL}/api/projects/{MOBILE_APP_ID}",
            headers=_hdr(admin_token),
            json={"budgeted_hours": 0},
            timeout=15,
        )
        assert r.status_code == 200, f"Admin PUT should be 200: {r.status_code} {r.text}"

        # Restore any change
        requests.put(
            f"{BASE_URL}/api/projects/{MOBILE_APP_ID}",
            headers=_hdr(admin_token),
            json={"budgeted_hours": before_budget},
            timeout=15,
        )


# ────────────── 12. Pure resource (non-lead) still blocked ──────────────
class TestPureResourceBlocked:
    def test_non_lead_resource_blocked_when_lead_removed(self, riley_token, admin_token):
        # Strip project_lead_id
        original = DB.projects.find_one({"_id": ObjectId(WEBSITE_REDESIGN_ID)}).get("project_lead_id")
        assert original == RILEY_RESOURCE_ID, f"Precondition failed - expected riley to be lead, got {original}"

        DB.projects.update_one(
            {"_id": ObjectId(WEBSITE_REDESIGN_ID)},
            {"$unset": {"project_lead_id": ""}},
        )

        try:
            # REST PUT should be 403
            r = requests.put(
                f"{BASE_URL}/api/projects/{WEBSITE_REDESIGN_ID}",
                headers=_hdr(riley_token),
                json={"budgeted_hours": 111},
                timeout=15,
            )
            assert r.status_code == 403, f"Expected 403 after removing lead, got {r.status_code}: {r.text}"

            # execute-action add_risk should be denied
            r2 = requests.post(
                f"{BASE_URL}/api/ai/chat/execute-action",
                headers=_hdr(riley_token),
                json={
                    "action": "add_risk",
                    "project_id": WEBSITE_REDESIGN_ID,
                    "description": "TEST_iter21_nonlead_should_fail",
                    "impact": "Low",
                    "probability": "Low",
                },
                timeout=20,
            )
            assert r2.status_code == 200
            body = r2.json()
            assert body.get("success") is False, f"Non-lead should be blocked: {body}"

            # Sanity - budget unchanged, no risk leaked
            wr = DB.projects.find_one({"_id": ObjectId(WEBSITE_REDESIGN_ID)})
            assert wr.get("budgeted_hours", 0) != 111, "Budget was updated despite refusal!"
            leaked = DB.risks.find_one({
                "project_id": WEBSITE_REDESIGN_ID,
                "description": "TEST_iter21_nonlead_should_fail",
            })
            assert leaked is None, "Risk leaked despite refusal"
        finally:
            # ALWAYS restore project_lead_id
            DB.projects.update_one(
                {"_id": ObjectId(WEBSITE_REDESIGN_ID)},
                {"$set": {"project_lead_id": RILEY_RESOURCE_ID}},
            )
