#!/usr/bin/env python3
"""
Verify BUG FIX in DD Planner Time Off (leave) approval workflow.

BUG: Leave requests were being AUTO-APPROVED (unexpected).
FIX: ALL time-off requests (including admin/super_admin) must start as "Pending"
     and require explicit approval by SUPER_ADMIN only.

Test credentials:
- admin@test.com / admin123 (role admin)
- qa_resource@test.com / Test@2026 (role resource)
- superadmin@test.com / Super@2026 (role super_admin)

Backend URL: https://proposal-approve.preview.emergentagent.com/api
Auth: OAuth2 form data (username & password fields)
"""

import requests
import json
from datetime import datetime

# Configuration
BACKEND_URL = "https://proposal-approve.preview.emergentagent.com"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"
RESOURCE_EMAIL = "qa_resource@test.com"
RESOURCE_PASSWORD = "Test@2026"
SUPERADMIN_EMAIL = "superadmin@test.com"
SUPERADMIN_PASSWORD = "Super@2026"

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

def test_step1_admin_self_request():
    """
    STEP 1: ADMIN self-request is NOT auto-approved
    - Login as admin@test.com
    - Get a resource_id from GET /api/resources (pick first)
    - POST /api/leaves with resource_id, dates, type, notes
    - ASSERT status == "Pending" (NOT "Approved")
    - ASSERT created_at present and non-null
    - ASSERT submitted_by == "admin@test.com"
    """
    print("\n=== STEP 1: ADMIN self-request is NOT auto-approved ===")
    
    # Login as admin
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        log_test("1.1 Admin login", False, "Failed to login as admin")
        return None
    log_test("1.1 Admin login", True, "Successfully logged in as admin@test.com")
    
    # Get resources
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.get(f"{BACKEND_URL}/api/resources", headers=headers)
    
    if response.status_code != 200:
        log_test("1.2 Get resources", False, f"Failed: {response.status_code}")
        return None
    
    resources = response.json()
    if not resources:
        log_test("1.2 Get resources", False, "No resources found")
        return None
    
    resource_id = resources[0].get("id")
    log_test("1.2 Get resources", True, f"Found resource_id: {resource_id}")
    
    # Create leave
    headers["Content-Type"] = "application/json"
    leave_data = {
        "resource_id": resource_id,
        "start_date": "2026-12-01",
        "end_date": "2026-12-03",
        "type": "Vacation",
        "notes": "Admin test leave"
    }
    
    response = requests.post(f"{BACKEND_URL}/api/leaves", json=leave_data, headers=headers)
    
    if response.status_code != 200:
        log_test("1.3 Create leave", False, f"Failed: {response.status_code} - {response.text}")
        return None
    
    leave = response.json()
    leave_id = leave.get("id")
    status = leave.get("status")
    created_at = leave.get("created_at")
    submitted_by = leave.get("submitted_by")
    
    created_leave_ids.append(leave_id)
    
    # CRITICAL ASSERTION: Status must be "Pending", NOT "Approved"
    if status == "Pending":
        log_test("1.3 Leave status is Pending (NOT auto-approved)", True, 
                f"✅✅✅ BUG FIX VERIFIED: Admin-created leave has status=Pending (leave_id={leave_id})")
    else:
        log_test("1.3 Leave status is Pending (NOT auto-approved)", False, 
                f"❌❌❌ BUG STILL EXISTS: Expected status=Pending, got status={status}")
    
    # Check metadata fields
    if created_at:
        log_test("1.4 created_at field present", True, f"created_at={created_at}")
    else:
        log_test("1.4 created_at field present", False, "created_at is null or missing")
    
    if submitted_by == ADMIN_EMAIL:
        log_test("1.5 submitted_by field correct", True, f"submitted_by={submitted_by}")
    else:
        log_test("1.5 submitted_by field correct", False, 
                f"Expected submitted_by={ADMIN_EMAIL}, got {submitted_by}")
    
    return leave_id

