# Timesheet System - Complete Technical Documentation

## Overview
The timesheet system tracks actual hours worked by resources on projects, compared against planned allocations. This document explains the complete data flow, storage, and retrieval process.

---

## Database Storage

### Collection: `timesheets`
**Location:** MongoDB database `resource_planner`
**Collection name:** `timesheets`

### Document Schema
```javascript
{
  _id: ObjectId,                    // MongoDB auto-generated ID
  resource_id: String,               // UUID of the resource (team member)
  project_id: String,                // UUID of the project
  phase_id: String | null,           // UUID of project phase (optional)
  
  week_start_date: DateTime,         // Monday of the week (ISO format)
  week_end_date: DateTime,           // Sunday of the week (ISO format)
  
  planned_hours: Float,              // Hours planned from allocation
  actual_hours: Float,               // Hours actually worked (user input)
  
  variance_hours: Float,             // Calculated: actual - planned
  variance_percentage: Float,        // Calculated: (variance/planned) * 100
  
  notes: String | null,              // Optional user notes
  status: String,                    // "Draft" | "Submitted" | "Approved"
  
  auto_filled: Boolean,              // True if pre-filled by system
  modified_by_user: Boolean,         // True if user edited values
  
  submitted_at: DateTime | null,     // When submitted
  created_at: DateTime               // When created
}
```

### Example Document
```json
{
  "_id": "507f1f77bcf86cd799439011",
  "resource_id": "6949f32496943efb2c1d331f",
  "project_id": "6949f32496943efb2c1d3321",
  "phase_id": "abc123def456",
  "week_start_date": "2026-01-27T00:00:00Z",
  "week_end_date": "2026-02-02T00:00:00Z",
  "planned_hours": 40.0,
  "actual_hours": 36.5,
  "variance_hours": -3.5,
  "variance_percentage": -8.75,
  "notes": "Took sick leave on Friday",
  "status": "Submitted",
  "auto_filled": true,
  "modified_by_user": true,
  "submitted_at": "2026-01-31T14:30:00Z",
  "created_at": "2026-01-27T09:00:00Z"
}
```

---

## Complete Workflow Process

### Step 1: Auto-Fill (Monday Morning)

**Trigger:** User clicks "Pre-fill This Week" button on Dashboard

**API Call:**
```http
POST /api/timesheets/auto-fill?week_start=2026-01-27
Authorization: Bearer <token>
```

**Backend Process** (server.py lines 2395-2495):
1. Parse week_start date
2. Calculate week_end (start + 6 days)
3. Find current user's resource profile
4. Query all active allocations for this resource that overlap with the week
5. For each allocation:
   - Calculate planned hours using `calculate_weekly_hours()` function
   - Check if timesheet already exists for this project/phase/week
   - If exists and not modified by user → update planned hours
   - If doesn't exist → create new draft timesheet with:
     - `planned_hours` = calculated from allocation
     - `actual_hours` = planned_hours (default assumption)
     - `status` = "Draft"
     - `auto_filled` = True
     - `modified_by_user` = False
6. Return count of created/updated timesheets

**Database Operations:**
```javascript
// Check existing
db.timesheets.findOne({
  resource_id: "...",
  project_id: "...",
  phase_id: "...",
  week_start_date: ISODate("2026-01-27")
})

// Insert new
db.timesheets.insertOne({
  resource_id: "...",
  project_id: "...",
  // ... all fields
  status: "Draft",
  created_at: new Date()
})
```

**Response:**
```json
{
  "message": "Timesheets auto-filled successfully",
  "created": 3,
  "updated": 1,
  "skipped": 0,
  "total": 4
}
```

### Step 2: View Timesheets (Dashboard)

**Component:** `TimesheetWeeklyCheckin.js`

**API Call:**
```http
GET /api/timesheets/my-week?week_start=2026-01-27
Authorization: Bearer <token>
```

