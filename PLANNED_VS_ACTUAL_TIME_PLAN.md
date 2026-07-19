# Planned vs Actual Time Tracking - Implementation Plan

## Executive Summary
Comprehensive plan to implement multi-level time tracking (Project → Phase → Resource) with automated pre-filling and drill-down reporting capabilities. Leverages existing allocations, weekly check-ins, and phase structures.

---

## Current System Analysis

### ✅ What We Have
1. **Allocations**: 
   - Fields: `percentage`, `hours`, `actual_percentage`, `confirmation_status`
   - Linked to projects, resources, and phases
   - Already tracks planned allocation (percentage/hours)

2. **Weekly Check-in System**:
   - Thursday/Friday restricted timesheet submissions (Sydney timezone)
   - Manual entry of `actual_percentage` per allocation
   - Confirmation workflow (Pending → Confirmed)

3. **Project Structure**:
   - Projects with phases (start_date, end_date)
   - Resource allocations can be assigned to specific phases
   - Project status tracking (Active, Pipeline, Completed)

4. **Status Updates Collection**:
   - Weekly project health check-ins
   - Progress tracking at project level

### 🔴 What's Missing
1. **Time-based tracking**: Currently only percentage-based
2. **Historical data**: No week-by-week time log
3. **Automated pre-filling**: Manual entry only
4. **Variance analysis**: No planned vs actual comparison
5. **Drill-down reporting**: No hierarchical views
6. **Phase-level actual time**: Can't track actuals per phase
7. **Budget tracking**: No cost calculations

---

## Proposed Solution Architecture

### Phase 1: Database Schema Enhancement (Week 1)

#### 1.1 New Collection: `timesheets`
Weekly time entries for granular tracking:

```javascript
{
  _id: "uuid",
  resource_id: "uuid",
  project_id: "uuid",
  phase_id: "uuid" (optional - if allocated to specific phase),
  week_start_date: "2026-01-20",
  week_end_date: "2026-01-26",
  
  // Planned data (from allocation)
  planned_hours: 40.0,
  planned_percentage: 100,
  
  // Actual data (user confirms/edits)
  actual_hours: 35.5,
  actual_percentage: 89,
  
  // Metadata
  status: "Draft" | "Submitted" | "Approved",
  submitted_at: "2026-01-24T10:00:00Z",
  notes: "User notes about the week",
  auto_filled: true,
  modified_by_user: false,
  
  // Variance (calculated)
  variance_hours: -4.5,
  variance_percentage: -11
}
```

**Benefits:**
- Historical tracking (week-by-week log)
- Supports automation (pre-filled from allocations)
- User can confirm or edit
- Maintains audit trail

#### 1.2 Enhance `allocations` Collection
Add calculated fields:

```javascript
{
  // Existing fields...
  percentage: 50,
  hours: 40,
  actual_percentage: 45,
  
  // NEW: Aggregated actuals
  total_planned_hours: 160.0,  // Calculated from allocation duration
  total_actual_hours: 142.0,   // Sum of timesheet entries
  variance_hours: -18.0,
  utilization_rate: 88.75,     // (actual / planned) * 100
  
  // NEW: Cost tracking (optional)
  hourly_rate: 150.00,         // From resource rate card
  planned_cost: 24000.00,      // total_planned_hours * hourly_rate
  actual_cost: 21300.00,       // total_actual_hours * hourly_rate
  cost_variance: -2700.00
}
```

#### 1.3 Enhance `projects` Collection
Add rollup fields:

```javascript
{
  // Existing fields...
  
  // NEW: Time tracking rollups
  total_planned_hours: 800.0,    // Sum of all allocation planned hours
  total_actual_hours: 720.0,     // Sum of all timesheet actual hours
  variance_hours: -80.0,
  completion_percentage: 90.0,   // (actual / planned) * 100
  
  // NEW: Budget tracking
  planned_budget: 120000.00,
  actual_cost: 108000.00,
  budget_variance: -12000.00,
  burn_rate: 0.90               // actual / planned
}
```

---

### Phase 2: Backend API Development (Week 1-2)

#### 2.1 Timesheet Management APIs

**POST /api/timesheets/auto-fill**
- Generates timesheet entries for current week based on active allocations
- Pre-fills planned hours/percentage
- Marks entries as `auto_filled: true`
- Returns: List of draft timesheets for user review

