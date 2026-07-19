# DD Planner - Feature Package Plan

## Overview
This document outlines the implementation plan for 4 feature updates requested by the user.

---

## Feature 1: Timesheet Restriction (Thursday/Friday Only)

### Requirements
- **Who:** All users (including admins)
- **When:** Can only confirm/update timesheets on Thursday or Friday
- **Timezone:** Sydney, Australia (AEDT/AEST - UTC+10/+11)
- **Grace Period:** If missed, can update the following week

### Implementation

#### Backend Changes (`server.py`)
1. Add helper function to check if current day is Thursday/Friday in Sydney timezone
```python
from datetime import datetime
import pytz

def is_timesheet_update_allowed():
    sydney_tz = pytz.timezone('Australia/Sydney')
    sydney_now = datetime.now(sydney_tz)
    # Thursday = 3, Friday = 4 (Monday = 0)
    return sydney_now.weekday() in [3, 4]
```

2. Update `/api/allocations/{allocation_id}/confirm` endpoint
   - Add check: if not Thursday/Friday, return 403 with message
   - Exception: Allow if the allocation week is from previous week (grace period)

3. Add new endpoint to check if updates are allowed
   - `GET /api/timesheet/can-update` - Returns `{allowed: bool, reason: string, next_allowed: datetime}`

#### Frontend Changes
1. **WeeklyCheckin.js**
   - Fetch `can-update` status on load
   - If not Thursday/Friday:
     - Disable "Confirm" buttons
     - Show banner: "Timesheet updates are only allowed on Thursday and Friday (Sydney time)"
     - Show countdown to next allowed day

2. **api.js**
   - Add `checkTimesheetUpdateAllowed()` function

#### Dependencies
- Add `pytz` to requirements.txt for timezone handling

---

## Feature 2: Show Project End Date in Progress Display

### Requirements
- Display end date next to progress bar in Project Portfolio table
- Format: "45% | Due: Jan 30"

### Implementation

#### Frontend Changes (`Dashboard.js`)
1. Update the Progress column in Project Portfolio table:

**Current:**
```jsx
<div className="flex items-center gap-2">
  <Progress value={project.progress} className="flex-1 h-2" />
  <span className="text-sm font-medium min-w-[40px] text-right">{project.progress}%</span>
</div>
```

**New:**
```jsx
<div className="flex items-center gap-2">
  <Progress value={project.progress} className="flex-1 h-2" />
  <span className="text-sm font-medium min-w-[40px] text-right">{project.progress}%</span>
  <span className="text-xs text-[#667085]">| Due: {format(parseISO(project.end_date), 'MMM d')}</span>
</div>
```

---

## Feature 3: Allocation with Project Phases

### Requirements
- When assigning a resource to a project:
  - Can only assign within project start/end dates (validation)
  - Can select 1 or many project phases
  - Dates auto-fill based on selected phase(s)
  - Creates ONE allocation spanning all selected phases
- Update AI command to support phase selection

### Implementation

#### Backend Changes (`server.py`)

1. **Update AllocationCreate model**
```python
class AllocationCreate(BaseModel):
    resource_id: str
    project_id: str
    start_date: date
    end_date: date
    percentage: Optional[int] = None
    phase_ids: Optional[List[str]] = None  # NEW: Selected phase names/ids
    # ... existing fields
```

2. **Add validation in allocation endpoints**
   - Fetch project dates
   - Validate: `allocation.start_date >= project.start_date`
   - Validate: `allocation.end_date <= project.end_date`
   - If validation fails, return 400 with clear error message

3. **Add endpoint to get project phases**
   - `GET /api/projects/{project_id}/phases` - Returns phases with dates

4. **Update AI command system prompt**
   - Add phase_names to entities
   - Example: "Assign Alice to Website project for Discovery and Design phases at 50%"

#### Frontend Changes

1. **AllocationEditor.js** - Update the allocation form
   - Add multi-select dropdown for phases (only show if project has phases)
   - When phases selected:
     - Auto-fill start_date = earliest phase start
     - Auto-fill end_date = latest phase end
   - Add validation message if dates outside project range

2. **Projects.js** - Edit Project dialog allocation section
   - Same phase selection functionality

3. **ConfirmCommandDialog.js**
   - Display selected phases in AI command preview

4. **Layout.js**
   - Handle phase extraction from AI response

---

## Feature 4: Fix Utilization Calculations

### Requirements
- **Team Utilization (Dashboard):** Show average for CURRENT WEEK
- **Avg Resource Load (Project Detail):** Show average allocation % per team member

### Implementation

#### Team Utilization Fix (`Dashboard.js`)

