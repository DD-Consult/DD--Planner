# Planned vs Actual Time Tracking - Implementation Checklist

## Phase 1: Backend Foundation (Current Session)

### Step 1: Database Models (Backend)
- [ ] Add Pydantic models for Timesheet (Create, Update, Response)
- [ ] Add timesheets_collection to database collections
- [ ] No changes to existing models/collections
- [ ] Test: Verify existing API endpoints still work

### Step 2: Core Timesheet APIs
- [ ] POST /api/timesheets - Create single timesheet entry
- [ ] GET /api/timesheets/my-week - Get current user's week
- [ ] PUT /api/timesheets/{id} - Update timesheet entry
- [ ] DELETE /api/timesheets/{id} - Delete timesheet entry
- [ ] Test: All CRUD operations work, existing features unaffected

### Step 3: Auto-fill Logic
- [ ] POST /api/timesheets/auto-fill - Generate draft timesheets for week
- [ ] Helper function: calculate_weekly_hours()
- [ ] Helper function: get_active_allocations_for_week()
- [ ] Test: Auto-fill creates correct entries, doesn't modify allocations

### Step 4: Submission Workflow
- [ ] POST /api/timesheets/submit-week - Bulk submit for week
- [ ] Validation: Check Thursday/Friday restriction (reuse existing logic)
- [ ] Status transitions: Draft → Submitted
- [ ] Test: Submission works, respects day restrictions

### Step 5: Backend Testing
- [ ] Unit tests for helper functions
- [ ] API tests via curl
- [ ] Integration test: Full workflow (auto-fill → edit → submit)
- [ ] Verify: No impact on existing allocations, weekly check-in

---

## Phase 2: Basic Frontend (Next Session)

### Step 6: Enhanced Weekly Check-in
- [ ] Add "Pre-fill This Week" button to WeeklyCheckin.js
- [ ] Display timesheet entries in editable grid
- [ ] Inline editing of actual hours
- [ ] Real-time variance calculation
- [ ] Test: Existing weekly check-in functionality preserved

### Step 7: API Integration
- [ ] Add new API functions to api.js
- [ ] Integrate with TanStack Query
- [ ] Error handling and loading states
- [ ] Test: No regressions in existing features

### Step 8: Frontend Testing
- [ ] UI testing with screenshot tool
- [ ] Call testing_agent for comprehensive test
- [ ] Verify: Original weekly check-in still works as before

---

## Phase 3: Reporting (Future Session)

### Step 9: Project Detail Time Tracking Tab
- [ ] New tab in ProjectDetail.js
- [ ] Summary cards (planned, actual, variance)
- [ ] Phase breakdown table
- [ ] Resource breakdown table

### Step 10: Reporting APIs
- [ ] GET /api/reports/planned-vs-actual/project/{id}
- [ ] Aggregation logic for rollups
- [ ] Export to CSV endpoint

---

## Safety Checklist (Before Each Commit)

✅ **Before making changes:**
- [ ] View the file to understand existing structure
- [ ] Identify exact insertion points (don't replace working code)
- [ ] Plan additions that don't modify existing logic

✅ **After making changes:**
- [ ] Compile check (esbuild for frontend, Python for backend)
- [ ] Check logs for errors
- [ ] Test affected endpoints/components
- [ ] Verify existing features still work

✅ **If anything breaks:**
- [ ] Immediately identify the breaking change
- [ ] Revert via search_replace to previous working state
- [ ] Re-plan the approach
- [ ] Try alternative implementation

---

## Current Session Goals

**Goal:** Complete Steps 1-5 (Backend Foundation)
**Success Criteria:**
- New timesheet endpoints work
- Auto-fill generates correct entries
- Existing features (allocations, weekly check-in) unaffected
- All tests pass

**Next Session:** Steps 6-8 (Frontend Integration)
