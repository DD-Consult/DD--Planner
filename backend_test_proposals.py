#!/usr/bin/env python3
"""
Comprehensive Backend Test for Secure AI-Guided Proposal Module
Tests all 12 steps of the proposal lifecycle as specified in the review request.
"""
import requests
import json
import time
from datetime import datetime

# Backend URL from frontend/.env
BACKEND_URL = "https://proposal-approve.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"

# Admin credentials from review request
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

# Test results tracking
test_results = []
proposal_id = None
proposal_token = None
project_id = None


def log_test(step, name, passed, details=""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    result = {
        "step": step,
        "name": name,
        "status": status,
        "passed": passed,
        "details": details
    }
    test_results.append(result)
    print(f"\n{status} | Step {step}: {name}")
    if details:
        print(f"  Details: {details}")
    return passed


def print_summary():
    """Print test summary table"""
    print("\n" + "="*80)
    print("TEST SUMMARY - Secure AI-Guided Proposal Module")
    print("="*80)
    
    passed_count = sum(1 for r in test_results if r["passed"])
    total_count = len(test_results)
    
    print(f"\nTotal: {passed_count}/{total_count} tests passed\n")
    
    for result in test_results:
        print(f"{result['status']} | Step {result['step']}: {result['name']}")
        if result['details'] and not result['passed']:
            print(f"  └─ {result['details']}")
    
    print("\n" + "="*80)
    return passed_count, total_count


def test_step_1_create_proposal(token):
    """Step 1: CREATE proposal"""
    print("\n" + "="*80)
    print("STEP 1: CREATE PROPOSAL")
    print("="*80)
    
    global proposal_id, proposal_token
    
    url = f"{API_BASE}/proposals"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "client_name": "Meridian Health Group",
        "proposal_title": "Care Operations Modernisation"
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code != 200:
            return log_test("1", "CREATE proposal", False, 
                          f"Expected 200, got {response.status_code}: {response.text[:200]}")
        
        data = response.json()
        
        # Check required fields
        if "id" not in data:
            return log_test("1", "CREATE proposal", False, "Missing 'id' field")
        
        if "token" not in data or not data["token"]:
            return log_test("1", "CREATE proposal", False, "Missing or empty 'token' field")
        
        if data.get("status") != "Draft":
            return log_test("1", "CREATE proposal", False, 
                          f"Expected status='Draft', got '{data.get('status')}'")
        
        # Check data field with v4 sample structure
        if "data" not in data:
            return log_test("1", "CREATE proposal", False, "Missing 'data' field")
        
        proposal_data = data["data"]
        
        # Check client_name was set
        if proposal_data.get("client_name") != "Meridian Health Group":
            return log_test("1", "CREATE proposal", False, 
                          f"Expected client_name='Meridian Health Group', got '{proposal_data.get('client_name')}'")
        
        # Check options has 3 entries with paths a/b/c
        options = proposal_data.get("options", [])
        if len(options) != 3:
            return log_test("1", "CREATE proposal", False, 
                          f"Expected 3 options, got {len(options)}")
        
        paths = {opt.get("path") for opt in options}
        if paths != {"a", "b", "c"}:
            return log_test("1", "CREATE proposal", False, 
                          f"Expected paths a/b/c, got {paths}")
        
        # Check pricing_model exists
        if "pricing_model" not in proposal_data:
            return log_test("1", "CREATE proposal", False, "Missing 'pricing_model' in data")
        
        # Save for later steps
        proposal_id = data["id"]
        proposal_token = data["token"]
        
        return log_test("1", "CREATE proposal", True, 
                       f"Created proposal {proposal_id} with token {proposal_token[:16]}...")
        
    except Exception as e:
        return log_test("1", "CREATE proposal", False, f"Exception: {str(e)}")


def test_step_2_get_list(token):
    """Step 2: GET LIST of proposals"""
    print("\n" + "="*80)
    print("STEP 2: GET LIST")
    print("="*80)
    
    url = f"{API_BASE}/proposals"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return log_test("2", "GET LIST", False, 
                          f"Expected 200, got {response.status_code}: {response.text[:200]}")
        
        data = response.json()
        
        if not isinstance(data, list):
            return log_test("2", "GET LIST", False, "Expected array response")
        
        # Find our created proposal
        found = False
        for prop in data:
            if prop.get("id") == proposal_id:
                found = True
                if prop.get("client_name") != "Meridian Health Group":
                    return log_test("2", "GET LIST", False, 
                                  f"Wrong client_name: {prop.get('client_name')}")
                if prop.get("status") != "Draft":
                    return log_test("2", "GET LIST", False, 
                                  f"Wrong status: {prop.get('status')}")
                break
        
        if not found:
            return log_test("2", "GET LIST", False, 
                          f"Created proposal {proposal_id} not found in list")
        
        return log_test("2", "GET LIST", True, 
                       f"Found proposal in list with {len(data)} total proposals")
        
    except Exception as e:
        return log_test("2", "GET LIST", False, f"Exception: {str(e)}")


def test_step_3_get_one(token):
    """Step 3: GET ONE proposal"""
    print("\n" + "="*80)
    print("STEP 3: GET ONE")
    print("="*80)
    
    url = f"{API_BASE}/proposals/{proposal_id}"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return log_test("3", "GET ONE", False, 
                          f"Expected 200, got {response.status_code}: {response.text[:200]}")
        
        data = response.json()
        
        if data.get("id") != proposal_id:
            return log_test("3", "GET ONE", False, "Wrong proposal ID")
        
        if "data" not in data:
            return log_test("3", "GET ONE", False, "Missing full 'data' field")
        
        proposal_data = data["data"]
        
        # Verify full data structure
        if "options" not in proposal_data:
            return log_test("3", "GET ONE", False, "Missing 'options' in data")
        
        if "pricing_model" not in proposal_data:
            return log_test("3", "GET ONE", False, "Missing 'pricing_model' in data")
        
        return log_test("3", "GET ONE", True, 
                       f"Retrieved full proposal with complete data structure")
        
    except Exception as e:
        return log_test("3", "GET ONE", False, f"Exception: {str(e)}")


def test_step_4_update(token):
    """Step 4: UPDATE proposal"""
    print("\n" + "="*80)
    print("STEP 4: UPDATE")
    print("="*80)
    
    # First, get current data
    url = f"{API_BASE}/proposals/{proposal_id}"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            return log_test("4", "UPDATE", False, "Failed to get current data")
        
        current_data = response.json()["data"]
        
        # Modify client_name
        current_data["client_name"] = "Meridian Health (Edited)"
        
        # Update
        update_url = f"{API_BASE}/proposals/{proposal_id}"
        update_payload = {"data": current_data}
        
        response = requests.put(update_url, headers=headers, json=update_payload, timeout=30)
        
        if response.status_code != 200:
            return log_test("4", "UPDATE", False, 
                          f"Expected 200, got {response.status_code}: {response.text[:200]}")
        
        # Verify persistence
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            return log_test("4", "UPDATE", False, "Failed to verify update")
        
        updated_data = response.json()["data"]
        
        if updated_data.get("client_name") != "Meridian Health (Edited)":
            return log_test("4", "UPDATE", False, 
                          f"Update not persisted. Got: {updated_data.get('client_name')}")
        
        return log_test("4", "UPDATE", True, 
                       "Successfully updated and verified client_name persistence")
        
    except Exception as e:
        return log_test("4", "UPDATE", False, f"Exception: {str(e)}")


def test_step_5_ai_draft(token):
    """Step 5: AI DRAFT (allow up to 60s, report WARN not hard-fail on timeout)"""
    print("\n" + "="*80)
    print("STEP 5: AI DRAFT (may take up to 60s)")
    print("="*80)
    
    url = f"{API_BASE}/proposals/{proposal_id}/ai-draft"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "message": "The client is Meridian Health Group, an aged care provider in NSW. They have 4 disconnected systems and manual compliance reporting. Recommend Path A discovery first."
    }
    
    try:
        start_time = time.time()
        response = requests.post(url, headers=headers, json=payload, timeout=65)
        elapsed = time.time() - start_time
        
        if response.status_code != 200:
            return log_test("5", "AI DRAFT", False, 
                          f"Expected 200, got {response.status_code}: {response.text[:200]}")
        
        data = response.json()
        
        # Check required keys
        if "assistant_message" not in data:
            return log_test("5", "AI DRAFT", False, "Missing 'assistant_message' key")
        
        if "data" not in data:
            return log_test("5", "AI DRAFT", False, "Missing 'data' key")
        
        assistant_msg = data["assistant_message"]
        
        # Check if it's a parse failure or timeout message
        if "couldn't parse" in assistant_msg.lower() or "unable to process" in assistant_msg.lower():
            return log_test("5", "AI DRAFT", True, 
                          f"⚠️  WARN: AI returned parse-failure message (not hard-fail): {assistant_msg[:100]}")
        
        # Check data structure
        proposal_data = data["data"]
        if "options" not in proposal_data:
            return log_test("5", "AI DRAFT", False, "Missing 'options' in returned data")
        
        options = proposal_data.get("options", [])
        paths = {opt.get("path") for opt in options}
        if paths != {"a", "b", "c"}:
            return log_test("5", "AI DRAFT", False, 
                          f"Options paths changed. Expected a/b/c, got {paths}")
        
        # Verify persistence
        verify_url = f"{API_BASE}/proposals/{proposal_id}"
        verify_response = requests.get(verify_url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
        
        if verify_response.status_code != 200:
            return log_test("5", "AI DRAFT", False, "Failed to verify persistence")
        
        persisted_data = verify_response.json()["data"]
        
        # Check if the AI changes were persisted (client_name should still be edited value or updated)
        if "client_name" not in persisted_data:
            return log_test("5", "AI DRAFT", False, "Persisted data missing client_name")
        
        return log_test("5", "AI DRAFT", True, 
                       f"AI draft completed in {elapsed:.1f}s. Assistant message: {assistant_msg[:80]}...")
        
    except requests.exceptions.Timeout:
        return log_test("5", "AI DRAFT", True, 
                       "⚠️  WARN: Request timed out after 65s (not hard-fail as per spec)")
    except Exception as e:
        return log_test("5", "AI DRAFT", False, f"Exception: {str(e)}")


def test_step_6_preview(token):
    """Step 6: PREVIEW"""
    print("\n" + "="*80)
    print("STEP 6: PREVIEW")
    print("="*80)
    
    url = f"{API_BASE}/proposals/{proposal_id}/preview"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.post(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return log_test("6", "PREVIEW", False, 
                          f"Expected 200, got {response.status_code}: {response.text[:200]}")
        
        # Check Content-Type
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type:
            return log_test("6", "PREVIEW", False, 
                          f"Expected text/html, got {content_type}")
        
        html = response.text
        
        # Check length
        if len(html) < 10000:
            return log_test("6", "PREVIEW", False, 
                          f"HTML too short: {len(html)} chars (expected > 10000)")
        
        # Check for client name
        if "Meridian Health" not in html:
            return log_test("6", "PREVIEW", False, 
                          "Client name not found in HTML")
        
        # Check for noindex
        if "noindex" not in html.lower():
            return log_test("6", "PREVIEW", False, 
                          "Missing 'noindex' in HTML")
        
        return log_test("6", "PREVIEW", True, 
                       f"Generated {len(html):,} char HTML with noindex and client name")
        
    except Exception as e:
        return log_test("6", "PREVIEW", False, f"Exception: {str(e)}")


def test_step_7_send(token):
    """Step 7: SEND"""
    print("\n" + "="*80)
    print("STEP 7: SEND")
    print("="*80)
    
    url = f"{API_BASE}/proposals/{proposal_id}/send"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.post(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return log_test("7", "SEND", False, 
                          f"Expected 200, got {response.status_code}: {response.text[:200]}")
        
        data = response.json()
        
        # Check required fields
        if "proposal_link" not in data:
            return log_test("7", "SEND", False, "Missing 'proposal_link' field")
        
        if "email_sent" not in data or not isinstance(data["email_sent"], bool):
            return log_test("7", "SEND", False, "Missing or invalid 'email_sent' field")
        
        proposal_link = data["proposal_link"]
        
        # Check link format
        if "/proposal/" not in proposal_link:
            return log_test("7", "SEND", False, 
                          f"Invalid proposal_link format: {proposal_link}")
        
        # Verify status changed to Sent
        verify_url = f"{API_BASE}/proposals/{proposal_id}"
        verify_response = requests.get(verify_url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
        
        if verify_response.status_code != 200:
            return log_test("7", "SEND", False, "Failed to verify status change")
        
        status = verify_response.json().get("status")
        if status != "Sent":
            return log_test("7", "SEND", False, 
                          f"Expected status='Sent', got '{status}'")
        
        return log_test("7", "SEND", True, 
                       f"Sent proposal. Link: {proposal_link}, Email sent: {data['email_sent']}")
        
    except Exception as e:
        return log_test("7", "SEND", False, f"Exception: {str(e)}")


def test_step_8_public_view():
    """Step 8: PUBLIC VIEW (NO AUTH)"""
    print("\n" + "="*80)
    print("STEP 8: PUBLIC VIEW (NO AUTH)")
    print("="*80)
    
    # First, public view
    url = f"{API_BASE}/proposals/public/{proposal_token}"
    
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code != 200:
            return log_test("8", "PUBLIC VIEW", False, 
                          f"Expected 200, got {response.status_code}: {response.text[:200]}")
        
        # Check Content-Type
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type:
            return log_test("8", "PUBLIC VIEW", False, 
                          f"Expected text/html, got {content_type}")
        
        html = response.text
        
        # Check length
        if len(html) < 10000:
            return log_test("8", "PUBLIC VIEW", False, 
                          f"HTML too short: {len(html)} chars")
        
        # Now verify status changed to Viewed (need admin auth)
        admin_token = get_admin_token()
        if not admin_token:
            return log_test("8", "PUBLIC VIEW", False, "Failed to get admin token for verification")
        
        verify_url = f"{API_BASE}/proposals/{proposal_id}"
        verify_response = requests.get(verify_url, 
                                      headers={"Authorization": f"Bearer {admin_token}"}, 
                                      timeout=30)
        
        if verify_response.status_code != 200:
            return log_test("8", "PUBLIC VIEW", False, "Failed to verify status change")
        
        status = verify_response.json().get("status")
        if status != "Viewed":
            return log_test("8", "PUBLIC VIEW", False, 
                          f"Expected status='Viewed', got '{status}'")
        
        return log_test("8", "PUBLIC VIEW", True, 
                       f"Public view successful. Status changed to 'Viewed'. HTML: {len(html):,} chars")
        
    except Exception as e:
        return log_test("8", "PUBLIC VIEW", False, f"Exception: {str(e)}")


def test_step_9_public_track():
    """Step 9: PUBLIC TRACK (NO AUTH)"""
    print("\n" + "="*80)
    print("STEP 9: PUBLIC TRACK (NO AUTH)")
    print("="*80)
    
    url = f"{API_BASE}/proposals/public/{proposal_token}/track"
    
    try:
        # Track option_interest
        payload1 = {
            "type": "option_interest",
            "path": "b",
            "at": "2026-01-01T00:00:00Z"
        }
        
        response1 = requests.post(url, json=payload1, timeout=30)
        
        if response1.status_code != 200:
            return log_test("9", "PUBLIC TRACK", False, 
                          f"Track option_interest failed: {response1.status_code}: {response1.text[:200]}")
        
        data1 = response1.json()
        if not data1.get("ok"):
            return log_test("9", "PUBLIC TRACK", False, 
                          f"Track option_interest returned ok=false: {data1}")
        
        # Track accepted
        payload2 = {
            "type": "accepted",
            "accepted_by": "Jane Doe, COO",
            "accepted_path": "a",
            "at": "2026-01-01T00:00:00Z"
        }
        
        response2 = requests.post(url, json=payload2, timeout=30)
        
        if response2.status_code != 200:
            return log_test("9", "PUBLIC TRACK", False, 
                          f"Track accepted failed: {response2.status_code}: {response2.text[:200]}")
        
        data2 = response2.json()
        if not data2.get("ok"):
            return log_test("9", "PUBLIC TRACK", False, 
                          f"Track accepted returned ok=false: {data2}")
        
        # Verify status changed to Accepted
        admin_token = get_admin_token()
        if not admin_token:
            return log_test("9", "PUBLIC TRACK", False, "Failed to get admin token for verification")
        
        verify_url = f"{API_BASE}/proposals/{proposal_id}"
        verify_response = requests.get(verify_url, 
                                      headers={"Authorization": f"Bearer {admin_token}"}, 
                                      timeout=30)
        
        if verify_response.status_code != 200:
            return log_test("9", "PUBLIC TRACK", False, "Failed to verify status change")
        
        proposal = verify_response.json()
        
        if proposal.get("status") != "Accepted":
            return log_test("9", "PUBLIC TRACK", False, 
                          f"Expected status='Accepted', got '{proposal.get('status')}'")
        
        if proposal.get("accepted_by") != "Jane Doe, COO":
            return log_test("9", "PUBLIC TRACK", False, 
                          f"Expected accepted_by='Jane Doe, COO', got '{proposal.get('accepted_by')}'")
        
        if proposal.get("accepted_path") != "a":
            return log_test("9", "PUBLIC TRACK", False, 
                          f"Expected accepted_path='a', got '{proposal.get('accepted_path')}'")
        
        return log_test("9", "PUBLIC TRACK", True, 
                       "Tracked option_interest (path b) and accepted (path a). Status changed to 'Accepted'")
        
    except Exception as e:
        return log_test("9", "PUBLIC TRACK", False, f"Exception: {str(e)}")


def test_step_10_events(token):
    """Step 10: EVENTS"""
    print("\n" + "="*80)
    print("STEP 10: EVENTS")
    print("="*80)
    
    url = f"{API_BASE}/proposals/{proposal_id}/events"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return log_test("10", "EVENTS", False, 
                          f"Expected 200, got {response.status_code}: {response.text[:200]}")
        
        data = response.json()
        
        # Check required fields
        if "events" not in data:
            return log_test("10", "EVENTS", False, "Missing 'events' field")
        
        if "summary" not in data:
            return log_test("10", "EVENTS", False, "Missing 'summary' field")
        
        events = data["events"]
        summary = data["summary"]
        
        if not isinstance(events, list):
            return log_test("10", "EVENTS", False, "Events is not an array")
        
        # Check summary fields
        if "opened" not in summary:
            return log_test("10", "EVENTS", False, "Missing 'opened' in summary")
        
        if "accepted" not in summary:
            return log_test("10", "EVENTS", False, "Missing 'accepted' in summary")
        
        # Check interested_path
        if summary.get("interested_path") != "b":
            return log_test("10", "EVENTS", False, 
                          f"Expected interested_path='b', got '{summary.get('interested_path')}'")
        
        return log_test("10", "EVENTS", True, 
                       f"Retrieved {len(events)} events. Summary shows interested_path='b', accepted={summary.get('accepted')}")
        
    except Exception as e:
        return log_test("10", "EVENTS", False, f"Exception: {str(e)}")


def test_step_11_confirm(token):
    """Step 11: CONFIRM (auto-provision)"""
    print("\n" + "="*80)
    print("STEP 11: CONFIRM (AUTO-PROVISION)")
    print("="*80)
    
    global project_id
    
    url = f"{API_BASE}/proposals/{proposal_id}/confirm"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.post(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return log_test("11", "CONFIRM", False, 
                          f"Expected 200, got {response.status_code}: {response.text[:500]}")
        
        data = response.json()
        
        # Check required fields
        if "project_id" not in data:
            return log_test("11", "CONFIRM", False, "Missing 'project_id' field")
        
        if "client_user_id" not in data:
            return log_test("11", "CONFIRM", False, "Missing 'client_user_id' field")
        
        if "report_link" not in data:
            return log_test("11", "CONFIRM", False, "Missing 'report_link' field")
        
        if "magic_link_sent" not in data or not isinstance(data["magic_link_sent"], bool):
            return log_test("11", "CONFIRM", False, "Missing or invalid 'magic_link_sent' field")
        
        project_id = data["project_id"]
        client_user_id = data["client_user_id"]
        report_link = data["report_link"]
        
        # Check report_link format
        if "/portal/" not in report_link:
            return log_test("11", "CONFIRM", False, 
                          f"Invalid report_link format: {report_link}")
        
        # Verify proposal status changed to Confirmed
        verify_url = f"{API_BASE}/proposals/{proposal_id}"
        verify_response = requests.get(verify_url, headers=headers, timeout=30)
        
        if verify_response.status_code != 200:
            return log_test("11", "CONFIRM", False, "Failed to verify proposal status")
        
        proposal = verify_response.json()
        
        if proposal.get("status") != "Confirmed":
            return log_test("11", "CONFIRM", False, 
                          f"Expected status='Confirmed', got '{proposal.get('status')}'")
        
        if proposal.get("linked_project_id") != project_id:
            return log_test("11", "CONFIRM", False, 
                          f"linked_project_id mismatch: {proposal.get('linked_project_id')} != {project_id}")
        
        # Verify project was created
        project_url = f"{API_BASE}/projects/{project_id}"
        project_response = requests.get(project_url, headers=headers, timeout=30)
        
        if project_response.status_code != 200:
            return log_test("11", "CONFIRM", False, 
                          f"Failed to get created project: {project_response.status_code}")
        
        project = project_response.json()
        
        if "client_name" not in project:
            return log_test("11", "CONFIRM", False, "Created project missing client_name")
        
        if "phases" not in project:
            return log_test("11", "CONFIRM", False, "Created project missing phases")
        
        # Verify client user was created/updated
        # Get proposal data to find contact_email
        proposal_data = proposal.get("data", {})
        contact_email = proposal_data.get("contact_email")
        
        if not contact_email:
            return log_test("11", "CONFIRM", False, "No contact_email in proposal data")
        
        # Get all clients to find the one with this email
        clients_url = f"{API_BASE}/admin/clients"
        clients_response = requests.get(clients_url, headers=headers, timeout=30)
        
        if clients_response.status_code != 200:
            return log_test("11", "CONFIRM", False, 
                          f"Failed to get clients list: {clients_response.status_code}")
        
        clients = clients_response.json()
        client_found = False
        
        for client in clients:
            if client.get("email") == contact_email:
                client_found = True
                allowed_projects = client.get("allowed_project_ids", [])
                if project_id not in allowed_projects:
                    return log_test("11", "CONFIRM", False, 
                                  f"Project {project_id} not in client's allowed_project_ids")
                break
        
        if not client_found:
            return log_test("11", "CONFIRM", False, 
                          f"Client user with email {contact_email} not found")
        
        return log_test("11", "CONFIRM", True, 
                       f"Auto-provisioned: project {project_id}, client {client_user_id}, report link created")
        
    except Exception as e:
        return log_test("11", "CONFIRM", False, f"Exception: {str(e)}")


def test_step_12_negative_checks(token):
    """Step 12: NEGATIVE/GUARD CHECKS"""
    print("\n" + "="*80)
    print("STEP 12: NEGATIVE/GUARD CHECKS")
    print("="*80)
    
    all_passed = True
    
    # Check 1: GET public with bad token -> 404
    try:
        bad_token = "random-bad-token-12345"
        url = f"{API_BASE}/proposals/public/{bad_token}"
        response = requests.get(url, timeout=30)
        
        if response.status_code != 404:
            log_test("12a", "Bad token -> 404", False, 
                    f"Expected 404, got {response.status_code}")
            all_passed = False
        else:
            log_test("12a", "Bad token -> 404", True, "Correctly returned 404")
    except Exception as e:
        log_test("12a", "Bad token -> 404", False, f"Exception: {str(e)}")
        all_passed = False
    
    # Check 2: DELETE confirmed proposal -> 400
    try:
        url = f"{API_BASE}/proposals/{proposal_id}"
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.delete(url, headers=headers, timeout=30)
        
        if response.status_code != 400:
            log_test("12b", "DELETE Confirmed -> 400", False, 
                    f"Expected 400, got {response.status_code}")
            all_passed = False
        else:
            log_test("12b", "DELETE Confirmed -> 400", True, "Correctly returned 400")
    except Exception as e:
        log_test("12b", "DELETE Confirmed -> 400", False, f"Exception: {str(e)}")
        all_passed = False
    
    # Check 3: Create and DELETE Draft proposal -> 200
    try:
        # Create a new Draft proposal
        create_url = f"{API_BASE}/proposals"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "client_name": "Test Client for Delete",
            "proposal_title": "Test Proposal"
        }
        
        create_response = requests.post(create_url, headers=headers, json=payload, timeout=30)
        
        if create_response.status_code != 200:
            log_test("12c", "DELETE Draft -> 200", False, 
                    f"Failed to create test proposal: {create_response.status_code}")
            all_passed = False
        else:
            draft_id = create_response.json()["id"]
            
            # Delete it
            delete_url = f"{API_BASE}/proposals/{draft_id}"
            delete_response = requests.delete(delete_url, headers=headers, timeout=30)
            
            if delete_response.status_code != 200:
                log_test("12c", "DELETE Draft -> 200", False, 
                        f"Expected 200, got {delete_response.status_code}")
                all_passed = False
            else:
                log_test("12c", "DELETE Draft -> 200", True, "Successfully deleted Draft proposal")
    except Exception as e:
        log_test("12c", "DELETE Draft -> 200", False, f"Exception: {str(e)}")
        all_passed = False
    
    return all_passed


def get_admin_token():
    """Get admin JWT token"""
    url = f"{API_BASE}/auth/login"
    
    # Try form-encoded first (OAuth2PasswordRequestForm)
    data = {
        "username": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    }
    
    try:
        response = requests.post(url, data=data, timeout=30)
        
        if response.status_code == 200:
            return response.json()["access_token"]
        
        # Try JSON format
        headers = {"Content-Type": "application/json"}
        json_data = {
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        }
        
        response = requests.post(url, headers=headers, json=json_data, timeout=30)
        
        if response.status_code == 200:
            return response.json()["access_token"]
        
        print(f"❌ Failed to authenticate: {response.status_code}: {response.text[:200]}")
        return None
        
    except Exception as e:
        print(f"❌ Authentication exception: {str(e)}")
        return None


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("SECURE AI-GUIDED PROPOSAL MODULE - COMPREHENSIVE BACKEND TEST")
    print("="*80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Admin: {ADMIN_EMAIL}")
    print(f"Test started: {datetime.now().isoformat()}")
    
    # Authenticate
    print("\n" + "="*80)
    print("AUTHENTICATION")
    print("="*80)
    
    token = get_admin_token()
    if not token:
        print("\n❌ FATAL: Failed to authenticate. Cannot proceed with tests.")
        return
    
    print(f"✅ Authenticated successfully. Token: {token[:20]}...")
    
    # Run all test steps
    test_step_1_create_proposal(token)
    
    if proposal_id:
        test_step_2_get_list(token)
        test_step_3_get_one(token)
        test_step_4_update(token)
        test_step_5_ai_draft(token)
        test_step_6_preview(token)
        test_step_7_send(token)
        test_step_8_public_view()
        test_step_9_public_track()
        test_step_10_events(token)
        test_step_11_confirm(token)
        test_step_12_negative_checks(token)
    else:
        print("\n❌ FATAL: Failed to create proposal. Skipping remaining tests.")
    
    # Print summary
    passed, total = print_summary()
    
    print(f"\nTest completed: {datetime.now().isoformat()}")
    print(f"Result: {passed}/{total} tests passed ({passed*100//total}%)")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! 🎉")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")


if __name__ == "__main__":
    main()
