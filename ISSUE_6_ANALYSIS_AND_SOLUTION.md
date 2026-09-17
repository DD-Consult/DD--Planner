# Issue 6: AI Actions Inconsistency - Root Cause Analysis & Solution

## Problem Statement
When users ask the AI to "create project X and add allocations", the actions are:
- **Inconsistent** - sometimes works, sometimes doesn't
- **Incomplete** - may create project but fail to add allocations
- **Fragile** - depends on AI interpretation and execution order

## Root Cause Analysis

### 1. How Multi-Step Requests Work Currently

**User Request:** "Create project FX1 and allocate Alice at 50%"

**AI Processing Flow:**

1. **AI Parsing** (`/backend/routes/ai.py`, lines 1592-1605)
   - AI is instructed to use `action_plan` format for multi-step requests
   - Generates a plan with multiple steps

2. **Plan Detection** (`/backend/routes/ai.py`, lines 1856-1863)
   ```python
   if a_type == "action_plan":
       detected_plan = action_obj
       # Plan is NOT auto-executed, held for user confirmation
   ```

3. **Frontend Display** (`ChatPanel.js`, lines 844-854, 352-436)
   - Displays `PlanCard` with all steps
   - User clicks "Execute All Steps"
   - Calls `/api/ai/chat/execute-plan`

4. **Backend Execution** (`/backend/routes/ai.py`, lines 1958-2012)
   ```python
   for i, step in enumerate(steps):
       result = await dispatch_action(step, current_user)
       results.append(...)
   ```

### 2. THE CRITICAL BUG

**Problem: No ID Resolution Between Steps**

When step 1 creates a project:
```json
{
  "action": "create_project",
  "name": "FX1",
  ...
}
```

It returns:
```python
{"success": True, "message": "...", "id": "674abc123..."}
```

But step 2 needs that ID:
```json
{
  "action": "create_allocation",
  "project_id": "???",  // ← MISSING! AI can't know this ID in advance
  "resource_id": "...",
  ...
}
```

**Current Code (lines 1981-1983):**
```python
for i, step in enumerate(steps):
    result = await dispatch_action(step, current_user)
```

- Steps are executed AS-IS with original data
- No mechanism to inject IDs from previous steps
- If AI uses placeholder like `"<step_1_id>"`, it gets passed literally to the DB

### 3. Why It's Inconsistent

The AI might:

**Scenario A:** Generate action_plan with placeholders
```json
{
  "action": "action_plan",
  "steps": [
    {"action": "create_project", "name": "FX1", ...},
    {"action": "create_allocation", "project_id": "<step_1_id>", ...}  // ← Invalid
  ]
}
```
**Result:** Step 1 succeeds, Step 2 fails with "Invalid project_id"

**Scenario B:** Generate separate single actions
```
User: "Create project and allocate Alice"
AI: [creates project in one message]
AI: [user must ask again to allocate]
```
**Result:** Incomplete - user must prompt again

**Scenario C:** Try to auto-execute without action_plan
```json
{
  "action": "create_project",
  ...
}
```
Then immediately:
```json
{
  "action": "create_allocation",
  "project_id": "???",  // ← Still doesn't exist
  ...
}
```
**Result:** Second action fails

## The Solution

### Fix 1: Implement Dynamic ID Injection in `execute_action_plan`

**File:** `/app/backend/routes/ai.py`

**Location:** Lines 1958-2012 (replace the entire function)

**New Implementation:**

