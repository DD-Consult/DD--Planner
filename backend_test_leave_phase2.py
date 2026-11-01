#!/usr/bin/env python3
"""
Leave Phase 2 Backend Testing (Parts B, C, D)
Test balances, allocation overrides, and attachments.

Backend URL: https://planner-holidays--04yvh1gp.preview.emergentagent.com/api
Test credentials:
- Super Admin: superadmin@test.com / Super@2026
- Admin: admin@test.com / admin123
- Resource: qa_resource@test.com / Test@2026

KNOWN resource_id: 6ab25bc82be78e05e89230ef (linked to qa_resource@test.com)
"""

import requests
import json
import base64
from datetime import datetime, timedelta
import time

# Configuration
BASE_URL = "https://planner-holidays--04yvh1gp.preview.emergentagent.com/api"
RESOURCE_ID = "6ab25bc82be78e05e89230ef"  # Known resource linked to qa_resource@test.com
CURRENT_YEAR = datetime.now().year

# Test credentials
SUPER_ADMIN = {"username": "superadmin@test.com", "password": "Super@2026"}
ADMIN = {"username": "admin@test.com", "password": "admin123"}
RESOURCE = {"username": "qa_resource@test.com", "password": "Test@2026"}

# Global tokens
super_admin_token = None
admin_token = None
resource_token = None

# Test data tracking
created_leave_types = []
created_leaves = []

def login(credentials):
    """Login and return JWT token."""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data=credentials,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception(f"Login failed: {response.status_code} {response.text}")

def auth_headers(token):
    """Return authorization headers."""
    return {"Authorization": f"Bearer {token}"}

def print_test(test_name):
    """Print test name."""
    print(f"\n{'='*80}")
    print(f"TEST: {test_name}")
    print('='*80)

