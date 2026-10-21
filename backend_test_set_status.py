#!/usr/bin/env python3
"""
Test script for PUT /api/leaves/{id}/set-status endpoint
Tests that super_admin can change an already-decided leave status
"""

import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "https://proposal-approve.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"

# Test accounts
RESOURCE_EMAIL = "qa_resource@test.com"
RESOURCE_PASSWORD = "Test@2026"
SUPERADMIN_EMAIL = "superadmin@test.com"
SUPERADMIN_PASSWORD = "Super@2026"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

# Test results storage
test_results = []

def login(email, password):
    """Login with OAuth2 form-encoded credentials"""
    url = f"{API_BASE}/auth/login"
    data = {
        "username": email,
        "password": password
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    response = requests.post(url, data=data, headers=headers)
    if response.status_code == 200:
        token = response.json().get("access_token")
        return token
    else:
        print(f"❌ Login failed for {email}: {response.status_code} - {response.text}")
        return None

def add_result(step, description, expected, actual, passed):
    """Add test result to results list"""
    test_results.append({
        "step": step,
        "description": description,
        "expected": expected,
        "actual": actual,
        "result": "✅ PASS" if passed else "❌ FAIL"
    })

def print_results_table():
    """Print test results in a formatted table"""
    print("\n" + "="*120)
    print("TEST RESULTS SUMMARY")
    print("="*120)
    print(f"{'STEP':<6} {'DESCRIPTION':<40} {'EXPECTED':<25} {'ACTUAL':<30} {'RESULT':<10}")
    print("-"*120)
    
    for result in test_results:
        step = result['step']
        desc = result['description'][:38]
        expected = str(result['expected'])[:23]
        actual = str(result['actual'])[:28]
        status = result['result']
        print(f"{step:<6} {desc:<40} {expected:<25} {actual:<30} {status:<10}")
    
    print("="*120)
    
    # Summary
    passed = sum(1 for r in test_results if r['result'] == "✅ PASS")
    total = len(test_results)
    print(f"\nTOTAL: {passed}/{total} tests passed")
    print("="*120 + "\n")

def main():
    print("="*120)
    print("TESTING: PUT /api/leaves/{id}/set-status - Super Admin Can Change Already-Decided Leave")
    print("="*120)
    
    leave_id = None
    resource_id = None
    resource_token = None
    superadmin_token = None
    admin_token = None
    
    # STEP 1: Login as resource and create a leave
    print("\n[STEP 1] Login as resource and create leave...")
    resource_token = login(RESOURCE_EMAIL, RESOURCE_PASSWORD)
    
    if not resource_token:
        add_result("1", "Login resource", "200 with token", "Login failed", False)
        print_results_table()
        return
    
    # Create leave
    url = f"{API_BASE}/leaves"
    headers = {
        "Authorization": f"Bearer {resource_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "start_date": "2026-11-17",
        "end_date": "2026-11-19",
        "type": "Vacation",
        "notes": "qa setstatus"
    }
    
    response = requests.post(url, json=payload, headers=headers)
    print(f"   POST /api/leaves: {response.status_code}")
    
    if response.status_code in [200, 201]:
        data = response.json()
        leave_id = data.get("id")
        resource_id = data.get("resource_id")
        status = data.get("status")
        
        print(f"   Created leave: id={leave_id}, resource_id={resource_id}, status={status}")
        
        passed = status == "Pending"
        add_result("1", "Create leave as resource", "status='Pending'", f"status='{status}'", passed)
        
        if not leave_id:
            print("❌ Failed to get leave ID from response")
            print_results_table()
            return
    else:
        print(f"❌ Failed to create leave: {response.text}")
        add_result("1", "Create leave as resource", "200/201", f"{response.status_code}", False)
        print_results_table()
        return
    
    # STEP 2: Login as super_admin and approve the leave
    print("\n[STEP 2] Login as super_admin and approve leave...")
    superadmin_token = login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)
    
    if not superadmin_token:
        add_result("2", "Login super_admin", "200 with token", "Login failed", False)
        print_results_table()
        return
    
    url = f"{API_BASE}/leaves/{leave_id}/set-status"
    headers = {
        "Authorization": f"Bearer {superadmin_token}",
        "Content-Type": "application/json"
    }
    payload = {"status": "Approved"}
    
    response = requests.put(url, json=payload, headers=headers)
    print(f"   PUT /api/leaves/{leave_id}/set-status (Approved): {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        status = data.get("status")
        approver_email = data.get("approver_email")
        decided_at = data.get("decided_at")
        
        print(f"   Response: status={status}, approver_email={approver_email}, decided_at={decided_at}")
        
        passed = (status == "Approved" and 
                 approver_email == SUPERADMIN_EMAIL and 
                 decided_at is not None)
        
        add_result("2", "Approve leave (super_admin)", 
                  "status='Approved', approver_email='superadmin@test.com', decided_at non-null",
                  f"status='{status}', approver_email='{approver_email}', decided_at={decided_at is not None}",
                  passed)
    else:
        print(f"❌ Failed to approve leave: {response.text}")
        add_result("2", "Approve leave (super_admin)", "200", f"{response.status_code}", False)
        print_results_table()
        return
    
    # STEP 3: CORE TEST - Change already-approved leave to Rejected
    print("\n[STEP 3] CORE TEST: Change already-approved leave to Rejected...")
    url = f"{API_BASE}/leaves/{leave_id}/set-status"
    headers = {
        "Authorization": f"Bearer {superadmin_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "status": "Rejected",
        "note": "revoked by QA"
    }
    
    response = requests.put(url, json=payload, headers=headers)
    print(f"   PUT /api/leaves/{leave_id}/set-status (Rejected): {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        status = data.get("status")
        decision_note = data.get("decision_note")
        
        print(f"   Response: status={status}, decision_note={decision_note}")
        
        passed = (status == "Rejected" and decision_note == "revoked by QA")
        
        add_result("3", "Change Approved→Rejected (CORE)", 
                  "status='Rejected', decision_note='revoked by QA'",
                  f"status='{status}', decision_note='{decision_note}'",
                  passed)
    else:
        print(f"❌ Failed to change status: {response.text}")
        add_result("3", "Change Approved→Rejected (CORE)", "200", f"{response.status_code}", False)
    
    # STEP 4: Change status back to Pending
    print("\n[STEP 4] Change status to Pending...")
    url = f"{API_BASE}/leaves/{leave_id}/set-status"
    headers = {
        "Authorization": f"Bearer {superadmin_token}",
        "Content-Type": "application/json"
    }
    payload = {"status": "Pending"}
    
    response = requests.put(url, json=payload, headers=headers)
    print(f"   PUT /api/leaves/{leave_id}/set-status (Pending): {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        status = data.get("status")
        approver_email = data.get("approver_email")
        decided_at = data.get("decided_at")
        
        print(f"   Response: status={status}, approver_email={approver_email}, decided_at={decided_at}")
        
        passed = (status == "Pending" and 
                 approver_email is None and 
                 decided_at is None)
        
        add_result("4", "Change to Pending", 
                  "status='Pending', approver_email=null, decided_at=null",
                  f"status='{status}', approver_email={approver_email}, decided_at={decided_at}",
                  passed)
    else:
        print(f"❌ Failed to change to Pending: {response.text}")
        add_result("4", "Change to Pending", "200", f"{response.status_code}", False)
    
    # STEP 5: Invalid status test
    print("\n[STEP 5] Test invalid status...")
    url = f"{API_BASE}/leaves/{leave_id}/set-status"
    headers = {
        "Authorization": f"Bearer {superadmin_token}",
        "Content-Type": "application/json"
    }
    payload = {"status": "Bogus"}
    
    response = requests.put(url, json=payload, headers=headers)
    print(f"   PUT /api/leaves/{leave_id}/set-status (Bogus): {response.status_code}")
    
    passed = response.status_code == 400
    add_result("5", "Invalid status 'Bogus'", "400", f"{response.status_code}", passed)
    
    # STEP 6a: RBAC test - admin should get 403
    print("\n[STEP 6a] RBAC test: admin tries to set status...")
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    
    if admin_token:
        url = f"{API_BASE}/leaves/{leave_id}/set-status"
        headers = {
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json"
        }
        payload = {"status": "Approved"}
        
        response = requests.put(url, json=payload, headers=headers)
        print(f"   PUT /api/leaves/{leave_id}/set-status (as admin): {response.status_code}")
        
        passed = response.status_code == 403
        add_result("6a", "RBAC: admin tries set-status", "403", f"{response.status_code}", passed)
    else:
        add_result("6a", "RBAC: admin login", "200 with token", "Login failed", False)
    
    # STEP 6b: RBAC test - resource should get 403
    print("\n[STEP 6b] RBAC test: resource tries to set status...")
    url = f"{API_BASE}/leaves/{leave_id}/set-status"
    headers = {
        "Authorization": f"Bearer {resource_token}",
        "Content-Type": "application/json"
    }
    payload = {"status": "Approved"}
    
    response = requests.put(url, json=payload, headers=headers)
    print(f"   PUT /api/leaves/{leave_id}/set-status (as resource): {response.status_code}")
    
    passed = response.status_code == 403
    add_result("6b", "RBAC: resource tries set-status", "403", f"{response.status_code}", passed)
    
    # STEP 7: 404 test with non-existent leave ID
    print("\n[STEP 7] Test 404 with non-existent leave ID...")
    url = f"{API_BASE}/leaves/000000000000000000000000/set-status"
    headers = {
        "Authorization": f"Bearer {superadmin_token}",
        "Content-Type": "application/json"
    }
    payload = {"status": "Approved"}
    
    response = requests.put(url, json=payload, headers=headers)
    print(f"   PUT /api/leaves/000000000000000000000000/set-status: {response.status_code}")
    
    passed = response.status_code == 404
    add_result("7", "Non-existent leave ID", "404", f"{response.status_code}", passed)
    
    # CLEANUP: Delete the test leave
    print("\n[CLEANUP] Deleting test leave...")
    url = f"{API_BASE}/leaves/{leave_id}"
    headers = {
        "Authorization": f"Bearer {superadmin_token}"
    }
    
    response = requests.delete(url, headers=headers)
    print(f"   DELETE /api/leaves/{leave_id}: {response.status_code}")
    
    if response.status_code in [200, 204]:
        print("   ✅ Test leave deleted successfully")
    else:
        print(f"   ⚠️  Failed to delete test leave: {response.text}")
    
    # Print final results table
    print_results_table()

if __name__ == "__main__":
    main()