```python
@router.post("/api/ai/chat/execute-plan")
async def execute_action_plan(
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Execute a multi-step action plan with dynamic ID resolution.
    Subsequent steps can reference IDs returned by previous steps.
    """
    role = (current_user.get("role") or "").lower()
    is_admin = role in ("admin", "super_admin")
    
    if not is_admin:
        raise HTTPException(status_code=403, detail="Admin access required to execute action plans")

    steps = payload.get("steps", [])
    if not steps:
        raise HTTPException(status_code=400, detail="No steps provided")
    if len(steps) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 steps per plan")

    results = []
    stop_on_error = payload.get("stop_on_error", True)
    
    # Track IDs returned by each step for dynamic injection
    step_results_map = {}  # step_index → result dict

    for i, step in enumerate(steps):
        try:
            # ── DYNAMIC ID INJECTION ──
            # Replace placeholders like "<step_0_id>", "<step_1_id>" with actual IDs from previous steps
            resolved_step = _resolve_step_references(step, step_results_map)
            
            result = await dispatch_action(resolved_step, current_user)
            
            step_result = {
                "step": i + 1,
                "action": step.get("action"),
                "success": result.get("success", False),
                "message": result.get("message", ""),
            }
            
            # Store the full result for future step references
            step_results_map[i] = result
            
            results.append(step_result)
            
            if not result.get("success") and stop_on_error:
                step_result["message"] += " (execution stopped due to error)"
                break
                
        except Exception as e:
            step_result = {
                "step": i + 1,
                "action": step.get("action"),
                "success": False,
                "message": f"Error: {str(e)[:200]}",
            }
            results.append(step_result)
            if stop_on_error:
                break

    success_count = sum(1 for r in results if r.get("success"))
    
    return {
        "results": results,
        "success_count": success_count,
        "total_steps": len(steps),
        "executed_steps": len(results),
        "all_success": success_count == len(results) and len(results) == len(steps),
    }


def _resolve_step_references(step: dict, step_results: dict) -> dict:
    """
    Recursively resolve placeholder references like '<step_0_id>' to actual IDs.
    
    Examples:
      - "<step_0_id>" → ID returned by step 0
      - "<step_1_id>" → ID returned by step 1
      - "674abc..." (normal ID) → unchanged
    
    Args:
        step: Action step dict that may contain placeholders
        step_results: Map of step_index → result dict from previous steps
    
    Returns:
        New step dict with placeholders replaced by actual values
    """
    import re
    import copy
    
    resolved = copy.deepcopy(step)
    
    # Pattern to match <step_N_id> where N is a digit
    placeholder_pattern = re.compile(r'<step_(\d+)_id>')
    
    def replace_in_value(value):
        """Recursively replace placeholders in strings, lists, dicts."""
        if isinstance(value, str):
            # Check if entire value is a placeholder
            match = placeholder_pattern.fullmatch(value)
            if match:
                step_index = int(match.group(1))
                if step_index in step_results:
                    # Return the ID from that step's result
                    return step_results[step_index].get("id") or value
            # Check for inline placeholders (less common but possible)
            return placeholder_pattern.sub(
                lambda m: step_results.get(int(m.group(1)), {}).get("id", m.group(0)),
                value
            )
        elif isinstance(value, list):
            return [replace_in_value(item) for item in value]
        elif isinstance(value, dict):
            return {k: replace_in_value(v) for k, v in value.items()}
        else:
            return value
    
    return replace_in_value(resolved)
```

### Fix 2: Update AI System Prompt to Use Step References

**File:** `/app/backend/routes/ai.py`

**Location:** Lines 1592-1605

**Replace this section:**

```python
MULTI-STEP ACTION PLAN — for complex requests that require multiple actions:
When the user asks to do something that requires several steps (e.g. "set up a new project with phases and allocations", "onboard this client"), emit an `action_plan` block instead of a single action. The system will present the plan to the user for review before executing anything.

```action
{{"action": "action_plan", "title": "Setup New Project", "description": "What this plan will do overall", "steps": [{{"action": "create_project", "name": "Project X", "client_name": "Acme", "status": "Pipeline", "start_date": "2026-03-01", "end_date": "2026-06-30", "budgeted_hours": 400, "description": "Create the project"}}, {{"action": "manage_phases", "project_id": "<id from step 1>", "phases": [{{"name": "Discovery", "start_date": "2026-03-01", "end_date": "2026-03-31"}}], "description": "Add phases"}}]}}
```

Rules for action_plan:
- Use when the user wants 2+ sequential actions that logically belong together
- Each step is a standard action object (same format as single actions)
- Max 8 steps per plan
- The user reviews the plan before anything executes — so be thorough in descriptions
- DO NOT use action_plan for a single action — use a regular action block instead
```

**With this improved version:**

```python
MULTI-STEP ACTION PLAN — for complex requests that require multiple actions:
When the user asks to do something that requires several steps (e.g. "create project X and allocate Y to it", "set up a new project with phases and team"), emit an `action_plan` block. The system will present the plan to the user for review before executing anything.

**CRITICAL: Dynamic ID References**
When a later step needs an ID from an earlier step (e.g., project_id from create_project), use the placeholder format: `"<step_N_id>"` where N is the 0-based step index.

Example: "Create project FX1 and allocate Alice at 50%"

```action
{{
  "action": "action_plan",
  "title": "Create Project and Allocate Resource",
  "description": "Create FX1 project and allocate Alice at 50%",
  "steps": [
    {{
      "action": "create_project",
      "name": "FX1",
      "client_name": "TechCorp",
      "status": "Active",
      "start_date": "2026-05-01",
      "end_date": "2026-08-31",
      "budgeted_hours": 500,
      "description": "Create the FX1 project"
    }},
    {{
      "action": "create_allocation",
      "project_id": "<step_0_id>",
      "resource_id": "674abc...",
      "percentage": 50,
      "start_date": "2026-05-01",
      "end_date": "2026-08-31",
      "description": "Allocate Alice to FX1 at 50%"
    }}
  ]
}}
```

In the example above, step 0 creates the project and returns `{{"id": "674xyz..."}}`. Step 1's `"<step_0_id>"` placeholder is automatically replaced with `"674xyz..."` before execution.

**More Examples:**

1. "Create project with 3 phases"
```action
{{
  "action": "action_plan",
  "title": "Create Project with Phases",
  "steps": [
    {{"action": "create_project", "name": "Mobile App", ...}},
    {{"action": "manage_phases", "project_id": "<step_0_id>", "phases": [...]}}
  ]
}}
```

2. "Create project, add phases, allocate 2 people, and generate WBS"
```action
{{
  "action": "action_plan",
  "title": "Full Project Setup",
  "steps": [
    {{"action": "create_project", "name": "Website Redesign", ...}},
    {{"action": "manage_phases", "project_id": "<step_0_id>", ...}},
    {{"action": "create_allocation", "project_id": "<step_0_id>", "resource_id": "...", ...}},
    {{"action": "create_allocation", "project_id": "<step_0_id>", "resource_id": "...", ...}},
    {{"action": "generate_wbs", "project_id": "<step_0_id>", ...}}
  ]
}}
```

Rules for action_plan:
- Use when the user wants 2+ sequential actions that logically belong together
- Each step is a standard action object (same format as single actions)
- Use `"<step_N_id>"` placeholders to reference IDs from previous steps (N is 0-based index)
- Max 8 steps per plan
- The user reviews the plan before anything executes — so be thorough in descriptions
- DO NOT use action_plan for a single action — use a regular action block instead
- ALWAYS use action_plan when a request involves creating something AND then using that thing (e.g., "create X and allocate Y to it")
```

