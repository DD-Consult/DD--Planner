# PUT /api/leaves/{id}/set-status - Test Report

## Test Execution Summary
**Date:** October 21, 2026  
**Backend URL:** https://proposal-approve.preview.emergentagent.com/api  
**Result:** ✅ **8/8 TESTS PASSED (100%)**

---

## Detailed Test Results

### STEP 1: Create Leave as Resource
**Action:** Login as `qa_resource@test.com` and POST /api/leaves  
**Payload:**
```json
{
  "start_date": "2026-11-17",
  "end_date": "2026-11-19",
  "type": "Vacation",
  "notes": "qa setstatus"
}
```

**Expected:** HTTP 200/201, status="Pending"  
**Actual Response:**
- HTTP Status: `200`
- Leave ID: `6ad825b520b01b18c544411c`
- Resource ID: `6ab25bc82be78e05e89230ef`
- Status: `Pending`

**Result:** ✅ **PASS**

---

### STEP 2: Approve Leave (Super Admin)
**Action:** Login as `superadmin@test.com` and PUT /api/leaves/{id}/set-status  
**Payload:**
```json
{
  "status": "Approved"
}
```

**Expected:** HTTP 200, status="Approved", approver_email="superadmin@test.com", decided_at non-null  
**Actual Response:**
- HTTP Status: `200`
- Status: `Approved`
- Approver Email: `superadmin@test.com`
- Decided At: `2026-10-21T02:38:46.041082+00:00`

**Result:** ✅ **PASS**

---

### STEP 3: CORE TEST - Change Already-Approved Leave to Rejected
**Action:** PUT /api/leaves/{id}/set-status (as super_admin)  
**Payload:**
```json
{
  "status": "Rejected",
  "note": "revoked by QA"
}
```

**Expected:** HTTP 200, status="Rejected", decision_note="revoked by QA"  
**Actual Response:**
- HTTP Status: `200`
- Status: `Rejected`
- Decision Note: `revoked by QA`

**Result:** ✅ **PASS** ✅✅✅ **CORE REQUIREMENT VERIFIED**

**This proves that a super_admin CAN change an already-approved leave status.**

---

### STEP 4: Change Status to Pending
**Action:** PUT /api/leaves/{id}/set-status (as super_admin)  
**Payload:**
```json
{
  "status": "Pending"
}
```

**Expected:** HTTP 200, status="Pending", approver_email=null, decided_at=null  
**Actual Response:**
- HTTP Status: `200`
- Status: `Pending`
- Approver Email: `None`
- Decided At: `None`

**Result:** ✅ **PASS**

---

### STEP 5: Invalid Status Test
**Action:** PUT /api/leaves/{id}/set-status (as super_admin)  
**Payload:**
```json
{
  "status": "Bogus"
}
```

**Expected:** HTTP 400  
**Actual Response:**
- HTTP Status: `400`

**Result:** ✅ **PASS**

---

### STEP 6a: RBAC Test - Admin Role
**Action:** Login as `admin@test.com` and PUT /api/leaves/{id}/set-status  
**Payload:**
```json
{
  "status": "Approved"
}
```

**Expected:** HTTP 403 (Forbidden)  
**Actual Response:**
- HTTP Status: `403`

**Result:** ✅ **PASS**

---

### STEP 6b: RBAC Test - Resource Role
**Action:** Login as `qa_resource@test.com` and PUT /api/leaves/{id}/set-status  
**Payload:**
```json
{
  "status": "Approved"
}
```

**Expected:** HTTP 403 (Forbidden)  
**Actual Response:**
- HTTP Status: `403`

**Result:** ✅ **PASS**

---

### STEP 7: Non-Existent Leave ID (404 Test)
**Action:** PUT /api/leaves/000000000000000000000000/set-status (as super_admin)  
**Payload:**
```json
{
  "status": "Approved"
}
```

**Expected:** HTTP 404 (Not Found)  
**Actual Response:**
- HTTP Status: `404`

**Result:** ✅ **PASS**

---

### CLEANUP
**Action:** DELETE /api/leaves/{id} (as super_admin)  
**Result:** HTTP 200 - Test leave deleted successfully

---

## Summary Table

| Step | Test Case | Expected | Actual | Result |
|------|-----------|----------|--------|--------|
| 1 | Create leave as resource | status='Pending' | status='Pending' | ✅ PASS |
| 2 | Approve leave (super_admin) | status='Approved', approver_email='superadmin@test.com', decided_at non-null | status='Approved', approver_email='superadmin@test.com', decided_at='2026-10-21T02:38:46.041082+00:00' | ✅ PASS |
| 3 | **Change Approved→Rejected (CORE)** | status='Rejected', decision_note='revoked by QA' | status='Rejected', decision_note='revoked by QA' | ✅ **PASS** |
| 4 | Change to Pending | status='Pending', approver_email=null, decided_at=null | status='Pending', approver_email=None, decided_at=None | ✅ PASS |
| 5 | Invalid status 'Bogus' | 400 | 400 | ✅ PASS |
| 6a | RBAC: admin tries set-status | 403 | 403 | ✅ PASS |
| 6b | RBAC: resource tries set-status | 403 | 403 | ✅ PASS |
| 7 | Non-existent leave ID | 404 | 404 | ✅ PASS |

---

## Final Verdict

✅✅✅ **ALL TESTS PASSED (8/8 = 100%)**

### Key Findings:
1. ✅ **CORE REQUIREMENT VERIFIED:** Super admin CAN change an already-decided leave (Approved → Rejected)
2. ✅ Status transitions work correctly: Pending → Approved → Rejected → Pending
3. ✅ Decision metadata (approver_email, decided_at, decision_note) is properly set and cleared
4. ✅ RBAC enforcement working: Only super_admin can use set-status endpoint (admin and resource get 403)
5. ✅ Validation working: Invalid status returns 400
6. ✅ Error handling working: Non-existent leave ID returns 404
7. ✅ No 500 errors encountered

### Authentication Details:
- OAuth2 form-encoded login working correctly
- Token format: Bearer token in Authorization header
- All three test accounts authenticated successfully

### Test Artifacts:
- Test script: `/app/backend_test_set_status.py`
- Test leave ID: `6ad825b520b01b18c544411c` (cleaned up)
- Resource ID: `6ab25bc82be78e05e89230ef`

**NO CODE MODIFICATIONS WERE MADE - THIS IS A PURE TEST REPORT**