**Backend Process** (server.py lines 2302-2332):
1. Parse week_start parameter
2. Find user's resource profile
3. Query timesheets:
   ```javascript
   db.timesheets.find({
     resource_id: "...",
     week_start_date: { $gte: start, $lte: end }
   })
   ```
4. Return array of timesheets

**Response:**
```json
[
  {
    "id": "507f1f77bcf86cd799439011",
    "resource_id": "6949f32496943efb2c1d331f",
    "project_id": "6949f32496943efb2c1d3321",
    "week_start_date": "2026-01-27T00:00:00",
    "planned_hours": 40.0,
    "actual_hours": 40.0,
    "variance_hours": 0.0,
    "status": "Draft",
    "auto_filled": true
  }
]
```

**Frontend Display:**
- Shows table with: Project | Planned | Actual | Variance | Status
- "Edit" button for each draft entry
- "Submit Week" button at bottom

### Step 3: Edit Timesheet (User Adjusts Hours)

**Trigger:** User clicks "Edit" on a timesheet entry

**Frontend:** Opens inline editor with:
- Actual hours input (number field)
- Notes textarea

**API Call (on Save):**
```http
PUT /api/timesheets/507f1f77bcf86cd799439011
Authorization: Bearer <token>
Content-Type: application/json

{
  "actual_hours": 36.5,
  "notes": "Took sick leave on Friday"
}
```

**Backend Process** (server.py lines 2334-2372):
1. Find timesheet by ID
2. Verify ownership (user can only edit their own)
3. Check status (can't edit if Submitted or Approved)
4. Update fields
5. Recalculate variance:
   ```python
   variance_hours = actual_hours - planned_hours
   variance_percentage = (variance_hours / planned_hours * 100)
   ```
6. Set `modified_by_user = True`
7. Save to database

**Database Operation:**
```javascript
db.timesheets.updateOne(
  { _id: ObjectId("507f1f77bcf86cd799439011") },
  { 
    $set: {
      actual_hours: 36.5,
      variance_hours: -3.5,
      variance_percentage: -8.75,
      notes: "Took sick leave on Friday",
      modified_by_user: true
    }
  }
)
```

**Response:**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "actual_hours": 36.5,
  "variance_hours": -3.5,
  "variance_percentage": -8.75,
  "notes": "Took sick leave on Friday",
  "status": "Draft"
}
```

### Step 4: Submit Week (Thursday/Friday Only)

**Trigger:** User clicks "Submit Week" button

**Day Restriction Check:**
```http
GET /api/timesheet/can-update
```
Returns: `{"allowed": true/false, "current_day": "Thursday"}`

**API Call:**
```http
POST /api/timesheets/submit-week?week_start=2026-01-27
Authorization: Bearer <token>
```

**Backend Process** (server.py lines 2498-2525):
1. Check if today is Thursday or Friday (Sydney timezone)
2. If not → return 403 Forbidden
3. Find all Draft timesheets for this user and week
4. Update all to "Submitted" status
5. Set `submitted_at` timestamp

**Database Operation:**
```javascript
db.timesheets.updateMany(
  {
    resource_id: "...",
    week_start_date: ISODate("2026-01-27"),
    status: "Draft"
  },
  {
    $set: {
      status: "Submitted",
      submitted_at: new Date()
    }
  }
)
```

**Response:**
```json
{
  "message": "Timesheets submitted successfully",
  "submitted_count": 4
}
```

### Step 5: View in Reports (Project Detail Page)

**Location:** Project Detail → Time Tracking tab

**API Call:**
```http
GET /api/reports/planned-vs-actual/project/6949f32496943efb2c1d3321
Authorization: Bearer <token>
```

**Backend Process** (server.py lines 2535-2643):
1. Get project details
2. Query ALL timesheets for this project:
   ```javascript
   db.timesheets.find({ project_id: "..." })
   ```
3. Aggregate by project level:
   - Sum all planned_hours
   - Sum all actual_hours
   - Calculate variance
4. Aggregate by phase:
   - Filter timesheets by phase_id
   - Sum hours per phase
5. Aggregate by resource:
   - Group by resource_id
   - Sum hours per resource
   - Calculate utilization rate

**Response:**
```json
{
  "project": {
    "id": "...",
    "name": "Website Redesign",
    "planned_hours": 120.0,
    "actual_hours": 110.5,
    "variance_hours": -9.5,
    "completion_rate": 92.08
  },
  "phases": [
    {
      "phase_name": "Discovery",
      "planned_hours": 40.0,
      "actual_hours": 36.5,
      "variance_hours": -3.5,
      "completion_rate": 91.25
    }
  ],
  "resources": [
    {
      "resource_name": "Don",
      "planned_hours": 60.0,
      "actual_hours": 55.0,
      "variance_hours": -5.0,
      "utilization_rate": 91.67
    }
  ]
}
```

---

## Data Relationships

### Timesheet → Resource
```javascript
// Timesheet has resource_id
{
  resource_id: "6949f32496943efb2c1d331f"
}

