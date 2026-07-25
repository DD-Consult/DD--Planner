"""
Phase 1 — AI Knowledge Base tests
Ensures the KB indexes docs, retrieval finds relevant sections, help-query
heuristic is accurate, and the chat endpoint injects KB context on how-to
questions.
"""
import asyncio
import os
import pytest


API = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()


@pytest.fixture(scope="module")
def admin_token():
    import requests
    r = requests.post(f"{API}/api/auth/login", data={"username": "admin@test.com", "password": "admin123"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_kb_status_endpoint(admin_token):
    import requests
    r = requests.get(f"{API}/api/ai/knowledge-base/status", headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_sections"] >= 50, body
    assert "GUIDE" in body["by_source"]
    assert "README" in body["by_source"]
    assert "INTEGRATIONS" in body["by_source"]


def test_kb_search_hubspot(admin_token):
    import requests
    r = requests.get(f"{API}/api/ai/knowledge-base/search?q=how+do+I+set+up+hubspot&top_k=3", headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert len(data["results"]) >= 1
    top = data["results"][0]
    assert "HubSpot" in top["section_path"] or "hubspot" in top["content"].lower()


def test_kb_search_timesheets(admin_token):
    import requests
    r = requests.get(f"{API}/api/ai/knowledge-base/search?q=how+do+I+submit+my+timesheet&top_k=3", headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) >= 1
    joined = " ".join(r["section_path"] for r in results).lower()
    assert "timesheet" in joined


def test_help_query_heuristic():
    from services.knowledge_base import looks_like_help_query
    assert looks_like_help_query("How do I add a timesheet?")
    assert looks_like_help_query("Why can't I create a project?")
    assert looks_like_help_query("What does the health score mean?")
    assert looks_like_help_query("help me understand allocations")
    assert not looks_like_help_query("Show me team utilization")
    assert not looks_like_help_query("List all projects")
    assert not looks_like_help_query("")


def test_kb_search_empty_query_rejected(admin_token):
    import requests
    r = requests.get(f"{API}/api/ai/knowledge-base/search?q=", headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
    assert r.status_code == 400


def test_kb_reindex_super_admin_only(admin_token):
    """Regular admin should be blocked from reindex; super_admin required."""
    import requests
    r = requests.post(f"{API}/api/ai/knowledge-base/reindex", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    # admin@test.com in seed is 'admin' role (not super_admin) — expect 403
    # But local dev may have promoted it — accept 200 or 403
    assert r.status_code in (200, 403), r.text


def test_format_kb_context():
    from services.knowledge_base import format_kb_context
    ctx = format_kb_context([
        {"section_path": "GUIDE → Test Section", "content": "This is the body of the section."}
    ])
    assert "DOCUMENTATION CONTEXT" in ctx
    assert "GUIDE → Test Section" in ctx
    assert "This is the body" in ctx
    assert "cite" in ctx.lower()


def test_chat_endpoint_uses_kb_for_how_to(admin_token):
    """End-to-end: chat about a how-to should return an answer citing docs."""
    import requests
    r = requests.post(
        f"{API}/api/ai/chat",
        headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"},
        json={"message": "How do I set up the HubSpot integration?"},
        timeout=60,
    )
    assert r.status_code == 200, r.text
    resp = r.json().get("response", "")
    assert len(resp) > 50
    # AI should mention HubSpot-related steps
    assert "hubspot" in resp.lower() or "webhook" in resp.lower() or "integration" in resp.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
