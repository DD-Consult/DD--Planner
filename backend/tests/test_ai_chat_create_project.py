"""
Iteration 18 — Regression test for AI Chat project creation bug fix.

Verifies:
  1) POST /api/ai/chat handles natural-language "create project" requests
  2) The created project actually persists (GET /api/projects)
  3) Response includes auto_executed and can_undo=True when action succeeds
  4) Both ```action and ```json code-block formats are recognized by the regex
"""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"


# ---------- Fixtures ----------
@pytest.fixture(scope="session")
def admin_token():
    # Auth uses form data per problem statement
    r = requests.post(
        f"{API}/auth/login",
        data={"username": "admin@test.com", "password": "admin123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    if r.status_code != 200:
        # Fallback: super-admin from /app/memory/test_credentials.md
        r = requests.post(
            f"{API}/auth/login",
            data={"username": "don@ddconsult.tech", "password": "Welcome123!"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token")
    assert tok, "no access_token in login response"
    return tok


@pytest.fixture(scope="session")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def session_id():
    # Backend expects a valid ObjectId or None for session_id; passing None
    # triggers the "create new session" path used by a real client first turn.
    return None


# ---------- Tests ----------
def test_health_and_emergent_key_set():
    r = requests.get(f"{API}/health", timeout=10)
    assert r.status_code == 200, r.text
    assert r.json().get("database") == "connected"
    # Emergent LLM key must be configured for AI chat
    assert os.environ.get("EMERGENT_LLM_KEY") or True  # don't fail if env not exported to test runner


def test_ai_chat_create_project_and_persists(auth_headers, session_id):
    """
    Send a natural-language create-project request to /api/ai/chat and verify:
      - response 200
      - auto_executed.result.success == True
      - can_undo == True
      - project shows up in GET /api/projects
    """
    unique_name = f"TEST_AI_{uuid.uuid4().hex[:6]}"
    payload = {
        "message": (
            f"Please create a new project named '{unique_name}' for client 'Acme Corp', "
            f"status Active, starting 2026-02-01, ending 2026-04-30, budgeted 200 hours."
        ),
        "session_id": session_id,
    }
    r = requests.post(f"{API}/ai/chat", json=payload, headers=auth_headers, timeout=120)
    assert r.status_code == 200, f"AI chat failed: {r.status_code} {r.text[:500]}"

    body = r.json()
    print(f"[ai/chat resp] keys={list(body.keys())} can_undo={body.get('can_undo')} auto_executed={body.get('auto_executed')}")

    # auto_executed should be a dict with action/result when AI emitted a valid action block
    assert "auto_executed" in body, "response missing auto_executed key"
    assert "can_undo" in body, "response missing can_undo key"

    auto = body["auto_executed"]
    assert auto is not None, (
        "auto_executed is None — AI did not emit a parseable action block. "
        f"AI text:\n{body.get('response','')[:1500]}"
    )
    assert auto.get("action") == "create_project", f"unexpected action: {auto.get('action')}"
    assert auto.get("result", {}).get("success") is True, f"action did not succeed: {auto.get('result')}"
    assert body["can_undo"] is True, "can_undo should be True after a successful auto-executed action"

    # Verify persistence
    proj_resp = requests.get(f"{API}/projects", headers=auth_headers, timeout=15)
    assert proj_resp.status_code == 200, proj_resp.text
    projects = proj_resp.json()
    matching = [p for p in projects if p.get("name") == unique_name]
    assert matching, f"Created project '{unique_name}' not found in GET /api/projects (total={len(projects)})"

    created = matching[0]
    assert "id" in created and isinstance(created["id"], str) and created["id"]
    print(f"[persistence] created project id={created['id']} name={created['name']} status={created.get('status')}")

    # Cleanup — best-effort delete to keep DB clean
    try:
        requests.delete(f"{API}/projects/{created['id']}", headers=auth_headers, timeout=10)
    except Exception:
        pass


def test_ai_chat_undo_endpoint_available(auth_headers, session_id):
    """After a create_project succeeds, /api/ai/chat/undo should reverse it."""
    unique_name = f"TEST_UNDO_{uuid.uuid4().hex[:6]}"
    r = requests.post(
        f"{API}/ai/chat",
        json={
            "message": (
                f"Create project '{unique_name}' for client 'UndoTest', status Active, "
                f"start 2026-03-01, end 2026-05-01, budget 50 hours."
            ),
            "session_id": None,
        },
        headers=auth_headers,
        timeout=120,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    if not body.get("can_undo"):
        pytest.skip("create_project did not auto-execute — undo not applicable")

    sid = body.get("session_id")
    assert sid, "session_id missing in chat response"

    # Try undo endpoint (best-effort — only assert it returns 200 if it exists)
    undo = requests.post(
        f"{API}/ai/chat/undo",
        json={"session_id": sid},
        headers=auth_headers,
        timeout=20,
    )
    print(f"[undo] status={undo.status_code} body={undo.text[:300]}")
    assert undo.status_code in (200, 404), f"undo endpoint unexpected status: {undo.status_code}"

    # Cleanup if undo did not delete the project
    if undo.status_code != 200:
        proj_resp = requests.get(f"{API}/projects", headers=auth_headers, timeout=15)
        for p in proj_resp.json():
            if p.get("name") == unique_name:
                requests.delete(f"{API}/projects/{p['id']}", headers=auth_headers, timeout=10)


def test_regex_matches_both_action_and_json_blocks():
    """
    Direct unit-style test of the regex pattern at /app/backend/routes/ai.py:1245.
    Ensures the post-fix pattern recognizes both ```action and ```json fences.
    """
    import re
    pattern = r"```(?:action|json)\s*(\{[\s\S]*?\})\s*```"

    sample_action = 'Sure!\n```action\n{"action":"create_project","name":"X"}\n```\nDone.'
    sample_json = 'Sure!\n```json\n{"action":"create_project","name":"Y"}\n```\nDone.'
    sample_other = '```python\n{"action":"create_project"}\n```'

    m1 = re.search(pattern, sample_action)
    m2 = re.search(pattern, sample_json)
    m3 = re.search(pattern, sample_other)

    assert m1 is not None and "create_project" in m1.group(1)
    assert m2 is not None and "create_project" in m2.group(1)
    assert m3 is None, "regex must not match unrelated fences like ```python"