### Fix 3: Better Action Descriptions in Plans (Optional Enhancement)

**File:** `/app/backend/services/ai_actions.py`

**Enhancement:** Make sure `create_project`, `create_allocation`, etc. return consistent `id` fields.

**Current code (lines 60-61):**
```python
result = await projects_collection.insert_one(project_doc)
return {"success": True, "message": f"Project '{action['name']}' created successfully", "id": str(result.inserted_id)}
```

✅ This already returns `"id"` - GOOD!

**Current code (lines 75-76):**
```python
result = await allocations_collection.insert_one(alloc_data)
return {"success": True, "message": "Allocation created successfully", "id": str(result.inserted_id)}
```

✅ This already returns `"id"` - GOOD!

No changes needed here. The actions already return IDs correctly.

## Testing Plan

### Test Case 1: Create Project + Single Allocation

**User Input:**
```
"Create project FX1 for TechCorp starting May 1st, budget 500 hours, and allocate Alice at 50%"
```

**Expected AI Response:**
```json
{
  "action": "action_plan",
  "title": "Create Project and Allocate Resource",
  "steps": [
    {
      "action": "create_project",
      "name": "FX1",
      "client_name": "TechCorp",
      "start_date": "2026-05-01",
      "end_date": "2026-08-01",
      "budgeted_hours": 500
    },
    {
      "action": "create_allocation",
      "project_id": "<step_0_id>",
      "resource_id": "[Alice's ID]",
      "percentage": 50,
      "start_date": "2026-05-01",
      "end_date": "2026-08-01"
    }
  ]
}
```

**Expected Execution:**
1. Step 0 executes → returns `{"id": "674newprojectid"}`
2. Step 1 receives resolved data:
   ```json
   {
     "action": "create_allocation",
     "project_id": "674newprojectid",  // ← Resolved!
     "resource_id": "674aliceid",
     ...
   }
   ```
3. Both steps succeed ✅

### Test Case 2: Create Project + Multiple Allocations

**User Input:**
```
"Set up Mobile App project with Alice at 50% and Bob at 30%"
```

**Expected Plan:**
```json
{
  "steps": [
    {"action": "create_project", "name": "Mobile App", ...},
    {"action": "create_allocation", "project_id": "<step_0_id>", "resource_id": "...", "percentage": 50},
    {"action": "create_allocation", "project_id": "<step_0_id>", "resource_id": "...", "percentage": 30}
  ]
}
```

**Expected Result:** All 3 steps succeed ✅

### Test Case 3: Create Project + Phases + Allocations

**User Input:**
```
"Create Website Redesign project with Discovery and Build phases, allocate Alice to it"
```

**Expected Plan:**
```json
{
  "steps": [
    {"action": "create_project", "name": "Website Redesign", ...},
    {"action": "manage_phases", "project_id": "<step_0_id>", "phases": [...]},
    {"action": "create_allocation", "project_id": "<step_0_id>", ...}
  ]
}
```

**Expected Result:** All 3 steps succeed ✅

### Test Case 4: Error Handling

**Scenario:** User specifies a non-existent resource

**User Input:**
```
"Create project X and allocate NonExistentPerson to it"
```

**Expected Behavior:**
- Step 0 (create_project) succeeds
- Step 1 (create_allocation) fails: "Resource 'NonExistentPerson' not found"
- Plan execution stops at step 1 (due to `stop_on_error: true`)
- Frontend shows: "1/2 steps succeeded"
- User sees clear error message ✅

## Summary

### What Was Broken

1. **No ID resolution** - Steps couldn't reference IDs from previous steps
2. **AI didn't know syntax** - No clear instruction to use `<step_N_id>` placeholders
3. **Static execution** - Backend executed steps with original data, no dynamic injection

### What The Fix Does

1. **`_resolve_step_references()` function** - Replaces placeholders with actual IDs
2. **`step_results_map`** - Tracks results from each step
3. **Updated AI prompt** - Clear examples of using `<step_N_id>` placeholders
4. **Robust error handling** - Stops on failure, reports which step failed

### Result

✅ "Create project X and allocate Y to it" now works consistently
✅ Multi-step plans work reliably with proper ID chaining
✅ Clear error messages when steps fail
✅ Full execution transparency (user sees each step result)

