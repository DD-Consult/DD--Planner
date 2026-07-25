"""
Phase 3 — AI Productivity tests
Status Update Drafter, Kickoff Wizard, and Similar Projects.
"""
import os
import pytest


API = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()


@pytest.fixture(scope="module")
def admin_token():
    import requests
    r = requests.post(f"{API}/api/auth/login", data={"username": "admin@test.com", "password": "admin123"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def first_project_id(admin_token):
    import requests
    r = requests.get(f"{API}/api/projects", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    return r.json()[0]["id"]


# ─── Status Update Drafter ──────────────────────────────────────────────

def test_status_draft(admin_token, first_project_id):
    import requests
    r = requests.post(f"{API}/api/ai/draft-status-update/{first_project_id}",
                      headers={"Authorization": f"Bearer {admin_token}"}, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "draft" in data
    draft = data["draft"]
    # Required fields present
    for k in ("health", "schedule_status", "accomplishments", "blockers", "next_steps"):
        assert k in draft, f"missing {k}"
    assert draft["health"] in ("Green", "Amber", "Red")
    assert draft["schedule_status"] in ("On Track", "Delayed", "Ahead of Schedule", "At Risk")
    # Consistency rule: if schedule is Delayed/At Risk, health should not be Green
    if draft["schedule_status"] in ("Delayed", "At Risk"):
        assert draft["health"] != "Green"


def test_status_draft_requires_auth():
    import requests
    r = requests.post(f"{API}/api/ai/draft-status-update/abc", timeout=10)
    assert r.status_code in (401, 403, 422)


# ─── Kickoff Wizard ─────────────────────────────────────────────────────

def test_kickoff_suggest_basic(admin_token):
    import requests
    payload = {
        "name": "New Ecommerce Platform",
        "goal": "Build a Shopify-integrated ecommerce site for a mid-size retailer",
        "client": "Acme Retail",
        "budget_hours": 400,
        "complexity": "standard",
    }
    r = requests.post(f"{API}/api/ai/kickoff-suggest",
                      headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"},
                      json=payload, timeout=90)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "phases" in data
    assert 2 <= len(data["phases"]) <= 8
    for p in data["phases"]:
        assert p.get("name")
        assert isinstance(p.get("duration_weeks"), (int, float))
    assert "team_roles" in data
    assert "budget_breakdown" in data


def test_kickoff_suggest_missing_input(admin_token):
    import requests
    r = requests.post(f"{API}/api/ai/kickoff-suggest",
                      headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"},
                      json={}, timeout=15)
    assert r.status_code == 400


def test_kickoff_requires_admin():
    import requests
    r = requests.post(f"{API}/api/ai/kickoff-suggest",
                      headers={"Content-Type": "application/json"}, json={"name": "x", "goal": "y"}, timeout=15)
    assert r.status_code in (401, 403, 422)


# ─── Similar Projects ───────────────────────────────────────────────────

def test_similar_projects(admin_token, first_project_id):
    import requests
    r = requests.get(f"{API}/api/ai/similar-projects/{first_project_id}",
                     headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["target_project_id"] == first_project_id
    assert "similar_projects" in data
    # WBS template is either present or None (no matches)
    assert "wbs_template_suggestion" in data


def test_similar_projects_invalid_id(admin_token):
    import requests
    r = requests.get(f"{API}/api/ai/similar-projects/not-an-id",
                     headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
    assert r.status_code in (400, 404, 500)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