// Linked to resources collection
db.resources.findOne({ _id: ObjectId("6949f32496943efb2c1d331f") })
// Returns: { name: "Don", ... }
```

### Timesheet → Project
```javascript
// Timesheet has project_id
{
  project_id: "6949f32496943efb2c1d3321"
}

// Linked to projects collection
db.projects.findOne({ _id: ObjectId("6949f32496943efb2c1d3321") })
// Returns: { name: "Website Redesign", ... }
```

### Timesheet → Phase
```javascript
// Timesheet has phase_id (optional)
{
  phase_id: "abc123def456"
}

// Linked to phase within project
db.projects.findOne(
  { _id: ObjectId("6949f32496943efb2c1d3321") },
  { phases: { $elemMatch: { id: "abc123def456" } } }
)
// Returns: { name: "Discovery", ... }
```

### Timesheet → Allocation
**Indirect relationship** - Timesheets are GENERATED from allocations but not directly linked:

```javascript
// Allocation defines planned work
db.allocations.findOne({
  resource_id: "6949f32496943efb2c1d331f",
  project_id: "6949f32496943efb2c1d3321",
  start_date: { $lte: ISODate("2026-01-27") },
  end_date: { $gte: ISODate("2026-01-27") }
})
// Returns: { percentage: 100, hours: 40, ... }

// This allocation is used to CREATE timesheets
// But timesheets are independent records after creation
```

---

## Query Patterns

### Get User's Week
```javascript
db.timesheets.find({
  resource_id: "6949f32496943efb2c1d331f",
  week_start_date: ISODate("2026-01-27")
})
```

### Get Project Totals
```javascript
db.timesheets.aggregate([
  { $match: { project_id: "6949f32496943efb2c1d3321" } },
  { $group: {
      _id: null,
      total_planned: { $sum: "$planned_hours" },
      total_actual: { $sum: "$actual_hours" }
    }
  }
])
```

### Get Phase Breakdown
```javascript
db.timesheets.aggregate([
  { $match: { 
      project_id: "6949f32496943efb2c1d3321",
      phase_id: "abc123def456"
    }
  },
  { $group: {
      _id: "$phase_id",
      planned: { $sum: "$planned_hours" },
      actual: { $sum: "$actual_hours" }
    }
  }
])
```

### Get Resource Utilization
```javascript
db.timesheets.aggregate([
  { $match: { 
      project_id: "6949f32496943efb2c1d3321"
    }
  },
  { $group: {
      _id: "$resource_id",
      planned: { $sum: "$planned_hours" },
      actual: { $sum: "$actual_hours" }
    }
  }
])
```

---

## Frontend Components

### 1. TimesheetWeeklyCheckin.js
**Location:** `/app/frontend/src/components/TimesheetWeeklyCheckin.js`
**Purpose:** Weekly timesheet entry widget on Dashboard
**Data Source:** `GET /api/timesheets/my-week`
**Features:**
- Pre-fill button
- Inline editing
- Real-time variance calculation
- Submit week button

### 2. ProjectDetail.js (Time Tracking Tab)
**Location:** `/app/frontend/src/pages/ProjectDetail.js`
**Purpose:** Project-level time tracking reports
**Data Source:** `GET /api/reports/planned-vs-actual/project/{id}`
**Features:**
- Summary cards (totals)
- Phase breakdown table
- Resource breakdown table
- Completion rates and utilization

---

## API Endpoints Summary

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/api/timesheets` | POST | Create manual timesheet | ✅ |
| `/api/timesheets/my-week` | GET | Get user's week timesheets | ✅ |
| `/api/timesheets/{id}` | PUT | Update timesheet | ✅ (owner only) |
| `/api/timesheets/{id}` | DELETE | Delete timesheet | ✅ (owner only) |
| `/api/timesheets/auto-fill` | POST | Generate from allocations | ✅ |
| `/api/timesheets/submit-week` | POST | Submit all drafts | ✅ (Thu/Fri only) |
| `/api/reports/planned-vs-actual/project/{id}` | GET | Project time report | ✅ |
| `/api/reports/time-tracking/summary` | GET | Dashboard summary | ✅ |

