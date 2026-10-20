#!/usr/bin/env python3
"""
Backend Test: Create Proposal from Existing Project (Phase 2a)

Tests the NEW POST /api/proposals/from-project endpoint that creates a proposal
pre-filled from an existing DD project.

Test credentials: admin@test.com / admin123 (super admin)
Backend URL: https://proposal-approve.preview.emergentagent.com
"""

import requests
import json
import time
from datetime import datetime

# Configuration
BASE_URL = "https://proposal-approve.preview.emergentagent.com"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

# Test results tracking
test_results = {
    "total": 0,
    "passed": 0,
    "failed": 0,
    "details": []
}

def log_test(test_name, passed, message=""):
    """Log test result"""
    test_results["total"] += 1
    if passed:
        test_results["passed"] += 1
        status = "✅ PASS"
    else:
        test_results["failed"] += 1
        status = "❌ FAIL"
    
    result = f"{status}: {test_name}"
    if message:
        result += f" - {message}"
    
    test_results["details"].append(result)
    print(result)
    return passed

def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {test_results['total']}")
    print(f"Passed: {test_results['passed']} ✅")
    print(f"Failed: {test_results['failed']} ❌")
    print(f"Success Rate: {(test_results['passed']/test_results['total']*100):.1f}%")
    print("="*80)
    print("\nDetailed Results:")
    for detail in test_results["details"]:
        print(detail)
    print("="*80)