def print_result(passed, message):
    """Print test result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {message}")

def find_business_day_range(year, month, num_days=5):
    """Find a range of business days (Mon-Fri) in the given month."""
    # Start from the first Monday of the month
    date = datetime(year, month, 1)
    while date.weekday() != 0:  # 0 = Monday
        date += timedelta(days=1)
    
    # Count business days
    start_date = date
    count = 0
    while count < num_days - 1:
        date += timedelta(days=1)
        if date.weekday() < 5:  # Mon-Fri
            count += 1
    end_date = date
    
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

# ============================================================
# SETUP
# ============================================================

print_test("SETUP - Authentication")
try:
    super_admin_token = login(SUPER_ADMIN)
    print_result(True, f"Super admin logged in successfully")
    
    admin_token = login(ADMIN)
    print_result(True, f"Admin logged in successfully")
    
    resource_token = login(RESOURCE)
    print_result(True, f"Resource logged in successfully")
except Exception as e:
    print_result(False, f"Authentication failed: {e}")
    exit(1)

# ============================================================
# SETUP - Create Leave Types
# ============================================================

print_test("SETUP - Create Leave Types")

# Create unique leave type names with timestamp
timestamp = int(time.time())
FIXED_TYPE_NAME = f"AnnualP2_{timestamp}"
MONTHLY_TYPE_NAME = f"SickP2_{timestamp}"

# Create FIXED type
try:
    response = requests.post(
        f"{BASE_URL}/leave-types",
        headers=auth_headers(admin_token),
        json={
            "name": FIXED_TYPE_NAME,
            "accrual_method": "fixed_annual",
            "annual_allowance": 25,
            "allow_negative": False
        }
    )
    if response.status_code == 200:
        fixed_type = response.json()
        created_leave_types.append(fixed_type["id"])
        print_result(True, f"Created FIXED leave type: {FIXED_TYPE_NAME} (annual_allowance=25)")
    else:
        print_result(False, f"Failed to create FIXED type: {response.status_code} {response.text}")
        exit(1)
except Exception as e:
    print_result(False, f"Exception creating FIXED type: {e}")
    exit(1)

# Create MONTHLY type
try:
    response = requests.post(
        f"{BASE_URL}/leave-types",
        headers=auth_headers(admin_token),
        json={
            "name": MONTHLY_TYPE_NAME,
            "accrual_method": "monthly_accrual",
            "accrual_rate": 1.0
        }
    )
    if response.status_code == 200:
        monthly_type = response.json()
        created_leave_types.append(monthly_type["id"])
        print_result(True, f"Created MONTHLY leave type: {MONTHLY_TYPE_NAME} (accrual_rate=1.0)")
    else:
        print_result(False, f"Failed to create MONTHLY type: {response.status_code} {response.text}")
        exit(1)
except Exception as e:
    print_result(False, f"Exception creating MONTHLY type: {e}")
    exit(1)

# ============================================================
# PART B - BALANCES
# ============================================================

print_test("PART B - BALANCES")

# B1: Create 5-day approved FIXED leave
print("\n--- B1: Create 5-day approved FIXED leave ---")
try:
    # Find a 5-day business week in current year
    start_date, end_date = find_business_day_range(CURRENT_YEAR, 6, 5)  # June
    
    # Create leave as admin
    response = requests.post(
        f"{BASE_URL}/leaves",
        headers=auth_headers(admin_token),
        json={
            "resource_id": RESOURCE_ID,
            "start_date": start_date,
            "end_date": end_date,
            "type": FIXED_TYPE_NAME,
            "notes": "B1 test - 5 day leave"
        }
    )
    if response.status_code == 200:
        leave_b1 = response.json()
        created_leaves.append(leave_b1["id"])
        print_result(True, f"Created leave B1: {leave_b1['id']} ({start_date} to {end_date})")
        
        # Approve as super_admin
        response = requests.put(
            f"{BASE_URL}/leaves/{leave_b1['id']}/approve",
            headers=auth_headers(super_admin_token),
            json={"note": "Approved for testing"}
        )
        if response.status_code == 200:
            print_result(True, f"Approved leave B1")
        else:
            print_result(False, f"Failed to approve B1: {response.status_code} {response.text}")
    else:
        print_result(False, f"Failed to create leave B1: {response.status_code} {response.text}")
except Exception as e:
    print_result(False, f"Exception in B1: {e}")

# B2: Create 2-day pending FIXED leave
print("\n--- B2: Create 2-day pending FIXED leave ---")
try:
    # Find a 2-day business week in current year (different from B1)
    start_date, end_date = find_business_day_range(CURRENT_YEAR, 7, 2)  # July
    
    response = requests.post(
        f"{BASE_URL}/leaves",
        headers=auth_headers(admin_token),
        json={
            "resource_id": RESOURCE_ID,
            "start_date": start_date,
            "end_date": end_date,
            "type": FIXED_TYPE_NAME,
            "notes": "B2 test - 2 day pending"
        }
    )
    if response.status_code == 200:
        leave_b2 = response.json()
        created_leaves.append(leave_b2["id"])
        print_result(True, f"Created pending leave B2: {leave_b2['id']} ({start_date} to {end_date})")
    else:
        print_result(False, f"Failed to create leave B2: {response.status_code} {response.text}")
except Exception as e:
    print_result(False, f"Exception in B2: {e}")

# B3: Get balances and verify
print("\n--- B3: Get balances and verify FIXED type ---")
try:
    response = requests.get(
        f"{BASE_URL}/leave-balances",
        headers=auth_headers(admin_token),
        params={"resource_id": RESOURCE_ID, "year": CURRENT_YEAR}
    )
    if response.status_code == 200:
        balances = response.json()
        print_result(True, f"Retrieved balances: {len(balances)} types")
        
        # Find FIXED type balance
        fixed_balance = next((b for b in balances if b["leave_type"] == FIXED_TYPE_NAME), None)
        if fixed_balance:
            print(f"  FIXED balance: {json.dumps(fixed_balance, indent=2)}")
            
            # Verify values
            checks = []
            checks.append(("allocated", fixed_balance.get("allocated") == 25, f"allocated={fixed_balance.get('allocated')} (expected 25)"))
            checks.append(("taken", fixed_balance.get("taken") == 5, f"taken={fixed_balance.get('taken')} (expected 5)"))
            checks.append(("pending", fixed_balance.get("pending") == 2, f"pending={fixed_balance.get('pending')} (expected 2)"))
            checks.append(("available", fixed_balance.get("available") == 18, f"available={fixed_balance.get('available')} (expected 18)"))
            checks.append(("accrual_method", fixed_balance.get("accrual_method") == "fixed_annual", f"accrual_method={fixed_balance.get('accrual_method')}"))
            
            for check_name, passed, message in checks:
                print_result(passed, f"B3 {check_name}: {message}")
        else:
            print_result(False, f"FIXED type balance not found in response")
    else:
        print_result(False, f"Failed to get balances: {response.status_code} {response.text}")
except Exception as e:
    print_result(False, f"Exception in B3: {e}")

# B4: Create half-day leave and verify
print("\n--- B4: Create half-day (am) leave and verify ---")
try:
    # Find a single day in current year
    start_date, _ = find_business_day_range(CURRENT_YEAR, 8, 1)  # August
    
    response = requests.post(
        f"{BASE_URL}/leaves",
        headers=auth_headers(admin_token),
        json={
            "resource_id": RESOURCE_ID,
            "start_date": start_date,
            "end_date": start_date,
            "type": FIXED_TYPE_NAME,
            "day_portion": "am",
            "notes": "B4 test - half day"
        }
    )
    if response.status_code == 200:
        leave_b4 = response.json()
        created_leaves.append(leave_b4["id"])
        print_result(True, f"Created half-day leave B4: {leave_b4['id']}")
        
        # Approve
        response = requests.put(
            f"{BASE_URL}/leaves/{leave_b4['id']}/approve",
            headers=auth_headers(super_admin_token),
            json={"note": "Approved"}
        )
        if response.status_code == 200:
            print_result(True, f"Approved half-day leave B4")
            
            # Re-fetch balances
            response = requests.get(
                f"{BASE_URL}/leave-balances",
                headers=auth_headers(admin_token),
                params={"resource_id": RESOURCE_ID, "year": CURRENT_YEAR}
            )
            if response.status_code == 200:
                balances = response.json()
                fixed_balance = next((b for b in balances if b["leave_type"] == FIXED_TYPE_NAME), None)
                if fixed_balance:
                    taken = fixed_balance.get("taken")
                    available = fixed_balance.get("available")
                    print_result(taken == 5.5, f"B4 taken: {taken} (expected 5.5)")
                    print_result(available == 17.5, f"B4 available: {available} (expected 17.5)")
                else:
                    print_result(False, f"FIXED balance not found after B4")
            else:
                print_result(False, f"Failed to get balances after B4: {response.status_code}")
        else:
            print_result(False, f"Failed to approve B4: {response.status_code}")
    else:
        print_result(False, f"Failed to create half-day leave B4: {response.status_code} {response.text}")
except Exception as e:
    print_result(False, f"Exception in B4: {e}")

# B5: Verify MONTHLY type balance
print("\n--- B5: Verify MONTHLY type balance ---")
try:
    response = requests.get(
        f"{BASE_URL}/leave-balances",
        headers=auth_headers(admin_token),
        params={"resource_id": RESOURCE_ID, "year": CURRENT_YEAR}
    )
    if response.status_code == 200:
        balances = response.json()
        monthly_balance = next((b for b in balances if b["leave_type"] == MONTHLY_TYPE_NAME), None)
        if monthly_balance:
            print(f"  MONTHLY balance: {json.dumps(monthly_balance, indent=2)}")
            
            current_month = datetime.now().month
            expected_allocated = current_month * 1.0  # accrual_rate = 1.0
            
            allocated = monthly_balance.get("allocated")
            taken = monthly_balance.get("taken")
            
            print_result(allocated == expected_allocated, f"B5 MONTHLY allocated: {allocated} (expected {expected_allocated} for month {current_month})")
            print_result(taken == 0, f"B5 MONTHLY taken: {taken} (expected 0)")
        else:
            print_result(False, f"MONTHLY type balance not found")
    else:
        print_result(False, f"Failed to get balances for B5: {response.status_code}")
except Exception as e:
    print_result(False, f"Exception in B5: {e}")

# B6: Permission checks
print("\n--- B6: Permission checks ---")
try:
    # B6.1: Resource without resource_id should get own balances
    response = requests.get(
        f"{BASE_URL}/leave-balances",
        headers=auth_headers(resource_token),
        params={"year": CURRENT_YEAR}
    )
    if response.status_code == 200:
        print_result(True, f"B6.1: Resource can get own balances without resource_id (200)")
    else:
        print_result(False, f"B6.1: Resource failed to get own balances: {response.status_code}")
    
    # B6.2: Resource trying to access different resource_id should get 403
    # Use a different resource_id (we'll use a fake one)
    different_resource_id = "6ab25bc82be78e05e89230ee"
    response = requests.get(
        f"{BASE_URL}/leave-balances",
        headers=auth_headers(resource_token),
        params={"resource_id": different_resource_id, "year": CURRENT_YEAR}
    )
    if response.status_code == 403:
        print_result(True, f"B6.2: Resource correctly denied access to different resource (403)")
    else:
        print_result(False, f"B6.2: Expected 403, got {response.status_code}")
except Exception as e:
    print_result(False, f"Exception in B6: {e}")

# ============================================================
# PART C - ALLOCATION OVERRIDES
# ============================================================

print_test("PART C - ALLOCATION OVERRIDES")

# C1: Create allocation override
print("\n--- C1: Create allocation override ---")
try:
    response = requests.put(
        f"{BASE_URL}/leave-allocations",
        headers=auth_headers(admin_token),
        json={
            "resource_id": RESOURCE_ID,
            "leave_type": FIXED_TYPE_NAME,
            "year": CURRENT_YEAR,
            "allocated": 30
        }
    )
    if response.status_code == 200:
        balance = response.json()
        print(f"  Override balance: {json.dumps(balance, indent=2)}")
        
        allocated = balance.get("allocated")
        is_override = balance.get("is_override")
        taken = balance.get("taken")
        pending = balance.get("pending")
        available = balance.get("available")
        
        print_result(response.status_code == 200, f"C1: PUT returned 200")
        print_result(allocated == 30, f"C1 allocated: {allocated} (expected 30)")
        print_result(is_override == True, f"C1 is_override: {is_override} (expected True)")
        
        # available = allocated - taken - pending = 30 - 5.5 - 2 = 22.5
        expected_available = 30 - 5.5 - 2
        print_result(available == expected_available, f"C1 available: {available} (expected {expected_available})")
    else:
        print_result(False, f"Failed to create override: {response.status_code} {response.text}")
except Exception as e:
    print_result(False, f"Exception in C1: {e}")

# C2: Delete allocation override
print("\n--- C2: Delete allocation override ---")
try:
    response = requests.delete(
        f"{BASE_URL}/leave-allocations",
        headers=auth_headers(admin_token),
        params={
            "resource_id": RESOURCE_ID,
            "leave_type": FIXED_TYPE_NAME,
            "year": CURRENT_YEAR
        }
    )
    if response.status_code == 200:
        balance = response.json()
        print(f"  Reverted balance: {json.dumps(balance, indent=2)}")
        
        allocated = balance.get("allocated")
        is_override = balance.get("is_override")
        
        print_result(response.status_code == 200, f"C2: DELETE returned 200")
        print_result(allocated == 25, f"C2 allocated: {allocated} (expected 25, reverted to default)")
        print_result(is_override == False, f"C2 is_override: {is_override} (expected False)")
    else:
        print_result(False, f"Failed to delete override: {response.status_code} {response.text}")
except Exception as e:
    print_result(False, f"Exception in C2: {e}")

# C3: Route collision check
print("\n--- C3: Route collision check ---")
try:
    # DELETE /api/leave-allocations should return balance object
    response = requests.delete(
        f"{BASE_URL}/leave-allocations",
        headers=auth_headers(admin_token),
        params={
            "resource_id": RESOURCE_ID,
            "leave_type": FIXED_TYPE_NAME,
            "year": CURRENT_YEAR
        }
    )
    if response.status_code == 200:
        data = response.json()
        # Check if it's a balance object (has keys: resource_id, leave_type, allocated, etc.)
        has_balance_keys = all(k in data for k in ["resource_id", "leave_type", "allocated", "taken", "pending", "available"])
        is_not_string = not isinstance(data, str)
        is_not_message = "message" not in data or data.get("message") != "Leave deleted"
        
        print_result(has_balance_keys and is_not_string and is_not_message, 
                    f"C3: DELETE /leave-allocations returns balance object (NOT 'Leave deleted' message)")
    else:
        print_result(False, f"C3: DELETE /leave-allocations failed: {response.status_code}")
    
    # DELETE /api/leaves/{id} should return message
    if created_leaves:
        # Create a test leave to delete
        start_date, end_date = find_business_day_range(CURRENT_YEAR, 9, 1)
        response = requests.post(
            f"{BASE_URL}/leaves",
            headers=auth_headers(admin_token),
            json={
                "resource_id": RESOURCE_ID,
                "start_date": start_date,
                "end_date": start_date,
                "type": FIXED_TYPE_NAME,
                "notes": "C3 test - to be deleted"
            }
        )
        if response.status_code == 200:
            leave_c3 = response.json()
            leave_id = leave_c3["id"]
            
            # Delete the leave
            response = requests.delete(
                f"{BASE_URL}/leaves/{leave_id}",
                headers=auth_headers(admin_token)
            )
            if response.status_code == 200:
                data = response.json()
                has_message = "message" in data and "deleted" in data.get("message", "").lower()
                print_result(has_message, f"C3: DELETE /leaves/{{id}} returns message: {data}")
            else:
                print_result(False, f"C3: DELETE /leaves/{{id}} failed: {response.status_code}")
        else:
            print_result(False, f"C3: Failed to create test leave for deletion: {response.status_code}")
except Exception as e:
    print_result(False, f"Exception in C3: {e}")

# ============================================================
# PART D - ATTACHMENTS
# ============================================================

print_test("PART D - ATTACHMENTS")

# Create a test leave for attachments
print("\n--- D0: Create test leave for attachments ---")
try:
    start_date, end_date = find_business_day_range(CURRENT_YEAR, 10, 3)
    response = requests.post(
        f"{BASE_URL}/leaves",
        headers=auth_headers(admin_token),
        json={
            "resource_id": RESOURCE_ID,
            "start_date": start_date,
            "end_date": end_date,
            "type": FIXED_TYPE_NAME,
            "notes": "D test - for attachments"
        }
    )
    if response.status_code == 200:
        leave_d = response.json()
        leave_d_id = leave_d["id"]
        created_leaves.append(leave_d_id)
        print_result(True, f"Created test leave D: {leave_d_id}")
    else:
        print_result(False, f"Failed to create test leave D: {response.status_code} {response.text}")
        leave_d_id = None
except Exception as e:
    print_result(False, f"Exception in D0: {e}")
    leave_d_id = None

if leave_d_id:
    # D1: Add attachment
    print("\n--- D1: Add attachment ---")
    try:
        # Create a small valid base64 PDF
        pdf_base64 = "JVBERi0xLjQKJeLjz9MKMyAwIG9iago8PC9UeXBlL1BhZ2UvUGFyZW50IDIgMCBSL01lZGlhQm94WzAgMCA2MTIgNzkyXS9Db250ZW50cyA0IDAgUj4+CmVuZG9iago0IDAgb2JqCjw8L0xlbmd0aCAzMz4+CnN0cmVhbQpCVAovRjEgMTIgVGYKMTAwIDcwMCBUZAooSGVsbG8gV29ybGQpIFRqCkVUCmVuZHN0cmVhbQplbmRvYmoKMSAwIG9iago8PC9UeXBlL0NhdGFsb2cvUGFnZXMgMiAwIFI+PgplbmRvYmoKMiAwIG9iago8PC9UeXBlL1BhZ2VzL0tpZHNbMyAwIFJdL0NvdW50IDE+PgplbmRvYmoKNSAwIG9iago8PC9UeXBlL0ZvbnQvU3VidHlwZS9UeXBlMS9CYXNlRm9udC9IZWx2ZXRpY2E+PgplbmRvYmoKeHJlZgowIDYKMDAwMDAwMDAwMCA2NTUzNSBmDQowMDAwMDAwMjE1IDAwMDAwIG4NCjAwMDAwMDAyNjQgMDAwMDAgbg0KMDAwMDAwMDAxNSAwMDAwMCBuDQowMDAwMDAwMTAzIDAwMDAwIG4NCjAwMDAwMDAzMTMgMDAwMDAgbg0KdHJhaWxlcgo8PC9TaXplIDYvUm9vdCAxIDAgUj4+CnN0YXJ0eHJlZgozODEKJSVFT0YK"
        
        response = requests.post(
            f"{BASE_URL}/leaves/{leave_d_id}/attachments",
            headers=auth_headers(admin_token),
            json={
                "filename": "cert.pdf",
                "content_type": "application/pdf",
                "data_base64": pdf_base64
            }
        )
        if response.status_code == 200:
            leave_with_attachment = response.json()
            attachments = leave_with_attachment.get("attachments", [])
            if attachments:
                attachment_d1 = attachments[0]
                attachment_d1_id = attachment_d1.get("id")
                print_result(True, f"D1: Added attachment: {attachment_d1_id}")
                print(f"  Attachment: {json.dumps(attachment_d1, indent=2)}")
            else:
                print_result(False, f"D1: No attachments in response")
                attachment_d1_id = None
        else:
            print_result(False, f"D1: Failed to add attachment: {response.status_code} {response.text}")
            attachment_d1_id = None
    except Exception as e:
        print_result(False, f"Exception in D1: {e}")
        attachment_d1_id = None
    
    # D2: Verify GET /leaves does NOT include data_base64
    print("\n--- D2: Verify GET /leaves excludes data_base64 ---")
    try:
        response = requests.get(
            f"{BASE_URL}/leaves",
            headers=auth_headers(admin_token)
        )
        if response.status_code == 200:
            leaves = response.json()
            leave_d_in_list = next((l for l in leaves if l["id"] == leave_d_id), None)
            if leave_d_in_list:
                attachments = leave_d_in_list.get("attachments", [])
                if attachments:
                    has_data_base64 = any("data_base64" in a for a in attachments)
                    print_result(not has_data_base64, f"D2: Attachments in GET /leaves do NOT include data_base64")
                    
                    # Check what fields are present
                    expected_fields = ["id", "filename", "content_type", "size", "uploaded_at"]
                    first_attachment = attachments[0]
                    has_expected = all(f in first_attachment for f in expected_fields)
                    print_result(has_expected, f"D2: Attachment has expected fields: {list(first_attachment.keys())}")
                else:
                    print_result(False, f"D2: No attachments found in leave")
            else:
                print_result(False, f"D2: Leave D not found in GET /leaves response")
        else:
            print_result(False, f"D2: Failed to GET /leaves: {response.status_code}")
    except Exception as e:
        print_result(False, f"Exception in D2: {e}")
    
    # D3: Get specific attachment with data_base64
    if attachment_d1_id:
        print("\n--- D3: Get specific attachment with data_base64 ---")
        try:
            response = requests.get(
                f"{BASE_URL}/leaves/{leave_d_id}/attachments/{attachment_d1_id}",
                headers=auth_headers(admin_token)
            )
            if response.status_code == 200:
                attachment = response.json()
                has_data = "data_base64" in attachment
                has_filename = "filename" in attachment
                has_content_type = "content_type" in attachment
                
                print_result(has_data and has_filename and has_content_type, 
                           f"D3: GET attachment returns data_base64, filename, content_type")
            else:
                print_result(False, f"D3: Failed to get attachment: {response.status_code}")
        except Exception as e:
            print_result(False, f"Exception in D3: {e}")
    
    # D4: Guards (max 3, content type, size)
    print("\n--- D4: Guards (max 3, content type, size) ---")
    try:
        # Add 2 more attachments (total 3)
        for i in range(2):
            response = requests.post(
                f"{BASE_URL}/leaves/{leave_d_id}/attachments",
                headers=auth_headers(admin_token),
                json={
                    "filename": f"doc{i+2}.pdf",
                    "content_type": "application/pdf",
                    "data_base64": pdf_base64
                }
            )
            if response.status_code == 200:
                print_result(True, f"D4: Added attachment {i+2}/3")
            else:
                print_result(False, f"D4: Failed to add attachment {i+2}: {response.status_code}")
        
        # Try to add 4th (should fail)
        response = requests.post(
            f"{BASE_URL}/leaves/{leave_d_id}/attachments",
            headers=auth_headers(admin_token),
            json={
                "filename": "doc4.pdf",
                "content_type": "application/pdf",
                "data_base64": pdf_base64
            }
        )
        if response.status_code == 400:
            print_result(True, f"D4: 4th attachment correctly rejected (400): {response.json().get('detail')}")
        else:
            print_result(False, f"D4: Expected 400 for 4th attachment, got {response.status_code}")
        
        # Try invalid content type
        response = requests.post(
            f"{BASE_URL}/leaves/{leave_d_id}/attachments",
            headers=auth_headers(admin_token),
            json={
                "filename": "test.txt",
                "content_type": "text/plain",
                "data_base64": "dGVzdA=="
            }
        )
        if response.status_code == 400:
            print_result(True, f"D4: Invalid content type correctly rejected (400)")
        else:
            print_result(False, f"D4: Expected 400 for invalid content type, got {response.status_code}")
        
        # Try oversized file (>5MB)
        # Create a base64 string that's > 5MB (base64 is ~1.33x original size)
        # So we need > 6.67MB base64 to exceed 5MB decoded
        large_base64 = "A" * (7 * 1024 * 1024)  # 7MB of 'A's
        response = requests.post(
            f"{BASE_URL}/leaves/{leave_d_id}/attachments",
            headers=auth_headers(admin_token),
            json={
                "filename": "large.pdf",
                "content_type": "application/pdf",
                "data_base64": large_base64
            }
        )
        if response.status_code == 400:
            print_result(True, f"D4: Oversized file correctly rejected (400)")
        else:
            print_result(False, f"D4: Expected 400 for oversized file, got {response.status_code}")
    except Exception as e:
        print_result(False, f"Exception in D4: {e}")
    
    # D5: Permission check
    print("\n--- D5: Permission check ---")
    try:
        # Create a leave for a different resource (we'll use admin's resource)
        # First, find admin's resource_id
        response = requests.get(
            f"{BASE_URL}/leave-balances",
            headers=auth_headers(admin_token),
            params={"year": CURRENT_YEAR}
        )
        if response.status_code == 200:
            balances = response.json()
            if balances:
                admin_resource_id = balances[0].get("resource_id")
                
                # Create a leave for admin's resource
                start_date, end_date = find_business_day_range(CURRENT_YEAR, 11, 1)
                response = requests.post(
                    f"{BASE_URL}/leaves",
                    headers=auth_headers(admin_token),
                    json={
                        "resource_id": admin_resource_id,
                        "start_date": start_date,
                        "end_date": end_date,
                        "type": FIXED_TYPE_NAME,
                        "notes": "D5 test - admin's leave"
                    }
                )
                if response.status_code == 200:
                    admin_leave = response.json()
                    admin_leave_id = admin_leave["id"]
                    created_leaves.append(admin_leave_id)
                    
                    # Try to add attachment as resource (should fail)
                    response = requests.post(
                        f"{BASE_URL}/leaves/{admin_leave_id}/attachments",
                        headers=auth_headers(resource_token),
                        json={
                            "filename": "unauthorized.pdf",
                            "content_type": "application/pdf",
                            "data_base64": pdf_base64
                        }
                    )
                    if response.status_code == 403:
                        print_result(True, f"D5: Resource correctly denied attaching to other's leave (403)")
                    else:
                        print_result(False, f"D5: Expected 403, got {response.status_code}")
                else:
                    print_result(False, f"D5: Failed to create admin's leave: {response.status_code}")
            else:
                print_result(False, f"D5: No balances found for admin")
        else:
            print_result(False, f"D5: Failed to get admin's balances: {response.status_code}")
    except Exception as e:
        print_result(False, f"Exception in D5: {e}")
    
    # D6: Delete attachment
    if attachment_d1_id:
        print("\n--- D6: Delete attachment ---")
        try:
            response = requests.delete(
                f"{BASE_URL}/leaves/{leave_d_id}/attachments/{attachment_d1_id}",
                headers=auth_headers(admin_token)
            )
            if response.status_code == 200:
                print_result(True, f"D6: Deleted attachment (200)")
                
                # Try to get deleted attachment (should 404)
                response = requests.get(
                    f"{BASE_URL}/leaves/{leave_d_id}/attachments/{attachment_d1_id}",
                    headers=auth_headers(admin_token)
                )
                if response.status_code == 404:
                    print_result(True, f"D6: Deleted attachment returns 404 on GET")
                else:
                    print_result(False, f"D6: Expected 404 for deleted attachment, got {response.status_code}")
            else:
                print_result(False, f"D6: Failed to delete attachment: {response.status_code}")
        except Exception as e:
            print_result(False, f"Exception in D6: {e}")

# ============================================================
# CLEANUP
# ============================================================

print_test("CLEANUP")

# Delete created leaves
print("\n--- Deleting created leaves ---")
for leave_id in created_leaves:
    try:
        response = requests.delete(
            f"{BASE_URL}/leaves/{leave_id}",
            headers=auth_headers(admin_token)
        )
        if response.status_code == 200:
            print(f"  ✅ Deleted leave: {leave_id}")
        else:
            print(f"  ⚠️ Failed to delete leave {leave_id}: {response.status_code}")
    except Exception as e:
        print(f"  ⚠️ Exception deleting leave {leave_id}: {e}")

# Delete created leave types
print("\n--- Deleting created leave types ---")
for type_id in created_leave_types:
    try:
        response = requests.delete(
            f"{BASE_URL}/leave-types/{type_id}",
            headers=auth_headers(admin_token)
        )
        if response.status_code == 200:
            print(f"  ✅ Deleted leave type: {type_id}")
        else:
            print(f"  ⚠️ Failed to delete leave type {type_id}: {response.status_code}")
    except Exception as e:
        print(f"  ⚠️ Exception deleting leave type {type_id}: {e}")

print("\n" + "="*80)
print("LEAVE PHASE 2 TESTING COMPLETE")
print("="*80)