def test_step2_resource_self_request():
    """
    STEP 2: RESOURCE self-request is Pending
    - Login as qa_resource@test.com
    - POST /api/leaves (no resource_id - backend fills own)
    - ASSERT status == "Pending"
    - ASSERT submitted_by == "qa_resource@test.com"
    - ASSERT created_at present
    """
    print("\n=== STEP 2: RESOURCE self-request is Pending ===")
    
    # Login as resource
    resource_token = login(RESOURCE_EMAIL, RESOURCE_PASSWORD)
    if not resource_token:
        log_test("2.1 Resource login", False, "Failed to login as resource")
        return None
    log_test("2.1 Resource login", True, "Successfully logged in as qa_resource@test.com")
    
    # Create leave
    headers = {"Authorization": f"Bearer {resource_token}", "Content-Type": "application/json"}
    leave_data = {
        "start_date": "2026-12-10",
        "end_date": "2026-12-11",
        "type": "Sick",
        "notes": "resource test"
    }
    
    response = requests.post(f"{BACKEND_URL}/api/leaves", json=leave_data, headers=headers)
    
    if response.status_code != 200:
        log_test("2.2 Create leave", False, f"Failed: {response.status_code} - {response.text}")
        return None
    
    leave = response.json()
    leave_id = leave.get("id")
    status = leave.get("status")
    created_at = leave.get("created_at")
    submitted_by = leave.get("submitted_by")
    
    created_leave_ids.append(leave_id)
    
    # Check status
    if status == "Pending":
        log_test("2.2 Leave status is Pending", True, f"status=Pending (leave_id={leave_id})")
    else:
        log_test("2.2 Leave status is Pending", False, f"Expected status=Pending, got {status}")
    
    # Check metadata
    if submitted_by == RESOURCE_EMAIL:
        log_test("2.3 submitted_by field correct", True, f"submitted_by={submitted_by}")
    else:
        log_test("2.3 submitted_by field correct", False, 
                f"Expected submitted_by={RESOURCE_EMAIL}, got {submitted_by}")
    
    if created_at:
        log_test("2.4 created_at field present", True, f"created_at={created_at}")
    else:
        log_test("2.4 created_at field present", False, "created_at is null or missing")
    
    return leave_id

def test_step3_admin_cannot_approve(leave_id):
    """
    STEP 3: ADMIN CANNOT approve (only super_admin can)
    - Login as admin@test.com
    - PUT /api/leaves/{leave_id}/approve
    - ASSERT 403 (admin is not super_admin)
    """
    print("\n=== STEP 3: ADMIN CANNOT approve (only super_admin can) ===")
    
    # Login as admin
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        log_test("3.1 Admin login", False, "Failed to login as admin")
        return
    
    # Try to approve
    headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    response = requests.put(
        f"{BACKEND_URL}/api/leaves/{leave_id}/approve",
        json={"note": "ok"},
        headers=headers
    )
    
    if response.status_code == 403:
        log_test("3.1 Admin approve returns 403", True, 
                "✅ Correctly blocked: Only super_admin can approve")
    else:
        log_test("3.1 Admin approve returns 403", False, 
                f"Expected 403, got {response.status_code} - {response.text}")

def test_step4_superadmin_pending_queue_and_approve(leave_id_1, leave_id_2):
    """
    STEP 4: SUPER_ADMIN pending queue + approve
    - Login as superadmin@test.com
    - GET /api/leaves/pending
    - ASSERT 200 and includes the two pending leaves
    - ASSERT each has resource_name, created_at, submitted_by
    - PUT /api/leaves/{leave_id_1}/approve with note
    - ASSERT 200, status=="Approved", approver_email=="superadmin@test.com", decided_at present
    """
    print("\n=== STEP 4: SUPER_ADMIN pending queue + approve ===")
    
    # Login as super_admin
    superadmin_token = login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)
    if not superadmin_token:
        log_test("4.1 Super_admin login", False, "Failed to login as super_admin")
        return
    log_test("4.1 Super_admin login", True, "Successfully logged in as superadmin@test.com")
    
    # Get pending leaves
    headers = {"Authorization": f"Bearer {superadmin_token}"}
    response = requests.get(f"{BACKEND_URL}/api/leaves/pending", headers=headers)
    
    if response.status_code != 200:
        log_test("4.2 GET /api/leaves/pending", False, f"Failed: {response.status_code} - {response.text}")
        return
    
    pending_leaves = response.json()
    log_test("4.2 GET /api/leaves/pending", True, f"Found {len(pending_leaves)} pending leaves")
    
    # Check if our two leaves are in the list
    leave_ids = [lv.get("id") for lv in pending_leaves]
    found_1 = leave_id_1 in leave_ids
    found_2 = leave_id_2 in leave_ids
    
    if found_1 and found_2:
        log_test("4.3 Pending queue includes both test leaves", True, 
                f"Found leave_id_1={leave_id_1} and leave_id_2={leave_id_2}")
    else:
        log_test("4.3 Pending queue includes both test leaves", False, 
                f"Missing leaves: found_1={found_1}, found_2={found_2}")
    
    # Check fields on first leave
    leave_1 = next((lv for lv in pending_leaves if lv.get("id") == leave_id_1), None)
    if leave_1:
        has_resource_name = "resource_name" in leave_1
        has_created_at = "created_at" in leave_1
        has_submitted_by = "submitted_by" in leave_1
        
        if has_resource_name and has_created_at and has_submitted_by:
            log_test("4.4 Pending leave has required fields", True, 
                    f"resource_name={leave_1.get('resource_name')}, created_at={leave_1.get('created_at')}, submitted_by={leave_1.get('submitted_by')}")
        else:
            log_test("4.4 Pending leave has required fields", False, 
                    f"Missing fields: resource_name={has_resource_name}, created_at={has_created_at}, submitted_by={has_submitted_by}")
    else:
        log_test("4.4 Pending leave has required fields", False, "Leave not found in pending queue")
    
    # Approve leave_id_1
    headers["Content-Type"] = "application/json"
    response = requests.put(
        f"{BACKEND_URL}/api/leaves/{leave_id_1}/approve",
        json={"note": "ok"},
        headers=headers
    )
    
    if response.status_code != 200:
        log_test("4.5 Approve leave", False, f"Failed: {response.status_code} - {response.text}")
        return
    
    approved_leave = response.json()
    status = approved_leave.get("status")
    approver_email = approved_leave.get("approver_email")
    decided_at = approved_leave.get("decided_at")
    
    checks = [
        ("status == Approved", status == "Approved"),
        ("approver_email == superadmin@test.com", approver_email == SUPERADMIN_EMAIL),
        ("decided_at present", decided_at is not None)
    ]
    
    all_passed = all(check[1] for check in checks)
    details = ", ".join([f"{check[0]}: {check[1]}" for check in checks])
    
    log_test("4.5 Approve leave with correct fields", all_passed, details)

