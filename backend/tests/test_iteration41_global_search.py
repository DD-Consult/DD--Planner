"""
Phase 5 — Global Search tests
Cross-collection semantic-lite search endpoint.
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
    return r.json()["access_token"]


def test_global_search_basic(admin_token):
    import requests
    r = requests.get(f"{API}/api/search/global?q=website", headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert "total" in data
    projects = data["results"].get("projects", [])
    assert any("website" in p["title"].lower() for p in projects), f"Should find Website Redesign in projects: {projects}"


def test_global_search_client_name(admin_token):
    import requests
    r = requests.get(f"{API}/api/search/global?q=acme", headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
    assert r.status_code == 200
    data = r.json()
    # Should match a project by client name
    projects = data["results"].get("projects", [])
    assert len(projects) >= 1


def test_global_search_scoped_to_resource(resource_token):
    """Resource shouldn't see resources they can't view."""
    import requests
    r = requests.get(f"{API}/api/search/global?q=alice", headers={"Authorization": f"Bearer {resource_token}"}, timeout=10)
    assert r.status_code == 200
    data = r.json()
    # Non-admin should NOT get resource results
    assert data["results"].get("resources", []) == []


def test_global_search_empty_query(admin_token):
    import requests
    r = requests.get(f"{API}/api/search/global?q=", headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
    assert r.status_code == 400


def test_global_search_requires_auth():
    import requests
    r = requests.get(f"{API}/api/search/global?q=test", timeout=5)
    assert r.status_code in (401, 403)


def test_global_search_multi_type(admin_token):
    """Verify the response shape includes all expected categories."""
    import requests
    r = requests.get(f"{API}/api/search/global?q=redesign", headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
    assert r.status_code == 200
    data = r.json()
    for key in ("projects", "resources", "tasks", "risks", "status_updates"):
        assert key in data["results"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
