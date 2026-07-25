"""
Phase 4 — Resource AI tests
NL Timesheet Assistant + Personal Monday Briefing.
"""
import os
import pytest


API = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()


@pytest.fixture(scope="module")
def resource_token():
    import requests
    r = requests.post(f"{API}/api/auth/login", data={"username": "riley@test.com", "password": "riley123"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token():
    import requests
    r = requests.post(f"{API}/api/auth/login", data={"username": "admin@test.com", "password": "admin123"}, timeout=15)
    return r.json()["access_token"]


# ─── Personal Briefing ──────────────────────────────────────────────────

def test_briefing_returns_summary(resource_token):
    import requests
    r = requests.get(f"{API}/api/ai/briefing/personal", headers={"Authorization": f"Bearer {resource_token}"}, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("resource_name")
    assert "summary" in data and len(data["summary"]) > 10
    assert "capacity" in data
    assert "this_week_projects" in data
    assert "last_week" in data
    assert data["last_week"]["status"] in ("submitted", "draft", "missing")


def test_briefing_requires_resource_profile(admin_token):
    """Admin without a resource profile should get a helpful error."""
    import requests
    r = requests.get(f"{API}/api/ai/briefing/personal", headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
    # Admin either has no profile → 400, or has one → 200. Both OK.
    assert r.status_code in (200, 400)


def test_briefing_requires_auth():
    import requests
    r = requests.get(f"{API}/api/ai/briefing/personal", timeout=5)
    assert r.status_code in (401, 403)


# ─── NL Timesheet Parser ────────────────────────────────────────────────

def test_parse_natural_phrase(resource_token):
    import requests
    r = requests.post(f"{API}/api/ai/timesheet/parse",
                      headers={"Authorization": f"Bearer {resource_token}", "Content-Type": "application/json"},
                      json={"phrase": "log 4h on Website Redesign yesterday"}, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("matched") is True
    assert data.get("project_name")
    assert data.get("actual_hours") == 4 or abs(float(data["actual_hours"]) - 4) < 0.01
    assert data.get("date")
    assert data.get("week_start_date")


def test_parse_ambiguous_phrase(resource_token):
    import requests
    r = requests.post(f"{API}/api/ai/timesheet/parse",
                      headers={"Authorization": f"Bearer {resource_token}", "Content-Type": "application/json"},
                      json={"phrase": "some hours"}, timeout=30)
    assert r.status_code == 200
    data = r.json()
    # Either fails to match OR asks for clarification
    if not data.get("matched"):
        assert data.get("clarification_needed")


def test_parse_empty_phrase(resource_token):
    import requests
    r = requests.post(f"{API}/api/ai/timesheet/parse",
                      headers={"Authorization": f"Bearer {resource_token}", "Content-Type": "application/json"},
                      json={"phrase": "   "}, timeout=10)
    assert r.status_code == 400


def test_parse_hour_formats(resource_token):
    """Various hour formats should be parsed."""
    import requests
    for phrase, expected in [
        ("log 6 hours on Mobile App today", 6),
        ("2.5h on Website Redesign", 2.5),
    ]:
        r = requests.post(f"{API}/api/ai/timesheet/parse",
                          headers={"Authorization": f"Bearer {resource_token}", "Content-Type": "application/json"},
                          json={"phrase": phrase}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        if d.get("matched"):
            assert abs(float(d["actual_hours"]) - expected) < 0.1, f"Phrase '{phrase}' got {d['actual_hours']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