def test_step5_superadmin_reject(leave_id):
    """
    STEP 5: SUPER_ADMIN reject
    - PUT /api/leaves/{leave_id}/reject with note
    - ASSERT 200, status=="Rejected"
    """
    print("\n=== STEP 5: SUPER_ADMIN reject ===")
    
    # Login as super_admin
    superadmin_token = login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)
    if not superadmin_token:
        log_test("5.1 Super_admin login", False, "Failed to login as super_admin")
        return
    
    # Reject leave
    headers = {"Authorization": f"Bearer {superadmin_token}", "Content-Type": "application/json"}
    response = requests.put(
        f"{BACKEND_URL}/api/leaves/{leave_id}/reject",
        json={"note": "not now"},
        headers=headers
    )
    
    if response.status_code != 200:
        log_test("5.1 Reject leave", False, f"Failed: {response.status_code} - {response.text}")
        return
    
    rejected_leave = response.json()
    status = rejected_leave.get("status")
    
    if status == "Rejected":
        log_test("5.1 Reject leave with status=Rejected", True, f"status={status}")
    else:
        log_test("5.1 Reject leave with status=Rejected", False, f"Expected status=Rejected, got {status}")

def test_step6_resource_cannot_approve():
    """
    STEP 6: RESOURCE cannot approve
    - Login as qa_resource@test.com
    - Create a pending leave
    - Try to approve it
    - ASSERT 403
    """
    print("\n=== STEP 6: RESOURCE cannot approve ===")
    
    # Login as resource
    resource_token = login(RESOURCE_EMAIL, RESOURCE_PASSWORD)
    if not resource_token:
        log_test("6.1 Resource login", False, "Failed to login as resource")
        return
    
    # Create a pending leave
    headers = {"Authorization": f"Bearer {resource_token}", "Content-Type": "application/json"}
    leave_data = {
        "start_date": "2026-12-15",
        "end_date": "2026-12-16",
        "type": "Sick",
        "notes": "test for resource approve"
    }
    
    response = requests.post(f"{BACKEND_URL}/api/leaves", json=leave_data, headers=headers)
    
    if response.status_code != 200:
        log_test("6.1 Create leave", False, f"Failed: {response.status_code} - {response.text}")
        return
    
    leave = response.json()
    leave_id = leave.get("id")
    created_leave_ids.append(leave_id)
    
    # Try to approve
    response = requests.put(
        f"{BACKEND_URL}/api/leaves/{leave_id}/approve",
        json={"note": "self-approve"},
        headers=headers
    )
    
    if response.status_code == 403:
        log_test("6.2 Resource approve returns 403", True, 
                "✅ Correctly blocked: Only super_admin can approve")
    else:
        log_test("6.2 Resource approve returns 403", False, 
                f"Expected 403, got {response.status_code} - {response.text}")

