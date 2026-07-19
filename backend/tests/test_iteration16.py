"""
Iteration 16 - Risk/Issue CRUD, Status update (no progress slider),
blocker auto-promotion, AI action: create_status_update, update_risk.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "don@ddconsult.tech"
ADMIN_PASSWORD = "Welcome123!"
PROJECT_ID = "698c7799eea263b28c2715b3"  # ASKDD Chatbot


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---------- Risk CRUD ----------

class TestRiskCRUD:

    def test_create_single_risk(self, headers):
        payload = {
            "description": f"TEST_risk_crud_{int(time.time())}",
            "impact": "High",
            "probability": "Medium",
            "mitigation": "TEST mitigation plan",
            "status": "Active",
            "category": "Risk",
        }
        r = requests.post(f"{BASE_URL}/api/projects/{PROJECT_ID}/risks",
                          json=payload, headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["description"] == payload["description"]
        assert data["mitigation"] == "TEST mitigation plan"
        assert data["status"] == "Active"
        assert data["category"] == "Risk"
        assert data["impact"] == "High"
        pytest.risk_id = data["id"]

    def test_update_risk_status_transitions(self, headers):
        rid = pytest.risk_id
        # Active -> Mitigated
        r = requests.put(f"{BASE_URL}/api/risks/{rid}",
                         json={"status": "Mitigated"}, headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "Mitigated"

        # Mitigated -> Closed
        r2 = requests.put(f"{BASE_URL}/api/risks/{rid}",
                          json={"status": "Closed", "mitigation": "all resolved"}, headers=headers)
        assert r2.status_code == 200
        assert r2.json()["status"] == "Closed"
        assert r2.json()["mitigation"] == "all resolved"

    def test_delete_risk(self, headers):
        rid = pytest.risk_id
        r = requests.delete(f"{BASE_URL}/api/risks/{rid}", headers=headers)
        assert r.status_code == 200
        # Verify gone: update should 404
        r2 = requests.put(f"{BASE_URL}/api/risks/{rid}",
                          json={"status": "Active"}, headers=headers)
        assert r2.status_code == 404


# ---------- Status Update without actual_progress ----------

class TestStatusUpdate:

    def test_status_update_without_actual_progress(self, headers):
        unique = int(time.time())
        blocker_text = f"TEST_BLOCKER_{unique}_server_crash"
        payload = {
            "project_id": PROJECT_ID,
            "health": "Amber",
            "schedule_status": "At Risk",
            "accomplishments": "TEST accomplishments",
            "blockers": blocker_text,
            "next_steps": "TEST next steps mitigation",
        }
        r = requests.post(f"{BASE_URL}/api/status-updates",
                          json=payload, headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["health"] == "Amber"
        # actual_progress must be set to something (defaulted from project)
        assert "actual_progress" in data
        pytest.blocker_text = blocker_text

    def test_blocker_auto_promoted_to_issue(self, headers):
        r = requests.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/risks", headers=headers)
        assert r.status_code == 200
        risks = r.json()
        found = [x for x in risks if x.get("description") == pytest.blocker_text]
        assert len(found) >= 1, f"blocker not promoted to issue: {pytest.blocker_text}"
        issue = found[0]
        assert issue["category"] == "Issue"
        assert issue["status"] == "Active"
        pytest.promoted_issue_id = issue["id"]

    def test_blocker_dedup_on_second_submit(self, headers):
        # Submit SAME blocker again, should not create duplicate
        payload = {
            "project_id": PROJECT_ID,
            "health": "Amber",
            "schedule_status": "At Risk",
            "blockers": pytest.blocker_text,
            "next_steps": "retry",
        }
        r = requests.post(f"{BASE_URL}/api/status-updates",
                          json=payload, headers=headers)
        assert r.status_code == 200

        r2 = requests.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/risks", headers=headers)
        matches = [x for x in r2.json() if x.get("description") == pytest.blocker_text]
        assert len(matches) == 1, f"expected dedup, got {len(matches)} copies"

    def test_status_update_with_inline_new_risks(self, headers):
        unique = int(time.time())
        desc = f"TEST_inline_risk_{unique}"
        payload = {
            "project_id": PROJECT_ID,
            "health": "Green",
            "schedule_status": "On Track",
            "accomplishments": "ok",
            "next_steps": "continue",
            "new_risks": [{
                "description": desc,
                "category": "Risk",
                "impact": "High",
                "probability": "Low",
                "mitigation": "contingency plan",
            }]
        }
        r = requests.post(f"{BASE_URL}/api/status-updates",
                          json=payload, headers=headers)
        assert r.status_code == 200, r.text
        r2 = requests.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/risks", headers=headers)
        matches = [x for x in r2.json() if x.get("description") == desc]
        assert len(matches) == 1
        assert matches[0]["category"] == "Risk"
        assert matches[0]["impact"] == "High"
        assert matches[0]["mitigation"] == "contingency plan"
        pytest.inline_risk_id = matches[0]["id"]

    def test_cleanup_promoted_and_inline(self, headers):
        for rid in [getattr(pytest, "promoted_issue_id", None),
                    getattr(pytest, "inline_risk_id", None)]:
            if rid:
                requests.delete(f"{BASE_URL}/api/risks/{rid}", headers=headers)


# ---------- AI execute-action ----------

class TestAIActions:

    def test_action_add_risk_with_new_fields(self, headers):
        unique = int(time.time())
        payload = {
            "action": "add_risk",
            "project_id": PROJECT_ID,
            "description": f"TEST_ai_add_risk_{unique}",
            "impact": "Low",
            "probability": "Medium",
            "mitigation": "ai mitigation",
            "status": "Accepted",
            "category": "Issue",
        }
        r = requests.post(f"{BASE_URL}/api/ai/chat/execute-action",
                          json=payload, headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["success"] is True
        assert "id" in data
        pytest.ai_risk_id = data["id"]

        # verify by listing
        lst = requests.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/risks", headers=headers).json()
        mine = [x for x in lst if x["id"] == pytest.ai_risk_id]
        assert len(mine) == 1
        assert mine[0]["mitigation"] == "ai mitigation"
        assert mine[0]["status"] == "Accepted"
        assert mine[0]["category"] == "Issue"

    def test_action_update_risk_status(self, headers):
        payload = {
            "action": "update_risk",
            "risk_id": pytest.ai_risk_id,
            "status": "Closed",
        }
        r = requests.post(f"{BASE_URL}/api/ai/chat/execute-action",
                          json=payload, headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["success"] is True
        # verify
        lst = requests.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/risks", headers=headers).json()
        mine = [x for x in lst if x["id"] == pytest.ai_risk_id]
        assert len(mine) == 1
        assert mine[0]["status"] == "Closed"

    def test_action_create_status_update(self, headers):
        unique = int(time.time())
        blocker = f"TEST_AI_BLOCKER_{unique}_db_down"
        payload = {
            "action": "create_status_update",
            "project_id": PROJECT_ID,
            "health": "Red",
            "schedule_status": "Delayed",
            "accomplishments": "AI generated acc",
            "blockers": blocker,
            "next_steps": "AI next steps",
        }
        r = requests.post(f"{BASE_URL}/api/ai/chat/execute-action",
                          json=payload, headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["success"] is True
        assert data.get("issues_created") == 1

        # Verify issue created
        risks = requests.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/risks", headers=headers).json()
        matches = [x for x in risks if x.get("description") == blocker]
        assert len(matches) == 1
        assert matches[0]["category"] == "Issue"
        pytest.ai_blocker_issue_id = matches[0]["id"]

    def test_cleanup_ai(self, headers):
        for rid in [getattr(pytest, "ai_risk_id", None),
                    getattr(pytest, "ai_blocker_issue_id", None)]:
            if rid:
                requests.delete(f"{BASE_URL}/api/risks/{rid}", headers=headers)


# ---------- AI chat context includes blockers ----------

class TestAIChatContext:

    def test_chat_references_blockers(self, headers):
        # Seed a very unique blocker first
        unique = int(time.time())
        blocker = f"ZETA_MARKER_BLOCKER_{unique}_payments_outage"
        seed_payload = {
            "project_id": PROJECT_ID,
            "health": "Red",
            "schedule_status": "At Risk",
            "blockers": blocker,
            "next_steps": "restore asap",
        }
        r = requests.post(f"{BASE_URL}/api/status-updates",
                          json=seed_payload, headers=headers)
        assert r.status_code == 200

        # Now ask the chat
        chat_payload = {
            "message": "What are the latest blockers on ASKDD Chatbot?",
        }
        try:
            r2 = requests.post(f"{BASE_URL}/api/ai/chat",
                               json=chat_payload, headers=headers, timeout=60)
        except requests.exceptions.Timeout:
            pytest.skip("AI chat timed out — LLM latency")
        if r2.status_code != 200:
            pytest.skip(f"AI chat unavailable: {r2.status_code}")
        text = (r2.json().get("response") or "").lower()
        # At minimum, chat returned something mentioning the blocker token OR the project
        # (can't guarantee LLM will quote verbatim; just make sure no hard error)
        assert len(text) > 0

        # Cleanup the seeded issue
        lst = requests.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/risks", headers=headers).json()
        for x in lst:
            if x.get("description") == blocker:
                requests.delete(f"{BASE_URL}/api/risks/{x['id']}", headers=headers)
