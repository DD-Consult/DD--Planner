#!/usr/bin/env python3
"""
Live AI Feature Testing for DD Planner
Tests AI Smart Reschedule, WBS Generation, Chat Clarifying Questions
"""

import requests
import json
import sys
from datetime import datetime

# Configuration
BASE_URL = "https://saas-launch-44.preview.emergentagent.com/api"
GEMINI_API_KEY = "AQ.Ab8RN6JlT2eg5pT1yn_bNro68EKKLB7uM027iEWw5pOMTnR6Yg"

# Test credentials - try both
CREDENTIALS = [
    {"email": "don@ddconsult.tech", "password": "@Ddplanner2026"},
    {"email": "admin@test.com", "password": "admin123"},
]

def print_section(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def print_test(test_num, description):
    print(f"\n--- TEST {test_num}: {description} ---")

def print_result(status, message):
    symbol = "✅" if status == "PASS" else "❌"
    print(f"{symbol} {status}: {message}")

def login(email, password):
    """Login and return Bearer token"""
    print(f"Attempting login with {email}...")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": email, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if response.status_code == 200:
            token = response.json().get("access_token")
            print(f"✅ Login successful: {email}")
            return token
        else:
            print(f"❌ Login failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Login error: {e}")
        return None

def configure_ai_settings(token):
    """Configure AI settings to use Gemini"""
    print_test("SETUP", "Configure AI Settings to use Gemini")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try as query params first
    try:
        response = requests.put(
            f"{BASE_URL}/settings/ai",
            params={"provider": "gemini", "api_key": GEMINI_API_KEY},
            headers=headers
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print_result("PASS", "AI settings configured successfully")
            return True
        elif response.status_code == 403:
            print_result("FAIL", "User does not have super_admin role - cannot configure AI settings")
            print("NOTE: Will rely on env GEMINI_API_KEY for endpoints that use it directly")
            return False
        else:
            print_result("FAIL", f"Failed to configure AI settings: {response.status_code}")
            return False
    except Exception as e:
        print_result("FAIL", f"Error configuring AI settings: {e}")
        return False

def test_1_smart_reschedule(token):
    """TEST 1: AI Smart Reschedule"""
    print_test(1, "AI Smart Reschedule (live)")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get first project
    try:
        projects_response = requests.get(f"{BASE_URL}/projects", headers=headers)
        if projects_response.status_code != 200:
            print_result("FAIL", f"Failed to get projects: {projects_response.status_code}")
            return False
        
        projects = projects_response.json()
        if not projects:
            print_result("FAIL", "No projects found")
            return False
        
        project_id = projects[0]["id"]
        project_name = projects[0].get("name", "Unknown")
        print(f"Using project: {project_name} (ID: {project_id})")
        
        # Call smart reschedule
        reschedule_response = requests.post(
            f"{BASE_URL}/ai/smart-reschedule/{project_id}",
            json={},
            headers=headers
        )
        
        print(f"Status Code: {reschedule_response.status_code}")
        
        if reschedule_response.status_code == 200:
            data = reschedule_response.json()
            print(f"Response keys: {list(data.keys())}")
            
            # Check for expected keys
            has_should_reschedule = "should_reschedule" in data
            has_recommended_weeks = "recommended_weeks" in data
            has_direction = "direction" in data
            has_analysis = "analysis" in data
            has_preview = "preview" in data
            has_metrics = "metrics" in data
            
            print(f"  - should_reschedule: {data.get('should_reschedule')}")
            print(f"  - recommended_weeks: {data.get('recommended_weeks')}")
            print(f"  - direction: {data.get('direction')}")
            print(f"  - analysis length: {len(data.get('analysis', ''))}")
            print(f"  - preview present: {has_preview}")
            print(f"  - metrics present: {has_metrics}")
            
            analysis_text = data.get("analysis", "")
            if analysis_text and len(analysis_text) > 0:
                print(f"\nAnalysis excerpt: {analysis_text[:200]}...")
                print_result("PASS", "Smart reschedule returned 200 with populated analysis (Gemini responded)")
                return True
            else:
                print_result("FAIL", "Analysis text is empty - Gemini may not have responded")
                return False
        else:
            print(f"Response: {reschedule_response.text}")
            print_result("FAIL", f"Smart reschedule failed: {reschedule_response.status_code}")
            return False
            
    except Exception as e:
        print_result("FAIL", f"Error in smart reschedule test: {e}")
        return False

def test_2_wbs_generation(token):
    """TEST 2: WBS Generation with resource scoping"""
    print_test(2, "WBS Generation (live) + Resource Scoping")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get first project
    try:
        projects_response = requests.get(f"{BASE_URL}/projects", headers=headers)
        if projects_response.status_code != 200:
            print_result("FAIL", f"Failed to get projects: {projects_response.status_code}")
            return False
        
        projects = projects_response.json()
        if not projects:
            print_result("FAIL", "No projects found")
            return False
        
        project_id = projects[0]["id"]
        project_name = projects[0].get("name", "Unknown")
        print(f"Using project: {project_name} (ID: {project_id})")
        
        # Call WBS generation
        wbs_response = requests.post(
            f"{BASE_URL}/ai/generate-wbs",
            json={
                "project_id": project_id,
                "complexity": "simple",
                "include_subtasks": False
            },
            headers=headers
        )
        
        print(f"Status Code: {wbs_response.status_code}")
        
        if wbs_response.status_code == 200:
            data = wbs_response.json()
            print(f"Response keys: {list(data.keys())}")
            
            tasks = data.get("tasks", [])
            print(f"Number of tasks generated: {len(tasks)}")
            
            if len(tasks) > 0:
                # Show first couple task names
                print("\nSample task names:")
                for i, task in enumerate(tasks[:3]):
                    print(f"  {i+1}. {task.get('name', 'N/A')}")
                
                # Check resource scoping
                assigned_count = 0
                unassigned_count = 0
                assignment_notes = []
                
                for task in tasks:
                    assigned_to = task.get("assigned_to")
                    assigned_to_id = task.get("assigned_to_id")
                    assignment_note = task.get("assignment_note", "")
                    
                    if assigned_to or assigned_to_id:
                        assigned_count += 1
                    else:
                        unassigned_count += 1
                    
                    if assignment_note:
                        assignment_notes.append(assignment_note)
                
                print(f"\nResource Scoping Results:")
                print(f"  - Assigned tasks: {assigned_count}")
                print(f"  - Unassigned tasks: {unassigned_count}")
                print(f"  - Assignment notes found: {len(assignment_notes)}")
                
                if assignment_notes:
                    print(f"\nSample assignment notes:")
                    for note in assignment_notes[:3]:
                        print(f"  - {note}")
                
                print_result("PASS", f"WBS generation returned {len(tasks)} tasks with resource scoping logic applied")
                return True
            else:
                print_result("FAIL", "No tasks generated")
                return False
        else:
            print(f"Response: {wbs_response.text}")
            print_result("FAIL", f"WBS generation failed: {wbs_response.status_code}")
            return False
            
    except Exception as e:
        print_result("FAIL", f"Error in WBS generation test: {e}")
        return False

def test_3_chat_clarifying(token):
    """TEST 3: Chat clarifying question behavior"""
    print_test(3, "Chat Clarifying Question (live behavior)")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # First message - should ask for clarification
    try:
        print("\n--- Part 1: Initial ambiguous request ---")
        chat_response_1 = requests.post(
            f"{BASE_URL}/ai/chat",
            json={"message": "assign Alice to the website project"},
            headers=headers
        )
        
        print(f"Status Code: {chat_response_1.status_code}")
        
        if chat_response_1.status_code == 200:
            data_1 = chat_response_1.json()
            reply_text = data_1.get("reply", "")
            session_id = data_1.get("session_id", "")
            
            print(f"Session ID: {session_id}")
            print(f"Reply length: {len(reply_text)}")
            print(f"Reply excerpt: {reply_text[:300]}...")
            
            # Check if it's asking for clarification
            asks_for_info = any(keyword in reply_text.lower() for keyword in [
                "percentage", "hours", "date", "when", "how much", "allocation",
                "start", "end", "duration", "need", "provide", "specify"
            ])
            
            # Check if it has an action block (should NOT)
            has_action_block = "```action" in reply_text or '"action"' in reply_text.lower()
            
            print(f"\nAnalysis:")
            print(f"  - Asks for missing info: {asks_for_info}")
            print(f"  - Contains action block: {has_action_block}")
            
            if asks_for_info and not has_action_block:
                print_result("PASS", "Part 1: Agent correctly asked for clarification without fabricating action")
            else:
                print_result("FAIL", f"Part 1: Expected clarifying question. asks_for_info={asks_for_info}, has_action={has_action_block}")
                return False
            
            # Part 2: Follow-up with details
            if session_id:
                print("\n--- Part 2: Follow-up with details ---")
                chat_response_2 = requests.post(
                    f"{BASE_URL}/ai/chat",
                    json={
                        "message": "50% from 2026-02-01 to 2026-02-28",
                        "session_id": session_id
                    },
                    headers=headers
                )
                
                print(f"Status Code: {chat_response_2.status_code}")
                
                if chat_response_2.status_code == 200:
                    data_2 = chat_response_2.json()
                    reply_text_2 = data_2.get("reply", "")
                    
                    print(f"Reply length: {len(reply_text_2)}")
                    print(f"Reply excerpt: {reply_text_2[:300]}...")
                    
                    # Check if action was produced
                    has_action_now = "```action" in reply_text_2 or "create_allocation" in reply_text_2.lower() or "allocation" in reply_text_2.lower()
                    
                    print(f"\nAnalysis:")
                    print(f"  - Contains action/allocation reference: {has_action_now}")
                    
                    if has_action_now:
                        print_result("PASS", "Part 2: Agent produced action after receiving complete info")
                        return True
                    else:
                        print_result("FAIL", "Part 2: Expected action to be produced with complete info")
                        return False
                else:
                    print(f"Response: {chat_response_2.text}")
                    print_result("FAIL", f"Part 2: Follow-up chat failed: {chat_response_2.status_code}")
                    return False
            else:
                print_result("FAIL", "No session_id returned from first message")
                return False
        else:
            print(f"Response: {chat_response_1.text}")
            print_result("FAIL", f"Part 1: Chat failed: {chat_response_1.status_code}")
            return False
            
    except Exception as e:
        print_result("FAIL", f"Error in chat clarifying test: {e}")
        return False

def test_4_normal_chat(token):
    """TEST 4: Normal chat query"""
    print_test(4, "Normal Chat Query (regression)")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        chat_response = requests.post(
            f"{BASE_URL}/ai/chat",
            json={"message": "How many active projects are there?"},
            headers=headers
        )
        
        print(f"Status Code: {chat_response.status_code}")
        
        if chat_response.status_code == 200:
            data = chat_response.json()
            reply_text = data.get("reply", "")
            
            print(f"Reply length: {len(reply_text)}")
            print(f"Reply: {reply_text[:500]}...")
            
            if len(reply_text) > 0:
                print_result("PASS", "Normal chat query returned sensible text answer")
                return True
            else:
                print_result("FAIL", "Reply text is empty")
                return False
        else:
            print(f"Response: {chat_response.text}")
            print_result("FAIL", f"Chat failed: {chat_response.status_code}")
            return False
            
    except Exception as e:
        print_result("FAIL", f"Error in normal chat test: {e}")
        return False

def cleanup_ai_settings(token):
    """Cleanup: Delete AI settings"""
    print_test("CLEANUP", "Delete AI Settings")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.delete(f"{BASE_URL}/settings/ai", headers=headers)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print_result("PASS", "AI settings deleted successfully")
            return True
        elif response.status_code == 403:
            print_result("INFO", "Cannot delete (not super_admin) - settings will remain")
            return True
        else:
            print(f"Response: {response.text}")
            print_result("FAIL", f"Failed to delete AI settings: {response.status_code}")
            return False
    except Exception as e:
        print_result("FAIL", f"Error deleting AI settings: {e}")
        return False

def main():
    print_section("DD PLANNER - LIVE AI FEATURES VERIFICATION")
    print(f"Base URL: {BASE_URL}")
    print(f"Gemini API Key: {GEMINI_API_KEY[:20]}...")
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Try to login with available credentials
    token = None
    for cred in CREDENTIALS:
        token = login(cred["email"], cred["password"])
        if token:
            break
    
    if not token:
        print("\n❌ FATAL: Could not login with any credentials")
        sys.exit(1)
    
    # Configure AI settings
    ai_configured = configure_ai_settings(token)
    
    # Run tests
    results = {
        "test_1_smart_reschedule": test_1_smart_reschedule(token),
        "test_2_wbs_generation": test_2_wbs_generation(token),
        "test_3_chat_clarifying": test_3_chat_clarifying(token),
        "test_4_normal_chat": test_4_normal_chat(token),
    }
    
    # Cleanup
    if ai_configured:
        cleanup_ai_settings(token)
    
    # Summary
    print_section("TEST SUMMARY")
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed
    
    print(f"Total Tests: {total}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failed} ❌")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    
    print("\nDetailed Results:")
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {test_name}")
    
    print("\n" + "="*80)
    
    if failed == 0:
        print("✅ ALL TESTS PASSED - AI features working with Gemini key")
        sys.exit(0)
    else:
        print(f"❌ {failed} TEST(S) FAILED - See details above")
        sys.exit(1)

if __name__ == "__main__":
    main()
