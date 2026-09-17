# Enhanced Phase-Picking Logic for Auto-Fill Timesheets

## Overview
Enhanced the `auto_fill_timesheets` function in `backend/routes/timesheets.py` to intelligently determine which project phase to apply when pre-filling timesheets based on allocations.

## Implementation Details

### Phase Selection Priority (Cascading Logic)

The system now follows a sophisticated cascading approach to determine the most appropriate phase:

#### 1. **Phase Allocations** (Highest Priority)
- Checks `allocation.get("phase_allocations")` for explicit phase-level allocations
- Collects phase_ids where `percentage > 0` or `hours > 0`
- Example:
  ```python
  phase_allocs = allocation.get("phase_allocations", [])
  active_phase_alloc_ids = [
      pa["phase_id"] for pa in phase_allocs 
      if pa.get("phase_id") and (pa.get("percentage", 0) > 0 or pa.get("hours", 0) > 0)
  ]
  ```

#### 2. **Explicit Phase IDs**
- Uses `allocation.get("phase_ids")` if present
- Direct phase selection from allocation

#### 3. **Phase Names with Case-Insensitive Matching**
- Checks `allocation.get("phase_names")`
- Performs **case-insensitive** matching against `phase.get("name")`
- Example: "Planning" matches "planning", "PLANNING", "PlAnNiNg"

#### 4. **Active WBS Tasks**
- Queries WBS tasks assigned to the resource with active status
- Query: `{"project_id": project_id, "assigned_to": resource_id, "status": {"$in": ["todo", "in_progress"]}}`
- Collects phase_ids from tasks and validates they exist in project phases
- If resource has active work in specific phases, those phases are selected

#### 5. **Date-Overlap Scoring**
- Calculates business day overlap between each phase and the current week
- Uses `coerce_date()` to safely parse phase dates
- Uses `count_business_days()` to calculate overlap
- Sorts phases by overlap (descending), then by start date (ascending)
- Picks the phase with the **highest overlap** with current week
- Example: If Phase A overlaps 3 days and Phase B overlaps 5 days, Phase B is selected

#### 6. **Status-Based Matching**
- Checks for phases with status: `"active"`, `"in_progress"`, or `"current"`
- Case-insensitive matching: `(phase.get("status") or "").lower()`
- Takes first matching active phase

#### 7. **Next Upcoming Phase**
- Finds phases where `phase_end >= week_start_date`
- Sorts by start date (ascending)
- Picks the earliest upcoming phase

#### 8. **First Phase Fallback**
- Ultimate fallback: uses `phases[0]["id"]`
- Ensures timesheet generation always succeeds when phases exist

### Validation and Filtering

After phase selection, the system:
1. **Validates phase IDs** - Ensures all selected phases exist in the project
2. **Filters None values** - Removes invalid entries
3. **Final safety check** - Falls back to first phase if validation fails

## Key Features

### Business Day Overlap Calculation
```python
overlap_start = max(phase_start, week_start_date)
overlap_end = min(phase_end, week_end_date)
if overlap_start <= overlap_end:
    overlap_days = count_business_days(overlap_start, overlap_end)
```

### Case-Insensitive Phase Name Matching
```python
phase_names_lower = [pn.lower() if isinstance(pn, str) else pn for pn in phase_names]
for phase in phases:
    phase_name = phase.get("name", "")
    if isinstance(phase_name, str) and phase_name.lower() in phase_names_lower:
        phase_ids_to_process.append(phase.get("id"))
```

### WBS Task Integration
```python
wbs_tasks = await wbs_tasks_collection.find({
    "project_id": project_id,
    "assigned_to": resource_id,
    "status": {"$in": ["todo", "in_progress"]}
}).to_list(length=100)

task_phase_ids = set()
for task in wbs_tasks:
    task_phase_id = task.get("phase_id")
    if task_phase_id:
        if any(p.get("id") == task_phase_id for p in phases):
            task_phase_ids.add(task_phase_id)
```

## Benefits

1. **Accuracy** - Selects the most relevant phase based on multiple data points
2. **Flexibility** - Supports various allocation configurations (phase_allocations, phase_ids, phase_names)
3. **Intelligence** - Uses date overlap and task assignments to make smart decisions
4. **Reliability** - Multiple fallback mechanisms ensure timesheets are always created
5. **Case-Insensitive** - Phase name matching is forgiving of capitalization differences

## Error Handling

- WBS task queries wrapped in try-except to prevent failures
- All date parsing uses `coerce_date()` for safety
- Extensive validation at each step
- Graceful degradation to fallback options

## Testing Recommendations

Test the following scenarios:
1. Allocation with `phase_allocations` set (should use those phases)
2. Allocation with `phase_names` in mixed case (should match case-insensitively)
3. Resource with active WBS tasks in specific phases (should use task phases)
4. Phase with high date overlap with current week (should select that phase)
5. Phase with status "active" or "in_progress" (should select active phase)
6. Allocation with no specific phase data (should use intelligent fallback)

## Files Modified

- **backend/routes/timesheets.py** - Lines 395-516 (enhanced phase-picking logic)

## Dependencies

- `utils.coerce_date()` - Safe date parsing
- `utils.count_business_days()` - Business day calculations
- `wbs_tasks_collection` - WBS task queries
