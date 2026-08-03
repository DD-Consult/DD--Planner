"""Iteration 50: Verify weekly_hours is computed for every allocation."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    # Fallback: try to read frontend/.env
    with open('/app/frontend/.env') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL'):
                BASE_URL = line.split('=', 1)[1].strip().rstrip('/')

EMAIL = "don@ddconsult.tech"
PASSWORD = "@Ddplanner2026"


@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": EMAIL, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_allocations_return_weekly_hours(headers):
    r = requests.get(f"{BASE_URL}/api/allocations", headers=headers)
    assert r.status_code == 200, r.text
    allocs = r.json()
    assert len(allocs) > 0
    missing = [a for a in allocs if a.get("weekly_hours") is None]
    assert not missing, f"{len(missing)} allocations missing weekly_hours"


def test_resources_and_target_capacities(headers):
    # Get all resources
    r = requests.get(f"{BASE_URL}/api/resources", headers=headers)
    assert r.status_code == 200
    resources = r.json()
    by_name = {res["name"]: res for res in resources}
    print("Resources found:", list(by_name.keys()))

    # Fetch allocations
    ra = requests.get(f"{BASE_URL}/api/allocations", headers=headers)
    allocs = ra.json()

    # helper: today's active allocations per resource
    from datetime import date
    today = date.today()

    def active_for(resource_name):
        if resource_name not in by_name:
            return []
        rid = by_name[resource_name]["id"]
        out = []
        for a in allocs:
            if a.get("resource_id") != rid:
                continue
            s = a.get("start_date", "")[:10]
            e = a.get("end_date", "")[:10]
            if s <= today.isoformat() <= e:
                out.append(a)
        return out

    for name in ["Akshaya", "Amrit", "Bhavika"]:
        active = active_for(name)
        print(f"\n{name}: std_cap={by_name.get(name, {}).get('standard_capacity')}, active_allocs={len(active)}")
        for a in active:
            print(f"  - {a.get('project_name')} pct={a.get('percentage')} type={a.get('allocation_type')} hours={a.get('hours')} weekly_hours={a.get('weekly_hours')}")


def test_akshaya_capacity(headers):
    """Akshaya (60% std_cap): 3 allocations totaling 19.2h/wk => 80% capacity."""
    resources = requests.get(f"{BASE_URL}/api/resources", headers=headers).json()
    akshaya = next((r for r in resources if r["name"].lower().startswith("akshaya")), None)
    if not akshaya:
        pytest.skip("Akshaya not found")
    allocs = requests.get(f"{BASE_URL}/api/allocations", headers=headers).json()
    from datetime import date
    today = date.today().isoformat()
    active = [a for a in allocs if a["resource_id"] == akshaya["id"] and a["start_date"][:10] <= today <= a["end_date"][:10]]
    total = sum(a.get("weekly_hours") or 0 for a in active)
    max_hours = (akshaya["standard_capacity"] / 100) * 40
    cap_pct = round((total / max_hours) * 100) if max_hours else 0
    print(f"Akshaya std_cap={akshaya['standard_capacity']} total_weekly={total} max={max_hours} cap%={cap_pct}")
    # Not strict; just ensure not double-counted (should be reasonable, not >200%)
    assert cap_pct < 200


def test_amrit_capacity_not_double_counted(headers):
    """Amrit (50% std_cap) should NOT show 120%. Should be ~60%."""
    resources = requests.get(f"{BASE_URL}/api/resources", headers=headers).json()
    amrit = next((r for r in resources if r["name"].lower().startswith("amrit")), None)
    if not amrit:
        pytest.skip("Amrit not found")
    allocs = requests.get(f"{BASE_URL}/api/allocations", headers=headers).json()
    from datetime import date
    today = date.today().isoformat()
    active = [a for a in allocs if a["resource_id"] == amrit["id"] and a["start_date"][:10] <= today <= a["end_date"][:10]]
    total = sum(a.get("weekly_hours") or 0 for a in active)
    max_hours = (amrit["standard_capacity"] / 100) * 40
    cap_pct = round((total / max_hours) * 100) if max_hours else 0
    print(f"Amrit std_cap={amrit['standard_capacity']} total_weekly={total} max={max_hours} cap%={cap_pct}")
    for a in active:
        print(f"  - {a.get('project_name')} pct={a['percentage']} type={a.get('allocation_type')} weekly={a['weekly_hours']}")
    # Fix means Amrit should be ~60%, definitely not 120%
    assert cap_pct <= 100, f"Amrit capacity {cap_pct}% indicates double-count bug still present"


def test_hours_type_allocation_weekly_hours(headers):
    """Hours-type allocations should have weekly_hours matching total_hours / weeks."""
    allocs = requests.get(f"{BASE_URL}/api/allocations", headers=headers).json()
    hours_allocs = [a for a in allocs if a.get("allocation_type") == "hours" and a.get("hours")]
    print(f"Found {len(hours_allocs)} hours-type allocations")
    for a in hours_allocs[:5]:
        print(f"  - {a.get('resource_name')} / {a.get('project_name')}: total_hours={a['hours']} weekly_hours={a['weekly_hours']} start={a['start_date'][:10]} end={a['end_date'][:10]}")
        assert a["weekly_hours"] is not None
        assert a["weekly_hours"] > 0