---

## Current System State

**Database:** `resource_planner`
**Collection:** `timesheets`
**Current Count:** 0 documents

**This means:**
- ✅ Collection exists and is ready
- ✅ All APIs are functional
- ⚠️ No timesheets have been submitted yet
- ⚠️ User needs to click "Pre-fill This Week" to start using the system

---

## Troubleshooting

### Issue: No timesheets showing after pre-fill
**Check:**
1. Does user have active allocations?
   ```javascript
   db.allocations.find({ resource_id: "..." })
   ```
2. Do allocations overlap with current week?
3. Is allocation percentage > 0?

### Issue: Timesheets not saving
**Check:**
1. Database connection: `db.timesheets.insertOne({ test: 1 })`
2. API authentication: Token valid?
3. User permissions: Correct role?

### Issue: Wrong hours calculated
**Check:**
1. Allocation percentage (100% = 40h/week)
2. Week overlap with allocation dates
3. `calculate_weekly_hours()` function logic

### Issue: Can't submit week
**Check:**
1. Current day (must be Thursday or Friday)
2. Timezone setting (Sydney: Australia/Sydney)
3. All timesheets in "Draft" status

---

## Performance Considerations

### Indexes Needed (Production)
```javascript
// For user queries
db.timesheets.createIndex({ resource_id: 1, week_start_date: -1 })

// For project reports
db.timesheets.createIndex({ project_id: 1, week_start_date: -1 })

// For phase reports
db.timesheets.createIndex({ project_id: 1, phase_id: 1 })

// For status filtering
db.timesheets.createIndex({ status: 1 })
```

### Query Optimization
- Use `$match` before `$group` in aggregations
- Limit results with `.limit()`
- Use projections to reduce data transfer
- Cache report results for 5 minutes (implemented)

---

## Security

### Authentication
- All endpoints require JWT token
- Token validated via `get_current_user` dependency

### Authorization
- Users can only view/edit their own timesheets
- Managers can view all timesheets (planned feature)
- Ownership verified by resource_id match

### Data Validation
- Date formats validated
- Hours must be positive
- Status transitions validated
- Week/phase must exist

---

## Summary

**Timesheets are stored in:**
- MongoDB database: `resource_planner`
- Collection: `timesheets`
- Current count: 0 (empty - waiting for user to start using)

**Data flow:**
1. User allocations → Auto-fill generates draft timesheets
2. User edits actual hours → Updates stored in DB
3. User submits week → Status changes to "Submitted"
4. Reports query submitted timesheets → Aggregate for display

**The system is fully functional but unused** - No one has clicked "Pre-fill This Week" yet to start tracking time!
