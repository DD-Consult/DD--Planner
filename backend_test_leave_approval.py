#!/usr/bin/env python3
"""
Test the Time Off (leave) request → approval workflow in DD Planner.
Tests the new leave status workflow with Pending/Approved/Rejected states.
"""

import requests
import json
from datetime import datetime, date

# Configuration
BACKEND_URL = "https://ddplanner-fixes.preview.emergentagent.com"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"
RESOURCE_EMAIL = "qa_resource@test.com"
RESOURCE_PASSWORD = "Test@2026"

# Test results tracking
test_results = []
created_leave_ids = []

def log_test(test_name, passed, details=""):
    """Log test result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    test_results.append({
        "test": test_name,
        "passed": passed,
        "details": details
    })
    print(f"{status}: {test_name}")
    if details:
        print(f"  Details: {details}")

def login(email, password):
    """Login and return token."""
    response = requests.post(
        f"{BACKEND_URL}/api/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token")
    else:
        print(f"Login failed for {email}: {response.status_code} - {response.text}")
        return None

def test_resource_self_submit():
    """Test A: Resource self-submit → Pending"""
    print("\n=== TEST A: Resource self-submit → Pending ===")
    
    # Login as resource
    resource_token = login(RESOURCE_EMAIL, RESOURCE_PASSWORD)
    if not resource_token:
        log_test("A1. Resource login", False, "Failed to login as resource")
        return None
    log_test("A1. Resource login", True, "Successfully logged in as qa_resource@test.com")
    
    # Create leave
    headers = {"Authorization": f"Bearer {resource_token}", "Content-Type": "application/json"}
    leave_data = {
        "start_date": "2026-11-02",
        "end_date": "2026-11-06",
        "type": "Annual Leave",
        "notes": "QA pending test"
    }
    
    response = requests.post(f"{BACKEND_URL}/api/leaves", json=leave_data, headers=headers)
    
    if response.status_code == 200:
        leave = response.json()
        leave_id = leave.get("id")
        status = leave.get("status")
        
        if status == "Pending":
            log_test("A2. Create leave with Pending status", True, f"Leave created with status=Pending, id={leave_id}")
            created_leave_ids.append(leave_id)
            
            # Verify in GET /api/leaves
            response = requests.get(f"{BACKEND_URL}/api/leaves", headers=headers)
            if response.status_code == 200:
                leaves = response.json()
                found = any(lv.get("id") == leave_id and lv.get("status") == "Pending" for lv in leaves)
                log_test("A3. Verify leave appears in GET /api/leaves", found, 
                        f"Leave {leave_id} found with status=Pending" if found else "Leave not found")
            else:
                log_test("A3. Verify leave appears in GET /api/leaves", False, 
                        f"GET /api/leaves failed: {response.status_code}")
            
            return leave_id
        else:
            log_test("A2. Create leave with Pending status", False, 
                    f"Expected status=Pending, got status={status}")
            return None
    else:
        log_test("A2. Create leave with Pending status", False, 
                f"Failed to create leave: {response.status_code} - {response.text}")
        return None

def test_admin_create():
    """Test B: Admin create → Approved"""
    print("\n=== TEST B: Admin create → Approved ===")
    
    # Login as admin
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        log_test("B1. Admin login", False, "Failed to login as admin")
        return None
    log_test("B1. Admin login", True, "Successfully logged in as admin@test.com")
    
    # Get Bob Smith's resource_id
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.get(f"{BACKEND_URL}/api/resources", headers=headers)
    
    if response.status_code != 200:
        log_test("B2. Get resources", False, f"Failed to get resources: {response.status_code}")
        return None
    
    resources = response.json()
    bob_smith = next((r for r in resources if r.get("name") == "Bob Smith"), None)
    
    if not bob_smith:
        log_test("B2. Get Bob Smith resource", False, "Bob Smith resource not found")
        return None
    
    resource_id = bob_smith.get("id")
    log_test("B2. Get Bob Smith resource", True, f"Found Bob Smith with id={resource_id}")
    
    # Create leave as admin
    headers["Content-Type"] = "application/json"
    leave_data = {
        "resource_id": resource_id,
        "start_date": "2026-11-09",
        "end_date": "2026-11-11",
        "type": "Annual Leave"
    }
    
    response = requests.post(f"{BACKEND_URL}/api/leaves", json=leave_data, headers=headers)
    
    if response.status_code == 200:
        leave = response.json()
        leave_id = leave.get("id")
        status = leave.get("status")
        
        if status == "Approved":
            log_test("B3. Admin create leave with Approved status", True, 
                    f"Leave created with status=Approved, id={leave_id}")
            created_leave_ids.append(leave_id)
            return leave_id
        else:
            log_test("B3. Admin create leave with Approved status", False, 
                    f"Expected status=Approved, got status={status}")
            return None
    else:
        log_test("B3. Admin create leave with Approved status", False, 
                f"Failed to create leave: {response.status_code} - {response.text}")
        return None

def test_pending_queue(pending_leave_id):
    """Test C: Pending queue (admin only)"""
    print("\n=== TEST C: Pending queue (admin only) ===")
    
    # Login as admin
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        log_test("C1. Admin login", False, "Failed to login as admin")
        return
    
    # Get pending leaves as admin
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.get(f"{BACKEND_URL}/api/leaves/pending", headers=headers)
    
    if response.status_code == 200:
        pending_leaves = response.json()
        
        # Check if our pending leave is in the list
        found_leave = next((lv for lv in pending_leaves if lv.get("id") == pending_leave_id), None)
        
        if found_leave:
            has_resource_name = "resource_name" in found_leave
            resource_name = found_leave.get("resource_name", "")
            
            log_test("C2. GET /api/leaves/pending includes pending leave", True, 
                    f"Found leave {pending_leave_id} in pending queue")
            log_test("C3. Pending leave has resource_name field", has_resource_name, 
                    f"resource_name={resource_name}" if has_resource_name else "resource_name field missing")
        else:
            log_test("C2. GET /api/leaves/pending includes pending leave", False, 
                    f"Leave {pending_leave_id} not found in pending queue")
            log_test("C3. Pending leave has resource_name field", False, "Leave not found")
    else:
        log_test("C2. GET /api/leaves/pending (admin)", False, 
                f"Failed: {response.status_code} - {response.text}")
        log_test("C3. Pending leave has resource_name field", False, "Could not fetch pending leaves")
    
    # Try as resource (should be 403)
    resource_token = login(RESOURCE_EMAIL, RESOURCE_PASSWORD)
    if resource_token:
        headers = {"Authorization": f"Bearer {resource_token}"}
        response = requests.get(f"{BACKEND_URL}/api/leaves/pending", headers=headers)
        
        if response.status_code == 403:
            log_test("C4. GET /api/leaves/pending as resource returns 403", True, 
                    "Correctly returned 403 for non-admin")
        else:
            log_test("C4. GET /api/leaves/pending as resource returns 403", False, 
                    f"Expected 403, got {response.status_code}")
    else:
        log_test("C4. GET /api/leaves/pending as resource returns 403", False, 
                "Failed to login as resource")

def test_approve_reject(pending_leave_id):
    """Test D: Approve / Reject (admin only)"""
    print("\n=== TEST D: Approve / Reject (admin only) ===")
    
    # Login as admin
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        log_test("D1. Admin login", False, "Failed to login as admin")
        return
    
    headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    
    # D6: Approve the pending leave with note
    response = requests.put(
        f"{BACKEND_URL}/api/leaves/{pending_leave_id}/approve",
        json={"note": "Approved by QA"},
        headers=headers
    )
    
    if response.status_code == 200:
        leave = response.json()
        status = leave.get("status")
        approver_email = leave.get("approver_email")
        decided_at = leave.get("decided_at")
        decision_note = leave.get("decision_note")
        
        checks = [
            ("status == Approved", status == "Approved"),
            ("approver_email set", approver_email is not None),
            ("decided_at set", decided_at is not None),
            ("decision_note == 'Approved by QA'", decision_note == "Approved by QA")
        ]
        
        all_passed = all(check[1] for check in checks)
        details = ", ".join([f"{check[0]}: {check[1]}" for check in checks])
        
        log_test("D1. Approve leave with note", all_passed, details)
    else:
        log_test("D1. Approve leave with note", False, 
                f"Failed: {response.status_code} - {response.text}")
    
    # D7: Create another pending leave and reject it
    resource_token = login(RESOURCE_EMAIL, RESOURCE_PASSWORD)
    if resource_token:
        headers_resource = {"Authorization": f"Bearer {resource_token}", "Content-Type": "application/json"}
        leave_data = {
            "start_date": "2026-11-16",
            "end_date": "2026-11-18",
            "type": "Annual Leave",
            "notes": "QA reject test"
        }
        
        response = requests.post(f"{BACKEND_URL}/api/leaves", json=leave_data, headers=headers_resource)
        
        if response.status_code == 200:
            leave = response.json()
            pending_leave_id_2 = leave.get("id")
            created_leave_ids.append(pending_leave_id_2)
            
            log_test("D2. Create second pending leave", True, f"Created leave {pending_leave_id_2}")
            
            # Reject it as admin
            headers_admin = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
            response = requests.put(
                f"{BACKEND_URL}/api/leaves/{pending_leave_id_2}/reject",
                json={"note": "Clash with deadline"},
                headers=headers_admin
            )
            
            if response.status_code == 200:
                leave = response.json()
                status = leave.get("status")
                decision_note = leave.get("decision_note")
                
                checks = [
                    ("status == Rejected", status == "Rejected"),
                    ("decision_note set", decision_note == "Clash with deadline")
                ]
                
                all_passed = all(check[1] for check in checks)
                details = ", ".join([f"{check[0]}: {check[1]}" for check in checks])
                
                log_test("D3. Reject leave with note", all_passed, details)
            else:
                log_test("D3. Reject leave with note", False, 
                        f"Failed: {response.status_code} - {response.text}")
        else:
            log_test("D2. Create second pending leave", False, 
                    f"Failed: {response.status_code} - {response.text}")
            log_test("D3. Reject leave with note", False, "Could not create second leave")
    else:
        log_test("D2. Create second pending leave", False, "Failed to login as resource")
        log_test("D3. Reject leave with note", False, "Could not login as resource")
    
    # D8: Try approve as resource (should be 403)
    if resource_token:
        headers_resource = {"Authorization": f"Bearer {resource_token}", "Content-Type": "application/json"}
        response = requests.put(
            f"{BACKEND_URL}/api/leaves/{pending_leave_id}/approve",
            json={},
            headers=headers_resource
        )
        
        if response.status_code == 403:
            log_test("D4. Approve as resource returns 403", True, "Correctly returned 403 for non-admin")
        else:
            log_test("D4. Approve as resource returns 403", False, 
                    f"Expected 403, got {response.status_code}")
    else:
        log_test("D4. Approve as resource returns 403", False, "Failed to login as resource")
    
    # D9: Approve/reject bogus id (should be 404)
    headers_admin = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    response = requests.put(
        f"{BACKEND_URL}/api/leaves/000000000000000000000000/approve",
        json={},
        headers=headers_admin
    )
    
    if response.status_code == 404:
        log_test("D5. Approve bogus id returns 404", True, "Correctly returned 404")
    else:
        log_test("D5. Approve bogus id returns 404", False, 
                f"Expected 404, got {response.status_code}")
    
    # D10: Approve with no body (should work)
    # Create another pending leave
    if resource_token:
        headers_resource = {"Authorization": f"Bearer {resource_token}", "Content-Type": "application/json"}
        leave_data = {
            "start_date": "2026-11-23",
            "end_date": "2026-11-25",
            "type": "Annual Leave"
        }
        
        response = requests.post(f"{BACKEND_URL}/api/leaves", json=leave_data, headers=headers_resource)
        
        if response.status_code == 200:
            leave = response.json()
            pending_leave_id_3 = leave.get("id")
            created_leave_ids.append(pending_leave_id_3)
            
            # Approve with no body
            headers_admin = {"Authorization": f"Bearer {admin_token}"}
            response = requests.put(
                f"{BACKEND_URL}/api/leaves/{pending_leave_id_3}/approve",
                headers=headers_admin
            )
            
            if response.status_code == 200:
                log_test("D6. Approve with no body works", True, "Approved without 422 error")
            else:
                log_test("D6. Approve with no body works", False, 
                        f"Expected 200, got {response.status_code}")
        else:
            log_test("D6. Approve with no body works", False, "Could not create third leave")
    else:
        log_test("D6. Approve with no body works", False, "Failed to login as resource")

def test_accounting_gating():
    """Test E: Accounting gating (CRITICAL)"""
    print("\n=== TEST E: Accounting gating (CRITICAL) ===")
    
    # Login as resource
    resource_token = login(RESOURCE_EMAIL, RESOURCE_PASSWORD)
    if not resource_token:
        log_test("E1. Resource login", False, "Failed to login as resource")
        return
    
    # E11: Create a PENDING leave for Bob Smith (2026-12-07 to 2026-12-11)
    headers_resource = {"Authorization": f"Bearer {resource_token}", "Content-Type": "application/json"}
    leave_data = {
        "start_date": "2026-12-07",
        "end_date": "2026-12-11",
        "type": "Annual Leave",
        "notes": "QA accounting test - PENDING"
    }
    
    response = requests.post(f"{BACKEND_URL}/api/leaves", json=leave_data, headers=headers_resource)
    
    if response.status_code != 200:
        log_test("E1. Create PENDING leave for accounting test", False, 
                f"Failed: {response.status_code} - {response.text}")
        return
    
    leave = response.json()
    pending_leave_id = leave.get("id")
    created_leave_ids.append(pending_leave_id)
    
    log_test("E1. Create PENDING leave for accounting test", True, 
            f"Created PENDING leave {pending_leave_id} for 2026-12-07 to 2026-12-11")
    
    # Login as admin to check capacity
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        log_test("E2. Admin login", False, "Failed to login as admin")
        return
    
    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    
    # Get capacity report BEFORE approval
    response = requests.get(
        f"{BACKEND_URL}/api/reports/capacity?start_date=2026-12-07&end_date=2026-12-11",
        headers=headers_admin
    )
    
    if response.status_code != 200:
        log_test("E2. GET capacity report (before approval)", False, 
                f"Failed: {response.status_code} - {response.text}")
        return
    
    capacity_before = response.json()
    
    # Find Bob Smith's row
    bob_row_before = next((r for r in capacity_before if r.get("resource_name") == "Bob Smith"), None)
    
    if not bob_row_before:
        log_test("E2. GET capacity report (before approval)", False, "Bob Smith not found in capacity report")
        return
    
    # Check days in the window (2026-12-07 to 2026-12-11)
    days_before = bob_row_before.get("days", [])
    leave_days_before = [d for d in days_before if d.get("date") >= "2026-12-07" and d.get("date") <= "2026-12-11"]
    
    # PENDING leave should NOT block capacity
    on_leave_before = any(d.get("on_leave") or d.get("color") == "leave" for d in leave_days_before)
    
    log_test("E2. PENDING leave does NOT block capacity", not on_leave_before, 
            f"Days 2026-12-07 to 2026-12-11: on_leave={on_leave_before} (should be False)")
    
    # E12: Now APPROVE the leave
    response = requests.put(
        f"{BACKEND_URL}/api/leaves/{pending_leave_id}/approve",
        json={"note": "Approved for accounting test"},
        headers=headers_admin
    )
    
    if response.status_code != 200:
        log_test("E3. Approve leave", False, f"Failed: {response.status_code} - {response.text}")
        return
    
    log_test("E3. Approve leave", True, f"Approved leave {pending_leave_id}")
    
    # Get capacity report AFTER approval
    response = requests.get(
        f"{BACKEND_URL}/api/reports/capacity?start_date=2026-12-07&end_date=2026-12-11",
        headers=headers_admin
    )
    
    if response.status_code != 200:
        log_test("E4. GET capacity report (after approval)", False, 
                f"Failed: {response.status_code} - {response.text}")
        return
    
    capacity_after = response.json()
    
    # Find Bob Smith's row
    bob_row_after = next((r for r in capacity_after if r.get("resource_name") == "Bob Smith"), None)
    
    if not bob_row_after:
        log_test("E4. GET capacity report (after approval)", False, "Bob Smith not found in capacity report")
        return
    
    # Check days in the window (2026-12-07 to 2026-12-11)
    days_after = bob_row_after.get("days", [])
    leave_days_after = [d for d in days_after if d.get("date") >= "2026-12-07" and d.get("date") <= "2026-12-11"]
    
    # APPROVED leave SHOULD block capacity
    on_leave_after = any(d.get("on_leave") or d.get("color") == "leave" for d in leave_days_after)
    
    log_test("E4. APPROVED leave DOES block capacity", on_leave_after, 
            f"Days 2026-12-07 to 2026-12-11: on_leave={on_leave_after} (should be True)")
    
    # E13: Optional - Timesheet auto-fill
    # Find a Monday that overlaps with an approved leave
    # We'll use 2026-12-07 (Monday)
    response = requests.post(
        f"{BACKEND_URL}/api/timesheets/auto-fill?week_start=2026-12-07",
        headers=headers_resource
    )
    
    if response.status_code == 200:
        log_test("E5. Timesheet auto-fill with approved leave", True, 
                "Auto-fill completed without error (200)")
    else:
        log_test("E5. Timesheet auto-fill with approved leave", False, 
                f"Failed: {response.status_code} - {response.text}")

def cleanup():
    """Clean up created leaves."""
    print("\n=== CLEANUP ===")
    
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        print("Failed to login as admin for cleanup")
        return
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    deleted_count = 0
    for leave_id in created_leave_ids:
        response = requests.delete(f"{BACKEND_URL}/api/leaves/{leave_id}", headers=headers)
        if response.status_code == 200:
            deleted_count += 1
            print(f"Deleted leave {leave_id}")
        else:
            print(f"Failed to delete leave {leave_id}: {response.status_code}")
    
    print(f"Cleanup complete: Deleted {deleted_count}/{len(created_leave_ids)} leaves")

def print_summary():
    """Print test summary."""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for t in test_results if t["passed"])
    total = len(test_results)
    
    print(f"\nTotal: {passed}/{total} tests passed ({100*passed//total}% success rate)\n")
    
    # Group by test section
    sections = {
        "A": "Resource self-submit → Pending",
        "B": "Admin create → Approved",
        "C": "Pending queue (admin only)",
        "D": "Approve / Reject (admin only)",
        "E": "Accounting gating (CRITICAL)"
    }
    
    for section_key, section_name in sections.items():
        print(f"\n{section_key}. {section_name}:")
        section_tests = [t for t in test_results if t["test"].startswith(section_key)]
        for test in section_tests:
            status = "✅" if test["passed"] else "❌"
            print(f"  {status} {test['test']}")
            if test["details"]:
                print(f"      {test['details']}")
    
    # Print failures
    failures = [t for t in test_results if not t["passed"]]
    if failures:
        print("\n" + "="*80)
        print("FAILURES")
        print("="*80)
        for test in failures:
            print(f"\n❌ {test['test']}")
            print(f"   {test['details']}")

def main():
    """Main test execution."""
    print("="*80)
    print("DD PLANNER - TIME OFF (LEAVE) APPROVAL WORKFLOW TEST")
    print("="*80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Admin: {ADMIN_EMAIL}")
    print(f"Resource: {RESOURCE_EMAIL}")
    print("="*80)
    
    try:
        # Test A: Resource self-submit → Pending
        pending_leave_id = test_resource_self_submit()
        
        # Test B: Admin create → Approved
        admin_leave_id = test_admin_create()
        
        # Test C: Pending queue (admin only)
        if pending_leave_id:
            test_pending_queue(pending_leave_id)
        else:
            print("\n⚠️ Skipping Test C: No pending leave created")
        
        # Test D: Approve / Reject (admin only)
        if pending_leave_id:
            test_approve_reject(pending_leave_id)
        else:
            print("\n⚠️ Skipping Test D: No pending leave created")
        
        # Test E: Accounting gating (CRITICAL)
        test_accounting_gating()
        
    finally:
        # Cleanup
        cleanup()
        
        # Print summary
        print_summary()

if __name__ == "__main__":
    main()
