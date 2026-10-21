#!/usr/bin/env python3
"""
Backend Test: Super Admin Leave Status Change Feature
Tests the NEW capability for super_admin to CHANGE the status of an ALREADY-DECIDED leave
via PUT /api/leaves/{id}/set-status

Review Request Steps:
1. SETUP: Login resource, create leave (should be Pending), save id
2. Login superadmin, approve via set-status → ASSERT 200, status=Approved, approver_email, decided_at
3. CHANGE AN APPROVED ONE (core ask): set-status to Rejected → ASSERT 200, status=Rejected, decision_note
4. RE-OPEN: set-status to Pending → ASSERT 200, status=Pending, approver_email=null, decided_at=null
5. CAPACITY EFFECT: Set to Approved, check capacity (on_leave=true), set to Rejected, check capacity (on_leave=false)
6. VALIDATION: set-status with invalid status → ASSERT 400
7. RBAC: admin and resource try set-status → ASSERT 403
8. 404: set-status on non-existent leave → ASSERT 404
"""

import requests
import sys
from datetime import datetime, timedelta

# Configuration
BASE_URL = "https://proposal-approve.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"

# Test credentials
RESOURCE_EMAIL = "qa_resource@test.com"
RESOURCE_PASSWORD = "Test@2026"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"
SUPERADMIN_EMAIL = "superadmin@test.com"
SUPERADMIN_PASSWORD = "Super@2026"

# Test counters
tests_passed = 0
tests_failed = 0

def log_test(test_name, passed, details=""):
    global tests_passed, tests_failed
    if passed:
        tests_passed += 1
        print(f"✅ PASS: {test_name}")
        if details:
            print(f"   {details}")
    else:
        tests_failed += 1
        print(f"❌ FAIL: {test_name}")
        if details:
            print(f"   {details}")