def test_step7_get_leaves_has_metadata():
    """
    STEP 7: GET /api/leaves returns created_at and submitted_by
    - Login as admin
    - GET /api/leaves
    - ASSERT entries have created_at and submitted_by fields
    """
    print("\n=== STEP 7: GET /api/leaves returns metadata fields ===")
    
    # Login as admin
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        log_test("7.1 Admin login", False, "Failed to login as admin")
        return
    
    # Get leaves
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.get(f"{BACKEND_URL}/api/leaves", headers=headers)
    
    if response.status_code != 200:
        log_test("7.1 GET /api/leaves", False, f"Failed: {response.status_code} - {response.text}")
        return
    
    leaves = response.json()
    
    if not leaves:
        log_test("7.1 GET /api/leaves", False, "No leaves found")
        return
    
    log_test("7.1 GET /api/leaves", True, f"Found {len(leaves)} leaves")
    
    # Check if our test leaves have the metadata fields
    test_leaves = [lv for lv in leaves if lv.get("id") in created_leave_ids]
    
    if not test_leaves:
        log_test("7.2 Test leaves have metadata fields", False, "Test leaves not found in response")
        return
    
    all_have_created_at = all("created_at" in lv for lv in test_leaves)
    all_have_submitted_by = all("submitted_by" in lv for lv in test_leaves)
    
    if all_have_created_at and all_have_submitted_by:
        log_test("7.2 Test leaves have metadata fields", True, 
                f"All {len(test_leaves)} test leaves have created_at and submitted_by")
    else:
        log_test("7.2 Test leaves have metadata fields", False, 
                f"Missing fields: created_at={all_have_created_at}, submitted_by={all_have_submitted_by}")

def cleanup():
    """Clean up created leaves."""
    print("\n=== CLEANUP ===")
    
    superadmin_token = login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)
    if not superadmin_token:
        print("Failed to login as super_admin for cleanup")
        return
    
    headers = {"Authorization": f"Bearer {superadmin_token}"}
    
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
    print("TEST SUMMARY - TIME OFF APPROVAL BUG FIX VERIFICATION")
    print("="*80)
    
    passed = sum(1 for t in test_results if t["passed"])
    total = len(test_results)
    
    print(f"\nTotal: {passed}/{total} tests passed ({100*passed//total if total > 0 else 0}% success rate)\n")
    
    # Print all results
    for test in test_results:
        status = "✅" if test["passed"] else "❌"
        print(f"{status} {test['test']}")
        if test["details"]:
            print(f"    {test['details']}")
    
    # Print failures
    failures = [t for t in test_results if not t["passed"]]
    if failures:
        print("\n" + "="*80)
        print("FAILURES")
        print("="*80)
        for test in failures:
            print(f"\n❌ {test['test']}")
            print(f"   {test['details']}")
    else:
        print("\n" + "="*80)
        print("✅✅✅ ALL TESTS PASSED - BUG FIX VERIFIED ✅✅✅")
        print("="*80)

def main():
    """Main test execution."""
    print("="*80)
    print("DD PLANNER - TIME OFF APPROVAL BUG FIX VERIFICATION")
    print("="*80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Admin: {ADMIN_EMAIL}")
    print(f"Resource: {RESOURCE_EMAIL}")
    print(f"Super Admin: {SUPERADMIN_EMAIL}")
    print("="*80)
    
    try:
        # STEP 1: Admin self-request is NOT auto-approved
        leave_id_1 = test_step1_admin_self_request()
        
        # STEP 2: Resource self-request is Pending
        leave_id_2 = test_step2_resource_self_request()
        
        # STEP 3: Admin CANNOT approve
        if leave_id_1:
            test_step3_admin_cannot_approve(leave_id_1)
        else:
            print("\n⚠️ Skipping STEP 3: No admin leave created")
        
        # STEP 4: Super_admin pending queue + approve
        if leave_id_1 and leave_id_2:
            test_step4_superadmin_pending_queue_and_approve(leave_id_1, leave_id_2)
        else:
            print("\n⚠️ Skipping STEP 4: Missing leaves")
        
        # STEP 5: Super_admin reject
        if leave_id_2:
            test_step5_superadmin_reject(leave_id_2)
        else:
            print("\n⚠️ Skipping STEP 5: No resource leave created")
        
        # STEP 6: Resource cannot approve
        test_step6_resource_cannot_approve()
        
        # STEP 7: GET /api/leaves has metadata
        test_step7_get_leaves_has_metadata()
        
    finally:
        # Cleanup
        cleanup()
        
        # Print summary
        print_summary()

if __name__ == "__main__":
    main()