**GET /api/timesheets/my-week?week_start={date}**
- Returns current user's timesheet entries for specified week
- Groups by project/phase
- Includes planned vs actual comparison
- Status: Draft, Submitted, Approved

**PUT /api/timesheets/{id}**
- User edits auto-filled or creates manual entry
- Sets `modified_by_user: true`
- Validates: actual_hours <= (working_hours_per_week * allocation_percentage)

**POST /api/timesheets/submit-week**
- Bulk submit all timesheets for the week
- Changes status: Draft → Submitted
- Triggers recalculation of project/allocation aggregates
- Restricted to Thursday/Friday (existing logic)

**GET /api/timesheets/pending-approvals**
- For managers: List of submitted timesheets awaiting approval
- Filterable by project, resource, date range

**POST /api/timesheets/{id}/approve**
- Manager approves timesheet
- Status: Submitted → Approved
- Locks entry from further editing

#### 2.2 Reporting APIs

**GET /api/reports/planned-vs-actual/project/{project_id}**
Returns:
```json
{
  "project": {
    "id": "...",
    "name": "Website Redesign",
    "planned_hours": 800,
    "actual_hours": 720,
    "variance_hours": -80,
    "variance_percentage": -10,
    "completion_rate": 90
  },
  "phases": [
    {
      "name": "Discovery",
      "planned_hours": 200,
      "actual_hours": 180,
      "variance_hours": -20,
      "completion_rate": 90
    }
  ],
  "resources": [
    {
      "name": "Don",
      "planned_hours": 400,
      "actual_hours": 360,
      "variance_hours": -40,
      "utilization_rate": 90
    }
  ]
}
```

**GET /api/reports/time-tracking/summary**
- Dashboard-level summary
- Team utilization
- Projects at risk (high variance)
- Weekly burn rate trends

**GET /api/reports/time-tracking/resource/{resource_id}**
- Individual resource report
- Week-by-week breakdown
- Multi-project time distribution
- Utilization trends

**GET /api/reports/time-tracking/export**
- CSV/Excel export
- Supports filters: date range, project, resource, phase
- Detailed transaction log

#### 2.3 Calculation Engine

**Background Job: `calculate_project_actuals()`**
- Runs after timesheet submission
- Aggregates timesheet entries → allocation totals
- Aggregates allocation totals → phase totals
- Aggregates phase totals → project totals
- Updates variance and completion rates

**Formula Reference:**
```python
# Planned hours calculation (from allocation)
planned_hours = (allocation.percentage / 100) * 
                working_hours_per_week * 
                number_of_weeks_in_allocation

# Variance
variance_hours = actual_hours - planned_hours
variance_percentage = (variance_hours / planned_hours) * 100

# Utilization rate
utilization_rate = (actual_hours / planned_hours) * 100

# Burn rate (project level)
burn_rate = actual_cost / planned_budget
```

---

### Phase 3: Frontend Development (Week 2-3)

#### 3.1 Enhanced Weekly Check-in Component

**Location:** `/app/frontend/src/components/WeeklyCheckin.js`

**New Features:**
1. **Auto-fill Button**
   - "Pre-fill This Week" button
   - Calls `/api/timesheets/auto-fill`
   - Shows loading state during generation
   - Displays success message with count

2. **Editable Timesheet Grid**
   ```
   Project        | Phase       | Planned | Actual | Variance | Status
   ---------------------------------------------------------------------------
   Website        | Discovery   | 40h     | [36h]  | -4h      | ✏️ Draft
   MVP 1          | Development | 20h     | [20h]  | 0h       | ✏️ Draft
   ---------------------------------------------------------------------------
   Total                        | 60h     | 56h    | -4h      |
   ```

3. **Inline Editing**
   - Click actual hours to edit
   - Real-time variance calculation
   - Visual indicators (green/amber/red for variance)
   - Save individual entries or bulk submit

4. **Notes Field**
   - Optional notes per entry
   - "Explain variance" prompt if >20% deviation

5. **Submit Week Button**
   - Validates all entries filled
   - Shows confirmation dialog
   - Restricted to Thursday/Friday

#### 3.2 New Component: `TimesheetHistory.js`

**Features:**
- Calendar view of submitted weeks
- Click week to see detail
- Visual heat map (utilization intensity)
- Filter by project/date range
- Export to CSV

