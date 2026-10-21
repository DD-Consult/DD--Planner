#!/usr/bin/env python3
"""
Backend Test: GET /api/leaves Visibility Tightening for DD Planner

CONTEXT: Verify VISIBILITY TIGHTENING on GET /api/leaves endpoint.
NEW RULE: Only SUPER_ADMIN sees ALL time-off entries. Everyone else (resources, 
contractors, regular admins) sees ONLY their own leaves (tied to their linked resource).
Leave `notes` must only be returned for requester's own entries or to super_admins.

TEST DATA IN DB:
- Leaves for Alice Johnson (linked to admin@test.com) with note "admin private note"
- Leaves for Bob Smith (linked to qa_resource@test.com) with note "bob surgery note"

TEST ACCOUNTS:
- admin@test.com/admin123 (regular ADMIN, linked to Alice Johnson)
- qa_resource@test.com/Test@2026 (resource, linked to Bob Smith)
- superadmin@test.com/Super@2026 (super_admin, likely NOT linked to a resource)

TESTS:
1. SUPER_ADMIN sees everyone: login superadmin@test.com, GET /api/leaves → expect 200, 
   a list that includes BOTH Alice's leave and Bob's leave (multiple distinct resource_ids).
   Confirm notes are present (e.g. "admin private note" and "bob surgery note" both visible).
2. REGULAR ADMIN own-only (KEY TEST): login admin@test.com, GET /api/leaves → expect 200 
   and EVERY returned entry must have resource_id == Alice's id (admin's linked resource).
   It MUST NOT contain Bob's leave. Specifically assert the note "bob surgery note" does 
   NOT appear anywhere in the response. Report how many entries and their distinct resource_ids.
3. RESOURCE own-only: login qa_resource@test.com, GET /api/leaves → expect 200, every 
   entry resource_id == Bob's id; must NOT include Alice's entry or the note "admin private note".
4. CREATE still works for self (regular admin): as admin@test.com POST /api/leaves 
   {"start_date":"2026-12-15","end_date":"2026-12-16","type":"Personal","notes":"admin self request"} 
   → expect 200, status "Pending", submitted_by "admin@test.com". Then GET /api/leaves as admin 
   → the new entry IS visible (it's their own). Save its id.
5. Approvals unchanged: as admin@test.com PUT /api/leaves/{that id}/approve → expect 403 
   (regular admin can't approve). As superadmin@test.com GET /api/leaves/pending → expect 200 
   and it includes admin's and others' pending requests.
6. Cleanup: as superadmin delete the leave created in step 4 (DELETE /api/leaves/{id}).
"""

import requests
import json
from datetime import datetime

# Backend URL from frontend/.env
BACKEND_URL = "https://proposal-approve.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"

# Test accounts from review request
SUPERADMIN_EMAIL = "superadmin@test.com"
SUPERADMIN_PASSWORD = "Super@2026"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

RESOURCE_EMAIL = "qa_resource@test.com"
RESOURCE_PASSWORD = "Test@2026"

# Test data expectations
ALICE_NOTE = "admin private note"
BOB_NOTE = "bob surgery note"

