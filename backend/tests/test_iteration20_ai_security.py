"""
Iteration 20 - AI Chat security & role-scoping tests.
Tests:
  1. Privilege-escalation closed for non-admin execute-action (legacy + registry).
  2. Client action block.
  3. Admin action still works.
  4. Data scoping in /api/ai/chat for resource user.
  5. Data scoping in /api/ai/chat for client user.
  6. Read-only conversational refusal for non-admin.
  7. Admin chat auto-execute regression.
  8. Admin lazy blocks (users list) - visible for admin, hidden for non-admin.
  9. Conversational tone soft check (qualitative log only).
"""
import os
import time
import pytest
import requests

BASE_URL = "http://localhost:8001"
CHAT_TIMEOUT = 90


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
def resource_token():
    return _login("riley@test.com", "riley123")


@pytest.fixture(scope="module")
def client_token():
    return _login("client@test.com", "client123")


@pytest.fixture(scope="module")
def projects_map(admin_token):
    r = requests.get(f"{BASE_URL}/api/projects", headers=_hdr(admin_token), timeout=15)
    assert r.status_code == 200
    m = {p["name"]: p["id"] for p in r.json()}
    # Sanity - the 4 canonical projects should exist
    for k in ("Website Redesign", "Mobile App", "Data Migration", "Legacy System"):
        assert k in m, f"Missing seed project {k}"
    return m