#### 3.3 Project Detail Page Enhancement

**Location:** `/app/frontend/src/pages/ProjectDetail.js`

**New Tab: "Time Tracking"**

Shows:
1. **Summary Cards**
   - Total Planned Hours
   - Total Actual Hours
   - Variance (hours & %)
   - Completion Rate
   - Budget Variance (if enabled)

2. **Phase Breakdown Table**
   ```
   Phase         | Planned | Actual | Variance | Progress | Status
   ------------------------------------------------------------------
   Discovery     | 200h    | 180h   | -20h     | 90%      | ✅ Complete
   Development   | 400h    | 320h   | -80h     | 80%      | 🟡 In Progress
   Testing       | 200h    | 0h     | 0h       | 0%       | ⏳ Not Started
   ------------------------------------------------------------------
   Total         | 800h    | 500h   | -100h    | 62.5%    |
   ```

3. **Resource Breakdown Table**
   ```
   Resource   | Role        | Planned | Actual | Utilization | Variance
   ----------------------------------------------------------------------
   Don        | PM          | 400h    | 360h   | 90%         | -40h
   Priya      | Developer   | 400h    | 140h   | 35%         | -260h (⚠️ Under-utilized)
   ----------------------------------------------------------------------
   ```

4. **Time Trend Chart**
   - Line chart: Planned vs Actual over weeks
   - Shows trajectory
   - Forecasts completion date based on burn rate

5. **Drill-down Capability**
   - Click phase → see resource breakdown for that phase
   - Click resource → see week-by-week timesheet entries
   - Expandable rows with detail

#### 3.4 Dashboard Widget: Time Tracking Summary

**Location:** `/app/frontend/src/pages/Dashboard.js`

**New Widget: "Team Time Tracking"**
- Cards:
  - This Week's Utilization: 78%
  - Pending Timesheet Approvals: 12
  - Projects Over Budget: 2
  - Top Performer: Don (95% utilization)

- Visual:
  - Bar chart: Team member utilization this week
  - Sparkline: 4-week utilization trend

---

### Phase 4: Automation Logic (Week 3)

#### 4.1 Auto-fill Algorithm

**Trigger:** User clicks "Pre-fill This Week" OR cron job runs Monday 9am

**Logic:**
```python
def auto_fill_timesheets(resource_id, week_start_date):
    # Get active allocations for this resource
    allocations = get_active_allocations(resource_id, week_start_date)
    
    # For each allocation
    for allocation in allocations:
        # Calculate planned hours for this week
        planned_hours = calculate_weekly_hours(
            allocation.percentage,
            allocation.start_date,
            allocation.end_date,
            week_start_date
        )
        
        # Check if timesheet already exists
        existing = get_timesheet(
            resource_id, 
            allocation.project_id, 
            week_start_date
        )
        
        if existing:
            # Update only if user hasn't modified
            if not existing.modified_by_user:
                existing.planned_hours = planned_hours
                existing.actual_hours = planned_hours  # Default assumption
        else:
            # Create new draft entry
            create_timesheet({
                resource_id: resource_id,
                project_id: allocation.project_id,
                phase_id: allocation.phase_id,
                week_start_date: week_start_date,
                planned_hours: planned_hours,
                actual_hours: planned_hours,  # Pre-filled with planned
                status: "Draft",
                auto_filled: true
            })
    
    return success
```

**Smart Features:**
1. **Carryover Logic**: If last week's actual < planned, suggest makeup hours
2. **Holiday Detection**: Reduce auto-filled hours for holiday weeks
3. **Partial Week**: Prorate hours if allocation starts/ends mid-week
4. **Multiple Projects**: Distribute hours proportionally across projects

#### 4.2 Exception Handling

**Scenarios where user must intervene:**
1. Allocation changed mid-week → Flag for review
2. New project added → Not auto-filled, user must enter
3. Leave taken → Reduce planned hours, flag for confirmation
4. Over-allocation (>100%) → Warning, user must prioritize

---

### Phase 5: Advanced Features (Week 4)

#### 5.1 Budget Tracking Integration

**Prerequisites:**
- Resource hourly rates defined
- Project budget configured

**Features:**
- Cost variance tracking (planned vs actual spend)
- Burn rate calculations
- Budget alerts (80%, 90%, 100% thresholds)
- Forecast: Estimated cost at completion

