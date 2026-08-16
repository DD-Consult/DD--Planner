"""
Cross-Tenant Isolation Regression Tests (Step 11 of MULTITENANT_PLAN.md).

Purpose:
    Prove that when MULTI_TENANT_ENABLED=true, two tenants with the same
    application code cannot see, modify, or authenticate against each other's
    data through ANY endpoint we've built in Steps 1-10.

Approach:
    - Sets up 2 real tenants ("iso-tenant-a" and "iso-tenant-b") via
      the public sign-up endpoint at the start of the suite.
    - Runs every isolation assertion.
    - Cleans up both tenants at the end (best-effort — safe to run repeatedly).

Preconditions:
    - Backend must be running with MULTI_TENANT_ENABLED=true.
      For CI: `MULTI_TENANT_ENABLED=true python -m pytest tests/test_multitenant_isolation.py`
    - MongoDB accessible (uses same MONGO_URL as backend).
    - No pre-existing 'iso-tenant-a' or 'iso-tenant-b' in platform_db.tenants
      (safe: setup deletes them first).

The suite runs whether the API is on localhost or a remote deployment;
override with BACKEND_URL env var (default: http://localhost:8001).
"""
from __future__ import annotations
import os
import pytest
import requests
import uuid
from pymongo import MongoClient

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")

TENANT_A_SLUG = "iso-tenant-a"
TENANT_B_SLUG = "iso-tenant-b"
TENANT_A_EMAIL = "admin@iso-tenant-a.io"
TENANT_B_EMAIL = "admin@iso-tenant-b.io"
TENANT_A_PWD = "IsoTenantA2026"
TENANT_B_PWD = "IsoTenantB2026"


# ────────────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def mongo():
    return MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)


@pytest.fixture(scope="module")
def clean_slate(mongo):
    """Drop any leftover data before + after the suite so re-runs are idempotent."""
    for slug in (TENANT_A_SLUG, TENANT_B_SLUG):
        mongo["platform_db"].tenants.delete_many({"slug": slug})
        mongo["platform_db"].tenant_modules.delete_many({"tenant_slug": slug})
        mongo["platform_db"].memberships.delete_many({"tenant_slug": slug})
        mongo["platform_db"].platform_audit_log.delete_many({"tenant_slug": slug})
        # Handle slug->dbname sanitization (dashes become underscores)
        safe = slug.replace("-", "_")
        mongo.drop_database(f"tenant_{safe}")
    yield
    for slug in (TENANT_A_SLUG, TENANT_B_SLUG):
        mongo["platform_db"].tenants.delete_many({"slug": slug})
        mongo["platform_db"].tenant_modules.delete_many({"tenant_slug": slug})
        mongo["platform_db"].memberships.delete_many({"tenant_slug": slug})
        mongo["platform_db"].platform_audit_log.delete_many({"tenant_slug": slug})
        safe = slug.replace("-", "_")
        mongo.drop_database(f"tenant_{safe}")


@pytest.fixture(scope="module")
def tenant_a(clean_slate):
    r = requests.post(f"{BACKEND_URL}/api/signup", json={
        "slug": TENANT_A_SLUG,
        "company_name": "Isolation Tenant A",
        "admin_email": TENANT_A_EMAIL,
        "admin_password": TENANT_A_PWD,
    })
    assert r.status_code == 201, f"Tenant A signup failed: {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="module")
def tenant_b(clean_slate):
    r = requests.post(f"{BACKEND_URL}/api/signup", json={
        "slug": TENANT_B_SLUG,
        "company_name": "Isolation Tenant B",
        "admin_email": TENANT_B_EMAIL,
        "admin_password": TENANT_B_PWD,
    })
    assert r.status_code == 201, f"Tenant B signup failed: {r.status_code} {r.text}"
    return r.json()


