"""Iteration 53: Verify project scoping for resource/contractor users across 4 endpoints + AI."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = ("don@ddconsult.tech", "@Ddplanner2026")
RES_LEAD = ("dhruti@ddconsult.tech", "Test@2026")  # allocated/leads 5 projects
RES_NONLEAD = ("akshaya@ddconsult.tech", "Test@2026")

NON_ALLOC_PROJECT_ID = "69ccce9bcb339343050d1d6d"  # QRIDA AWS POC - Dhruti NOT allocated


def _login(email, pwd):
    r = requests.post(f"{API}/auth/login", data={"username": email, "password": pwd})
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def dhruti_token():
    return _login(*RES_LEAD)


@pytest.fixture(scope="module")
def akshaya_token():
    return _login(*RES_NONLEAD)


def _h(t):
    return {"Authorization": f"Bearer {t}"}


# ---------- all-active-summary ----------
def test_all_active_summary_admin_sees_all(admin_token):
    r = requests.get(f"{API}/projects/all-active-summary", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    data = r.json()
    # Admin should see all 24 active projects
    assert len(data) >= 20, f"admin only sees {len(data)} active projects"
    print(f"Admin all-active-summary: {len(data)} projects")


def test_all_active_summary_dhruti_scoped(dhruti_token, admin_token):
    r = requests.get(f"{API}/projects/all-active-summary", headers=_h(dhruti_token))
    assert r.status_code == 200, r.text
    data = r.json()
    admin_r = requests.get(f"{API}/projects/all-active-summary", headers=_h(admin_token)).json()
    print(f"Dhruti all-active-summary: {len(data)} projects (admin: {len(admin_r)})")
    assert len(data) < len(admin_r), "resource should see fewer than admin"
    assert len(data) <= 6, f"expected ~5 projects, got {len(data)}"


# ---------- portfolio health-scores ----------
def test_health_scores_admin(admin_token):
    r = requests.get(f"{API}/insights/portfolio/health-scores", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    data = r.json()
    projects = data["projects"] if isinstance(data, dict) else data
    print(f"Admin health-scores: {len(projects)} entries; total_count={data.get('total_count') if isinstance(data, dict) else 'n/a'}")
    assert len(projects) >= 20


def test_health_scores_dhruti_scoped(dhruti_token, admin_token):
    r = requests.get(f"{API}/insights/portfolio/health-scores", headers=_h(dhruti_token))
    assert r.status_code == 200, r.text
    data = r.json()
    projects = data["projects"] if isinstance(data, dict) else data
    admin_data = requests.get(f"{API}/insights/portfolio/health-scores", headers=_h(admin_token)).json()
    admin_projects = admin_data["projects"] if isinstance(admin_data, dict) else admin_data
    print(f"Dhruti health-scores: {len(projects)} vs admin {len(admin_projects)}")
    assert len(projects) < len(admin_projects)
    assert len(projects) <= 6


# ---------- planned-vs-actual overview ----------
def test_pva_admin(admin_token):
    r = requests.get(f"{API}/reports/planned-vs-actual/overview", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    data = r.json()
    # response could be list or dict; find projects count
    projects = data.get("projects") if isinstance(data, dict) else data
    print(f"Admin PvA overview keys/len: {type(data).__name__} count={len(projects) if projects is not None else 'n/a'}")
    assert projects is not None
    assert len(projects) >= 20


def test_pva_dhruti_scoped(dhruti_token, admin_token):
    r = requests.get(f"{API}/reports/planned-vs-actual/overview", headers=_h(dhruti_token))
    assert r.status_code == 200, r.text
    data = r.json()
    projects = data.get("projects") if isinstance(data, dict) else data
    admin_data = requests.get(f"{API}/reports/planned-vs-actual/overview", headers=_h(admin_token)).json()
    admin_projects = admin_data.get("projects") if isinstance(admin_data, dict) else admin_data
    print(f"Dhruti PvA: {len(projects)} vs admin {len(admin_projects)}")
    assert len(projects) < len(admin_projects)
    assert len(projects) <= 6


# ---------- /api/projects ----------
def test_projects_list_dhruti_scoped(dhruti_token, admin_token):
    r_d = requests.get(f"{API}/projects", headers=_h(dhruti_token))
    r_a = requests.get(f"{API}/projects", headers=_h(admin_token))
    assert r_d.status_code == 200 and r_a.status_code == 200
    d, a = r_d.json(), r_a.json()
    print(f"/projects dhruti={len(d)} admin={len(a)}")
    assert len(d) < len(a)
    assert len(d) <= 6


# ---------- project detail 403 ----------
def test_project_detail_403_for_non_allocated(dhruti_token):
    r = requests.get(f"{API}/projects/{NON_ALLOC_PROJECT_ID}", headers=_h(dhruti_token))
    print(f"Non-alloc project detail status: {r.status_code}")
    assert r.status_code in (403, 404), f"expected 403/404 got {r.status_code}: {r.text[:200]}"


# ---------- AI command scoping ----------
def test_ai_command_dhruti_scoped(dhruti_token):
    r = requests.post(
        f"{API}/ai/command",
        headers=_h(dhruti_token),
        json={"query": "list all projects you know about", "project_id": None},
        timeout=60,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    resp_text = (data.get("response") or data.get("message") or str(data)).lower()
    print(f"AI response snippet: {resp_text[:400]}")
    # Should NOT mention QRIDA (a non-allocated project name)
    forbidden = ["qrida"]
    for f in forbidden:
        assert f not in resp_text, f"AI leaked non-allocated project name: {f}"