**New Fields:**
- `resources.hourly_rate: float`
- `projects.budget: float`
- Calculations happen in real-time

#### 5.2 Client Reporting

**New Page:** `/client-reports/{project_id}`

**Features:**
- Simplified, client-friendly view
- Hides internal cost details (optional)
- Shows:
  - Project progress (% complete)
  - Hours invested
  - Milestone completion
  - Next period forecast
- PDF export for invoicing

#### 5.3 Capacity Planning Enhancement

**Leverage time tracking data:**
- Historical utilization rates → Improve future allocation predictions
- Identify over/under-utilized resources
- Suggest rebalancing
- "Available capacity" widget (considers actual vs planned patterns)

---

## Implementation Timeline

### Week 1: Foundation
- [ ] Database schema design and migration
- [ ] Backend APIs for timesheet CRUD
- [ ] Auto-fill algorithm implementation
- [ ] Unit tests for calculation engine

### Week 2: Core UI
- [ ] Enhanced WeeklyCheckin component
- [ ] Project Detail "Time Tracking" tab
- [ ] Reporting APIs (planned vs actual)
- [ ] Frontend integration tests

### Week 3: Automation & Polish
- [ ] Auto-fill cron job setup
- [ ] Exception handling logic
- [ ] Dashboard widgets
- [ ] Historical reporting views

### Week 4: Advanced Features
- [ ] Budget tracking integration
- [ ] Client reporting portal
- [ ] Export functionality (CSV/PDF)
- [ ] Capacity planning enhancements

### Week 5: Testing & Refinement
- [ ] End-to-end testing with testing agent
- [ ] Performance optimization
- [ ] User acceptance testing
- [ ] Documentation and training materials

---

## Data Migration Strategy

### Existing Data Handling
1. **Current allocations**: Keep as-is (no disruption)
2. **Historical `actual_percentage`**: 
   - One-time migration script
   - Convert to timesheet entries (retroactive)
   - Mark as `migrated: true`
3. **Going forward**: New timesheet-based tracking

### Migration Script Pseudocode:
```python
# For each confirmed allocation with actual_percentage
for allocation in confirmed_allocations:
    # Calculate actual hours from percentage
    actual_hours = (allocation.actual_percentage / 100) * 
                   calculate_total_hours(allocation)
    
    # Create historical timesheet entries (weekly breakdown)
    create_historical_timesheets(
        allocation,
        actual_hours,
        status="Approved",
        migrated=true
    )
```

---

## Key Design Decisions

### 1. Why Weekly Timesheets vs Daily?
**Rationale:**
- Aligns with existing Thursday/Friday submission workflow
- Lower overhead for team members
- Sufficient granularity for project planning
- Can aggregate to daily if needed later

**Trade-off:** Less precision, but better adoption

### 2. Why Auto-fill with Confirmation vs Pure Manual?
**Rationale:**
- Reduces data entry burden (user experience)
- Maintains accuracy (user reviews and edits)
- Encourages timely submission
- Catches allocation changes automatically

**Trade-off:** More complex logic, but worth it

### 3. Why Separate `timesheets` Collection vs Extending `allocations`?
**Rationale:**
- Allocations = Plan (forward-looking)
- Timesheets = Actuals (historical log)
- Enables week-by-week variance tracking
- Supports audit trail and versioning
- Cleaner data model

**Trade-off:** More storage, more joins, but better architecture

---

## Success Metrics

### Adoption Metrics
- % of team submitting timesheets weekly: Target >90%
- Average time to submit: Target <10 minutes
- Auto-fill acceptance rate: Target >80% (minimal edits)

### Business Metrics
- Variance accuracy: ±5% between planned and actual
- Budget tracking: 100% of projects with cost visibility
- Forecasting improvement: Delivery prediction within ±1 week
- Resource utilization: Team average between 75-85%

### System Metrics
- API response time: <500ms for reports
- Auto-fill processing: <5 seconds for team of 50
- Report generation: <2 seconds for drill-down

---

## Risk Assessment

### High Risk
1. **User adoption**: Team may resist time tracking
   - **Mitigation**: Make it fast (auto-fill), show value (reports), management buy-in

2. **Data accuracy**: Garbage in, garbage out
   - **Mitigation**: Validation rules, variance alerts, periodic audits