def _login(host: str, email: str, password: str) -> str:
    r = requests.post(
        f"{BACKEND_URL}/api/auth/login",
        data={"username": email, "password": password},
        headers={"Host": host, "Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200, f"Login failed for {email}@{host}: {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def token_a(tenant_a) -> str:
    return _login(f"{TENANT_A_SLUG}.ddplanner.io", TENANT_A_EMAIL, TENANT_A_PWD)


@pytest.fixture(scope="module")
def token_b(tenant_b) -> str:
    return _login(f"{TENANT_B_SLUG}.ddplanner.io", TENANT_B_EMAIL, TENANT_B_PWD)


# ────────────────────────────────────────────────────────────────────────────
# 1. Signup / login isolation
# ────────────────────────────────────────────────────────────────────────────

def test_tenants_have_distinct_databases(tenant_a, tenant_b):
    assert tenant_a["tenant_slug"] != tenant_b["tenant_slug"]
    assert tenant_a["tenant_id"] != tenant_b["tenant_id"]


def test_token_a_cannot_reach_tenant_b_host(token_a, tenant_b):
    """DD's JWT used on Acme's subdomain → 401. Prevents JWT replay attack."""
    r = requests.get(
        f"{BACKEND_URL}/api/projects",
        headers={
            "Host": f"{TENANT_B_SLUG}.ddplanner.io",
            "Authorization": f"Bearer {token_a}",
        },
    )
    assert r.status_code == 401, f"Cross-tenant JWT replay must be 401, got {r.status_code}: {r.text}"


def test_token_b_cannot_reach_tenant_a_host(token_b, tenant_a):
    r = requests.get(
        f"{BACKEND_URL}/api/projects",
        headers={
            "Host": f"{TENANT_A_SLUG}.ddplanner.io",
            "Authorization": f"Bearer {token_b}",
        },
    )
    assert r.status_code == 401


def test_login_with_tenant_a_email_on_tenant_b_host_fails(tenant_a, tenant_b):
    """Tenant A user email doesn't exist in Tenant B DB → 401."""
    r = requests.post(
        f"{BACKEND_URL}/api/auth/login",
        data={"username": TENANT_A_EMAIL, "password": TENANT_A_PWD},
        headers={"Host": f"{TENANT_B_SLUG}.ddplanner.io", "Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 401


# ────────────────────────────────────────────────────────────────────────────
# 2. Data isolation — projects, resources, allocations
# ────────────────────────────────────────────────────────────────────────────

def test_tenant_a_sees_only_welcome_project(token_a):
    r = requests.get(
        f"{BACKEND_URL}/api/projects",
        headers={"Host": f"{TENANT_A_SLUG}.ddplanner.io", "Authorization": f"Bearer {token_a}"},
    )
    assert r.status_code == 200
    projects = r.json()
    assert len(projects) == 1, f"Fresh tenant should have 1 welcome project, got {len(projects)}"
    assert "Welcome to DD Planner" in projects[0]["name"]


def test_project_created_in_a_invisible_to_b(token_a, token_b):
    # Create in A
    create_r = requests.post(
        f"{BACKEND_URL}/api/projects",
        headers={"Host": f"{TENANT_A_SLUG}.ddplanner.io", "Authorization": f"Bearer {token_a}"},
        json={
            "name": f"ISO_TEST_PROJECT_{uuid.uuid4().hex[:6]}",
            "client_name": "Iso Client",
            "status": "Pipeline",
            "start_date": "2026-09-01",
            "end_date": "2026-10-01",
        },
    )
    assert create_r.status_code == 200, f"Create failed: {create_r.text}"
    created_id = create_r.json()["id"]

    # Verify A sees it
    a_list = requests.get(
        f"{BACKEND_URL}/api/projects",
        headers={"Host": f"{TENANT_A_SLUG}.ddplanner.io", "Authorization": f"Bearer {token_a}"},
    ).json()
    assert any(p["id"] == created_id for p in a_list)

    # Verify B does NOT see it
    b_list = requests.get(
        f"{BACKEND_URL}/api/projects",
        headers={"Host": f"{TENANT_B_SLUG}.ddplanner.io", "Authorization": f"Bearer {token_b}"},
    ).json()
    assert not any(p.get("id") == created_id for p in b_list), (
        f"CROSS-TENANT LEAK: project {created_id} created in A visible in B"
    )


def test_direct_id_access_from_wrong_tenant_403_or_404(token_a, token_b):
    """B tries to fetch A's welcome project by ID → should not succeed."""
    a_list = requests.get(
        f"{BACKEND_URL}/api/projects",
        headers={"Host": f"{TENANT_A_SLUG}.ddplanner.io", "Authorization": f"Bearer {token_a}"},
    ).json()
    if not a_list:
        pytest.skip("Tenant A has no projects")
    a_project_id = a_list[0]["id"]
    r = requests.get(
        f"{BACKEND_URL}/api/projects/{a_project_id}",
        headers={"Host": f"{TENANT_B_SLUG}.ddplanner.io", "Authorization": f"Bearer {token_b}"},
    )
    assert r.status_code in (403, 404), (
        f"CROSS-TENANT LEAK: tenant B could access tenant A's project by ID. Got {r.status_code}"
    )


# ────────────────────────────────────────────────────────────────────────────
# 3. Integration isolation — HubSpot config
# ────────────────────────────────────────────────────────────────────────────

def test_hubspot_config_written_to_a_not_visible_in_b(token_a, token_b):
    # Configure HubSpot in A
    put_r = requests.put(
        f"{BACKEND_URL}/api/integrations/settings",
        headers={"Host": f"{TENANT_A_SLUG}.ddplanner.io", "Authorization": f"Bearer {token_a}"},
        json={"hubspot": {"enabled": True, "private_app_token": "TENANT-A-SECRET-TOKEN", "portal_id": "A-PORTAL-99"}},
    )
    assert put_r.status_code == 200, put_r.text

    # A sees it via summary
    a_summary = requests.get(
        f"{BACKEND_URL}/api/tenant/integrations-summary",
        headers={"Host": f"{TENANT_A_SLUG}.ddplanner.io", "Authorization": f"Bearer {token_a}"},
    ).json()
    assert a_summary["hubspot"]["connected"] is True
    assert a_summary["hubspot"]["portal_id"] == "A-PORTAL-99"

    # B sees no HubSpot config
    b_summary = requests.get(
        f"{BACKEND_URL}/api/tenant/integrations-summary",
        headers={"Host": f"{TENANT_B_SLUG}.ddplanner.io", "Authorization": f"Bearer {token_b}"},
    ).json()
    assert b_summary["hubspot"]["connected"] is False, "CROSS-TENANT LEAK: A's HubSpot config visible in B"
    assert b_summary["hubspot"]["portal_id"] is None


def test_integrations_summary_never_exposes_secrets(token_a):
    r = requests.get(
        f"{BACKEND_URL}/api/tenant/integrations-summary",
        headers={"Host": f"{TENANT_A_SLUG}.ddplanner.io", "Authorization": f"Bearer {token_a}"},
    )
    assert r.status_code == 200
    body_str = r.text
    # Fail hard if any known secret string appears
    assert "TENANT-A-SECRET-TOKEN" not in body_str, "SECRET LEAK: token exposed in integrations-summary"
    assert "private_app_token" not in body_str, "FIELD LEAK: private_app_token field should not be in response"


# ────────────────────────────────────────────────────────────────────────────
# 4. Integration isolation — MCP API keys
# ────────────────────────────────────────────────────────────────────────────

def test_mcp_key_generation_creates_distinct_keys(token_a, token_b):
    key_a = requests.post(
        f"{BACKEND_URL}/api/integrations/agent-api/regenerate",
        headers={"Host": f"{TENANT_A_SLUG}.ddplanner.io", "Authorization": f"Bearer {token_a}"},
    ).json().get("api_key")
    key_b = requests.post(
        f"{BACKEND_URL}/api/integrations/agent-api/regenerate",
        headers={"Host": f"{TENANT_B_SLUG}.ddplanner.io", "Authorization": f"Bearer {token_b}"},
    ).json().get("api_key")
    assert key_a and key_b, "Both tenants must have MCP keys"
    assert key_a != key_b, "MCP keys must be distinct across tenants"


def test_mcp_key_from_a_rejected_at_b_endpoint(token_a, token_b):
    key_a = requests.post(
        f"{BACKEND_URL}/api/integrations/agent-api/regenerate",
        headers={"Host": f"{TENANT_A_SLUG}.ddplanner.io", "Authorization": f"Bearer {token_a}"},
    ).json().get("api_key")
    assert key_a

    # Use A's key against B's endpoint → must 401
    r = requests.post(
        f"{BACKEND_URL}/api/mcp",
        headers={
            "Host": f"{TENANT_B_SLUG}.ddplanner.io",
            "X-Agent-Key": key_a,
            "Content-Type": "application/json",
        },
        json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
    )
    assert r.status_code == 401, (
        f"CROSS-TENANT LEAK: A's MCP key accepted on B's endpoint. Got {r.status_code}: {r.text}"
    )


# ────────────────────────────────────────────────────────────────────────────
# 5. Tenant branding isolation
# ────────────────────────────────────────────────────────────────────────────

def test_branding_written_to_a_not_leaked_to_b(token_a, token_b):
    requests.patch(
        f"{BACKEND_URL}/api/tenant/branding",
        headers={"Host": f"{TENANT_A_SLUG}.ddplanner.io", "Authorization": f"Bearer {token_a}"},
        json={"name": "Iso Tenant A — Custom", "primary_color": "#FF00FF", "accent_color": "#00FF00"},
    )
    a = requests.get(
        f"{BACKEND_URL}/api/tenant/branding",
        headers={"Host": f"{TENANT_A_SLUG}.ddplanner.io", "Authorization": f"Bearer {token_a}"},
    ).json()
    assert a["branding"]["primary_color"] == "#FF00FF"
    assert a["name"] == "Iso Tenant A — Custom"

    b = requests.get(
        f"{BACKEND_URL}/api/tenant/branding",
        headers={"Host": f"{TENANT_B_SLUG}.ddplanner.io", "Authorization": f"Bearer {token_b}"},
    ).json()
    assert b["branding"]["primary_color"] != "#FF00FF", "CROSS-TENANT LEAK: A's branding visible in B"
    assert b["name"] != "Iso Tenant A — Custom"


# ────────────────────────────────────────────────────────────────────────────
# 6. Module toggle isolation
# ────────────────────────────────────────────────────────────────────────────

def test_module_toggle_in_a_does_not_affect_b(mongo, tenant_a, tenant_b, token_a, token_b):
    tenant_a_id = mongo["platform_db"].tenants.find_one({"slug": TENANT_A_SLUG})["_id"]
    # Disable 'timesheets' for A only (write directly for test isolation)
    mongo["platform_db"].tenant_modules.update_one(
        {"tenant_id": str(tenant_a_id), "module_key": "timesheets"},
        {"$set": {"enabled": False}},
    )

    # Wait small moment for tenant cache invalidation
    import time; time.sleep(0.5)

    a_modules = requests.get(
        f"{BACKEND_URL}/api/tenant/modules",
        headers={"Host": f"{TENANT_A_SLUG}.ddplanner.io", "Authorization": f"Bearer {token_a}"},
    ).json()
    b_modules = requests.get(
        f"{BACKEND_URL}/api/tenant/modules",
        headers={"Host": f"{TENANT_B_SLUG}.ddplanner.io", "Authorization": f"Bearer {token_b}"},
    ).json()

    assert a_modules["modules"]["timesheets"] is False, "A's timesheets toggle didn't apply"
    assert b_modules["modules"]["timesheets"] is True, "CROSS-TENANT LEAK: A's toggle affected B"

    # Restore
    mongo["platform_db"].tenant_modules.update_one(
        {"tenant_id": str(tenant_a_id), "module_key": "timesheets"},
        {"$set": {"enabled": True}},
    )


# ────────────────────────────────────────────────────────────────────────────
# 7. Platform admin can see across tenants; tenants cannot
# ────────────────────────────────────────────────────────────────────────────

def test_platform_admin_sees_both_tenants():
    r = requests.post(
        f"{BACKEND_URL}/api/platform/auth/login",
        data={"username": "don@ddconsult.tech", "password": "Welcome123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    ptoken = r.json()["access_token"]

    tenants = requests.get(
        f"{BACKEND_URL}/api/platform/tenants",
        headers={"Authorization": f"Bearer {ptoken}"},
    ).json()
    slugs = {t["slug"] for t in tenants}
    assert TENANT_A_SLUG in slugs and TENANT_B_SLUG in slugs, (
        f"Platform admin must see both test tenants. Got: {slugs}"
    )


def test_platform_admin_token_rejected_on_tenant_route():
    """Platform tokens must never be usable on tenant endpoints (Step 5 security)."""
    r = requests.post(
        f"{BACKEND_URL}/api/platform/auth/login",
        data={"username": "don@ddconsult.tech", "password": "Welcome123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    ptoken = r.json()["access_token"]
    r = requests.get(
        f"{BACKEND_URL}/api/projects",
        headers={
            "Host": f"{TENANT_A_SLUG}.ddplanner.io",
            "Authorization": f"Bearer {ptoken}",
        },
    )
    assert r.status_code == 403, f"Platform token on tenant route must 403. Got {r.status_code}: {r.text}"


def test_tenant_admin_cannot_access_platform_endpoints(token_a):
    r = requests.get(
        f"{BACKEND_URL}/api/platform/tenants",
        headers={
            "Host": f"{TENANT_A_SLUG}.ddplanner.io",
            "Authorization": f"Bearer {token_a}",
        },
    )
    assert r.status_code in (401, 403), f"Tenant token on platform endpoint must be blocked. Got {r.status_code}"