# ────────────── SECURITY 1 — resource cannot execute actions ──────────────
class TestResourcePrivilegeEscalation:
    def test_legacy_add_risk_blocked(self, resource_token, admin_token, projects_map):
        # Riley is now LEAD of Website Redesign (iteration 21) — use a project he does NOT lead
        pid = projects_map["Mobile App"]
        # Snapshot risks BEFORE
        before = requests.get(
            f"{BASE_URL}/api/projects/{pid}/risks", headers=_hdr(admin_token), timeout=15
        )
        before_ids = {r["id"] for r in before.json()} if before.status_code == 200 else set()

        r = requests.post(
            f"{BASE_URL}/api/ai/chat/execute-action",
            headers=_hdr(resource_token),
            json={
                "action": "add_risk",
                "project_id": pid,
                "description": "TEST_privilege_esc_riley",
                "impact": "High",
                "probability": "High",
            },
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is False, f"Expected success=false, got {body}"
        msg = (body.get("message") or body.get("error") or "").lower()
        assert "admin" in msg, f"Expected 'admin' in refusal message, got: {body}"

        # Confirm no risk was created
        after = requests.get(
            f"{BASE_URL}/api/projects/{pid}/risks", headers=_hdr(admin_token), timeout=15
        )
        after_ids = {r["id"] for r in after.json()} if after.status_code == 200 else set()
        new_ids = after_ids - before_ids
        # Cleanup any leaked risks just in case, then assert
        for rid in new_ids:
            requests.delete(f"{BASE_URL}/api/projects/{pid}/risks/{rid}", headers=_hdr(admin_token))
        assert not new_ids, f"Risk was created despite refusal: {new_ids}"

    def test_registry_create_resource_blocked(self, resource_token, admin_token):
        # Snapshot resource count
        before = requests.get(f"{BASE_URL}/api/resources", headers=_hdr(admin_token), timeout=15).json()
        before_names = {res["name"] for res in before}

        r = requests.post(
            f"{BASE_URL}/api/ai/chat/execute-action",
            headers=_hdr(resource_token),
            json={"action": "create_resource", "name": "TEST_Hacker_riley"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is False, f"Expected success=false, got {body}"
        msg = (body.get("message") or body.get("error") or "").lower()
        assert "admin" in msg, f"Expected 'admin' in refusal message, got: {body}"

        after = requests.get(f"{BASE_URL}/api/resources", headers=_hdr(admin_token), timeout=15).json()
        after_names = {res["name"] for res in after}
        new_names = after_names - before_names
        # Cleanup + assert
        for res in after:
            if res["name"].startswith("TEST_Hacker"):
                requests.delete(f"{BASE_URL}/api/resources/{res['id']}", headers=_hdr(admin_token))
        assert "TEST_Hacker_riley" not in new_names, f"Resource created despite refusal"


# ────────────── SECURITY 2 — client blocked ──────────────
class TestClientPrivilegeEscalation:
    def test_legacy_add_risk_blocked(self, client_token, admin_token, projects_map):
        pid = projects_map["Website Redesign"]
        r = requests.post(
            f"{BASE_URL}/api/ai/chat/execute-action",
            headers=_hdr(client_token),
            json={
                "action": "add_risk",
                "project_id": pid,
                "description": "TEST_privilege_esc_client",
                "impact": "High",
                "probability": "High",
            },
            timeout=20,
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("success") is False, body
        assert "admin" in (body.get("message") or body.get("error") or "").lower()

    def test_registry_create_resource_blocked(self, client_token, admin_token):
        r = requests.post(
            f"{BASE_URL}/api/ai/chat/execute-action",
            headers=_hdr(client_token),
            json={"action": "create_resource", "name": "TEST_Hacker_client"},
            timeout=20,
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("success") is False, body
        assert "admin" in (body.get("message") or body.get("error") or "").lower()

        # Safety cleanup
        after = requests.get(f"{BASE_URL}/api/resources", headers=_hdr(admin_token), timeout=15).json()
        for res in after:
            if res["name"].startswith("TEST_Hacker"):
                requests.delete(f"{BASE_URL}/api/resources/{res['id']}", headers=_hdr(admin_token))


# ────────────── SECURITY 3 — admin still works ──────────────
class TestAdminActionsWork:
    def test_admin_add_risk_success(self, admin_token, projects_map):
        pid = projects_map["Legacy System"]
        r = requests.post(
            f"{BASE_URL}/api/ai/chat/execute-action",
            headers=_hdr(admin_token),
            json={
                "action": "add_risk",
                "project_id": pid,
                "description": "TEST_admin_ok_iter20",
                "impact": "High",
                "probability": "Medium",
            },
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True, f"Admin add_risk failed: {body}"

        # Cleanup - find and delete the risk we created
        risks = requests.get(
            f"{BASE_URL}/api/projects/{pid}/risks", headers=_hdr(admin_token), timeout=15
        ).json()
        for rk in risks:
            if rk.get("description") == "TEST_admin_ok_iter20":
                requests.delete(
                    f"{BASE_URL}/api/projects/{pid}/risks/{rk['id']}", headers=_hdr(admin_token)
                )


# ────────────── DATA SCOPING — resource user ──────────────
class TestResourceDataScoping:
    def test_resource_only_sees_own_project(self, resource_token):
        r = requests.post(
            f"{BASE_URL}/api/ai/chat",
            headers=_hdr(resource_token),
            json={"message": "list every project we have with budgets"},
            timeout=CHAT_TIMEOUT,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        text = (body.get("response") or "").lower()
        print(f"\n[RESOURCE SCOPING RESPONSE]: {body.get('response')[:500]}")

        assert "website redesign" in text, "Riley's own project missing from response"
        # Must NOT mention any of these projects
        for forbidden in ("data migration", "legacy system", "mobile app"):
            assert forbidden not in text, (
                f"Resource user response leaked forbidden project '{forbidden}': {text[:600]}"
            )


# ────────────── DATA SCOPING — client user ──────────────
class TestClientDataScoping:
    def test_client_scoping_and_no_allocation_pct(self, client_token):
        r = requests.post(
            f"{BASE_URL}/api/ai/chat",
            headers=_hdr(client_token),
            json={"message": "list all projects and allocation percentages"},
            timeout=CHAT_TIMEOUT,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        text = (body.get("response") or "").lower()
        print(f"\n[CLIENT SCOPING RESPONSE]: {body.get('response')[:600]}")

        # Client is allowed Website Redesign + Mobile App
        assert "website redesign" in text or "mobile app" in text, "Client's allowed project missing"
        for forbidden in ("data migration", "legacy system"):
            assert forbidden not in text, (
                f"Client response leaked forbidden project '{forbidden}': {text[:600]}"
            )
        # No allocation percentages ("50%", "100%", etc.) revealed
        import re
        pct_matches = re.findall(r"\d{1,3}\s*%", text)
        assert not pct_matches, (
            f"Client response revealed allocation percentages: {pct_matches} in {text[:600]}"
        )


# ────────────── READ-ONLY CONVERSATIONAL REFUSAL ──────────────
class TestReadOnlyRefusal:
    def test_resource_delete_project_refused(self, resource_token, projects_map):
        pid_before = projects_map["Website Redesign"]
        r = requests.post(
            f"{BASE_URL}/api/ai/chat",
            headers=_hdr(resource_token),
            json={"message": "delete the Website Redesign project"},
            timeout=CHAT_TIMEOUT,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        text = body.get("response") or ""
        print(f"\n[RO REFUSAL RESPONSE]: {text[:500]}")

        # Must NOT auto-execute
        assert not body.get("auto_executed"), f"auto_executed should be falsy: {body}"
        # Response must not contain an action block
        assert "```action" not in text.lower(), "action block present in read-only response"
        # Must conversationally imply admin needed / cannot do it
        assert any(k in text.lower() for k in ("admin", "cannot", "can't", "not allowed", "permission", "read-only", "unable")), (
            f"Refusal wording missing: {text[:400]}"
        )

        # Sanity - project still exists
        r2 = requests.get(f"{BASE_URL}/api/projects", headers=_hdr(_login('admin@test.com','admin123')), timeout=15)
        assert any(p["id"] == pid_before for p in r2.json()), "Website Redesign somehow deleted"


# ────────────── ADMIN CHAT ACTION REGRESSION ──────────────
class TestAdminChatActionRegression:
    def test_admin_auto_execute_add_risk(self, admin_token, projects_map):
        pid = projects_map["Legacy System"]

        r = requests.post(
            f"{BASE_URL}/api/ai/chat",
            headers=_hdr(admin_token),
            json={
                "message": "add a risk to Legacy System: TEST_iter20_vendor_contract_uncertainty, medium impact, low probability"
            },
            timeout=CHAT_TIMEOUT,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        text = body.get("response") or ""
        print(f"\n[ADMIN AUTO EXEC]: auto_executed={body.get('auto_executed')} text={text[:400]}")

        ae = body.get("auto_executed")
        # auto_executed can be True or a dict {action, result:{success:true}} — both count as executed
        executed = bool(ae) and (ae is True or (isinstance(ae, dict) and ae.get("result", {}).get("success") is True))
        assert executed, f"Expected auto_executed to indicate success, got {body}"
        assert "✅" in text or "done" in text.lower(), f"Expected success confirmation, got: {text[:300]}"

        # Verify risk exists in DB
        risks = requests.get(
            f"{BASE_URL}/api/projects/{pid}/risks", headers=_hdr(admin_token), timeout=15
        ).json()
        matched = [r for r in risks if "TEST_iter20_vendor" in (r.get("description") or "") or "vendor" in (r.get("description") or "").lower()]
        assert matched, f"No matching risk found in DB after auto-execute; risks={risks}"

        # Cleanup
        for rk in matched:
            requests.delete(f"{BASE_URL}/api/projects/{pid}/risks/{rk['id']}", headers=_hdr(admin_token))


# ────────────── ADMIN LAZY BLOCKS ──────────────
class TestLazyBlocks:
    def test_admin_can_see_users(self, admin_token):
        r = requests.post(
            f"{BASE_URL}/api/ai/chat",
            headers=_hdr(admin_token),
            json={"message": "what users exist in the system and their roles?"},
            timeout=CHAT_TIMEOUT,
        )
        assert r.status_code == 200
        text = (r.json().get("response") or "").lower()
        print(f"\n[ADMIN USERS]: {text[:500]}")
        assert "@" in text and ("admin" in text or "resource" in text or "client" in text), (
            f"Admin should see user emails/roles: {text[:400]}"
        )

    def test_resource_cannot_see_users(self, resource_token):
        r = requests.post(
            f"{BASE_URL}/api/ai/chat",
            headers=_hdr(resource_token),
            json={"message": "what users exist in the system and their emails and roles?"},
            timeout=CHAT_TIMEOUT,
        )
        assert r.status_code == 200
        text = (r.json().get("response") or "").lower()
        print(f"\n[RESOURCE USERS]: {text[:500]}")
        # riley must not see admin@test.com or client@test.com emails leaked
        assert "admin@test.com" not in text, f"Resource leaked admin email: {text[:400]}"
        assert "client@test.com" not in text, f"Resource leaked client email: {text[:400]}"


# ────────────── CONVERSATIONAL TONE (soft) ──────────────
class TestConversationalTone:
    def test_admin_response_readable(self, admin_token):
        r = requests.post(
            f"{BASE_URL}/api/ai/chat",
            headers=_hdr(admin_token),
            json={"message": "how are our projects doing?"},
            timeout=CHAT_TIMEOUT,
        )
        assert r.status_code == 200
        text = r.json().get("response") or ""
        print(f"\n[TONE CHECK]: {text[:800]}")
        # Qualitative log only - do not fail unless egregiously data-dump.
        # Heuristic: response should have some prose (sentences ending in '.') and not be >80% pipe-tables.
        pipe_ratio = text.count("|") / max(1, len(text))
        print(f"Pipe density: {pipe_ratio:.3f}, length: {len(text)}")
        # Only fail if response is essentially raw table (>10% pipes) AND lacks periods
        if pipe_ratio > 0.10 and text.count(".") < 3:
            pytest.fail(f"Response reads like a raw data dump: {text[:500]}")
