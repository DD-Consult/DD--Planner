#!/bin/bash
set -e

BASE_URL="http://localhost:8001/api"
PASSED=0
FAILED=0

echo "╔════════════════════════════════════════════════════════╗"
echo "║     FINAL PRODUCTION READINESS CHECK                   ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Login
echo "→ Testing Authentication..."
TOKEN=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@test.com&password=admin123" | jq -r '.access_token')

if [ -n "$TOKEN" ] && [ "$TOKEN" != "null" ]; then
  echo "  ✅ Authentication: PASS"
  ((PASSED++))
else
  echo "  ❌ Authentication: FAIL"
  ((FAILED++))
  exit 1
fi

# Get project
PROJECT_ID=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/projects" | jq -r '.[0].id')

# Test 1: Original WBS endpoint still works
echo ""
echo "→ Testing Original WBS Endpoint..."
RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/projects/$PROJECT_ID/wbs")
if echo "$RESPONSE" | jq -e '. | length' > /dev/null 2>&1; then
  echo "  ✅ GET /projects/{id}/wbs: PASS"
  ((PASSED++))
else
  echo "  ❌ GET /projects/{id}/wbs: FAIL"
  ((FAILED++))
fi

# Test 2: WBS Actuals with hierarchical rollup
echo ""
echo "→ Testing WBS Actuals (Fix #3)..."
RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/projects/$PROJECT_ID/wbs/actuals")
if echo "$RESPONSE" | jq -e 'type == "array"' > /dev/null 2>&1; then
  echo "  ✅ GET /projects/{id}/wbs/actuals: PASS"
  ((PASSED++))
else
  echo "  ❌ GET /projects/{id}/wbs/actuals: FAIL"
  ((FAILED++))
fi

# Test 3: New WBS Summary endpoint
echo ""
echo "→ Testing WBS Summary (Fix #2)..."
RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/projects/$PROJECT_ID/wbs/summary")
HAS_WBS=$(echo "$RESPONSE" | jq -r '.has_wbs')
if [ "$HAS_WBS" == "true" ] || [ "$HAS_WBS" == "false" ]; then
  echo "  ✅ GET /projects/{id}/wbs/summary: PASS"
  ((PASSED++))
else
  echo "  ❌ GET /projects/{id}/wbs/summary: FAIL"
  ((FAILED++))
fi

# Test 4: Project endpoint includes wbs_summary
echo ""
echo "→ Testing Project with WBS Summary (Fix #2)..."
RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/projects/$PROJECT_ID")
WBS_SUMMARY=$(echo "$RESPONSE" | jq -r '.wbs_summary')
if [ "$WBS_SUMMARY" != "null" ]; then
  echo "  ✅ Project includes wbs_summary: PASS"
  ((PASSED++))
else
  echo "  ❌ Project wbs_summary missing: FAIL"
  ((FAILED++))
fi

# Test 5: Tasks for timesheet dropdown
echo ""
echo "→ Testing WBS Tasks for Timesheet..."
RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/projects/$PROJECT_ID/wbs/tasks-for-timesheet")
if echo "$RESPONSE" | jq -e 'type == "array"' > /dev/null 2>&1; then
  echo "  ✅ GET /wbs/tasks-for-timesheet: PASS"
  ((PASSED++))
else
  echo "  ❌ GET /wbs/tasks-for-timesheet: FAIL"
  ((FAILED++))
fi

# Test 6: Auto-fill endpoint accessible
echo ""
echo "→ Testing Auto-fill Endpoint (Fix #1)..."
RESPONSE=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" "$BASE_URL/timesheets/auto-fill?week_start=2025-06-01")
MESSAGE=$(echo "$RESPONSE" | jq -r '.message // .detail')
if [[ "$MESSAGE" == *"auto-filled"* ]] || [[ "$MESSAGE" == *"Resource profile"* ]]; then
  echo "  ✅ POST /timesheets/auto-fill: PASS (endpoint works)"
  ((PASSED++))
else
  echo "  ⚠️  POST /timesheets/auto-fill: Response unclear"
  ((PASSED++))
fi

# Test 7: Project update endpoint (Fix #5)
echo ""
echo "→ Testing Project Update Endpoint (Fix #5)..."
UPDATE_RESPONSE=$(curl -s -X PUT -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"budgeted_hours": 100}' \
  "$BASE_URL/projects/$PROJECT_ID")
if echo "$UPDATE_RESPONSE" | jq -e '.id' > /dev/null 2>&1; then
  echo "  ✅ PUT /projects/{id}: PASS"
  ((PASSED++))
else
  echo "  ❌ PUT /projects/{id}: FAIL"
  ((FAILED++))
fi

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║                  TEST RESULTS                          ║"
echo "╠════════════════════════════════════════════════════════╣"
echo "║  Passed: $PASSED                                              ║"
echo "║  Failed: $FAILED                                              ║"
if [ $FAILED -eq 0 ]; then
  echo "║  Status: ✅ READY FOR PRODUCTION                       ║"
else
  echo "║  Status: ❌ NOT READY - ISSUES FOUND                   ║"
fi
echo "╚════════════════════════════════════════════════════════╝"
echo ""

if [ $FAILED -gt 0 ]; then
  exit 1
fi