def main():
    print("="*80)
    print("BACKEND TEST: Create Proposal from Existing Project (Phase 2a)")
    print("="*80)
    print(f"Backend URL: {BASE_URL}")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # STEP 1: Login as admin and get JWT token
    print("\n[STEP 1] Login as admin and get JWT token")
    print("-" * 80)
    
    try:
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={
                "username": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        log_test(
            "Admin login",
            login_response.status_code == 200,
            f"Status: {login_response.status_code}"
        )
        
        if login_response.status_code != 200:
            print(f"❌ Login failed: {login_response.text}")
            print_summary()
            return
        
        login_data = login_response.json()
        token = login_data.get("access_token")
        
        log_test(
            "JWT token received",
            token is not None,
            f"Token length: {len(token) if token else 0}"
        )
        
        if not token:
            print("❌ No access token received")
            print_summary()
            return
        
        headers = {"Authorization": f"Bearer {token}"}
        print(f"✅ Authenticated as: {login_data.get('email')} (role: {login_data.get('role')})")
        
    except Exception as e:
        log_test("Admin login", False, f"Exception: {str(e)}")
        print_summary()
        return
    
    # STEP 2: GET /api/projects?scope=all to pick a project
    print("\n[STEP 2] GET /api/projects?scope=all to pick a project")
    print("-" * 80)
    
    try:
        projects_response = requests.get(
            f"{BASE_URL}/api/projects?scope=all",
            headers=headers
        )
        
        log_test(
            "GET /api/projects?scope=all",
            projects_response.status_code == 200,
            f"Status: {projects_response.status_code}"
        )
        
        if projects_response.status_code != 200:
            print(f"❌ Failed to get projects: {projects_response.text}")
            print_summary()
            return
        
        projects = projects_response.json()
        
        log_test(
            "Projects list is not empty",
            len(projects) > 0,
            f"Found {len(projects)} projects"
        )
        
        if len(projects) == 0:
            print("❌ No projects found")
            print_summary()
            return
        
        # Pick the first project
        project = projects[0]
        project_id = project.get("id")
        project_name = project.get("name", "Unknown")
        client_name = project.get("client_name", "Unknown")
        
        log_test(
            "Project has required fields",
            project_id is not None and project_name and client_name,
            f"ID: {project_id}, Name: {project_name}, Client: {client_name}"
        )
        
        print(f"✅ Selected project: '{project_name}' (Client: {client_name}, ID: {project_id})")
        
        # Verify it's a real project (not dummy data)
        log_test(
            "Project has real-looking data",
            "test" not in project_name.lower() and "test" not in client_name.lower(),
            f"Name: {project_name}, Client: {client_name}"
        )
        
    except Exception as e:
        log_test("GET /api/projects", False, f"Exception: {str(e)}")
        print_summary()
        return
    
    # STEP 3: POST /api/proposals/from-project with use_ai=true
    print("\n[STEP 3] POST /api/proposals/from-project with use_ai=true")
    print("-" * 80)
    
    try:
        print(f"Creating proposal from project {project_id} with AI polish...")
        print("⏳ This may take up to ~70 seconds (LLM call)...")
        
        start_time = time.time()
        
        create_response = requests.post(
            f"{BASE_URL}/api/proposals/from-project",
            headers={**headers, "Content-Type": "application/json"},
            json={
                "project_id": project_id,
                "use_ai": True
            },
            timeout=90  # Allow up to 90 seconds
        )
        
        elapsed_time = time.time() - start_time
        
        log_test(
            "POST /api/proposals/from-project (with AI)",
            create_response.status_code == 200,
            f"Status: {create_response.status_code}, Time: {elapsed_time:.1f}s"
        )
        
        if create_response.status_code != 200:
            print(f"❌ Failed to create proposal: {create_response.text}")
            print_summary()
            return
        
        proposal = create_response.json()
        proposal_id = proposal.get("id")
        proposal_token = proposal.get("token")
        proposal_status = proposal.get("status")
        proposal_data = proposal.get("data", {})
        assistant_message = proposal.get("assistant_message", "")
        warnings = proposal.get("warnings", [])
        linked_project_id = proposal.get("linked_project_id")
        source = proposal.get("source", {})
        
        print(f"✅ Proposal created: ID={proposal_id}, Token={proposal_token[:20]}...")
        print(f"   Status: {proposal_status}")
        print(f"   Assistant message: {assistant_message[:100]}...")
        print(f"   Warnings: {len(warnings)}")
        print(f"   Linked project: {linked_project_id}")
        print(f"   Source: {source}")
        
        # CRITICAL ASSERTIONS on the returned proposal
        log_test(
            "Proposal has id",
            proposal_id is not None,
            f"ID: {proposal_id}"
        )
        
        log_test(
            "Proposal has token",
            proposal_token is not None and len(proposal_token) > 20,
            f"Token length: {len(proposal_token) if proposal_token else 0}"
        )
        
        log_test(
            "Proposal status is Draft",
            proposal_status == "Draft",
            f"Status: {proposal_status}"
        )
        
        log_test(
            "Proposal has data object",
            isinstance(proposal_data, dict) and len(proposal_data) > 0,
            f"Data keys: {len(proposal_data)}"
        )
        
        log_test(
            "Proposal has assistant_message",
            isinstance(assistant_message, str) and len(assistant_message) > 0,
            f"Message length: {len(assistant_message)}"
        )
        
        log_test(
            "Proposal has warnings array",
            isinstance(warnings, list),
            f"Warnings count: {len(warnings)}"
        )
        
        log_test(
            "Proposal linked_project_id matches",
            linked_project_id == project_id,
            f"Expected: {project_id}, Got: {linked_project_id}"
        )
        
        log_test(
            "Proposal source.type is 'project'",
            source.get("type") == "project",
            f"Source type: {source.get('type')}"
        )
        
        # CRITICAL assertions on the returned data
        data_client_name = proposal_data.get("client_name", "")
        data_proposal_title = proposal_data.get("proposal_title", "")
        data_options = proposal_data.get("options", [])
        data_pricing_model = proposal_data.get("pricing_model", {})
        data_success = proposal_data.get("success", {})
        data_team = proposal_data.get("team", [])
        
        log_test(
            "data.client_name matches or derived from project",
            client_name.lower() in data_client_name.lower() or data_client_name.lower() in client_name.lower(),
            f"Project client: '{client_name}', Data client: '{data_client_name}'"
        )
        
        log_test(
            "data.proposal_title relates to project name",
            project_name.lower() in data_proposal_title.lower() or 
            any(word.lower() in data_proposal_title.lower() for word in project_name.split() if len(word) > 3),
            f"Project name: '{project_name}', Proposal title: '{data_proposal_title}'"
        )
        
        # Check if options is a list or dict (handle both structures)
        if isinstance(data_options, list):
            log_test(
                "data.options contains exactly 3 entries",
                len(data_options) == 3,
                f"Options count: {len(data_options)}"
            )
            
            # Check if options have paths a, b, c
            option_paths = [opt.get("path") for opt in data_options if isinstance(opt, dict)]
            log_test(
                "data.options has paths a, b, c",
                set(option_paths) == {"a", "b", "c"},
                f"Option paths: {option_paths}"
            )
        elif isinstance(data_options, dict):
            log_test(
                "data.options contains exactly 3 entries",
                len(data_options) == 3,
                f"Options count: {len(data_options)}"
            )
            
            log_test(
                "data.options has paths a, b, c",
                "a" in data_options and "b" in data_options and "c" in data_options,
                f"Options keys: {list(data_options.keys())}"
            )
        else:
            log_test(
                "data.options is valid structure",
                False,
                f"Options type: {type(data_options)}"
            )
        
        log_test(
            "data.pricing_model exists",
            isinstance(data_pricing_model, dict) and len(data_pricing_model) > 0,
            f"Pricing model keys: {len(data_pricing_model)}"
        )
        
        gates = data_success.get("gates", [])
        log_test(
            "data.success.gates has 4 entries",
            len(gates) == 4,
            f"Gates count: {len(gates)}"
        )
        
        log_test(
            "data.team is a non-empty list",
            isinstance(data_team, list) and len(data_team) > 0,
            f"Team count: {len(data_team)}"
        )
        
        # Check if AI was slow but still succeeded
        if elapsed_time > 60:
            print(f"⚠️  WARN: AI step took {elapsed_time:.1f}s (>60s) but returned valid brief")
        
    except requests.exceptions.Timeout:
        log_test(
            "POST /api/proposals/from-project (with AI)",
            False,
            "Request timed out after 90 seconds"
        )
        print_summary()
        return
    except Exception as e:
        log_test("POST /api/proposals/from-project", False, f"Exception: {str(e)}")
        print_summary()
        return
    
    # STEP 4: GET /api/proposals/{id} to confirm persistence
    print("\n[STEP 4] GET /api/proposals/{id} to confirm persistence")
    print("-" * 80)
    
    try:
        get_response = requests.get(
            f"{BASE_URL}/api/proposals/{proposal_id}",
            headers=headers
        )
        
        log_test(
            "GET /api/proposals/{id}",
            get_response.status_code == 200,
            f"Status: {get_response.status_code}"
        )
        
        if get_response.status_code != 200:
            print(f"❌ Failed to get proposal: {get_response.text}")
        else:
            persisted_proposal = get_response.json()
            persisted_data = persisted_proposal.get("data", {})
            persisted_linked_project_id = persisted_proposal.get("linked_project_id")
            
            log_test(
                "Persisted proposal has same data",
                persisted_data.get("client_name") == data_client_name and
                persisted_data.get("proposal_title") == data_proposal_title,
                f"Client: {persisted_data.get('client_name')}, Title: {persisted_data.get('proposal_title')}"
            )
            
            log_test(
                "Persisted proposal has same linked_project_id",
                persisted_linked_project_id == linked_project_id,
                f"Linked project: {persisted_linked_project_id}"
            )
            
            print(f"✅ Proposal persisted correctly")
        
    except Exception as e:
        log_test("GET /api/proposals/{id}", False, f"Exception: {str(e)}")
    
    # STEP 5: POST /api/proposals/{id}/preview
    print("\n[STEP 5] POST /api/proposals/{id}/preview")
    print("-" * 80)
    
    try:
        preview_response = requests.post(
            f"{BASE_URL}/api/proposals/{proposal_id}/preview",
            headers=headers
        )
        
        log_test(
            "POST /api/proposals/{id}/preview",
            preview_response.status_code == 200,
            f"Status: {preview_response.status_code}"
        )
        
        if preview_response.status_code != 200:
            print(f"❌ Failed to get preview: {preview_response.text}")
        else:
            html_content = preview_response.text
            
            log_test(
                "Preview is text/html",
                "text/html" in preview_response.headers.get("content-type", ""),
                f"Content-Type: {preview_response.headers.get('content-type')}"
            )
            
            log_test(
                "Preview HTML length > 10000",
                len(html_content) > 10000,
                f"HTML length: {len(html_content)}"
            )
            
            log_test(
                "Preview contains client name",
                client_name.lower() in html_content.lower() or data_client_name.lower() in html_content.lower(),
                f"Searching for '{client_name}' or '{data_client_name}'"
            )
            
            print(f"✅ Preview generated: {len(html_content)} characters")
        
    except Exception as e:
        log_test("POST /api/proposals/{id}/preview", False, f"Exception: {str(e)}")
    
    # STEP 6: NEGATIVE TEST - POST with non-existent project_id
    print("\n[STEP 6] NEGATIVE TEST: POST with non-existent project_id")
    print("-" * 80)
    
    try:
        negative_response = requests.post(
            f"{BASE_URL}/api/proposals/from-project",
            headers={**headers, "Content-Type": "application/json"},
            json={
                "project_id": "000000000000000000000000",
                "use_ai": False
            }
        )
        
        log_test(
            "POST with non-existent project returns 404",
            negative_response.status_code == 404,
            f"Status: {negative_response.status_code}"
        )
        
        if negative_response.status_code == 404:
            print(f"✅ Correctly returned 404 for non-existent project")
        else:
            print(f"❌ Expected 404, got {negative_response.status_code}: {negative_response.text}")
        
    except Exception as e:
        log_test("Negative test (404)", False, f"Exception: {str(e)}")
    
    # STEP 7: NON-AI PATH - POST with use_ai=false
    print("\n[STEP 7] NON-AI PATH: POST with use_ai=false")
    print("-" * 80)
    
    try:
        print(f"Creating proposal from project {project_id} WITHOUT AI polish...")
        
        start_time = time.time()
        
        no_ai_response = requests.post(
            f"{BASE_URL}/api/proposals/from-project",
            headers={**headers, "Content-Type": "application/json"},
            json={
                "project_id": project_id,
                "use_ai": False
            },
            timeout=30
        )
        
        elapsed_time = time.time() - start_time
        
        log_test(
            "POST /api/proposals/from-project (without AI)",
            no_ai_response.status_code == 200,
            f"Status: {no_ai_response.status_code}, Time: {elapsed_time:.1f}s"
        )
        
        if no_ai_response.status_code != 200:
            print(f"❌ Failed to create proposal: {no_ai_response.text}")
        else:
            no_ai_proposal = no_ai_response.json()
            no_ai_data = no_ai_proposal.get("data", {})
            no_ai_assistant_message = no_ai_proposal.get("assistant_message", "")
            no_ai_team = no_ai_data.get("team", [])
            
            log_test(
                "Non-AI response is fast (<10s)",
                elapsed_time < 10,
                f"Time: {elapsed_time:.1f}s"
            )
            
            log_test(
                "Non-AI data has client_name set",
                len(no_ai_data.get("client_name", "")) > 0,
                f"Client: {no_ai_data.get('client_name')}"
            )
            
            log_test(
                "Non-AI data has proposal_title set",
                len(no_ai_data.get("proposal_title", "")) > 0,
                f"Title: {no_ai_data.get('proposal_title')}"
            )
            
            log_test(
                "Non-AI data has team list present",
                isinstance(no_ai_team, list),
                f"Team count: {len(no_ai_team)}"
            )
            
            log_test(
                "Non-AI assistant_message mentions pre-filled",
                "pre-filled" in no_ai_assistant_message.lower() or "mapped" in no_ai_assistant_message.lower(),
                f"Message: {no_ai_assistant_message[:100]}..."
            )
            
            print(f"✅ Non-AI proposal created in {elapsed_time:.1f}s")
            print(f"   Assistant message: {no_ai_assistant_message}")
        
    except Exception as e:
        log_test("POST /api/proposals/from-project (no AI)", False, f"Exception: {str(e)}")
    
    # Print final summary
    print_summary()

if __name__ == "__main__":
    main()