**Current (WRONG):**
```javascript
const totalAllocationPercentage = filteredAllocations.reduce((sum, alloc) => sum + (alloc.percentage || 0), 0);
const totalPossible = resources.length * 100;
return Math.round((totalAllocationPercentage / totalPossible) * 100);
// Result: 211% (sums ALL allocations ever)
```

**New (CORRECT):**
```javascript
const teamUtilization = useMemo(() => {
  if (!filteredAllocations || !resources) return 0;
  
  // Get current week's date range
  const today = new Date();
  const weekStart = startOfWeek(today, { weekStartsOn: 1 }); // Monday
  const weekEnd = endOfWeek(today, { weekStartsOn: 1 }); // Sunday
  
  // For each resource, calculate their utilization for this week
  let totalUtilization = 0;
  
  resources.forEach(resource => {
    // Get allocations active this week for this resource
    const activeAllocs = filteredAllocations.filter(alloc => 
      alloc.resource_id === resource.id &&
      areIntervalsOverlapping(
        { start: parseISO(alloc.start_date), end: parseISO(alloc.end_date) },
        { start: weekStart, end: weekEnd }
      )
    );
    
    // Sum percentages (cap at 100% would show over-allocation)
    const resourceUtil = activeAllocs.reduce((sum, a) => sum + (a.percentage || 0), 0);
    totalUtilization += Math.min(resourceUtil, 100); // Cap at 100% per resource for average
  });
  
  // Average utilization across all resources
  return resources.length > 0 ? Math.round(totalUtilization / resources.length) : 0;
}, [filteredAllocations, resources]);
```

#### Avg Resource Load Fix (`ProjectDetail.js`)

**Current (WRONG):**
```javascript
const avgLoad = totalAllocationPercentage / projectDays;
// Result: 290 / 30 = 10% (doesn't make sense)
```

**New (CORRECT):**
```javascript
const resourceLoad = useMemo(() => {
  if (!allocations || allocations.length === 0) return 0;
  
  // Get unique resources on this project
  const uniqueResourceIds = [...new Set(allocations.map(a => a.resource_id))];
  const numResources = uniqueResourceIds.length;
  
  if (numResources === 0) return 0;
  
  // Calculate average allocation per resource
  // For each resource, take their highest allocation on this project
  const resourceLoads = uniqueResourceIds.map(resourceId => {
    const resourceAllocs = allocations.filter(a => a.resource_id === resourceId);
    // Sum their allocations on this project (they might have multiple phases)
    return resourceAllocs.reduce((sum, a) => sum + (a.percentage || 0), 0);
  });
  
  // Average load per team member
  const avgLoad = resourceLoads.reduce((sum, load) => sum + load, 0) / numResources;
  return Math.round(avgLoad);
}, [allocations]);
```

**Label Change:**
- Change label from "Avg Resource Load" to "Avg Team Member Load"

---

## Files to Modify

| File | Changes |
|------|---------|
| `backend/server.py` | Timesheet restriction, allocation validation, phase support |
| `backend/requirements.txt` | Add `pytz` |
| `frontend/src/api.js` | Add timesheet check, phase endpoints |
| `frontend/src/pages/Dashboard.js` | End date display, fix utilization calc |
| `frontend/src/pages/ProjectDetail.js` | Fix resource load calc |
| `frontend/src/components/WeeklyCheckin.js` | Timesheet restriction UI |
| `frontend/src/components/AllocationEditor.js` | Phase selection |
| `frontend/src/components/Layout.js` | AI phase handling |
| `frontend/src/components/ConfirmCommandDialog.js` | Phase display |

---

## Testing Checklist

### Feature 1: Timesheet Restriction
- [ ] Cannot confirm timesheet on Monday-Wednesday
- [ ] Can confirm timesheet on Thursday
- [ ] Can confirm timesheet on Friday
- [ ] Error message shows clearly when restricted
- [ ] Previous week's timesheets can still be updated (grace period)

### Feature 2: End Date Display
- [ ] End date shows next to progress in Project Portfolio
- [ ] Format is correct (e.g., "Due: Jan 30")

### Feature 3: Phase Allocation
- [ ] Phase dropdown appears when project has phases
- [ ] Selecting phase(s) auto-fills dates
- [ ] Cannot select dates outside project range
- [ ] AI command "Assign X to Y for Phase Z" works

### Feature 4: Calculation Fixes
- [ ] Team Utilization shows reasonable % (not 200%+)
- [ ] Avg Resource Load shows per-team-member average
- [ ] Values update when allocations change

---

## Estimated Implementation Time
- Feature 1: ~45 mins
- Feature 2: ~10 mins  
- Feature 3: ~60 mins
- Feature 4: ~30 mins
- Testing: ~30 mins

**Total: ~3 hours**