### Medium Risk
3. **Performance**: Large datasets (1000s of timesheets)
   - **Mitigation**: Indexing, caching, pagination, background jobs

4. **Complexity**: Multi-level drill-down can be complex
   - **Mitigation**: Phased rollout, user testing, iterative design

### Low Risk
5. **Integration**: Existing system already has foundational pieces
   - **Mitigation**: Leverage what works, extend incrementally

---

## Next Steps for Approval

### Questions for User:
1. **Budget tracking priority**: Implement in Phase 1 or defer to Phase 5?
2. **Approval workflow**: Do managers need to approve timesheets, or is self-service sufficient?
3. **Holiday calendar integration**: Should we integrate company holidays to auto-adjust planned hours?
4. **Client visibility**: Should clients have direct access to time reports, or via admin only?
5. **Billing integration**: Any existing billing system to integrate with?

### Decision Required:
- **Proceed with Week 1 implementation?**
  - If yes: Start with database schema and core APIs
  - Timeline: 5 weeks to full rollout
  - Resource requirement: 1 full-time developer + testing

---

## Technical Notes

### Database Indexes Needed
```javascript
// timesheets collection
db.timesheets.createIndex({ resource_id: 1, week_start_date: -1 })
db.timesheets.createIndex({ project_id: 1, week_start_date: -1 })
db.timesheets.createIndex({ status: 1 })

// allocations collection  
db.allocations.createIndex({ project_id: 1, resource_id: 1 })
db.allocations.createIndex({ start_date: 1, end_date: 1 })
```

### API Rate Limiting
- Auto-fill endpoint: 5 requests/minute per user
- Report generation: 20 requests/minute
- Timesheet submission: 10 requests/minute

### Caching Strategy
- Project totals: Cache for 5 minutes
- Dashboard stats: Cache for 1 minute
- Timesheet lists: No cache (real-time)

---

## Appendix: UI Mockups

### A. Weekly Check-in (Enhanced)
```
┌────────────────────────────────────────────────────────────┐
│  My Weekly Check-in                                        │
│  Week: Jan 20 - Jan 26, 2026                    [Pre-fill] │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  Project         Phase      Planned  Actual  Variance      │
│  ──────────────────────────────────────────────────────    │
│  Website         Discovery   40h    [36h]    -4h  ⚠️       │
│  Redesign                                                   │
│                                                             │
│  MVP 1           Dev Sprint  20h    [20h]    0h   ✅       │
│                                                             │
│  FX1 Audit       Testing     0h     [8h]     +8h  📝       │
│  (Unplanned)                                                │
│  ──────────────────────────────────────────────────────    │
│  Total:                      60h     64h     +4h           │
│                                                             │
│  Notes: Extra hours on FX1 due to urgent bug fix           │
│                                                             │
│                                    [Save Draft] [Submit →] │
└────────────────────────────────────────────────────────────┘
```

### B. Project Time Tracking Tab
```
┌────────────────────────────────────────────────────────────┐
│  Website Redesign Project > Time Tracking                  │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  Summary                                                    │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐          │
│  │ 800h   │  │ 720h   │  │ -80h   │  │ 90%    │          │
│  │Planned │  │ Actual │  │Variance│  │Complete│          │
│  └────────┘  └────────┘  └────────┘  └────────┘          │
│                                                             │
│  Phase Breakdown                              [Export CSV] │
│  Phase        Planned  Actual  Var.   Progress  ───Chart── │
│  ──────────────────────────────────────────────────────    │
│  ▼ Discovery   200h    180h   -20h    90%    ▓▓▓▓▓▓▓▓▓░   │
│     Don         100h    90h   -10h                          │
│     Priya       100h    90h   -10h                          │
│                                                             │
│  ▼ Development 400h    320h   -80h    80%    ▓▓▓▓▓▓▓▓░░   │
│     Don         200h   180h   -20h                          │
│     Priya       200h   140h   -60h    ⚠️ Under-utilized   │
│                                                             │
│  ▶ Testing     200h      0h     0h     0%    ░░░░░░░░░░   │
│  ──────────────────────────────────────────────────────    │
│  Total:        800h    500h  -100h    62.5%                │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

---

**Document Version:** 1.0  
**Created:** 2026-01-22  
**Last Updated:** 2026-01-22  
**Status:** Pending Approval
