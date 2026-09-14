#!/usr/bin/env python3
"""
FINAL COMPREHENSIVE AI FEATURE TESTING
Tests all 4 AI features with correct response parsing
"""

import requests
import json
import sys
from datetime import datetime

BASE_URL = "https://saas-launch-44.preview.emergentagent.com/api"
GEMINI_API_KEY = "AQ.Ab8RN6JlT2eg5pT1yn_bNro68EKKLB7uM027iEWw5pOMTnR6Yg"

def print_section(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def print_test(test_num, description):
    print(f"\n{'─'*80}")
    print(f"TEST {test_num}: {description}")
    print(f"{'─'*80}")

def print_result(status, message):
    symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "ℹ️"
    print(f"{symbol} {status}: {message}")

def login():
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": "admin@test.com", "password": "admin123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if response.status_code == 200:
        print_result("PASS", "Login successful: admin@test.com")
        return response.json().get("access_token")
    else:
        print_result("FAIL", f"Login failed: {response.status_code}")
        return None

def configure_ai_settings(token):
    print_test("SETUP", "Configure AI Settings to use Gemini")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.put(
        f"{BASE_URL}/settings/ai",
        params={"provider": "gemini", "api_key": GEMINI_API_KEY},
        headers=headers
    )
    
    if response.status_code == 200:
        print_result("PASS", "AI settings configured successfully")
        return True
    elif response.status_code == 403:
        print_result("INFO", "User not super_admin - will rely on env GEMINI_API_KEY")
        return False
    else:
        print_result("FAIL", f"Failed to configure: {response.status_code}")
        return False

def test_1_smart_reschedule(token):
    print_test(1, "AI Smart Reschedule (live)")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        # Get first project
        projects = requests.get(f"{BASE_URL}/projects", headers=headers).json()
        project_id = projects[0]["id"]
        project_name = projects[0].get("name", "Unknown")
        
        print(f"Project: {project_name} (ID: {project_id})")
        
        # Call smart reschedule
        response = requests.post(
            f"{BASE_URL}/ai/smart-reschedule/{project_id}",
            json={},
            headers=headers
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # The response structure has "analysis" as a dict
            analysis_obj = data.get("analysis", {})
            
            if isinstance(analysis_obj, dict):
                should_reschedule = analysis_obj.get("should_reschedule")
                recommended_weeks = analysis_obj.get("recommended_weeks")
                direction = analysis_obj.get("direction")
                analysis_text = analysis_obj.get("analysis", "")
                confidence = analysis_obj.get("confidence", 0)
                reasons = analysis_obj.get("reasons", [])
                
                print(f"\n📊 Analysis Results:")
                print(f"  • should_reschedule: {should_reschedule}")
                print(f"  • recommended_weeks: {recommended_weeks}")
                print(f"  • direction: {direction}")
                print(f"  • confidence: {confidence}")
                print(f"  • analysis text length: {len(analysis_text)}")
                print(f"  • reasons count: {len(reasons)}")
                
                print(f"\n📝 Analysis Text:")
                print(f"  {analysis_text}")
                
                print(f"\n📋 Reasons:")
                for i, reason in enumerate(reasons, 1):
                    print(f"  {i}. {reason}")
                
                # Check preview and metrics
                preview = data.get("preview", {})
                metrics = data.get("metrics", {})
                
                print(f"\n📦 Preview:")
                print(f"  • Phases: {preview.get('phases_count', 0)}")
                print(f"  • Allocations: {preview.get('allocations_count', 0)}")
                print(f"  • WBS Tasks: {preview.get('wbs_tasks_count', 0)}")
                print(f"  • Milestones: {preview.get('milestones_count', 0)}")
                
                print(f"\n📈 Metrics:")
                print(f"  • Time Progress: {metrics.get('time_progress', 0)}%")
                print(f"  • Actual Progress: {metrics.get('actual_progress', 0)}%")
                print(f"  • Overdue Tasks: {metrics.get('overdue_tasks', 0)}")
                
                # Verify all expected keys are present
                has_all_keys = all([
                    should_reschedule is not None,
                    recommended_weeks is not None,
                    direction is not None,
                    len(analysis_text) > 0,
                    preview,
                    metrics
                ])
                
                if has_all_keys:
                    print_result("PASS", "Smart reschedule returned 200 with complete analysis (Gemini responded)")
                    return True
                else:
                    print_result("FAIL", "Missing expected keys in response")
                    return False
            else:
                print_result("FAIL", f"Analysis is not a dict: {type(analysis_obj)}")
                return False
        else:
            print(f"Response: {response.text}")
            print_result("FAIL", f"Request failed: {response.status_code}")
            return False
            
    except Exception as e:
        print_result("FAIL", f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_2_wbs_generation(token):
    print_test(2, "WBS Generation (live) + Resource Scoping")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        # Get first project
        projects = requests.get(f"{BASE_URL}/projects", headers=headers).json()
        project_id = projects[0]["id"]
        project_name = projects[0].get("name", "Unknown")
        
        print(f"Project: {project_name} (ID: {project_id})")
        
        # Call WBS generation
        response = requests.post(
            f"{BASE_URL}/ai/generate-wbs",
            json={
                "project_id": project_id,
                "complexity": "simple",
                "include_subtasks": False
            },
            headers=headers
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            tasks = data.get("tasks", [])
            
            print(f"\n📊 Generated {len(tasks)} tasks")
            
            if len(tasks) > 0:
                # Show sample task names
                print(f"\n📝 Sample Task Names:")
                for i, task in enumerate(tasks[:3], 1):
                    print(f"  {i}. {task.get('name', 'N/A')}")
                
                # Resource scoping analysis
                assigned_count = 0
                unassigned_count = 0
                assignment_notes = []
                
                print(f"\n👥 Resource Scoping Results:")
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
                
                print(f"  • Assigned tasks: {assigned_count}")
                print(f"  • Unassigned tasks: {unassigned_count}")
                print(f"  • Assignment notes: {len(assignment_notes)}")
                
                # Show sample assignments
                print(f"\n📋 Sample Task Assignments:")
                for i, task in enumerate(tasks[:5], 1):
                    assigned_to = task.get("assigned_to", "Unassigned")
                    assignment_note = task.get("assignment_note", "")
                    note_text = f" ({assignment_note})" if assignment_note else ""
                    print(f"  {i}. {task.get('name', 'N/A')[:50]}")
                    print(f"     → {assigned_to}{note_text}")
                
                print_result("PASS", f"WBS generation returned {len(tasks)} tasks with resource scoping")
                return True
            else:
                print_result("FAIL", "No tasks generated")
                return False
        else:
            print(f"Response: {response.text}")
            print_result("FAIL", f"Request failed: {response.status_code}")
            return False
            
    except Exception as e:
        print_result("FAIL", f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_3_chat_clarifying(token):
    print_test(3, "Chat Clarifying Question (live behavior)")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        # Part 1: Ambiguous request
        print("\n📝 Part 1: Initial ambiguous request")
        print("Message: 'assign Alice to the website project'")
        
        response1 = requests.post(
            f"{BASE_URL}/ai/chat",
            json={"message": "assign Alice to the website project"},
            headers=headers
        )
        
        print(f"Status Code: {response1.status_code}")
        
        if response1.status_code == 200:
            data1 = response1.json()
            session_id = data1.get("session_id", "")
            
            # Parse the response field (it's a JSON string)
            response_str = data1.get("response", "{}")
            try:
                response_obj = json.loads(response_str)
                reply_text = response_obj.get("message", "")
            except:
                reply_text = ""
            
            print(f"Session ID: {session_id}")
            print(f"\n💬 Assistant Reply:")
            print(f"  {reply_text}")
            
            # Check if it's asking for clarification
            asks_for_info = any(keyword in reply_text.lower() for keyword in [
                "percentage", "hours", "date", "when", "how much", "allocation",
                "start", "end", "duration", "need", "provide", "specify", "range"
            ])
            
            # Check if it has an action block (should NOT)
            has_action_block = "```action" in reply_text
            
            print(f"\n🔍 Analysis:")
            print(f"  • Asks for missing info: {asks_for_info}")
            print(f"  • Contains action block: {has_action_block}")
            
            if asks_for_info and not has_action_block:
                print_result("PASS", "Part 1: Agent correctly asked for clarification without fabricating action")
            else:
                print_result("FAIL", f"Part 1: Expected clarifying question (asks={asks_for_info}, action={has_action_block})")
                return False
            
            # Part 2: Follow-up with details
            if session_id:
                print("\n📝 Part 2: Follow-up with complete details")
                print("Message: '50% from 2026-02-01 to 2026-02-28'")
                
                response2 = requests.post(
                    f"{BASE_URL}/ai/chat",
                    json={
                        "message": "50% from 2026-02-01 to 2026-02-28",
                        "session_id": session_id
                    },
                    headers=headers
                )
                
                print(f"Status Code: {response2.status_code}")
                
                if response2.status_code == 200:
                    data2 = response2.json()
                    
                    # Parse the response field
                    response_str2 = data2.get("response", "{}")
                    try:
                        response_obj2 = json.loads(response_str2)
                        reply_text2 = response_obj2.get("message", "")
                    except:
                        reply_text2 = ""
                    
                    print(f"\n💬 Assistant Reply:")
                    print(f"  {reply_text2[:200]}...")
                    
                    # Check if action was produced
                    has_action_now = "```action" in reply_text2 or "create_allocation" in reply_text2
                    
                    print(f"\n🔍 Analysis:")
                    print(f"  • Contains action block: {has_action_now}")
                    
                    if has_action_now:
                        print_result("PASS", "Part 2: Agent produced action after receiving complete info")
                        return True
                    else:
                        print_result("FAIL", "Part 2: Expected action to be produced")
                        return False
                else:
                    print_result("FAIL", f"Part 2: Request failed: {response2.status_code}")
                    return False
            else:
                print_result("FAIL", "No session_id returned")
                return False
        else:
            print_result("FAIL", f"Part 1: Request failed: {response1.status_code}")
            return False
            
    except Exception as e:
        print_result("FAIL", f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_4_normal_chat(token):
    print_test(4, "Normal Chat Query (regression)")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        print("Message: 'How many active projects are there?'")
        
        response = requests.post(
            f"{BASE_URL}/ai/chat",
            json={"message": "How many active projects are there?"},
            headers=headers
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Parse the response field
            response_str = data.get("response", "{}")
            try:
                response_obj = json.loads(response_str)
                reply_text = response_obj.get("message", "")
            except:
                reply_text = ""
            
            print(f"\n💬 Assistant Reply:")
            print(f"  {reply_text}")
            
            if len(reply_text) > 0:
                print_result("PASS", "Normal chat query returned sensible text answer")
                return True
            else:
                print_result("FAIL", "Reply text is empty")
                return False
        else:
            print_result("FAIL", f"Request failed: {response.status_code}")
            return False
            
    except Exception as e:
        print_result("FAIL", f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def cleanup_ai_settings(token):
    print_test("CLEANUP", "Delete AI Settings")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.delete(f"{BASE_URL}/settings/ai", headers=headers)
        
        if response.status_code == 200:
            print_result("PASS", "AI settings deleted successfully")
            return True
        elif response.status_code == 403:
            print_result("INFO", "Cannot delete (not super_admin) - settings will remain")
            return True
        else:
            print_result("FAIL", f"Failed to delete: {response.status_code}")
            return False
    except Exception as e:
        print_result("FAIL", f"Error: {e}")
        return False

def main():
    print_section("DD PLANNER - LIVE AI FEATURES VERIFICATION")
    print(f"Base URL: {BASE_URL}")
    print(f"Gemini API Key: {GEMINI_API_KEY[:20]}...")
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Test Credentials: admin@test.com / admin123")
    
    # Login
    token = login()
    if not token:
        print("\n❌ FATAL: Could not login")
        sys.exit(1)
    
    # Configure AI settings
    ai_configured = configure_ai_settings(token)
    
    # Run tests
    results = {
        "TEST 1 - AI Smart Reschedule": test_1_smart_reschedule(token),
        "TEST 2 - WBS Generation": test_2_wbs_generation(token),
        "TEST 3 - Chat Clarifying": test_3_chat_clarifying(token),
        "TEST 4 - Normal Chat": test_4_normal_chat(token),
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
    
    print("\n📋 Detailed Results:")
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {test_name}")
    
    print("\n" + "="*80)
    
    if failed == 0:
        print("✅ ALL TESTS PASSED")
        print("\n🎯 Overall Verdict:")
        print("  • AI Reschedule: Working live with Gemini key")
        print("  • WBS Generation: Working with resource scoping")
        print("  • Chat Clarifying: Working correctly (asks for info, then acts)")
        print("  • Normal Chat: Working correctly")
        sys.exit(0)
    else:
        print(f"❌ {failed} TEST(S) FAILED - See details above")
        sys.exit(1)

if __name__ == "__main__":
    main()