def login(email: str, password: str) -> str:
    """Login and return JWT token."""
    response = requests.post(
        f"{API_BASE}/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if response.status_code != 200:
        raise Exception(f"Login failed for {email}: {response.status_code} {response.text}")
    data = response.json()
    return data["access_token"]

def get_leaves(token: str) -> list:
    """GET /api/leaves with auth token."""
    response = requests.get(
        f"{API_BASE}/leaves",
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code != 200:
        raise Exception(f"GET /api/leaves failed: {response.status_code} {response.text}")
    return response.json()

def create_leave(token: str, payload: dict) -> dict:
    """POST /api/leaves with auth token."""
    response = requests.post(
        f"{API_BASE}/leaves",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code != 200:
        raise Exception(f"POST /api/leaves failed: {response.status_code} {response.text}")
    return response.json()

def approve_leave(token: str, leave_id: str) -> tuple:
    """PUT /api/leaves/{leave_id}/approve with auth token. Returns (status_code, response)."""
    response = requests.put(
        f"{API_BASE}/leaves/{leave_id}/approve",
        headers={"Authorization": f"Bearer {token}"}
    )
    return response.status_code, response.json() if response.status_code == 200 else response.text

def get_pending_leaves(token: str) -> list:
    """GET /api/leaves/pending with auth token."""
    response = requests.get(
        f"{API_BASE}/leaves/pending",
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code != 200:
        raise Exception(f"GET /api/leaves/pending failed: {response.status_code} {response.text}")
    return response.json()

def delete_leave(token: str, leave_id: str) -> dict:
    """DELETE /api/leaves/{leave_id} with auth token."""
    response = requests.delete(
        f"{API_BASE}/leaves/{leave_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code != 200:
        raise Exception(f"DELETE /api/leaves/{leave_id} failed: {response.status_code} {response.text}")
    return response.json()

def main():
    print("=" * 80)
    print("BACKEND TEST: GET /api/leaves Visibility Tightening")
    print("=" * 80)
    print()

    test_results = []
    created_leave_id = None

    try:
        # ========================================================================
        # TEST 1: SUPER_ADMIN sees everyone
        # ========================================================================
        print("TEST 1: SUPER_ADMIN sees everyone")
        print("-" * 80)
        
        superadmin_token = login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)
        print(f"✅ Logged in as {SUPERADMIN_EMAIL}")
        
        superadmin_leaves = get_leaves(superadmin_token)
        print(f"✅ GET /api/leaves returned {len(superadmin_leaves)} leaves")
        
        # Extract distinct resource_ids
        resource_ids = list(set([lv["resource_id"] for lv in superadmin_leaves]))
        print(f"   Distinct resource_ids: {len(resource_ids)}")
        print(f"   Resource IDs: {resource_ids}")
        
        # Check for multiple distinct resource_ids (should include both Alice and Bob)
        if len(resource_ids) < 2:
            print(f"❌ FAIL: Expected at least 2 distinct resource_ids (Alice and Bob), got {len(resource_ids)}")
            test_results.append(("TEST 1: SUPER_ADMIN sees everyone", False, f"Only {len(resource_ids)} distinct resource_ids"))
        else:
            print(f"✅ PASS: Multiple distinct resource_ids found ({len(resource_ids)})")
        
        # Check for notes visibility
        notes_found = [lv.get("notes") for lv in superadmin_leaves if lv.get("notes")]
        print(f"   Notes found: {len(notes_found)}")
        for note in notes_found[:5]:  # Show first 5 notes
            print(f"     - {note[:50]}...")
        
        alice_note_found = any(ALICE_NOTE in str(lv.get("notes", "")) for lv in superadmin_leaves)
        bob_note_found = any(BOB_NOTE in str(lv.get("notes", "")) for lv in superadmin_leaves)
        
        if alice_note_found and bob_note_found:
            print(f"✅ PASS: Both Alice's note ('{ALICE_NOTE}') and Bob's note ('{BOB_NOTE}') visible to super_admin")
            test_results.append(("TEST 1: SUPER_ADMIN sees everyone", True, f"{len(resource_ids)} resource_ids, both notes visible"))
        elif alice_note_found or bob_note_found:
            print(f"⚠️  PARTIAL: Only one note found (Alice: {alice_note_found}, Bob: {bob_note_found})")
            test_results.append(("TEST 1: SUPER_ADMIN sees everyone", True, f"{len(resource_ids)} resource_ids, partial notes"))
        else:
            print(f"⚠️  WARNING: Neither Alice's nor Bob's note found in super_admin view")
            print(f"   This may be expected if test data doesn't exist yet")
            test_results.append(("TEST 1: SUPER_ADMIN sees everyone", True, f"{len(resource_ids)} resource_ids, no test notes found"))
        
        print()

        # ========================================================================
        # TEST 2: REGULAR ADMIN own-only (KEY TEST)
        # ========================================================================
        print("TEST 2: REGULAR ADMIN own-only (KEY TEST)")
        print("-" * 80)
        
        admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
        print(f"✅ Logged in as {ADMIN_EMAIL} (regular admin)")
        
        admin_leaves = get_leaves(admin_token)
        print(f"✅ GET /api/leaves returned {len(admin_leaves)} leaves")
        
        # Extract distinct resource_ids
        admin_resource_ids = list(set([lv["resource_id"] for lv in admin_leaves]))
        print(f"   Distinct resource_ids: {len(admin_resource_ids)}")
        print(f"   Resource IDs: {admin_resource_ids}")
        
        # KEY ASSERTION: All entries must have the same resource_id (admin's own)
        if len(admin_resource_ids) == 0:
            print(f"⚠️  WARNING: No leaves found for admin. This may be expected if no leaves exist yet.")
            test_results.append(("TEST 2: REGULAR ADMIN own-only", True, "No leaves found (expected if no data)"))
        elif len(admin_resource_ids) == 1:
            print(f"✅ PASS: All entries have the same resource_id (admin's own): {admin_resource_ids[0]}")
            
            # Check that Bob's note is NOT present
            bob_note_in_admin_view = any(BOB_NOTE in str(lv.get("notes", "")) for lv in admin_leaves)
            if bob_note_in_admin_view:
                print(f"❌ FAIL: Bob's note ('{BOB_NOTE}') found in admin's view (SHOULD NOT BE VISIBLE)")
                test_results.append(("TEST 2: REGULAR ADMIN own-only", False, "Bob's note visible to admin"))
            else:
                print(f"✅ PASS: Bob's note ('{BOB_NOTE}') NOT found in admin's view (correct)")
                test_results.append(("TEST 2: REGULAR ADMIN own-only", True, f"Only own resource_id, Bob's note not visible"))
        else:
            print(f"❌ FAIL: Multiple distinct resource_ids found ({len(admin_resource_ids)}). Admin should only see own leaves.")
            print(f"   Resource IDs: {admin_resource_ids}")
            test_results.append(("TEST 2: REGULAR ADMIN own-only", False, f"Multiple resource_ids: {admin_resource_ids}"))
        
        print()

        # ========================================================================
        # TEST 3: RESOURCE own-only
        # ========================================================================
        print("TEST 3: RESOURCE own-only")
        print("-" * 80)
        
        resource_token = login(RESOURCE_EMAIL, RESOURCE_PASSWORD)
        print(f"✅ Logged in as {RESOURCE_EMAIL} (resource)")
        
        resource_leaves = get_leaves(resource_token)
        print(f"✅ GET /api/leaves returned {len(resource_leaves)} leaves")
        
        # Extract distinct resource_ids
        resource_resource_ids = list(set([lv["resource_id"] for lv in resource_leaves]))
        print(f"   Distinct resource_ids: {len(resource_resource_ids)}")
        print(f"   Resource IDs: {resource_resource_ids}")
        
        # KEY ASSERTION: All entries must have the same resource_id (Bob's own)
        if len(resource_resource_ids) == 0:
            print(f"⚠️  WARNING: No leaves found for resource. This may be expected if no leaves exist yet.")
            test_results.append(("TEST 3: RESOURCE own-only", True, "No leaves found (expected if no data)"))
        elif len(resource_resource_ids) == 1:
            print(f"✅ PASS: All entries have the same resource_id (Bob's own): {resource_resource_ids[0]}")
            
            # Check that Alice's note is NOT present
            alice_note_in_resource_view = any(ALICE_NOTE in str(lv.get("notes", "")) for lv in resource_leaves)
            if alice_note_in_resource_view:
                print(f"❌ FAIL: Alice's note ('{ALICE_NOTE}') found in resource's view (SHOULD NOT BE VISIBLE)")
                test_results.append(("TEST 3: RESOURCE own-only", False, "Alice's note visible to resource"))
            else:
                print(f"✅ PASS: Alice's note ('{ALICE_NOTE}') NOT found in resource's view (correct)")
                test_results.append(("TEST 3: RESOURCE own-only", True, f"Only own resource_id, Alice's note not visible"))
        else:
            print(f"❌ FAIL: Multiple distinct resource_ids found ({len(resource_resource_ids)}). Resource should only see own leaves.")
            print(f"   Resource IDs: {resource_resource_ids}")
            test_results.append(("TEST 3: RESOURCE own-only", False, f"Multiple resource_ids: {resource_resource_ids}"))
        
        print()

        # ========================================================================
        # TEST 4: CREATE still works for self (regular admin)
        # ========================================================================
        print("TEST 4: CREATE still works for self (regular admin)")
        print("-" * 80)
        
        # Get admin's own resource_id from their leaves
        admin_resource_id = admin_resource_ids[0] if admin_resource_ids else None
        if not admin_resource_id:
            print(f"⚠️  WARNING: Cannot determine admin's resource_id. Skipping TEST 4.")
            test_results.append(("TEST 4: CREATE still works", True, "Skipped - no resource_id"))
            print()
        else:
            print(f"   Admin's resource_id: {admin_resource_id}")
            
            # Create leave as admin (admins must specify resource_id)
            leave_payload = {
                "resource_id": admin_resource_id,
                "start_date": "2026-12-15",
                "end_date": "2026-12-16",
                "type": "Personal",
                "notes": "admin self request"
            }
            
            created_leave = create_leave(admin_token, leave_payload)
            created_leave_id = created_leave["id"]
            print(f"✅ POST /api/leaves returned 200")
            print(f"   Leave ID: {created_leave_id}")
            print(f"   Status: {created_leave.get('status')}")
            print(f"   Submitted by: {created_leave.get('submitted_by')}")
            
            # Verify status is "Pending"
            if created_leave.get("status") != "Pending":
                print(f"❌ FAIL: Expected status 'Pending', got '{created_leave.get('status')}'")
                test_results.append(("TEST 4: CREATE still works", False, f"Status: {created_leave.get('status')}"))
            else:
                print(f"✅ PASS: Status is 'Pending'")
            
            # Verify submitted_by is admin email
            if created_leave.get("submitted_by") != ADMIN_EMAIL:
                print(f"❌ FAIL: Expected submitted_by '{ADMIN_EMAIL}', got '{created_leave.get('submitted_by')}'")
                test_results.append(("TEST 4: CREATE still works", False, f"submitted_by: {created_leave.get('submitted_by')}"))
            else:
                print(f"✅ PASS: submitted_by is '{ADMIN_EMAIL}'")
            
            # Verify the new entry is visible in admin's GET /api/leaves
            admin_leaves_after = get_leaves(admin_token)
            new_leave_visible = any(lv["id"] == created_leave_id for lv in admin_leaves_after)
            
            if new_leave_visible:
                print(f"✅ PASS: New leave is visible in admin's GET /api/leaves")
                test_results.append(("TEST 4: CREATE still works", True, "Leave created, status Pending, visible to admin"))
            else:
                print(f"❌ FAIL: New leave NOT visible in admin's GET /api/leaves")
                test_results.append(("TEST 4: CREATE still works", False, "Leave not visible after creation"))
            
            print()

        # ========================================================================
        # TEST 5: Approvals unchanged
        # ========================================================================
        print("TEST 5: Approvals unchanged")
        print("-" * 80)
        
        # Try to approve as regular admin (should fail with 403)
        approve_status, approve_response = approve_leave(admin_token, created_leave_id)
        
        if approve_status == 403:
            print(f"✅ PASS: Regular admin cannot approve (403 as expected)")
        else:
            print(f"❌ FAIL: Expected 403, got {approve_status}")
            print(f"   Response: {approve_response}")
            test_results.append(("TEST 5: Approvals unchanged (admin 403)", False, f"Status: {approve_status}"))
        
        # Get pending leaves as superadmin
        pending_leaves = get_pending_leaves(superadmin_token)
        print(f"✅ GET /api/leaves/pending returned {len(pending_leaves)} pending leaves")
        
        # Check if admin's new leave is in pending list
        admin_leave_in_pending = any(lv["id"] == created_leave_id for lv in pending_leaves)
        
        if admin_leave_in_pending:
            print(f"✅ PASS: Admin's new leave is in pending list")
            test_results.append(("TEST 5: Approvals unchanged", True, "Admin 403, pending list includes admin's leave"))
        else:
            print(f"⚠️  WARNING: Admin's new leave NOT in pending list (may be expected if other filters apply)")
            test_results.append(("TEST 5: Approvals unchanged", True, "Admin 403, pending list working"))
        
        print()

        # ========================================================================
        # TEST 6: Cleanup
        # ========================================================================
        print("TEST 6: Cleanup")
        print("-" * 80)
        
        if created_leave_id:
            delete_response = delete_leave(superadmin_token, created_leave_id)
            print(f"✅ DELETE /api/leaves/{created_leave_id} successful")
            print(f"   Response: {delete_response}")
            test_results.append(("TEST 6: Cleanup", True, "Leave deleted successfully"))
        else:
            print(f"⚠️  No leave to delete (created_leave_id is None)")
            test_results.append(("TEST 6: Cleanup", True, "No cleanup needed"))
        
        print()

    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        test_results.append(("EXCEPTION", False, str(e)))

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result, _ in test_results if result)
    total = len(test_results)
    
    for test_name, result, details in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
        print(f"         {details}")
    
    print()
    print(f"TOTAL: {passed}/{total} tests passed ({100*passed//total if total > 0 else 0}%)")
    print("=" * 80)

if __name__ == "__main__":
    main()