def login(email, password):
    """Login and return access token and user data"""
    response = requests.post(
        f"{API_BASE}/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if response.status_code == 200:
        data = response.json()
        return data["access_token"], data.get("user", {})
    else:
        print(f"❌ Login failed for {email}: {response.status_code} {response.text}")
        return None, None

def main():
    print("=" * 80)
    print("BACKEND TEST: Super Admin Leave Status Change Feature")
    print("=" * 80)
    print()

    # Calculate test dates (future dates to avoid conflicts)
    start_date = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    end_date = (datetime.now() + timedelta(days=12)).strftime("%Y-%m-%d")
    
    print(f"Test dates: {start_date} to {end_date}")
    print()

    # ========================================================================
    # STEP 1: SETUP - Login resource, create leave (should be Pending)
    # ========================================================================
    print("STEP 1: SETUP - Create leave as resource")
    print("-" * 80)
    
    resource_token, resource_user = login(RESOURCE_EMAIL, RESOURCE_PASSWORD)
    if not resource_token:
        print("❌ CRITICAL: Failed to login as resource")
        sys.exit(1)
    
    resource_id = resource_user.get("resource_id")
    if not resource_id:
        print("❌ CRITICAL: Failed to get resource_id from user data")
        sys.exit(1)
    
    print(f"Resource ID: {resource_id}")
    
    # Create leave request
    create_payload = {
        "resource_id": resource_id,
        "start_date": start_date,
        "end_date": end_date,
        "type": "Vacation",
        "notes": "QA test for set-status feature"
    }
    
    response = requests.post(
        f"{API_BASE}/leaves",
        json=create_payload,
        headers={"Authorization": f"Bearer {resource_token}"}
    )
    
    if response.status_code != 200:
        print(f"❌ CRITICAL: Failed to create leave: {response.status_code} {response.text}")
        sys.exit(1)
    
    leave_data = response.json()
    leave_id = leave_data["id"]
    
    log_test(
        "Create leave request",
        leave_data["status"] == "Pending",
        f"Leave ID: {leave_id}, Status: {leave_data['status']}"
    )
    
    print()

    # ========================================================================
    # STEP 2: Login superadmin, approve via set-status
    # ========================================================================
    print("STEP 2: Approve leave via set-status (superadmin)")
    print("-" * 80)
    
    superadmin_token, _ = login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)
    if not superadmin_token:
        print("❌ CRITICAL: Failed to login as superadmin")
        sys.exit(1)
    
    response = requests.put(
        f"{API_BASE}/leaves/{leave_id}/set-status",
        json={"status": "Approved"},
        headers={"Authorization": f"Bearer {superadmin_token}"}
    )
    
    log_test(
        "set-status returns 200",
        response.status_code == 200,
        f"Status code: {response.status_code}"
    )
    
    if response.status_code == 200:
        leave_data = response.json()
        log_test(
            "Status is Approved",
            leave_data["status"] == "Approved",
            f"Status: {leave_data['status']}"
        )
        log_test(
            "approver_email is set",
            leave_data.get("approver_email") == SUPERADMIN_EMAIL,
            f"Approver: {leave_data.get('approver_email')}"
        )
        log_test(
            "decided_at is present",
            leave_data.get("decided_at") is not None,
            f"Decided at: {leave_data.get('decided_at')}"
        )
    
    print()

    # ========================================================================
    # STEP 3: CHANGE AN APPROVED ONE (core ask) - set-status to Rejected
    # ========================================================================
    print("STEP 3: CHANGE AN APPROVED LEAVE to Rejected (CORE TEST)")
    print("-" * 80)
    
    response = requests.put(
        f"{API_BASE}/leaves/{leave_id}/set-status",
        json={"status": "Rejected", "note": "revoked by QA"},
        headers={"Authorization": f"Bearer {superadmin_token}"}
    )
    
    log_test(
        "set-status to Rejected returns 200",
        response.status_code == 200,
        f"Status code: {response.status_code}"
    )
    
    if response.status_code == 200:
        leave_data = response.json()
        log_test(
            "Status is Rejected",
            leave_data["status"] == "Rejected",
            f"Status: {leave_data['status']}"
        )
        log_test(
            "decision_note is set",
            leave_data.get("decision_note") == "revoked by QA",
            f"Decision note: {leave_data.get('decision_note')}"
        )
        log_test(
            "approver_email is still set",
            leave_data.get("approver_email") == SUPERADMIN_EMAIL,
            f"Approver: {leave_data.get('approver_email')}"
        )
    
    print()

    # ========================================================================
    # STEP 4: RE-OPEN - set-status to Pending (should clear approver/decided_at)
    # ========================================================================
    print("STEP 4: RE-OPEN leave by setting status to Pending")
    print("-" * 80)
    
    response = requests.put(
        f"{API_BASE}/leaves/{leave_id}/set-status",
        json={"status": "Pending"},
        headers={"Authorization": f"Bearer {superadmin_token}"}
    )
    
    log_test(
        "set-status to Pending returns 200",
        response.status_code == 200,
        f"Status code: {response.status_code}"
    )
    
    if response.status_code == 200:
        leave_data = response.json()
        log_test(
            "Status is Pending",
            leave_data["status"] == "Pending",
            f"Status: {leave_data['status']}"
        )
        log_test(
            "approver_email is cleared (null)",
            leave_data.get("approver_email") is None,
            f"Approver: {leave_data.get('approver_email')}"
        )
        log_test(
            "decided_at is cleared (null)",
            leave_data.get("decided_at") is None,
            f"Decided at: {leave_data.get('decided_at')}"
        )
    
    print()

    # ========================================================================
    # STEP 5: CAPACITY EFFECT - Approve, check capacity, Reject, check capacity
    # ========================================================================
    print("STEP 5: CAPACITY EFFECT - Verify capacity changes with status")
    print("-" * 80)
    
    # First, approve the leave
    response = requests.put(
        f"{API_BASE}/leaves/{leave_id}/set-status",
        json={"status": "Approved"},
        headers={"Authorization": f"Bearer {superadmin_token}"}
    )
    
    log_test(
        "Re-approve leave for capacity test",
        response.status_code == 200,
        f"Status code: {response.status_code}"
    )
    
    # Check capacity - should show on_leave=true
    response = requests.get(
        f"{API_BASE}/reports/capacity",
        params={"start_date": start_date, "end_date": end_date},
        headers={"Authorization": f"Bearer {superadmin_token}"}
    )
    
    log_test(
        "Capacity endpoint returns 200",
        response.status_code == 200,
        f"Status code: {response.status_code}"
    )
    
    if response.status_code == 200:
        capacity_data = response.json()
        # Find the resource in the capacity report
        resource_found = False
        on_leave_when_approved = False
        
        for resource in capacity_data.get("resources", []):
            if resource["resource_id"] == resource_id:
                resource_found = True
                # Check if any day in the range shows on_leave=true
                for day in resource["days"]:
                    if day.get("on_leave") is True:
                        on_leave_when_approved = True
                        break
                break
        
        log_test(
            "Resource found in capacity report",
            resource_found,
            f"Resource ID: {resource_id}"
        )
        
        log_test(
            "Resource shows on_leave=true when Approved",
            on_leave_when_approved,
            f"on_leave status: {on_leave_when_approved}"
        )
    
    # Now reject the leave
    response = requests.put(
        f"{API_BASE}/leaves/{leave_id}/set-status",
        json={"status": "Rejected"},
        headers={"Authorization": f"Bearer {superadmin_token}"}
    )
    
    log_test(
        "Reject leave for capacity test",
        response.status_code == 200,
        f"Status code: {response.status_code}"
    )
    
    # Check capacity again - should show on_leave=false
    response = requests.get(
        f"{API_BASE}/reports/capacity",
        params={"start_date": start_date, "end_date": end_date},
        headers={"Authorization": f"Bearer {superadmin_token}"}
    )
    
    if response.status_code == 200:
        capacity_data = response.json()
        # Find the resource in the capacity report
        on_leave_when_rejected = False
        
        for resource in capacity_data.get("resources", []):
            if resource["resource_id"] == resource_id:
                # Check if any day in the range shows on_leave=true
                for day in resource["days"]:
                    if day.get("on_leave") is True:
                        on_leave_when_rejected = True
                        break
                break
        
        log_test(
            "Resource shows on_leave=false when Rejected (capacity freed)",
            not on_leave_when_rejected,
            f"on_leave status: {on_leave_when_rejected} (should be False)"
        )
    
    print()

    # ========================================================================
    # STEP 6: VALIDATION - Invalid status should return 400
    # ========================================================================
    print("STEP 6: VALIDATION - Invalid status")
    print("-" * 80)
    
    response = requests.put(
        f"{API_BASE}/leaves/{leave_id}/set-status",
        json={"status": "Bogus"},
        headers={"Authorization": f"Bearer {superadmin_token}"}
    )
    
    log_test(
        "Invalid status returns 400",
        response.status_code == 400,
        f"Status code: {response.status_code}, Response: {response.text[:100]}"
    )
    
    print()

    # ========================================================================
    # STEP 7: RBAC - Admin and resource should get 403
    # ========================================================================
    print("STEP 7: RBAC - Admin and resource cannot use set-status")
    print("-" * 80)
    
    # Try as admin
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if admin_token:
        response = requests.put(
            f"{API_BASE}/leaves/{leave_id}/set-status",
            json={"status": "Approved"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        log_test(
            "Admin gets 403 (not super_admin)",
            response.status_code == 403,
            f"Status code: {response.status_code}"
        )
    
    # Try as resource
    response = requests.put(
        f"{API_BASE}/leaves/{leave_id}/set-status",
        json={"status": "Approved"},
        headers={"Authorization": f"Bearer {resource_token}"}
    )
    
    log_test(
        "Resource gets 403 (not super_admin)",
        response.status_code == 403,
        f"Status code: {response.status_code}"
    )
    
    print()

    # ========================================================================
    # STEP 8: 404 - Non-existent leave
    # ========================================================================
    print("STEP 8: 404 - Non-existent leave")
    print("-" * 80)
    
    response = requests.put(
        f"{API_BASE}/leaves/000000000000000000000000/set-status",
        json={"status": "Approved"},
        headers={"Authorization": f"Bearer {superadmin_token}"}
    )
    
    log_test(
        "Non-existent leave returns 404",
        response.status_code == 404,
        f"Status code: {response.status_code}"
    )
    
    print()

    # ========================================================================
    # CLEANUP - Delete test leave
    # ========================================================================
    print("CLEANUP: Delete test leave")
    print("-" * 80)
    
    response = requests.delete(
        f"{API_BASE}/leaves/{leave_id}",
        headers={"Authorization": f"Bearer {superadmin_token}"}
    )
    
    log_test(
        "Test leave deleted",
        response.status_code == 200,
        f"Status code: {response.status_code}"
    )
    
    print()

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"✅ Tests Passed: {tests_passed}")
    print(f"❌ Tests Failed: {tests_failed}")
    print(f"📊 Total Tests: {tests_passed + tests_failed}")
    print(f"🎯 Success Rate: {tests_passed / (tests_passed + tests_failed) * 100:.1f}%")
    print()
    
    if tests_failed == 0:
        print("🎉 ALL TESTS PASSED! The super_admin leave status change feature is working correctly.")
        print()
        print("KEY FINDINGS:")
        print("✅ Super admin can approve leaves via set-status")
        print("✅ Super admin can CHANGE already-approved leaves to Rejected (CORE FEATURE)")
        print("✅ Super admin can RE-OPEN leaves by setting status to Pending (clears approver/decided_at)")
        print("✅ Capacity correctly reflects leave status (Approved = on_leave, Rejected = capacity freed)")
        print("✅ Validation works (invalid status returns 400)")
        print("✅ RBAC works (admin and resource get 403)")
        print("✅ 404 handling works (non-existent leave returns 404)")
        sys.exit(0)
    else:
        print("⚠️  SOME TESTS FAILED. Please review the failures above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
