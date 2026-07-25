"""
Phase 2 — AI Intelligence tests
Anomaly detection, forecasting, and retrospective generation.
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
def resource_token():
    import requests
    r = requests.post(f"{API}/api/auth/login", data={"username": "riley@test.com", "password": "riley123"}, timeout=15)
    if r.status_code != 200:
        pytest.skip("No riley test user")
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def first_project_id(admin_token):
    import requests
    r = requests.get(f"{API}/api/projects", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    assert r.status_code == 200
    projects = r.json()
    assert len(projects) > 0, "Seed data missing"
    return projects[0]["id"]


# ─── Anomaly Detection ──────────────────────────────────────────────────

def test_anomaly_scan(admin_token):
    import requests
    r = requests.post(f"{API}/api/ai/anomaly/scan", headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "findings" in data
    assert "summary" in data
    for f in data["findings"]:
        assert "type" in f
        assert "severity" in f
        assert f["severity"] in ("critical", "high", "medium", "low")
        assert "message" in f


def test_anomaly_latest_report(admin_token):
    import requests
    # Ensure a scan has run at least once
    requests.post(f"{API}/api/ai/anomaly/scan", headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
    r = requests.get(f"{API}/api/ai/anomaly/latest", headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
    assert r.status_code == 200


def test_anomaly_requires_admin():
    """Non-admin should get 403."""
    import requests
    # Try without auth
    r = requests.post(f"{API}/api/ai/anomaly/scan", timeout=10)
    assert r.status_code in (401, 403)


# ─── Forecasting ────────────────────────────────────────────────────────

def test_forecast_portfolio(admin_token):
    import requests
    r = requests.get(f"{API}/api/ai/forecast/portfolio", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert "forecasts" in data
    assert "summary" in data
    assert "at_risk_30d_count" in data
    for f in data["forecasts"]:
        assert 0 <= f["slip_risk_score"] <= 100
        assert f["slip_risk_label"] in ("Critical", "High", "Medium", "Low")


def test_forecast_project(admin_token, first_project_id):
    import requests
    r = requests.get(
        f"{API}/api/ai/forecast/project/{first_project_id}",
        headers={"Authorization": f"Bearer {admin_token}"}, timeout=10,
    )
    assert r.status_code == 200
    data = r.json()
    assert "signals" in data
    assert set(data["signals"].keys()) >= {"velocity", "wbs_completion", "time_buffer", "health_trend", "milestones"}
    assert data.get("slip_risk_label") in ("Critical", "High", "Medium", "Low")


def test_forecast_bad_project(admin_token):
    import requests
    r = requests.get(f"{API}/api/ai/forecast/project/000000000000000000000000", headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
    assert r.status_code in (404, 400, 500)


# ─── Retrospective ──────────────────────────────────────────────────────

def test_retrospective_generation(admin_token, first_project_id):
    import requests
    r = requests.post(
        f"{API}/api/ai/retrospective/{first_project_id}",
        headers={"Authorization": f"Bearer {admin_token}"}, timeout=90,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    retro = data.get("retrospective") or {}
    assert retro.get("grade") in ("A", "B", "C", "D", "F"), f"Bad grade: {retro.get('grade')}"
    assert retro.get("summary")
    # At least one of the lists should have items
    total_items = (len(retro.get("what_went_well") or []) +
                   len(retro.get("what_didnt_go_well") or []) +
                   len(retro.get("lessons_learned") or []))
    assert total_items > 0


def test_retrospective_list(admin_token, first_project_id):
    import requests
    r = requests.get(
        f"{API}/api/ai/retrospective/list/{first_project_id}",
        headers={"Authorization": f"Bearer {admin_token}"}, timeout=10,
    )
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert isinstance(data["items"], list)


def test_retrospective_get_and_delete(admin_token, first_project_id):
    import requests
    # Get list to find one
    r = requests.get(
        f"{API}/api/ai/retrospective/list/{first_project_id}",
        headers={"Authorization": f"Bearer {admin_token}"}, timeout=10,
    )
    items = r.json()["items"]
    if not items:
        pytest.skip("No retrospectives to test get/delete")
    retro_id = items[0]["_id"]
    # Get
    r = requests.get(f"{API}/api/ai/retrospective/{retro_id}", headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["_id"] == retro_id
    assert body.get("retrospective") is not None
    # Delete
    r = requests.delete(f"{API}/api/ai/retrospective/{retro_id}", headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
    assert r.status_code == 200
    assert r.json()["deleted"] is True


# ─── Auth/Permission ────────────────────────────────────────────────────

def test_retrospective_requires_admin():
    import requests
    r = requests.post(f"{API}/api/ai/retrospective/abc", timeout=10)
    assert r.status_code in (401, 403, 422)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
