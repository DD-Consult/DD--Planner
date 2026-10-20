#!/usr/bin/env python3
"""
Backend Test: Create Proposal from Project - Coercion Layer Fix (Phase 2a)

Re-verify the FIXED "create proposal from project" endpoint. A coercion layer was 
added so AI output is always repaired to a schema-valid brief (previously the AI 
sometimes returned options with 1 made-up path, breaking preview).

Test credentials: admin@test.com / admin123 (admin)
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
    if test_results['total'] > 0:
        print(f"Success Rate: {(test_results['passed']/test_results['total']*100):.1f}%")
    print("="*80)
    print("\nDetailed Results:")
    for detail in test_results["details"]:
        print(detail)
    print("="*80)

def main():
    print("="*80)
    print("BACKEND TEST: Create Proposal from Project - Coercion Layer Fix")
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
    print("\n[STEP 2] GET /api/projects?scope=all to pick first project")
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
        
    except Exception as e:
        log_test("GET /api/projects", False, f"Exception: {str(e)}")
        print_summary()
        return
    
    # Helper function to test proposal creation and preview
    def test_proposal_creation_and_preview(run_number, use_ai=True):
        """Test proposal creation and preview, return (proposal_id, options_paths, preview_status)"""
        print(f"\n[RUN {run_number}] POST /api/proposals/from-project (use_ai={use_ai})")
        print("-" * 80)
        
        try:
            if use_ai:
                print(f"Creating proposal from project {project_id} with AI polish...")
                print("⏳ This may take up to ~70 seconds (LLM call)...")
            else:
                print(f"Creating proposal from project {project_id} WITHOUT AI polish...")
            
            start_time = time.time()
            
            create_response = requests.post(
                f"{BASE_URL}/api/proposals/from-project",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "project_id": project_id,
                    "use_ai": use_ai
                },
                timeout=90 if use_ai else 30
            )
            
            elapsed_time = time.time() - start_time
            
            log_test(
                f"RUN {run_number}: POST /api/proposals/from-project (use_ai={use_ai})",
                create_response.status_code == 200,
                f"Status: {create_response.status_code}, Time: {elapsed_time:.1f}s"
            )
            
            if create_response.status_code != 200:
                print(f"❌ Failed to create proposal: {create_response.text}")
                return None, None, None
            
            proposal = create_response.json()
            proposal_id = proposal.get("id")
            proposal_data = proposal.get("data", {})
            
            print(f"✅ Proposal created: ID={proposal_id}")
            
            # CRITICAL ASSERTIONS on the returned data
            data_options = proposal_data.get("options", [])
            data_recommended_path = proposal_data.get("recommended_path")
            data_success = proposal_data.get("success", {})
            data_gates = data_success.get("gates", [])
            data_plan = proposal_data.get("plan", {})
            data_stage_deliverables = data_plan.get("stage_deliverables", {})
            data_pricing_model = proposal_data.get("pricing_model", {})
            data_team = proposal_data.get("team", [])
            
            # Check options structure
            if isinstance(data_options, list):
                option_paths = [opt.get("path") for opt in data_options if isinstance(opt, dict)]
                log_test(
                    f"RUN {run_number}: data.options has EXACTLY 3 entries",
                    len(data_options) == 3,
                    f"Options count: {len(data_options)}"
                )
                
                log_test(
                    f"RUN {run_number}: data.options has paths a, b, c",
                    set(option_paths) == {"a", "b", "c"},
                    f"Option paths: {option_paths}"
                )
            else:
                log_test(
                    f"RUN {run_number}: data.options is valid list",
                    False,
                    f"Options type: {type(data_options)}"
                )
                option_paths = []
            
            # Check recommended_path
            log_test(
                f"RUN {run_number}: data.recommended_path in [a,b,c]",
                data_recommended_path in ["a", "b", "c"],
                f"Recommended path: {data_recommended_path}"
            )
            
            # Check success.gates
            log_test(
                f"RUN {run_number}: data.success.gates length == 4",
                len(data_gates) == 4,
                f"Gates count: {len(data_gates)}"
            )
            
            # Check plan.stage_deliverables
            stage_keys = set(data_stage_deliverables.keys())
            log_test(
                f"RUN {run_number}: data.plan.stage_deliverables has keys '1'..'4'",
                stage_keys == {"1", "2", "3", "4"},
                f"Stage keys: {sorted(stage_keys)}"
            )
            
            # Check pricing_model
            has_path_a = "path_a" in data_pricing_model
            has_path_b = "path_b" in data_pricing_model
            has_path_c = "path_c" in data_pricing_model
            log_test(
                f"RUN {run_number}: data.pricing_model has path_a/path_b/path_c",
                has_path_a and has_path_b and has_path_c,
                f"Has path_a: {has_path_a}, path_b: {has_path_b}, path_c: {has_path_c}"
            )
            
            # Check team
            log_test(
                f"RUN {run_number}: data.team is non-empty",
                isinstance(data_team, list) and len(data_team) > 0,
                f"Team count: {len(data_team)}"
            )
            
            # CRITICAL: Test preview endpoint
            print(f"\n[RUN {run_number}] POST /api/proposals/{proposal_id}/preview")
            print("-" * 80)
            
            preview_response = requests.post(
                f"{BASE_URL}/api/proposals/{proposal_id}/preview",
                headers=headers
            )
            
            preview_status = preview_response.status_code
            
            log_test(
                f"RUN {run_number}: POST /api/proposals/{proposal_id}/preview returns 200",
                preview_status == 200,
                f"Status: {preview_status}"
            )
            
            if preview_status == 200:
                html_content = preview_response.text
                
                log_test(
                    f"RUN {run_number}: Preview is text/html",
                    "text/html" in preview_response.headers.get("content-type", ""),
                    f"Content-Type: {preview_response.headers.get('content-type')}"
                )
                
                log_test(
                    f"RUN {run_number}: Preview HTML length > 10000",
                    len(html_content) > 10000,
                    f"HTML length: {len(html_content)}"
                )
                
                log_test(
                    f"RUN {run_number}: Preview contains client name",
                    client_name.lower() in html_content.lower(),
                    f"Searching for '{client_name}'"
                )
                
                print(f"✅ Preview generated: {len(html_content)} characters")
            else:
                print(f"❌ Preview failed with status {preview_status}: {preview_response.text}")
            
            return proposal_id, option_paths, preview_status
            
        except requests.exceptions.Timeout:
            log_test(
                f"RUN {run_number}: POST /api/proposals/from-project",
                False,
                "Request timed out"
            )
            return None, None, None
        except Exception as e:
            log_test(f"RUN {run_number}: Exception", False, f"Exception: {str(e)}")
            return None, None, None
    
    # STEP 3-5: Test AI path THREE times (as requested)
    print("\n" + "="*80)
    print("TESTING AI PATH (3 RUNS)")
    print("="*80)
    
    ai_results = []
    for i in range(1, 4):
        proposal_id, option_paths, preview_status = test_proposal_creation_and_preview(i, use_ai=True)
        ai_results.append({
            "run": i,
            "proposal_id": proposal_id,
            "option_paths": option_paths,
            "preview_status": preview_status
        })
        time.sleep(2)  # Brief pause between runs
    
    # Summary of AI runs
    print("\n" + "="*80)
    print("AI PATH SUMMARY")
    print("="*80)
    for result in ai_results:
        print(f"Run {result['run']}: Proposal ID={result['proposal_id']}, "
              f"Option paths={result['option_paths']}, Preview status={result['preview_status']}")
    
    all_previews_200 = all(r['preview_status'] == 200 for r in ai_results if r['preview_status'] is not None)
    log_test(
        "ALL AI runs: Preview returned 200",
        all_previews_200,
        f"Preview statuses: {[r['preview_status'] for r in ai_results]}"
    )
    
    # STEP 6: Test non-AI path
    print("\n" + "="*80)
    print("TESTING NON-AI PATH")
    print("="*80)
    
    proposal_id, option_paths, preview_status = test_proposal_creation_and_preview(4, use_ai=False)
    
    log_test(
        "Non-AI path: Preview returned 200",
        preview_status == 200,
        f"Preview status: {preview_status}"
    )
    
    # STEP 7: Test normal AI builder (create blank proposal, ai-draft, preview)
    print("\n" + "="*80)
    print("TESTING NORMAL AI BUILDER")
    print("="*80)
    
    print("\n[STEP 7a] Create blank proposal")
    print("-" * 80)
    
    try:
        blank_response = requests.post(
            f"{BASE_URL}/api/proposals",
            headers={**headers, "Content-Type": "application/json"},
            json={
                "client_name": "Test Co"
            }
        )
        
        log_test(
            "Create blank proposal",
            blank_response.status_code == 200,
            f"Status: {blank_response.status_code}"
        )
        
        if blank_response.status_code != 200:
            print(f"❌ Failed to create blank proposal: {blank_response.text}")
        else:
            blank_proposal = blank_response.json()
            blank_proposal_id = blank_proposal.get("id")
            print(f"✅ Blank proposal created: ID={blank_proposal_id}")
            
            # STEP 7b: AI draft
            print("\n[STEP 7b] POST /api/proposals/{id}/ai-draft")
            print("-" * 80)
            
            print("⏳ Calling AI draft endpoint (may take ~70 seconds)...")
            start_time = time.time()
            
            ai_draft_response = requests.post(
                f"{BASE_URL}/api/proposals/{blank_proposal_id}/ai-draft",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "message": "Make this a cloud migration proposal for a logistics firm; recommend discovery first"
                },
                timeout=90
            )
            
            elapsed_time = time.time() - start_time
            
            log_test(
                "POST /api/proposals/{id}/ai-draft",
                ai_draft_response.status_code == 200,
                f"Status: {ai_draft_response.status_code}, Time: {elapsed_time:.1f}s"
            )
            
            if ai_draft_response.status_code != 200:
                print(f"❌ AI draft failed: {ai_draft_response.text}")
            else:
                ai_draft_data = ai_draft_response.json()
                assistant_message = ai_draft_data.get("assistant_message", "")
                print(f"✅ AI draft completed: {assistant_message[:100]}...")
                
                # STEP 7c: Preview
                print("\n[STEP 7c] POST /api/proposals/{id}/preview (after ai-draft)")
                print("-" * 80)
                
                preview_response = requests.post(
                    f"{BASE_URL}/api/proposals/{blank_proposal_id}/preview",
                    headers=headers
                )
                
                log_test(
                    "AI builder: Preview returned 200 (after ai-draft)",
                    preview_response.status_code == 200,
                    f"Status: {preview_response.status_code}"
                )
                
                if preview_response.status_code == 200:
                    html_content = preview_response.text
                    print(f"✅ Preview generated: {len(html_content)} characters")
                else:
                    print(f"❌ Preview failed: {preview_response.text}")
    
    except Exception as e:
        log_test("Normal AI builder test", False, f"Exception: {str(e)}")
    
    # Print final summary
    print_summary()

if __name__ == "__main__":
    main()
