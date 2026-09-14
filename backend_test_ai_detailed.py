#!/usr/bin/env python3
"""
Detailed AI Feature Testing - Check actual response structures
"""

import requests
import json
import sys

BASE_URL = "https://saas-launch-44.preview.emergentagent.com/api"
GEMINI_API_KEY = "AQ.Ab8RN6JlT2eg5pT1yn_bNro68EKKLB7uM027iEWw5pOMTnR6Yg"

def login():
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": "admin@test.com", "password": "admin123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    return response.json().get("access_token")

def test_smart_reschedule(token):
    print("\n" + "="*80)
    print("TEST 1: AI Smart Reschedule - Detailed Response Analysis")
    print("="*80)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get first project
    projects = requests.get(f"{BASE_URL}/projects", headers=headers).json()
    project_id = projects[0]["id"]
    project_name = projects[0].get("name", "Unknown")
    
    print(f"\nProject: {project_name} (ID: {project_id})")
    
    # Call smart reschedule
    response = requests.post(
        f"{BASE_URL}/ai/smart-reschedule/{project_id}",
        json={},
        headers=headers
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        
        print("\n--- Full Response Structure ---")
        print(json.dumps(data, indent=2, default=str))
        
        print("\n--- Analysis ---")
        print(f"Response keys: {list(data.keys())}")
        
        # Check analysis field
        analysis = data.get("analysis", "")
        print(f"\nAnalysis field type: {type(analysis)}")
        print(f"Analysis field value: {repr(analysis)}")
        
        if isinstance(analysis, str):
            print(f"Analysis length: {len(analysis)}")
            if len(analysis) > 0:
                print(f"Analysis content: {analysis}")
        
        # Check preview
        preview = data.get("preview", {})
        print(f"\nPreview keys: {list(preview.keys()) if isinstance(preview, dict) else 'Not a dict'}")
        
        # Check metrics
        metrics = data.get("metrics", {})
        print(f"Metrics keys: {list(metrics.keys()) if isinstance(metrics, dict) else 'Not a dict'}")
        
        # Expected fields from review request
        expected_fields = ["should_reschedule", "recommended_weeks", "direction", "analysis", "preview", "metrics"]
        missing_fields = [f for f in expected_fields if f not in data]
        
        print(f"\nExpected fields: {expected_fields}")
        print(f"Missing fields: {missing_fields}")
        
        return data
    else:
        print(f"ERROR: {response.text}")
        return None

def test_wbs_generation(token):
    print("\n" + "="*80)
    print("TEST 2: WBS Generation - Detailed Response Analysis")
    print("="*80)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get first project
    projects = requests.get(f"{BASE_URL}/projects", headers=headers).json()
    project_id = projects[0]["id"]
    
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
        
        print(f"\nResponse keys: {list(data.keys())}")
        
        tasks = data.get("tasks", [])
        print(f"Number of tasks: {len(tasks)}")
        
        if len(tasks) > 0:
            print("\n--- First Task Structure ---")
            print(json.dumps(tasks[0], indent=2, default=str))
            
            # Resource scoping analysis
            print("\n--- Resource Scoping Analysis ---")
            for i, task in enumerate(tasks[:5]):
                assigned_to = task.get("assigned_to")
                assigned_to_id = task.get("assigned_to_id")
                assignment_note = task.get("assignment_note", "")
                
                print(f"\nTask {i+1}: {task.get('name', 'N/A')}")
                print(f"  assigned_to: {assigned_to}")
                print(f"  assigned_to_id: {assigned_to_id}")
                print(f"  assignment_note: {assignment_note}")
        
        return data
    else:
        print(f"ERROR: {response.text}")
        return None

def test_chat(token):
    print("\n" + "="*80)
    print("TEST 3 & 4: Chat - Detailed Response Analysis")
    print("="*80)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test 1: Ambiguous request
    print("\n--- Chat Test 1: Ambiguous Request ---")
    response1 = requests.post(
        f"{BASE_URL}/ai/chat",
        json={"message": "assign Alice to the website project"},
        headers=headers
    )
    
    print(f"Status Code: {response1.status_code}")
    
    if response1.status_code == 200:
        data1 = response1.json()
        
        print("\n--- Full Response Structure ---")
        print(json.dumps(data1, indent=2, default=str))
        
        reply = data1.get("reply", "")
        session_id = data1.get("session_id", "")
        
        print(f"\nReply type: {type(reply)}")
        print(f"Reply value: {repr(reply)}")
        print(f"Reply length: {len(reply) if isinstance(reply, str) else 'N/A'}")
        print(f"Session ID: {session_id}")
        
        if isinstance(reply, str) and len(reply) > 0:
            print(f"\nReply content:\n{reply}")
        
        # Test 2: Follow-up with details
        if session_id:
            print("\n--- Chat Test 2: Follow-up with Details ---")
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
                
                print("\n--- Full Response Structure ---")
                print(json.dumps(data2, indent=2, default=str))
                
                reply2 = data2.get("reply", "")
                print(f"\nReply type: {type(reply2)}")
                print(f"Reply value: {repr(reply2)}")
                print(f"Reply length: {len(reply2) if isinstance(reply2, str) else 'N/A'}")
                
                if isinstance(reply2, str) and len(reply2) > 0:
                    print(f"\nReply content:\n{reply2}")
    
    # Test 3: Normal query
    print("\n--- Chat Test 3: Normal Query ---")
    response3 = requests.post(
        f"{BASE_URL}/ai/chat",
        json={"message": "How many active projects are there?"},
        headers=headers
    )
    
    print(f"Status Code: {response3.status_code}")
    
    if response3.status_code == 200:
        data3 = response3.json()
        
        print("\n--- Full Response Structure ---")
        print(json.dumps(data3, indent=2, default=str))
        
        reply3 = data3.get("reply", "")
        print(f"\nReply type: {type(reply3)}")
        print(f"Reply value: {repr(reply3)}")
        print(f"Reply length: {len(reply3) if isinstance(reply3, str) else 'N/A'}")
        
        if isinstance(reply3, str) and len(reply3) > 0:
            print(f"\nReply content:\n{reply3}")

def main():
    print("DD PLANNER - DETAILED AI RESPONSE ANALYSIS")
    print("="*80)
    
    # Configure AI settings first
    token = login()
    
    headers = {"Authorization": f"Bearer {token}"}
    config_response = requests.put(
        f"{BASE_URL}/settings/ai",
        params={"provider": "gemini", "api_key": GEMINI_API_KEY},
        headers=headers
    )
    print(f"AI Settings configured: {config_response.status_code}")
    
    # Run tests
    test_smart_reschedule(token)
    test_wbs_generation(token)
    test_chat(token)
    
    # Cleanup
    requests.delete(f"{BASE_URL}/settings/ai", headers=headers)
    print("\n" + "="*80)
    print("Testing complete")

if __name__ == "__main__":
    main()
