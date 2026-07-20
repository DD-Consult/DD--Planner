from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date, timedelta, timezone
from bson import ObjectId
import json
import re
import uuid as uuid_module

from database import (
    projects_collection, resources_collection, allocations_collection,
    timesheets_collection, risks_collection, status_updates_collection,
    settings_collection, chat_sessions_collection, leaves_collection,
    holidays_collection, wbs_tasks_collection, EMERGENT_LLM_KEY, SYDNEY_TZ,
    ai_memory_collection,
)
from models.schemas import (
    AICommandRequest, AICommandResponse, ChatMessage,
    LeaveCreate, LeaveResponse, HolidayCreate, HolidayResponse,
)
from auth.dependencies import get_current_user, require_admin, require_super_admin
from utils import serialize_doc
from services.ai_providers import (
    get_ai_config, call_openai_api, call_gemini_api, call_emergent_fallback,
)
from services.ai_actions import (
    AUTO_EXECUTE_ACTIONS, execute_ai_action, capture_pre_state,
    build_undo_spec, apply_undo,
)
from services.ai_action_registry import dispatch_action, ACTIONS as REGISTERED_ACTIONS, build_actions_prompt
from services.ai_instructions import get_instructions_for_prompt
from services.specialist_agents import detect_specialist, get_specialist_header, list_specialist_triggers

router = APIRouter()

@router.get("/api/settings/ai")
async def get_ai_settings(current_user: dict = Depends(require_super_admin)):
    """Get app-wide AI settings (super_admin only). Never returns raw key."""
    settings = await settings_collection.find_one({"type": "ai_config"})
    if settings and settings.get("ai_api_key"):
        key = settings["ai_api_key"]
        masked = key[:7] + "..." + key[-4:] if len(key) > 11 else key[:4] + "..."
        return {
            "provider": settings.get("ai_provider", "openai"),
            "api_key_masked": masked,
            "has_key": True,
            "has_emergent_fallback": bool(EMERGENT_LLM_KEY),
        }
    return {
        "provider": "openai",
        "api_key_masked": "",
        "has_key": False,
        "has_emergent_fallback": bool(EMERGENT_LLM_KEY),
    }


@router.put("/api/settings/ai")
async def update_ai_settings(
    provider: str,
    api_key: str,
    current_user: dict = Depends(require_super_admin),
):
    """Update app-wide AI settings (super_admin only)."""
    if provider not in ("openai", "gemini"):
        raise HTTPException(status_code=400, detail="Provider must be 'openai' or 'gemini'")
    await settings_collection.update_one(
        {"type": "ai_config"},
        {"$set": {"type": "ai_config", "ai_provider": provider, "ai_api_key": api_key}},
        upsert=True,
    )
    return {"message": "AI settings saved successfully"}


@router.delete("/api/settings/ai")
async def clear_ai_settings(current_user: dict = Depends(require_super_admin)):
    """Clear app-wide AI settings, reverting to Emergent LLM key fallback."""
    await settings_collection.delete_one({"type": "ai_config"})
    return {"message": "AI settings cleared. Emergent LLM key will be used as fallback."}


@router.get("/api/leaves", response_model=List[LeaveResponse])
async def get_leaves(current_user: dict = Depends(get_current_user)):
    role = current_user.get("role", "")
    is_admin = role in ("admin", "super_admin")
    if is_admin:
        cursor = leaves_collection.find()
    else:
        # Resources see only their own leaves
        from utils import find_user_resource
        resource = await find_user_resource(current_user)
        if not resource:
            return []
        cursor = leaves_collection.find({"resource_id": str(resource["_id"])})
    leaves = await cursor.to_list(length=10000)
    return serialize_doc(leaves)


@router.post("/api/leaves", response_model=LeaveResponse)
async def create_leave(leave: LeaveCreate, current_user: dict = Depends(get_current_user)):
    role = current_user.get("role", "")
    is_admin = role in ("admin", "super_admin")
    leave_doc = leave.dict()
    if not is_admin:
        # Resources can only create leave for themselves
        from utils import find_user_resource
        resource = await find_user_resource(current_user)
        if not resource:
            raise HTTPException(status_code=403, detail="No resource profile linked to your account. Contact an admin.")
        # Force resource_id to own resource
        leave_doc["resource_id"] = str(resource["_id"])
    else:
        # Admins must specify a resource_id
        if not leave_doc.get("resource_id"):
            raise HTTPException(status_code=400, detail="resource_id is required")
    # Convert date to datetime for MongoDB
    if isinstance(leave_doc.get("start_date"), date):
        leave_doc["start_date"] = datetime.combine(leave_doc["start_date"], datetime.min.time())
    if isinstance(leave_doc.get("end_date"), date):
        leave_doc["end_date"] = datetime.combine(leave_doc["end_date"], datetime.min.time())
    result = await leaves_collection.insert_one(leave_doc)
    leave_doc["_id"] = result.inserted_id
    return serialize_doc(leave_doc)


@router.delete("/api/leaves/{leave_id}")
async def delete_leave(leave_id: str, current_user: dict = Depends(get_current_user)):
    role = current_user.get("role", "")
    is_admin = role in ("admin", "super_admin")
    leave = await leaves_collection.find_one({"_id": ObjectId(leave_id)})
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")
    if not is_admin:
        # Resources can only delete their own leave
        from utils import find_user_resource
        resource = await find_user_resource(current_user)
        if not resource or leave.get("resource_id") != str(resource["_id"]):
            raise HTTPException(status_code=403, detail="You can only delete your own time off entries.")
    await leaves_collection.delete_one({"_id": ObjectId(leave_id)})
    return {"message": "Leave deleted"}


# Holiday endpoints
@router.get("/api/holidays", response_model=List[HolidayResponse])
async def get_holidays(current_user: dict = Depends(get_current_user)):
    cursor = holidays_collection.find()
    holidays = await cursor.to_list(length=1000)
    return serialize_doc(holidays)


@router.post("/api/holidays", response_model=HolidayResponse)
async def create_holiday(holiday: HolidayCreate, admin: dict = Depends(require_admin)):
    holiday_doc = holiday.dict()
    # Convert date to datetime for MongoDB
    if isinstance(holiday_doc.get("date"), date):
        holiday_doc["date"] = datetime.combine(holiday_doc["date"], datetime.min.time())
    
    result = await holidays_collection.insert_one(holiday_doc)
    holiday_doc["_id"] = result.inserted_id
    return serialize_doc(holiday_doc)


@router.delete("/api/holidays/{holiday_id}")
async def delete_holiday(holiday_id: str, admin: dict = Depends(require_admin)):
    result = await holidays_collection.delete_one({"_id": ObjectId(holiday_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Holiday not found")
    return {"message": "Holiday deleted"}

@router.get("/api/ai/portfolio-budget-analysis")
async def get_portfolio_budget_analysis(current_user: dict = Depends(get_current_user)):
    """
    AI-powered cross-project portfolio budget analysis.
    Reuses same LLM pattern as project-level analysis.
    """
    import json as json_module
    import re

    # Get overview data by calling the same logic
    cursor = projects_collection.find({"status": {"$in": ["Active", "Pipeline"]}})
    projects = await cursor.to_list(length=500)
    all_timesheets = await timesheets_collection.find().to_list(length=50000)
    ts_by_project = {}
    for t in all_timesheets:
        pid = t.get("project_id", "")
        ts_by_project.setdefault(pid, []).append(t)

    project_summaries = []
    total_budget = 0.0
    total_actual = 0.0
    for project in projects:
        pid = str(project["_id"])
        budget = float(project.get("budgeted_hours") or 0)
        ts_list = ts_by_project.get(pid, [])
        actual = round(sum(t.get("actual_hours", 0) for t in ts_list), 1)
        pct = round(actual / budget * 100, 1) if budget > 0 else 0
        total_budget += budget
        total_actual += actual
        project_summaries.append({
            "name": project.get("name"),
            "client": project.get("client_name", ""),
            "budget": budget,
            "actual": actual,
            "pct_used": pct,
            "status": project.get("status"),
            "health": project.get("health", "Unknown"),
        })

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    context = f"""Portfolio Overview ({today_str})
Total Projects: {len(projects)}
Total Budget: {total_budget}h
Total Actual: {total_actual}h
Overall Usage: {round(total_actual/total_budget*100,1) if total_budget>0 else 0}%

Project Breakdown:
{json_module.dumps(project_summaries, indent=2)}"""

    system_prompt = """You are an AI portfolio analyst. Analyze the cross-project budget data and provide a structured analysis.

Return ONLY valid JSON:
{
  "narrative": "2-3 sentence executive summary of portfolio budget health with specific numbers",
  "alerts": [{"severity": "critical|warning|info", "title": "Brief title", "message": "Specific details"}],
  "recommendations": [{"priority": "high|medium|low", "title": "Brief title", "action": "Specific action"}],
  "project_highlights": [{"project": "Name", "status": "on_track|at_risk|over_budget", "note": "One sentence"}]
}

Be concise, use real numbers, flag over-budget projects as critical."""

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import uuid as uuid_module

        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"portfolio-analysis-{uuid_module.uuid4()}",
            system_message=system_prompt
        ).with_model("openai", "gpt-4o-mini")

        response = await chat.send_message(UserMessage(text=f"Analyze:\n\n{context}\n\nRespond with valid JSON only."))
        if isinstance(response, str):
            cleaned = re.sub(r'^```(?:json)?\s*', '', response.strip())
            cleaned = re.sub(r'\s*```$', '', cleaned)
            response = cleaned.strip()
        return json_module.loads(response)
    except Exception as e:
        print(f"Portfolio AI analysis error: {type(e).__name__}: {str(e)}")
        # Fallback
        alerts = []
        for p in project_summaries:
            if p["budget"] > 0 and p["pct_used"] > 100:
                alerts.append({"severity": "critical", "title": f"{p['name']} over budget", "message": f"{p['actual']}h used of {p['budget']}h budget ({p['pct_used']}%)"})
            elif p["budget"] > 0 and p["pct_used"] > 80:
                alerts.append({"severity": "warning", "title": f"{p['name']} nearing budget", "message": f"{p['pct_used']}% of budget consumed"})
        no_budget = [p for p in project_summaries if p["budget"] == 0]
        recs = []
        if no_budget:
            recs.append({"priority": "high", "title": "Set budgets", "action": f"{len(no_budget)} projects have no budget set: {', '.join(p['name'] for p in no_budget[:3])}"})
        return {
            "narrative": f"Portfolio has {len(projects)} projects with {total_budget}h total budget and {total_actual}h actual ({round(total_actual/total_budget*100,1) if total_budget>0 else 0}% used).",
            "alerts": alerts,
            "recommendations": recs,
            "project_highlights": [{"project": p["name"], "status": "over_budget" if p["pct_used"]>100 else "at_risk" if p["pct_used"]>80 else "on_track", "note": f"{p['pct_used']}% budget used"} for p in project_summaries if p["budget"]>0][:5]
        }



@router.post("/api/ai/command", response_model=AICommandResponse)
async def ai_command(command: AICommandRequest, current_user: dict = Depends(get_current_user)):
    """
    AI-powered natural language command parser
    Supports OpenAI and Gemini providers with Emergent LLM fallback
    """
    import json
    import httpx
    
    # Fetch context: active resources and projects
    resources_cursor = resources_collection.find({"active": {"$ne": False}})
    resources = await resources_cursor.to_list(length=1000)
    resource_names = [r["name"] for r in resources]
    
    projects_cursor = projects_collection.find({"status": {"$in": ["Active", "Pipeline"]}})
    projects = await projects_cursor.to_list(length=100)
    project_info = [f"{p['name']} (Client: {p.get('client_name', 'Unknown')})" for p in projects]
    
    # System prompt for intent parsing - EXPANDED with more capabilities
    system_prompt = f"""You are an AI assistant for a Resource Planning application called DD Planner.
Your job is to parse user commands and extract structured information for project management tasks.

Available Resources: {', '.join(resource_names)}
Available Projects: {', '.join(project_info)}

Supported Intents:

1. ASSIGN_RESOURCE - Assign a resource to a project
   Example: "Assign Alice to Website project at 50%"
   
2. CREATE_PROJECT_FULL - Create a new project with phases and optional resource assignments
   Example: "Create project called Mobile App for TechCorp with phases Initiate, Plan, Execute, Close each 3 weeks, assign Bob at 60%"
   
3. RESCHEDULE_PROJECT - Move project dates, phases, and allocations forward/backward
   Example: "Project X is behind schedule, move everything out by 2 weeks"
   Example: "Shift Mobile App project forward by 3 weeks"
   
4. MOVE_RESOURCE - Remove resource from one project and assign to another
   Example: "Move Alice from Project A to Project B at same allocation"
   
5. REMOVE_ALLOCATION - Remove a resource from a project
   Example: "Remove Bob from Website Redesign project"
   
6. CREATE_RISK - Add risks to a project
   Example: "Add risk to Mobile App: Budget overrun due to scope creep, High impact"
   
7. UPDATE_SUMMARY - Regenerate AI summary for projects
   Example: "Update AI summaries for Website and Mobile App projects"
   
8. PROJECT_STATUS_UPDATE - Submit a weekly project status check-in
   Example: "Website project is delayed, we're at 60% complete, blocked on API integration, completed the UI design this week"
   Example: "FX1 project is on track at 80%, health is green, finished testing phase"
   
9. QUERY_CAPACITY - Check resource availability or project status
   Example: "Is Alice available next week?" or "Show me overallocated resources"
   
10. TIMESHEET_INSIGHTS - Analyze timesheet patterns and trends
   Example: "Show me timesheet insights for Alice this month"
   Example: "Analyze variance between planned and actual hours for Website project"
   Example: "Who is consistently over-reporting hours?"
   
11. PLAN_FUTURE_ALLOCATION - Plan resource allocations for upcoming projects
   Example: "Can we staff a new project with 2 developers and 1 designer starting next month?"
   Example: "Plan allocation for Q2 Mobile App project"
   Example: "Find available resources for March-April"
   
12. MOVE_PROJECT_PHASE - Shift a specific project phase
   Example: "Move the Execute phase of Mobile App forward by 1 week"
   Example: "Delay the testing phase of Website by 5 days"

13. BUDGET_ANALYSIS - Analyze budget vs actual hours for a project
   Example: "Analyze the budget for FX1 project"
   Example: "How is the Website project tracking against budget?"
   Example: "Show me budget health for all projects"
   Example: "Is the Mobile App project on track financially?"

Return ONLY valid JSON with this structure:
{{
  "intent": "ASSIGN_RESOURCE | CREATE_PROJECT_FULL | RESCHEDULE_PROJECT | MOVE_RESOURCE | REMOVE_ALLOCATION | CREATE_RISK | UPDATE_SUMMARY | PROJECT_STATUS_UPDATE | QUERY_CAPACITY | TIMESHEET_INSIGHTS | PLAN_FUTURE_ALLOCATION | MOVE_PROJECT_PHASE | BUDGET_ANALYSIS",
  "entities": {{
    "resource_name": "name from available resources (if applicable)",
    "resource_names": ["list of resource names if multiple"],
    "project_name": "name from available projects or new project name",
    "target_project_name": "for MOVE_RESOURCE - destination project",
    "source_project_name": "for MOVE_RESOURCE - source project",
    "project_names": ["list of project names if multiple"],
    "percentage": 50,
    "weeks_to_shift": 2,
    "days_to_shift": 5,
    "shift_direction": "forward | backward",
    "phase_name": "for MOVE_PROJECT_PHASE - which phase to move",
    "time_period": "this month | last week | Q1 | etc",
    "analysis_type": "variance | patterns | over_reporting | utilization",
    "start_date": "YYYY-MM-DD for future planning",
    "end_date": "YYYY-MM-DD for future planning",
    "phases": [
      {{"name": "Phase Name", "duration_weeks": 3}}
    ],
    "client_name": "client name for new projects",
    "risk_description": "description of the risk",
    "risk_impact": "Low | Medium | High | Critical",
    "risks": [
      {{"description": "risk text", "impact": "High", "probability": "Medium"}}
    ],
    "status_update": {{
      "health": "Green | Amber | Red",
      "schedule_status": "On Track | Delayed | Ahead of Schedule | At Risk",
      "actual_progress": 60,
      "accomplishments": "what was completed this week",
      "blockers": "any blockers or issues",
      "next_steps": "planned next actions"
    }}
  }},
  "confidence": 0.95,
  "natural_language": "Clear human-friendly explanation of what will be done"
}}

Important:
- Match resource and project names to the available ones listed above
- For CREATE_PROJECT_FULL, generate appropriate phases if user mentions standard phases like "initiate, plan, execute, close"
- For RESCHEDULE_PROJECT, extract the number of weeks and direction
- For MOVE_RESOURCE, identify both source and target projects
- For PROJECT_STATUS_UPDATE: 
  * The 'health' status MUST reflect the 'schedule_status'. If schedule_status is 'Delayed' or 'At Risk', then health MUST be 'Amber' or 'Red', NOT 'Green'.
  * If the user mentions delays, blockers, or risks, set health to 'Amber' (minor issues) or 'Red' (critical issues).
  * Only set health to 'Green' when the project is explicitly on track with no issues.
  * Extract progress percentage, accomplishments, blockers, and next steps from the command.
- Only include entities relevant to the detected intent
- Be specific in natural_language about what changes will be made"""

    user_message = f"User request: {command.query}"
    
    try:
        ai_response = None
        provider_used = "unknown"
        
        # Get app-wide AI config (DB settings → Emergent fallback)
        ai_config = await get_ai_config()
        config_provider = ai_config["provider"]
        config_key = ai_config["api_key"]

        if not config_key:
            raise HTTPException(status_code=500, detail="No AI provider configured. Ask a super admin to set up AI settings.")

        if config_provider == "openai":
            response = await call_openai_api(config_key, system_prompt, user_message)
            if response.status_code == 200:
                result = response.json()
                ai_response = json.loads(result["choices"][0]["message"]["content"])
                provider_used = "openai"
            else:
                # Try Emergent LLM as fallback
                ai_response = await call_emergent_fallback(system_prompt, user_message)
                if ai_response:
                    provider_used = "emergent_fallback"
                else:
                    raise HTTPException(status_code=500, detail="AI service failed. Please check API key in Settings.")

        elif config_provider == "gemini":
            response = await call_gemini_api(config_key, system_prompt, user_message)
            if response.status_code == 200:
                result = response.json()
                ai_response = json.loads(result["candidates"][0]["content"]["parts"][0]["text"])
                provider_used = "gemini"
            else:
                ai_response = await call_emergent_fallback(system_prompt, user_message)
                if ai_response:
                    provider_used = "emergent_fallback"
                else:
                    raise HTTPException(status_code=500, detail="AI service failed. Please check API key in Settings.")

        else:
            # "emergent" provider — use Emergent LLM directly
            ai_response = await call_emergent_fallback(system_prompt, user_message)
            if ai_response:
                provider_used = "emergent"
            else:
                raise HTTPException(status_code=500, detail="AI service unavailable. Please try again later.")
        
        if ai_response is None:
            raise HTTPException(status_code=500, detail="Failed to get AI response")
        
        # Add provider indicator to natural language response
        provider_msg = ""
        if provider_used == "emergent_fallback":
            provider_msg = " (using backup AI)"
        elif provider_used == "gemini":
            provider_msg = " (Gemini)"
        elif provider_used == "openai":
            provider_msg = " (OpenAI)"
        
        return AICommandResponse(
            intent=ai_response.get("intent", "UNKNOWN"),
            entities=ai_response.get("entities", {}),
            confidence=ai_response.get("confidence", 0.0),
            natural_language=ai_response.get("natural_language", "Action parsed successfully") + provider_msg,
            provider_used=provider_used
        )
    
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI service timeout. Please try again.")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid response from AI service")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI command failed: {str(e)}")


# ==================== AI ANALYSIS ENDPOINTS ====================



@router.get("/api/ai/project-budget-analysis/{project_id}")
async def get_project_budget_analysis(project_id: str, current_user: dict = Depends(get_current_user)):
    """
    AI-powered budget vs actual analysis for a project.
    Returns narrative summary, proactive alerts, and recommendations.
    """
    import json
    import re

    # Gather project data
    project = await projects_collection.find_one({"_id": ObjectId(project_id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get timesheets
    timesheets = await timesheets_collection.find({"project_id": project_id}).to_list(length=10000)
    
    # Get allocations
    allocations = await allocations_collection.find({"project_id": project_id}).to_list(length=1000)
    
    # Get resource names
    all_resources = await resources_collection.find().to_list(length=1000)
    resource_map = {str(r["_id"]): r.get("name", "Unknown") for r in all_resources}

    # Calculate project-level metrics
    total_planned = sum(t.get("planned_hours", 0) for t in timesheets)
    total_actual = sum(t.get("actual_hours", 0) for t in timesheets)
    project_budget = float(project.get("budgeted_hours") or 0)

    # Phase breakdown
    phases = project.get("phases", [])
    phase_data = []
    for phase in phases:
        pid = phase.get("id")
        phase_ts = [t for t in timesheets if t.get("phase_id") == pid]
        p_planned = sum(t.get("planned_hours", 0) for t in phase_ts)
        p_actual = sum(t.get("actual_hours", 0) for t in phase_ts)
        p_budget = float(phase.get("budgeted_hours") or 0)
        phase_data.append({
            "name": phase.get("name", "Unknown"),
            "status": phase.get("status", "Not Started"),
            "budgeted_hours": p_budget,
            "planned_hours": round(p_planned, 1),
            "actual_hours": round(p_actual, 1),
            "start_date": str(phase.get("start_date", "")),
            "end_date": str(phase.get("end_date", "")),
        })

    # Resource breakdown
    resource_data = {}
    for t in timesheets:
        rid = t.get("resource_id", "")
        if rid not in resource_data:
            resource_data[rid] = {"name": resource_map.get(rid, "Unknown"), "planned": 0, "actual": 0}
        resource_data[rid]["planned"] += t.get("planned_hours", 0)
        resource_data[rid]["actual"] += t.get("actual_hours", 0)

    # Allocation info
    alloc_info = []
    for a in allocations:
        rid = a.get("resource_id", "")
        alloc_info.append({
            "resource": resource_map.get(rid, "Unknown"),
            "percentage": a.get("percentage", 0),
            "role": a.get("role", ""),
            "start": str(a.get("start_date", "")),
            "end": str(a.get("end_date", "")),
        })

    # Build the AI prompt
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    project_context = f"""Project: {project.get("name")}
Client: {project.get("client_name", "Unknown")}
Status: {project.get("status", "Unknown")}
Health: {project.get("health", "Unknown")}
Start: {project.get("start_date", "N/A")}
End: {project.get("end_date", "N/A")}
Today: {today}

BUDGET:
- Total Budget: {project_budget}h
- Total Planned (from timesheets): {round(total_planned, 1)}h
- Total Actual (from timesheets): {round(total_actual, 1)}h
- Budget Used: {round(total_actual / project_budget * 100, 1) if project_budget > 0 else 0}%

PHASES:
{json.dumps(phase_data, indent=2)}

RESOURCE ALLOCATION:
{json.dumps(alloc_info, indent=2)}

RESOURCE TIMESHEET DATA:
{json.dumps([{"name": v["name"], "planned": round(v["planned"], 1), "actual": round(v["actual"], 1)} for v in resource_data.values()], indent=2)}"""

    system_prompt = """You are an AI project management analyst. Analyze the project budget and time tracking data and provide a structured analysis.

Return ONLY valid JSON with this structure:
{
  "narrative": "A 2-3 sentence executive summary of the project's budget health. Be specific with numbers. Example: 'FX1 is currently tracking well at 3% budget utilization with 6h of the 300h budget consumed. The Execution phase shows the most activity...'",
  "burn_rate": {
    "current_weekly": 0,
    "projected_total": 0,
    "weeks_remaining_at_rate": 0,
    "on_track": true
  },
  "alerts": [
    {
      "severity": "critical|warning|info",
      "title": "Brief alert title",
      "message": "Explanation of the alert with specific data"
    }
  ],
  "recommendations": [
    {
      "priority": "high|medium|low",
      "title": "Brief recommendation title",
      "action": "Specific actionable recommendation"
    }
  ],
  "phase_insights": [
    {
      "phase": "Phase Name",
      "status": "on_track|at_risk|over_budget|under_utilized",
      "insight": "One sentence insight about this phase"
    }
  ]
}

Rules:
- If there's no budget set, note it as a recommendation to set one
- If there's no timesheet data, note it and provide setup recommendations
- Be concise and action-oriented
- Use actual numbers from the data, don't make up values
- For burn rate, calculate based on actual hours logged per week
- Flag any phase where actual > budgeted as critical
- Flag phases with no activity but approaching deadlines as warnings"""

    # Inject custom AI instructions
    custom_instructions = await get_instructions_for_prompt(category="chat", project_id=project_id)
    system_prompt += custom_instructions

    # Call AI
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import uuid as uuid_module
        
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"budget-analysis-{uuid_module.uuid4()}",
            system_message=system_prompt
        ).with_model("openai", "gpt-4o-mini")
        
        user_msg = UserMessage(text=f"Analyze this project data:\n\n{project_context}\n\nRespond with valid JSON only, no markdown.")
        response = await chat.send_message(user_msg)
        
        # Clean response
        if isinstance(response, str):
            cleaned = re.sub(r'^```(?:json)?\s*', '', response.strip())
            cleaned = re.sub(r'\s*```$', '', cleaned)
            response = cleaned.strip()
        
        analysis = json.loads(response)
        return analysis
    except json.JSONDecodeError:
        # Return a fallback analysis based on the data
        return _generate_fallback_analysis(project, project_budget, total_planned, total_actual, phase_data, alloc_info)
    except Exception as e:
        print(f"AI budget analysis error: {type(e).__name__}: {str(e)}")
        return _generate_fallback_analysis(project, project_budget, total_planned, total_actual, phase_data, alloc_info)


def _generate_fallback_analysis(project, budget, planned, actual, phases, allocations):
    """Generate a rule-based fallback when AI is unavailable."""
    budget_used_pct = round(actual / budget * 100, 1) if budget > 0 else 0
    
    alerts = []
    if budget == 0:
        alerts.append({"severity": "warning", "title": "No budget set", "message": "This project has no budget configured. Set a budget to enable burn rate tracking."})
    elif budget_used_pct > 90:
        alerts.append({"severity": "critical", "title": "Budget nearly exhausted", "message": f"Project has used {budget_used_pct}% of its {budget}h budget."})
    elif budget_used_pct > 70:
        alerts.append({"severity": "warning", "title": "Budget usage high", "message": f"Project has used {budget_used_pct}% of its {budget}h budget."})
    
    for p in phases:
        if p["budgeted_hours"] > 0 and p["actual_hours"] > p["budgeted_hours"]:
            alerts.append({"severity": "critical", "title": f"{p['name']} over budget", "message": f"Phase has used {p['actual_hours']}h of {p['budgeted_hours']}h budget."})
    
    if actual == 0 and planned == 0:
        alerts.append({"severity": "info", "title": "No time logged", "message": "No timesheets have been submitted for this project yet."})

    recommendations = []
    if budget == 0:
        recommendations.append({"priority": "high", "title": "Set project budget", "action": "Define budgeted hours at the project and phase level to enable tracking."})
    if len(allocations) == 0:
        recommendations.append({"priority": "medium", "title": "Add resource allocations", "action": "Allocate team members to this project to track capacity."})

    narrative = f"Project '{project.get('name')}' has logged {actual}h actual hours"
    if budget > 0:
        narrative += f" against a {budget}h budget ({budget_used_pct}% used)."
    else:
        narrative += ". No budget has been set for tracking."

    return {
        "narrative": narrative,
        "burn_rate": {"current_weekly": 0, "projected_total": actual, "weeks_remaining_at_rate": 0, "on_track": budget_used_pct <= 100 if budget > 0 else True},
        "alerts": alerts,
        "recommendations": recommendations,
        "phase_insights": [{"phase": p["name"], "status": "over_budget" if (p["budgeted_hours"] > 0 and p["actual_hours"] > p["budgeted_hours"]) else "on_track", "insight": f"{p['actual_hours']}h actual vs {p['budgeted_hours']}h budget"} for p in phases if p["budgeted_hours"] > 0]
    }



@router.post("/api/ai/timesheet-insights")
async def get_timesheet_insights(
    project_name: Optional[str] = None,
    resource_name: Optional[str] = None,
    time_period: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Analyze timesheet patterns and return structured insights."""
    # Get all timesheets
    query = {}
    if project_name:
        project = await projects_collection.find_one({"name": {"$regex": project_name, "$options": "i"}})
        if project:
            query["project_id"] = str(project["_id"])
    
    if resource_name:
        resource = await resources_collection.find_one({"name": {"$regex": resource_name, "$options": "i"}})
        if resource:
            query["resource_id"] = str(resource["_id"])
    
    timesheets = await timesheets_collection.find(query).to_list(length=10000)
    
    if not timesheets:
        return {"insights": [], "summary": "No timesheet data found for the given criteria."}
    
    # Calculate insights
    total_planned = sum(t.get("planned_hours", 0) for t in timesheets)
    total_actual = sum(t.get("actual_hours", 0) for t in timesheets)
    variance = total_actual - total_planned
    variance_pct = (variance / total_planned * 100) if total_planned > 0 else 0
    
    # Per-resource breakdown
    resource_map = {}
    all_resources = await resources_collection.find().to_list(length=1000)
    r_name_map = {str(r["_id"]): r.get("name", "Unknown") for r in all_resources}
    
    for t in timesheets:
        rid = t.get("resource_id", "unknown")
        if rid not in resource_map:
            resource_map[rid] = {"planned": 0, "actual": 0}
        resource_map[rid]["planned"] += t.get("planned_hours", 0)
        resource_map[rid]["actual"] += t.get("actual_hours", 0)
    
    resource_insights = []
    for rid, data in resource_map.items():
        v = data["actual"] - data["planned"]
        resource_insights.append({
            "resource_name": r_name_map.get(rid, "Unknown"),
            "planned_hours": round(data["planned"], 2),
            "actual_hours": round(data["actual"], 2),
            "variance_hours": round(v, 2),
            "utilization_pct": round((data["actual"] / data["planned"] * 100) if data["planned"] > 0 else 0, 1)
        })
    
    resource_insights.sort(key=lambda x: abs(x["variance_hours"]), reverse=True)
    
    # Over-reporters
    over_reporters = [r for r in resource_insights if r["variance_hours"] > 2]
    under_reporters = [r for r in resource_insights if r["variance_hours"] < -2]
    
    insights = []
    if abs(variance_pct) > 20:
        insights.append(f"Overall variance is {variance_pct:+.1f}% ({variance:+.1f}h). This is significant and should be reviewed.")
    if over_reporters:
        names = ", ".join(r["resource_name"] for r in over_reporters[:3])
        insights.append(f"Over-reporting: {names} logged more hours than planned.")
    if under_reporters:
        names = ", ".join(r["resource_name"] for r in under_reporters[:3])
        insights.append(f"Under-reporting: {names} logged fewer hours than planned.")
    
    return {
        "summary": {
            "total_entries": len(timesheets),
            "total_planned_hours": round(total_planned, 2),
            "total_actual_hours": round(total_actual, 2),
            "variance_hours": round(variance, 2),
            "variance_percentage": round(variance_pct, 1)
        },
        "resource_breakdown": resource_insights[:10],
        "insights": insights
    }


@router.post("/api/ai/plan-allocation")
async def plan_future_allocation(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    required_count: int = 1,
    current_user: dict = Depends(get_current_user)
):
    """Find available resources for future project planning."""
    from datetime import datetime
    
    # Default to next month if no dates given
    today = datetime.now()
    if not start_date:
        next_month = today.replace(day=1) + timedelta(days=32)
        start_date = next_month.replace(day=1).strftime("%Y-%m-%d")
    if not end_date:
        end_dt = datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=60)
        end_date = end_dt.strftime("%Y-%m-%d")
    
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    
    # Get all resources (active only — deactivated resources are not plannable)
    all_resources = await resources_collection.find({"active": {"$ne": False}}).to_list(length=1000)
    
    # Get allocations overlapping with the date range
    allocations = await allocations_collection.find().to_list(length=10000)
    
    resource_availability = []
    for resource in all_resources:
        rid = str(resource["_id"])
        
        # Sum existing allocation percentages in the date range
        existing_pct = 0
        for alloc in allocations:
            if alloc.get("resource_id") != rid:
                continue
            try:
                a_start = datetime.strptime(alloc["start_date"][:10], "%Y-%m-%d") if isinstance(alloc["start_date"], str) else alloc["start_date"]
                a_end = datetime.strptime(alloc["end_date"][:10], "%Y-%m-%d") if isinstance(alloc["end_date"], str) else alloc["end_date"]
            except (ValueError, TypeError):
                continue
            # Check overlap
            if a_start <= end_dt and a_end >= start_dt:
                existing_pct += alloc.get("percentage", 0)
        
        available_pct = max(0, 100 - existing_pct)
        resource_availability.append({
            "resource_id": rid,
            "resource_name": resource.get("name", "Unknown"),
            "role": resource.get("role", "N/A"),
            "current_allocation_pct": existing_pct,
            "available_pct": available_pct
        })
    
    # Sort by availability (most available first)
    resource_availability.sort(key=lambda x: x["available_pct"], reverse=True)
    
    available = [r for r in resource_availability if r["available_pct"] >= 20]
    
    return {
        "date_range": {"start": start_date, "end": end_date},
        "total_resources": len(all_resources),
        "available_resources": available[:10],
        "fully_booked": [r for r in resource_availability if r["available_pct"] < 20][:5],
        "can_staff": len(available) >= required_count,
        "recommendation": f"{'Yes' if len(available) >= required_count else 'No'}, {len(available)} resources available (need {required_count})."
    }


@router.post("/api/projects/{project_id}/move-phase")
async def move_project_phase(
    project_id: str,
    phase_name: str,
    days_to_shift: int = 0,
    weeks_to_shift: int = 0,
    direction: str = "forward",
    admin: dict = Depends(require_admin)
):
    """Shift a specific project phase forward or backward."""
    project = await projects_collection.find_one({"_id": ObjectId(project_id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    phases = project.get("phases", [])
    if not phases:
        raise HTTPException(status_code=400, detail="Project has no phases")
    
    total_days = days_to_shift + (weeks_to_shift * 7)
    if direction == "backward":
        total_days = -total_days
    
    if total_days == 0:
        raise HTTPException(status_code=400, detail="No shift specified")
    
    # Find the phase
    phase_found = False
    for phase in phases:
        if phase.get("name", "").lower() == phase_name.lower():
            phase_found = True
            try:
                start = phase.get("start_date")
                end = phase.get("end_date")
                
                if isinstance(start, str):
                    start = datetime.fromisoformat(start.replace("Z", "+00:00"))
                if isinstance(end, str):
                    end = datetime.fromisoformat(end.replace("Z", "+00:00"))
                
                phase["start_date"] = (start + timedelta(days=total_days)).isoformat()
                phase["end_date"] = (end + timedelta(days=total_days)).isoformat()
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Could not parse phase dates: {str(e)}")
            break
    
    if not phase_found:
        available = [p.get("name") for p in phases]
        raise HTTPException(status_code=404, detail=f"Phase '{phase_name}' not found. Available: {', '.join(available)}")
    
    await projects_collection.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {"phases": phases}}
    )
    
    updated = await projects_collection.find_one({"_id": ObjectId(project_id)})
    return serialize_doc(updated)


# ==================== AI SMART RESCHEDULE ====================


@router.post("/api/ai/smart-reschedule/{project_id}")
async def ai_smart_reschedule(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    AI-powered smart reschedule analysis.
    Analyzes project status, progress, delays, and WBS completion to recommend
    optimal rescheduling. Returns analysis + preview of date changes.
    """
    import json
    from utils import count_business_days, snap_to_weekday
    
    # Gather all project data
    project = await projects_collection.find_one({"_id": ObjectId(project_id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get allocations
    allocs = await allocations_collection.find({"project_id": project_id}).to_list(1000)
    
    # Get WBS tasks
    wbs_tasks = await wbs_tasks_collection.find({"project_id": project_id}).to_list(10000)
    
    # Get latest status update
    latest_status = await status_updates_collection.find_one(
        {"project_id": project_id},
        sort=[("created_at", -1)]
    )
    
    # Calculate project metrics
    today = date.today()
    project_start = project.get("start_date")
    project_end = project.get("end_date")
    
    if isinstance(project_start, datetime):
        project_start = project_start.date()
    if isinstance(project_end, datetime):
        project_end = project_end.date()
    
    total_biz_days = count_business_days(project_start, project_end) if project_start and project_end else 0
    elapsed_biz_days = count_business_days(project_start, today) if project_start else 0
    remaining_biz_days = count_business_days(today, project_end) if project_end else 0
    time_progress = round((elapsed_biz_days / total_biz_days * 100) if total_biz_days > 0 else 0, 1)
    
    # WBS stats
    total_tasks = len(wbs_tasks)
    completed_tasks = sum(1 for t in wbs_tasks if t.get("status") == "done")
    milestone_tasks = [t for t in wbs_tasks if t.get("is_milestone")]
    overdue_tasks = [t for t in wbs_tasks if t.get("end_date") and not t.get("status") == "done"]
    
    # Count overdue
    overdue_count = 0
    for t in overdue_tasks:
        end = t.get("end_date")
        if isinstance(end, str):
            try:
                end = datetime.strptime(end[:10], "%Y-%m-%d").date()
            except ValueError:
                continue
        elif isinstance(end, datetime):
            end = end.date()
        if end and end < today:
            overdue_count += 1
    
    actual_progress = project.get("actual_progress", 0)
    health = project.get("health", "Green")
    schedule_status = project.get("schedule_status", "On Track")
    
    # Phases info
    phases_info = []
    for p in project.get("phases", []):
        phases_info.append({
            "name": p.get("name"),
            "start_date": str(p.get("start_date", ""))[:10],
            "end_date": str(p.get("end_date", ""))[:10],
            "status": p.get("status", "active")
        })
    
    # Build context for AI
    context = f"""
Project: {project.get('name')} (Client: {project.get('client_name', 'N/A')})
Status: {project.get('status')} | Health: {health} | Schedule: {schedule_status}
Dates: {str(project_start)} to {str(project_end)} ({total_biz_days} business days)
Time elapsed: {time_progress}% | Actual progress: {actual_progress}%
Phases: {json.dumps(phases_info)}
WBS: {total_tasks} tasks, {completed_tasks} completed, {overdue_count} overdue
Milestones: {len(milestone_tasks)} total, {sum(1 for m in milestone_tasks if m.get('milestone_completed'))} completed
Allocations: {len(allocs)} team members
Latest status: {latest_status.get('blockers', 'None reported') if latest_status else 'No status updates'}
Today's date: {today.isoformat()}
"""
    
    system_prompt = """You are a project scheduling AI expert. Analyze the project data and recommend whether and how to reschedule.

Consider:
1. Gap between time elapsed vs actual progress (if time is 80% but progress is 40%, project is significantly behind)
2. Number of overdue WBS tasks
3. Health and schedule status
4. Blockers mentioned in latest status update
5. Remaining milestones vs remaining time

Return ONLY valid JSON:
{
  "should_reschedule": true/false,
  "recommended_weeks": 0,
  "direction": "forward",
  "confidence": 0.85,
  "analysis": "2-3 sentence analysis of the project schedule health",
  "reasons": ["reason 1", "reason 2"],
  "risk_if_not_rescheduled": "What happens if we don't reschedule",
  "impact_summary": "Brief summary of what will change"
}

If the project is on track, set should_reschedule=false and recommended_weeks=0.
Be conservative — only recommend rescheduling when there's a clear gap between time and progress.
Recommended weeks should be between 1 and 8."""

    # Inject custom AI instructions
    custom_instructions = await get_instructions_for_prompt(category="reschedule", project_id=project_id)
    system_prompt += custom_instructions

    try:
        ai_config = await get_ai_config()
        config_key = ai_config["api_key"]
        
        if not config_key:
            raise HTTPException(status_code=500, detail="No AI provider configured")
        
        ai_response = None
        provider = ai_config["provider"]
        
        if provider == "openai":
            response = await call_openai_api(config_key, system_prompt, context)
            if response.status_code == 200:
                result = response.json()
                ai_response = json.loads(result["choices"][0]["message"]["content"])
        
        if not ai_response:
            ai_response = await call_emergent_fallback(system_prompt, context)
        
        if not ai_response:
            raise HTTPException(status_code=500, detail="AI service unavailable")
        
        # Build preview of date changes
        weeks = ai_response.get("recommended_weeks", 0)
        direction = ai_response.get("direction", "forward")
        days_shift = weeks * 7 * (1 if direction == "forward" else -1)
        shift_delta = timedelta(days=days_shift)
        
        preview = {
            "project": {
                "current_start": str(project_start),
                "current_end": str(project_end),
                "new_start": str(snap_to_weekday(project_start + shift_delta)) if project_start and weeks > 0 else str(project_start),
                "new_end": str(snap_to_weekday(project_end + shift_delta)) if project_end and weeks > 0 else str(project_end),
            },
            "phases_count": len(project.get("phases", [])),
            "allocations_count": len(allocs),
            "wbs_tasks_count": total_tasks,
            "milestones_count": len(milestone_tasks),
        }
        
        return {
            "project_id": project_id,
            "project_name": project.get("name"),
            "analysis": ai_response,
            "preview": preview,
            "metrics": {
                "time_progress": time_progress,
                "actual_progress": actual_progress,
                "overdue_tasks": overdue_count,
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "health": health,
                "schedule_status": schedule_status,
                "remaining_biz_days": remaining_biz_days,
            }
        }
    
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid AI response format")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Smart reschedule analysis failed: {str(e)}")


# ==================== DATA EXPORT/SYNC API ====================


@router.post("/api/ai/chat")
async def ai_chat(req: ChatMessage, current_user: dict = Depends(get_current_user)):
    """
    Conversational AI agent with multi-turn memory.
    Can answer questions about projects, resources, budgets, and execute actions.
    """
    user_email = current_user["email"]
    session_id = req.session_id

    # Load or create session
    session = None
    if session_id:
        session = await chat_sessions_collection.find_one({
            "_id": ObjectId(session_id), "user_email": user_email
        })

    if not session:
        session = {
            "user_email": user_email,
            "messages": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        result = await chat_sessions_collection.insert_one(session)
        session["_id"] = result.inserted_id
        session_id = str(result.inserted_id)

    # Build context from live data
    projects = await projects_collection.find().to_list(length=500)
    resources = await resources_collection.find().to_list(length=500)
    allocations = await allocations_collection.find().to_list(length=2000)
    timesheets = await timesheets_collection.find().to_list(length=5000)
    status_updates = await status_updates_collection.find().to_list(length=500)

    # ── ROLE-BASED DATA SCOPING — mirror the REST API permission model ──
    role = (current_user.get("role") or "").lower()
    is_admin = role in ("admin", "super_admin")
    my_rid = None
    allowed_pids = None  # None = unrestricted (admin)
    led_pids = set()     # projects this (non-admin) user LEADS — limited actions allowed

    if not is_admin:
        from utils import find_user_resource
        if role == "client":
            allowed_pids = {str(pid) for pid in current_user.get("allowed_project_ids", [])}
        else:
            resource_doc = await find_user_resource(current_user)
            my_rid = str(resource_doc["_id"]) if resource_doc else None
            allowed_pids = {a.get("project_id") for a in allocations if a.get("resource_id") == my_rid}
            allowed_pids |= {str(p["_id"]) for p in projects if p.get("project_lead_id") == my_rid}

        projects = [p for p in projects if str(p["_id"]) in allowed_pids]
        allocations = [a for a in allocations if a.get("project_id") in allowed_pids]
        status_updates = [s for s in status_updates if s.get("project_id") in allowed_pids]
        if role == "client":
            timesheets = []  # clients never see timesheet data
            team_rids = {a.get("resource_id") for a in allocations}
            resources = [r for r in resources if str(r["_id"]) in team_rids]
        else:
            timesheets = [t for t in timesheets if t.get("resource_id") == my_rid]
            team_rids = {a.get("resource_id") for a in allocations} | ({my_rid} if my_rid else set())
            resources = [r for r in resources if str(r["_id"]) in team_rids]
        if my_rid:
            led_pids = {str(p["_id"]) for p in projects if str(p.get("project_lead_id") or "") == my_rid}

    can_act = is_admin or bool(led_pids)

    # Build maps EARLY so lazy-load blocks below can use them
    resource_map = {str(r["_id"]): r.get("name", "Unknown") for r in resources}
    project_map = {str(p["_id"]): p.get("name", "Unknown") for p in projects}

    # ── SMART ROUTING: detect intent in the user message and lazy-load
    # extra context blocks only when needed. Keeps the prompt small for the
    # 80% of queries that don't need deep drilling.
    _msg_lower = (req.message or "").lower()

    def _wants(keywords):
        return any(k in _msg_lower for k in keywords)

    needs_wbs        = _wants(["wbs", "task", "breakdown", "subtask", "deliverable", "estimated"])
    needs_baseline   = _wants(["baseline", "variance", "drift", "vs original", "vs plan", "schedule slip"])
    needs_holidays   = _wants(["holiday", "public holiday", "stat day", "stat. day"])
    needs_leaves     = _wants(["leave", "vacation", "pto", "time off", "annual leave"])
    needs_users      = _wants(["user", "role", "permission", "access ", "login", "password"])
    needs_changelog  = _wants(["change log", "changelog", "audit", "history", "who changed", "who modified"])
    needs_reconcile  = _wants(["reconcile", "reconciliation", "budget vs", "allocated vs", "actual vs"])

    extra_context_blocks = []

    if needs_wbs:
        wbs_tasks = await wbs_tasks_collection.find().to_list(length=5000)
        if not is_admin:
            wbs_tasks = [t for t in wbs_tasks if t.get("project_id") in allowed_pids]
        # Group by project for compact display
        wbs_by_proj = {}
        for t in wbs_tasks:
            pid = t.get("project_id", "?")
            wbs_by_proj.setdefault(pid, []).append(t)
        wbs_lines = [f"\nWBS TASKS (total: {len(wbs_tasks)}):"]
        for pid, tasks in list(wbs_by_proj.items())[:20]:
            pname = project_map.get(pid, "?")
            wbs_lines.append(f"  • {pname} ({len(tasks)} tasks):")
            for t in tasks[:15]:
                status = t.get("status", "?")
                est = t.get("estimated_hours") or "—"
                wbs_lines.append(f"    - [{status}] {t.get('name','?')} (est: {est}h, phase: {t.get('phase_name','?')}, id: {str(t.get('_id'))})")
        extra_context_blocks.append("\n".join(wbs_lines))

    if needs_baseline or needs_reconcile:
        try:
            from services.budget_reconciliation import reconciliation_summary
            bl_lines = ["\nBUDGET RECONCILIATION & BASELINE VARIANCE (per project):"]
            for p in projects[:20]:
                s = await reconciliation_summary(str(p["_id"]))
                t = s.get("totals", {})
                bl_lines.append(
                    f"  • {p.get('name')}: Budget={t.get('budget',0)}h | "
                    f"Estimated={t.get('estimated',0)}h | Allocated={t.get('allocated',0)}h | "
                    f"Actual={t.get('actual',0)}h | warnings={s.get('warning_count', 0)}"
                )
                # Also include drift if any
                if t.get("estimated_vs_budget"):
                    bl_lines.append(f"      drift: est {t['estimated_vs_budget']:+.1f}h, alloc {t.get('allocated_vs_budget',0):+.1f}h, actual {t.get('actual_vs_budget',0):+.1f}h vs budget")
            extra_context_blocks.append("\n".join(bl_lines))
        except Exception:
            pass

    if needs_holidays:
        try:
            from database import holidays_collection
            holidays = await holidays_collection.find().to_list(length=200)
            if holidays:
                h_lines = [f"\nPUBLIC HOLIDAYS ({len(holidays)}):"]
                for h in holidays[:30]:
                    d = str(h.get("date", ""))[:10]
                    h_lines.append(f"  • {d} — {h.get('name','?')} ({h.get('region','?')}) [id: {str(h.get('_id'))}]")
                extra_context_blocks.append("\n".join(h_lines))
        except Exception:
            pass

    if needs_leaves:
        try:
            from database import leaves_collection
            leaves = await leaves_collection.find().to_list(length=500)
            if not is_admin:
                leaves = [lv for lv in leaves if lv.get("resource_id") == my_rid]
            if leaves:
                l_lines = [f"\nLEAVE ENTRIES ({len(leaves)}):"]
                for lv in leaves[:30]:
                    r_name = resource_map.get(lv.get("resource_id", ""), "?")
                    s = str(lv.get("start_date", ""))[:10]
                    e = str(lv.get("end_date", ""))[:10]
                    l_lines.append(f"  • {r_name}: {s} → {e} ({lv.get('type') or lv.get('reason','-')}) [id: {str(lv.get('_id'))}]")
                extra_context_blocks.append("\n".join(l_lines))
        except Exception:
            pass

    if needs_users and is_admin:
        try:
            from database import users_collection
            users = await users_collection.find().to_list(length=500)
            u_lines = [f"\nUSERS ({len(users)}):"]
            for u in users[:50]:
                disabled = " [DISABLED]" if u.get("disabled") else ""
                u_lines.append(f"  • {u.get('email','?')} — role: {u.get('role','?')}{disabled}")
            extra_context_blocks.append("\n".join(u_lines))
        except Exception:
            pass

    if needs_changelog:
        try:
            from database import change_log_collection
            entries = await change_log_collection.find().sort("timestamp", -1).limit(50).to_list(length=50)
            if entries:
                cl_lines = [f"\nRECENT CHANGE LOG (last 50):"]
                for e in entries:
                    cl_lines.append(f"  • {str(e.get('timestamp',''))[:19]} | {e.get('user_email','?')} | {e.get('entity_type','?')}.{e.get('field','')} | {e.get('action','?')}")
                extra_context_blocks.append("\n".join(cl_lines))
        except Exception:
            pass

    extra_context_text = "\n".join(extra_context_blocks)

    sydney_now = datetime.now(SYDNEY_TZ)
    today_str = sydney_now.strftime("%Y-%m-%d")
    from_date = sydney_now - timedelta(days=sydney_now.weekday())  # Monday this week
    week_start = from_date.strftime("%Y-%m-%d")
    week_end = (from_date + timedelta(days=4)).strftime("%Y-%m-%d")  # Friday

    # Compact ID reference table
    id_table = "PROJECT & RESOURCE IDs (use these exact IDs in actions):\n"
    for p in projects:
        id_table += f"  Project \"{p.get('name')}\" = {str(p['_id'])}\n"
    for r in resources:
        id_table += f"  Resource \"{r.get('name')}\" = {str(r['_id'])}\n"

    # Project summaries (compact)
    proj_lines = []
    for p in projects:
        pid = str(p["_id"])
        p_allocs = [a for a in allocations if a.get("project_id") == pid]
        actual_hrs = sum(t.get("actual_hours", 0) for t in timesheets if t.get("project_id") == pid)
        team = [resource_map.get(a.get("resource_id"), "?") for a in p_allocs]
        lead = resource_map.get(p.get("project_lead_id"), "Unassigned")
        proj_lines.append(
            f"- {p.get('name')} | Client: {p.get('client_name')} | Status: {p.get('status')} | "
            f"Budget: {p.get('budgeted_hours', 'N/A')}h | Actual: {actual_hrs}h | "
            f"Lead: {lead} | Team: {', '.join(set(team[:4])) or 'None'} | "
            f"{str(p.get('start_date',''))[:10]} to {str(p.get('end_date',''))[:10]}"
        )

    # Current allocations with dates and IDs (critical for "this week" queries and updates)
    alloc_lines = []
    for a in allocations:
        res_name = resource_map.get(a.get("resource_id"), "?")
        proj_name = project_map.get(a.get("project_id"), "?")
        start = str(a.get("start_date", ""))[:10]
        end = str(a.get("end_date", ""))[:10]
        pct = a.get("percentage", 0)
        alloc_id = str(a.get("_id", ""))
        alloc_lines.append(f"- {res_name} -> {proj_name} | {pct}% | {start} to {end} | alloc_id: {alloc_id}")

    # Resource summaries with utilization analysis
    # Hide deactivated resources from team/utilization lists (names still resolve via maps)
    active_resources = [r for r in resources if r.get("active") is not False]
    res_lines = []
    for r in active_resources:
        rid = str(r["_id"])
        r_allocs = [a for a in allocations if a.get("resource_id") == rid]
        total_pct = sum(a.get("percentage", 0) for a in r_allocs)
        status = "OVER-UTILIZED" if total_pct > 100 else ("AT CAPACITY" if total_pct == 100 else "Available")
        res_lines.append(f"- {r.get('name')} | {r.get('role')} | Total alloc: {total_pct}% | {status}")

    # Clients may know WHO is on their projects, but not internal allocation %/utilization
    if role == "client":
        alloc_lines = ["(allocation percentages are internal-only)"]
        res_lines = [f"- {r.get('name')} | {r.get('role')}" for r in active_resources]

    # Weekly timesheet analysis (last 4 weeks) - Planned vs Actual hours
    # Non-admins only see their own row (matches REST API scoping)
    visible_resources = active_resources if is_admin else [r for r in active_resources if str(r["_id"]) == my_rid]
    four_weeks_ago = sydney_now - timedelta(days=28)
    timesheet_analysis = []
    for r in visible_resources:
        rid = str(r["_id"])
        r_name = r.get("name", "Unknown")
        # Get active allocations for this resource
        r_allocs = [a for a in allocations if a.get("resource_id") == rid]
        # Calculate planned weekly hours (assuming 40hr week, allocation % of that)
        planned_weekly = sum(a.get("percentage", 0) for a in r_allocs) * 0.4  # 40 hrs * percentage/100
        # Get actual hours logged in last 4 weeks
        r_timesheets = [t for t in timesheets if t.get("resource_id") == rid]
        actual_4weeks = sum(t.get("actual_hours", 0) for t in r_timesheets)
        planned_4weeks = planned_weekly * 4
        variance = actual_4weeks - planned_4weeks
        if planned_4weeks > 0:
            variance_pct = (variance / planned_4weeks) * 100
            status = "OVER" if variance > 0 else ("UNDER" if variance < -5 else "ON TRACK")
            timesheet_analysis.append(
                f"- {r_name}: Planned {planned_4weeks:.0f}h | Actual {actual_4weeks:.0f}h | Variance: {variance:+.0f}h ({variance_pct:+.0f}%) | {status}"
            )
        else:
            timesheet_analysis.append(f"- {r_name}: No planned hours | Actual {actual_4weeks:.0f}h logged")

    # Per-resource current-week AND previous-week submission status
    # This lets the AI answer "who has submitted this week?" / "who hasn't filled last week's timesheet?"
    prev_week_start_dt = from_date - timedelta(days=7)
    prev_week_end_dt = from_date - timedelta(days=1)
    prev_week_start = prev_week_start_dt.strftime("%Y-%m-%d")
    prev_week_end = prev_week_end_dt.strftime("%Y-%m-%d")

    def _week_bucket(ts, ws, we):
        # Each timesheet stores week_start_date; match on that string (YYYY-MM-DD)
        tws = str(ts.get("week_start_date", ""))[:10]
        return tws == ws

    def _summarize_resource_week(rid, ws, we):
        rows = [t for t in timesheets if t.get("resource_id") == rid and _week_bucket(t, ws, we)]
        if not rows:
            return "MISSING (no entries)"
        submitted = [t for t in rows if t.get("status") == "Submitted"]
        drafts = [t for t in rows if t.get("status") != "Submitted"]
        total_actual = sum(t.get("actual_hours", 0) for t in rows)
        total_planned = sum(t.get("planned_hours", 0) for t in rows)
        n_proj = len(set(t.get("project_id") for t in rows))
        if submitted and not drafts:
            overall = "SUBMITTED"
        elif submitted and drafts:
            overall = f"PARTIALLY SUBMITTED ({len(submitted)}/{len(rows)})"
        else:
            overall = "DRAFT (not submitted)"
        return f"{overall} | {total_actual:.0f}h actual / {total_planned:.0f}h planned across {n_proj} project(s)"

    curr_week_status_lines = []
    prev_week_status_lines = []
    for r in visible_resources:
        rid = str(r["_id"])
        r_name = r.get("name", "Unknown")
        curr_week_status_lines.append(f"- {r_name}: {_summarize_resource_week(rid, week_start, week_end)}")
        prev_week_status_lines.append(f"- {r_name}: {_summarize_resource_week(rid, prev_week_start, prev_week_end)}")

    # Projects without leads (for bulk assignment queries)
    projects_no_lead = [p.get("name") for p in projects if not p.get("project_lead_id")]
    no_lead_text = f"PROJECTS WITHOUT LEADS ({len(projects_no_lead)}): {', '.join(projects_no_lead[:10])}" if projects_no_lead else "All projects have leads assigned."

    # Recent project status updates (latest per project) — surfaces blockers, health, next-steps
    status_updates_all = await status_updates_collection.find().sort("created_at", -1).to_list(length=500)
    latest_status_per_project = {}
    for su in status_updates_all:
        pid = su.get("project_id")
        if pid and pid not in latest_status_per_project:
            latest_status_per_project[pid] = su

    status_update_lines = []
    for p in projects:
        pid = str(p["_id"])
        latest = latest_status_per_project.get(pid)
        if not latest:
            continue
        update_date = str(latest.get("update_date", ""))[:10]
        health = latest.get("health", "?")
        schedule = latest.get("schedule_status", "?")
        accomplishments = (latest.get("accomplishments") or "").strip().replace("\n", " ")[:200]
        blockers_val = latest.get("blockers")
        if isinstance(blockers_val, list):
            blockers_str = "; ".join([str(b).strip() for b in blockers_val if b]).strip()
        else:
            blockers_str = str(blockers_val or "").strip()
        next_steps = (latest.get("next_steps") or "").strip().replace("\n", " ")[:200]
        status_update_lines.append(
            f"- {p.get('name')} ({update_date}) | Health: {health} | Schedule: {schedule}"
            + (f" | Accomplishments: {accomplishments}" if accomplishments else "")
            + (f" | BLOCKERS: {blockers_str}" if blockers_str else " | Blockers: none")
            + (f" | Next: {next_steps}" if next_steps else "")
        )

    # Active risks & issues (not closed/mitigated)
    all_risks = await risks_collection.find().to_list(length=2000)
    if not is_admin:
        all_risks = [rk for rk in all_risks if rk.get("project_id") in allowed_pids]
    active_risk_lines = []
    for rk in all_risks:
        rk_status = rk.get("status", "Active")
        if rk_status in ("Closed", "Mitigated"):
            continue
        pid = rk.get("project_id")
        p_name = project_map.get(pid, "?")
        cat = rk.get("category", "Risk")
        active_risk_lines.append(
            f"- [{cat}] {p_name}: {rk.get('description','')[:150]} | Impact: {rk.get('impact')} | Probability: {rk.get('probability')} | Status: {rk_status}"
            + (f" | Mitigation: {rk.get('mitigation','')[:100]}" if rk.get("mitigation") else "")
        )

    data_context = f"""TODAY: {today_str} (Sydney time). This week: {week_start} to {week_end}. Last week: {prev_week_start} to {prev_week_end}.

PROJECTS ({len(projects)}):
{chr(10).join(proj_lines)}

CURRENT ALLOCATIONS ({len(allocations)}):
{chr(10).join(alloc_lines)}

RESOURCES ({len(resources)}):
{chr(10).join(res_lines)}

TIMESHEET ANALYSIS (Last 4 Weeks - Planned vs Actual):
{chr(10).join(timesheet_analysis)}

CURRENT WEEK TIMESHEET SUBMISSIONS ({week_start} to {week_end}):
{chr(10).join(curr_week_status_lines)}

LAST WEEK TIMESHEET SUBMISSIONS ({prev_week_start} to {prev_week_end}):
{chr(10).join(prev_week_status_lines)}

LATEST PROJECT STATUS UPDATES (per project — includes accomplishments, BLOCKERS, next steps):
{chr(10).join(status_update_lines) if status_update_lines else "(no status updates recorded yet)"}

ACTIVE RISKS & ISSUES (status = Active or Accepted):
{chr(10).join(active_risk_lines) if active_risk_lines else "(no active risks/issues)"}

{no_lead_text}

STATS: {sum(1 for p in projects if p.get('status')=='Active')} active, {sum(1 for p in projects if p.get('status')=='Pipeline')} pipeline, {sum(1 for p in projects if p.get('status')=='Completed')} completed. {sum(t.get('actual_hours',0) for t in timesheets):.0f} total hours logged.

{extra_context_text}
"""

    # Build conversation history
    history = session.get("messages", [])[-20:]  # Keep last 20 messages for context
    history_text = ""
    if history:
        history_text = "CONVERSATION HISTORY:\n"
        for msg in history:
            role = "User" if msg["role"] == "user" else "Assistant"
            history_text += f"{role}: {msg['content']}\n"

    # Build ID lookup tables for the AI
    project_id_list = "\n".join([
        f"  \"{p.get('name')}\" -> id: \"{str(p['_id'])}\""
        for p in projects
    ])
    resource_id_list = "\n".join([
        f"  \"{r.get('name')}\" -> id: \"{str(r['_id'])}\""
        for r in resources
    ])

    # Build the extended actions documentation block from the registry
    extended_actions_prompt = build_actions_prompt()
    specialist_triggers_doc = list_specialist_triggers()

    system_prompt_header = f"""You are DD Planner AI — the team's project-operations copilot inside DD Planner. You have live access to every project, resource, allocation, timesheet, risk, and status update, and you can take real actions on the user's behalf.

TONE & STYLE (very important — this defines you):
- Talk like a sharp, friendly colleague on the team, not like a reporting tool. Write the way a great chief-of-staff would reply on Slack.
- LEAD with the answer in plain conversational sentences. Weave the key numbers into your prose ("Henry's sitting at 120% next week, mostly because of the ASKDD overlap") instead of dumping labelled data rows.
- Only use bullet lists or tables when you're genuinely comparing 3+ items or the user asks for a list/breakdown. A short question deserves a short, natural answer — one to three sentences is often perfect.
- Never dump everything you know. Pick the 2-4 facts that actually answer the question; offer to go deeper ("want the phase-by-phase split?").
- Refer to people and projects by name, never by ID, in your visible text (IDs belong only inside action JSON).
- Have some warmth and judgement: acknowledge ("Nice — that's done"), flag concerns like a human would ("heads up, that puts the budget over by 40h"), and when it feels natural end with ONE helpful follow-up suggestion or question — never a list of questions.
- No corporate filler ("As per the data provided…", "Based on the information available…"). Just say it.
- Match the user's energy: casual message → casual reply; detailed analysis request → structured deep-dive.

Your capabilities:
1. ANALYSIS: Answer questions about project health, budgets, utilisation, risks, and trends.
2. RECOMMENDATIONS: Suggest resource optimizations, flag risks, and provide strategic insights.
"""

    actions_section = f"""3. ACTIONS: You can execute actions. When the user wants to perform an action, include a JSON action block in your response using this exact format:

```action
{{"action": "create_allocation", "resource_id": "...", "project_id": "...", "percentage": 50, "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "description": "Assign Alice to Project X at 50%"}}
```

Available actions:
- create_project: {{"action":"create_project","name":"Project Name","client_name":"Client","status":"Active|Pipeline","start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD","budgeted_hours":100,"project_lead_id":null,"description":"Create new project"}}
- create_allocation: {{"action":"create_allocation","resource_id":"...","project_id":"...","percentage":N,"start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD","description":"..."}}
- update_allocation: {{"action":"update_allocation","allocation_id":"...","percentage":N,"start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD","description":"..."}}
- remove_allocation [destructive — requires `confirm_token`]: {{"action":"remove_allocation","allocation_id":"...","description":"Remove X from project Y"}}
- update_project_status: {{"action":"update_project_status","project_id":"...","status":"Active|Pipeline|Completed","description":"..."}}
- update_project_dates: {{"action":"update_project_dates","project_id":"...","start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD","description":"Reschedule project"}}
- add_risk: {{"action":"add_risk","project_id":"...","description":"risk text","impact":"Low|Medium|High|Critical","probability":"Low|Medium|High","mitigation":"optional mitigation plan","status":"Active|Mitigated|Accepted|Closed (default Active)","category":"Risk|Issue (default Risk)","summary":"..."}}
- update_risk: {{"action":"update_risk","risk_id":"...","status":"Active|Mitigated|Accepted|Closed","mitigation":"optional","description":"..."}}
- set_project_lead: {{"action":"set_project_lead","project_id":"...","resource_id":"...","description":"Set X as lead for Y"}}
- bulk_set_project_lead: {{"action":"bulk_set_project_lead","resource_id":"...","force_all":true/false,"description":"Set X as lead for all projects (force_all=true for ALL, false for only projects without leads)"}}
- create_status_update: {{"action":"create_status_update","project_id":"...","health":"Green|Amber|Red","schedule_status":"On Track|Delayed|Ahead of Schedule|At Risk","accomplishments":"summary of what was done","blockers":"current blockers — each will auto-become an Issue in the risk register","next_steps":"plan for next week","description":"Submit weekly status update for Project X"}}

WBS (Work Breakdown Structure) ACTIONS (FIX #4):
- generate_wbs: {{"action":"generate_wbs","project_id":"...","complexity":"simple|standard|detailed (default: standard)","additional_context":"optional context for AI generation","description":"Generate a Work Breakdown Structure for Project X"}}
- create_wbs_task: {{"action":"create_wbs_task","project_id":"...","name":"Task Name","description":"Task description","estimated_hours":16,"priority":"low|medium|high|critical (default: medium)","phase_name":"Phase name","assigned_to":"resource_id (optional)","description":"Create task 'Backend API' in Project X"}}
- update_wbs_task: {{"action":"update_wbs_task","task_id":"...","status":"todo|in_progress|done|on_hold|blocked","priority":"low|medium|high|critical","estimated_hours":20,"description":"Update task status or details"}}
- delete_wbs_task [destructive — requires `confirm_token`]: {{"action":"delete_wbs_task","task_id":"...","description":"Delete task and all its subtasks"}}
- assign_wbs_task: {{"action":"assign_wbs_task","task_id":"...","resource_id":"...","description":"Assign task to team member"}}

When user asks to "plan the project", "break down tasks", "create a WBS", or "decompose the project", use generate_wbs.

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

═══════════════════════════════════════════════════════════════════════
EXTENDED ADMIN ACTIONS — full admin parity (auto-registered)
═══════════════════════════════════════════════════════════════════════
{extended_actions_prompt}

DESTRUCTIVE ACTIONS (marked [destructive] above):
  • For regular admins: the FIRST emission returns a confirmation token. The system replies with "🔐 reply with `confirm <token>`". The user then types "confirm <token>" and you re-emit the SAME action with the additional field `"confirm_token": "<token>"`.
  • For super-admins: destructive actions execute immediately without needing a token.
  • Tokens expire in 10 minutes.

SUPER-ADMIN ACTIONS (marked [super-admin only]):
  • Only super-admin users can execute these. If a regular admin tries, the system responds with "🔒 super-admin required" — explain that to the user and suggest asking a super-admin.

Always explain what the action will do BEFORE the action block. The user will see a confirm button.

EXECUTION BEHAVIOUR (CRITICAL — read carefully):
⚠️ For EVERY action request, you MUST output BOTH in the SAME response:
  (1) A short, natural past-tense confirmation line (conversational, e.g. "Done — bumped Alice to 75% on ASKDD through end of July.")
  (2) A ```action``` JSON block on its own line(s)

Without the JSON block, NOTHING HAPPENS in the database. The past-tense narrative ALONE is a HALLUCINATION that misleads the user. Never do this. No narrative should claim "I added/created/removed/updated" (or softer phrasings like "is now logged/recorded/in place") unless the ```action``` block is also present in the same message.

CORRECT example:
"Added a Medium impact / Medium probability risk 'Database scaling' to ASKDD Chatbot.
```action
{{"action":"add_risk","project_id":"698c7799eea263b28c2715b3","description":"Database scaling","impact":"Medium","probability":"Medium"}}
```"

WRONG examples (NEVER do these):
• "A new risk was added to the project with the following details: ..."  ← missing action block = hallucination
• "I will add the risk..."  ← future tense + no action block
• "Shall I add this risk?"  ← asking permission

SYSTEM CONTRACT:
- The ```action``` block is AUTOMATICALLY executed the moment you emit it. You never need confirmation.
- The system appends "✅ **Done.** {{result message}}" after your narrative to show success.
- If an action fails, the system appends "⚠️ **Action failed:** {{reason}}" — so omitting the block means failure, not success.
- If the user says "yes" / "go ahead" after an already-executed action, say "Already done — confirmed" WITHOUT re-emitting the action.

PROJECT IDs:
{project_id_list}

RESOURCE IDs:
{resource_id_list}
"""

    readonly_section = f"""READ-ONLY MODE (CRITICAL):
The current user ({user_email}, role: {current_user.get('role')}) does NOT have admin rights.
- You MUST NOT emit any ```action``` JSON blocks. Actions are disabled for this account and will be rejected by the system.
- If they ask you to change, create, or delete anything, explain it warmly and conversationally: changes need an admin — offer to draft the exact details they can pass along ("I can't make that change from your account, but here's exactly what to ask an admin for: ...").
- The data you can see is already scoped to the projects this user is allowed to view. Never speculate about other projects, budgets, team members, or company-wide figures — if it's not in your data, it's not theirs to see.
"""

    led_project_names = [p.get("name") for p in projects if str(p["_id"]) in led_pids]
    lead_section = f"""PROJECT LEAD MODE (CRITICAL):
The current user ({user_email}, role: {current_user.get('role')}) is not an admin, but they are the PROJECT LEAD for: {', '.join(led_project_names)}.
For the project(s) they lead ONLY, you can execute a limited action set. Same contract as always: in the SAME response give a short, natural past-tense confirmation line AND a ```action``` JSON block — the system executes it automatically and appends the result. Only ONE action block per response. NEVER say "I can't" for these actions on their led projects.

Allowed actions (for led projects only):
- update_project — patch fields: {{"action": "update_project", "project_id": "<id>", "name": "...", "budgeted_hours": 600, "status": "Active", "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "description": "..."}} (include only fields to change)
- manage_phases — ADD or UPDATE phases without touching others (default merge mode). Only pass the phase(s) you want to change; existing phases are preserved. Use `"mode": "replace"` only to fully overwrite: {{"action": "manage_phases", "project_id": "<id>", "phases": [{{"name": "Discovery", "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "budgeted_hours": 80}}], "mode": "merge"}}
- reschedule_project — shift all dates: {{"action": "reschedule_project", "project_id": "<id>", "shift_days": 14}}
- update_project_dates: {{"action": "update_project_dates", "project_id": "<id>", "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}}
- update_project_status: {{"action": "update_project_status", "project_id": "<id>", "status": "Active"}}
- add_risk: {{"action": "add_risk", "project_id": "<id>", "description": "...", "impact": "Medium", "probability": "High", "mitigation": "..."}}
- update_risk: {{"action": "update_risk", "risk_id": "<id>", "status": "Mitigated", "mitigation": "..."}}
- delete_risk (destructive — the system will ask them to confirm): {{"action": "delete_risk", "risk_id": "<id>"}}
- polish_all_risks: {{"action": "polish_all_risks", "project_id": "<id>"}}
- create_status_update — weekly check-in: {{"action": "create_status_update", "project_id": "<id>", "health": "Green", "schedule_status": "On Track", "accomplishments": "...", "blockers": "...", "next_steps": "..."}}
- sync_phase_to_wbs: {{"action": "sync_phase_to_wbs", "project_id": "<id>", "phase_id": "<phase_uuid>"}}

PROJECT IDs you may act on: {'; '.join(f'"{p.get("name")}" = {str(p["_id"])}' for p in projects if str(p["_id"]) in led_pids)}

For ANYTHING else (allocations, resources, timesheets of others, users, other projects), do NOT emit an action — explain conversationally that it needs an admin.
"""

    system_prompt = system_prompt_header + (
        actions_section if is_admin else (lead_section if led_pids else readonly_section)
    ) + f"""
Guidelines:
- Answer the actual question first, conversationally; add supporting detail after.
- When discussing budgets, mention hours and percentages naturally in your sentences.
- Proactively flag risks, over-allocations, and overdue items when they're relevant to what the user asked — like a colleague who's paying attention.
- If asked about something not in the data, say so plainly and suggest where it might live.
- Remember the conversation context and refer back to earlier messages when relevant ("like the reschedule we did earlier").
- Only include ONE action block per response. If the user wants multiple actions, do the first and tell them what's next ("done — say the word and I'll do the same for Phase 2").
- For timesheet submission questions ("who submitted this week?", "who missed last week's timesheet?", "has X filled their timesheet?"): use the CURRENT WEEK TIMESHEET SUBMISSIONS and LAST WEEK TIMESHEET SUBMISSIONS sections below. They already list every resource with SUBMITTED / PARTIALLY SUBMITTED / DRAFT / MISSING status — do NOT say you lack this data.
- For project health questions, blockers, or "what's going wrong on project X": use the LATEST PROJECT STATUS UPDATES and ACTIVE RISKS & ISSUES sections. Reference specific blocker text verbatim when relevant.
- When the user asks you to "submit a status update" or "update status for project X", use the create_status_update action. Any text they provide as blockers will be automatically promoted to Issues in the risk register.
- To save an important decision or preference to memory so it's remembered in future sessions: use `save_memory` action.
- To run a proactive health check across all projects: use `run_health_check` action.
{specialist_triggers_doc}

{data_context}

{history_text}
"""

    # ── Inject agent memories ──
    try:
        # Load global memories + project-specific memories for the current context
        project_ids_in_context = [str(p["_id"]) for p in projects]
        mem_query = {
            "active": {"$ne": False},
            "$or": [{"scope": "global"}] + [{"project_id": pid} for pid in project_ids_in_context] if project_ids_in_context else [{"scope": "global"}]
        }
        memories = await ai_memory_collection.find(mem_query).sort("created_at", -1).to_list(length=50)
        if memories:
            mem_lines = ["\nAGENT MEMORY (key decisions & context — use these to inform your responses):"]
            global_mems = [m for m in memories if m.get("scope") == "global"]
            proj_mems = [m for m in memories if m.get("scope") == "project"]
            if global_mems:
                mem_lines.append("Global:")
                for m in global_mems[:10]:
                    cat = m.get("category", "note").title()
                    mem_lines.append(f"  [{cat}] {m.get('title')}: {m.get('content')}")
            if proj_mems:
                # Group by project
                by_proj: dict = {}
                for m in proj_mems:
                    pid = m.get("project_id", "?")
                    by_proj.setdefault(pid, []).append(m)
                for pid, mems in list(by_proj.items())[:5]:
                    p_name = project_map.get(pid, pid[:8])
                    mem_lines.append(f"Project '{p_name}':")
                    for m in mems[:5]:
                        cat = m.get("category", "note").title()
                        mem_lines.append(f"  [{cat}] {m.get('title')}: {m.get('content')}")
            system_prompt += "\n" + "\n".join(mem_lines) + "\n"
    except Exception as _me:
        pass  # Never fail the chat because memory injection failed

    # Inject custom AI instructions
    custom_ai_instructions = await get_instructions_for_prompt(category="chat")
    system_prompt += custom_ai_instructions

    # ── Specialist routing — prepend focused prompt if @mention detected ──
    specialist_key = detect_specialist(req.message)
    if specialist_key:
        system_prompt = get_specialist_header(specialist_key) + system_prompt

    user_message = req.message

    try:
        ai_config = await get_ai_config()
        ai_response_text = None

        if ai_config["api_key"]:
            if ai_config["provider"] == "openai":
                response = await call_openai_api(ai_config["api_key"], system_prompt, user_message)
                if response.status_code == 200:
                    data = response.json()
                    ai_response_text = data["choices"][0]["message"]["content"].strip()
            elif ai_config["provider"] == "gemini":
                response = await call_gemini_api(ai_config["api_key"], system_prompt, user_message)
                if response.status_code == 200:
                    data = response.json()
                    ai_response_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            elif ai_config["provider"] == "emergent":
                # Use emergentintegrations library for Emergent LLM key
                try:
                    import uuid as _uuid
                    from emergentintegrations.llm.chat import LlmChat, UserMessage as EmUserMessage
                    chat = LlmChat(
                        api_key=ai_config["api_key"],
                        session_id=f"chat-{_uuid.uuid4()}",
                        system_message=system_prompt
                    ).with_model("openai", "gpt-4o")
                    resp = await chat.send_message(EmUserMessage(text=user_message))
                    ai_response_text = resp if isinstance(resp, str) else str(resp)
                except Exception as e:
                    print(f"[AI Chat] Emergent LLM error: {e}")

        # Fallback to Emergent LLM if primary failed
        if not ai_response_text and EMERGENT_LLM_KEY:
            try:
                import uuid as _uuid
                from emergentintegrations.llm.chat import LlmChat, UserMessage as EmUserMessage
                chat = LlmChat(
                    api_key=EMERGENT_LLM_KEY,
                    session_id=f"chat-fallback-{_uuid.uuid4()}",
                    system_message=system_prompt
                ).with_model("openai", "gpt-4o")
                resp = await chat.send_message(EmUserMessage(text=user_message))
                ai_response_text = resp if isinstance(resp, str) else str(resp)
            except Exception as e:
                print(f"[AI Chat] Emergent fallback error: {e}")

        if not ai_response_text:
            ai_response_text = "I'm unable to process your request right now. Please check the AI configuration in Settings."

        # ---------- AUTO-EXECUTE SAFE ACTIONS ----------
        # Parse any action block in the response. If it's a SAFE action type,
        # execute it immediately and append a "✓ Done" confirmation so the user
        # doesn't have to click a confirm button.
        auto_action_executed = None
        undo_spec = None
        detected_plan = None  # action_plan blocks are held for user confirmation

        if not can_act:
            # Defense in depth: strip any action block a non-admin response may contain
            _stripped = re.sub(r"```(?:action|json)\s*\{[\s\S]*?\}\s*```", "", ai_response_text)
            if _stripped != ai_response_text:
                ai_response_text = _stripped.rstrip() + "\n\n🔒 Making changes needs an admin account — happy to draft the details for you to pass along."
        try:
            action_match = None
            raw_json = None
            if can_act:
                # Match both ```action and ```json code blocks (LLMs sometimes use either)
                action_match = re.search(r"```(?:action|json)\s*(\{[\s\S]*?\})\s*```", ai_response_text)
            
            if action_match:
                raw_json = action_match.group(1)
                print(f"[AI Chat] Found fenced action block")
            elif can_act:
                # Gemini often returns bare JSON without fences - try to extract it
                # Look for a JSON object containing "action" key
                bare_match = re.search(r'(\{[^{}]*"action"\s*:\s*"[^"]+[^{}]*\})', ai_response_text, re.DOTALL)
                if bare_match:
                    raw_json = bare_match.group(1)
                    action_match = bare_match  # Use for position tracking
                    print(f"[AI Chat] Found bare JSON action block")
            
            if raw_json:
                print(f"[AI Chat] Parsing JSON...")
                action_obj = json.loads(raw_json)
                a_type = action_obj.get("action")
                print(f"[AI Chat] Action type: {a_type}")

                # ── Multi-step plan: hold for user confirmation, don't auto-execute ──
                if a_type == "action_plan":
                    detected_plan = action_obj
                    step_count = len(action_obj.get("steps", []))
                    ai_response_text = (
                        ai_response_text[: action_match.start()].rstrip()
                        + f"\n\n📋 **{step_count}-step action plan ready** — review the steps below and click **Execute Plan** to proceed."
                        + ai_response_text[action_match.end():]
                    )
                else:
                    # Combine legacy + registry actions
                    all_auto = set(AUTO_EXECUTE_ACTIONS) | set(REGISTERED_ACTIONS.keys())
                    if a_type in all_auto:
                        # Snapshot pre-state for undo (what will be changed) — only meaningful for legacy actions
                        pre_state = await capture_pre_state(action_obj)
                        print(f"[AI Chat] Executing action: {a_type}")
                        # Use new dispatcher (handles registry + falls back to legacy)
                        result = await dispatch_action(action_obj, current_user)
                        print(f"[AI Chat] Action result: {result}")
                        # Build the undo spec from pre_state + post-result
                        undo_spec = build_undo_spec(a_type, action_obj, pre_state, result)
                        auto_action_executed = {"action": a_type, "result": result}
                        # Strip the action block; append a completion line.
                        ok = result.get("success", False)
                        needs_confirm = result.get("needs_confirmation", False)
                        msg = result.get("message", "")
                        if needs_confirm:
                            completion_line = f"\n\n🔐 {msg}"
                        elif ok:
                            completion_line = f"\n\n✅ Done — {msg}"
                        else:
                            completion_line = f"\n\n⚠️ That didn't go through: {msg}"
                        ai_response_text = (
                            ai_response_text[: action_match.start()].rstrip()
                            + completion_line
                            + ai_response_text[action_match.end():]
                        )
                    else:
                        print(f"[AI Chat] Action type '{a_type}' not in AUTO_EXECUTE_ACTIONS: {AUTO_EXECUTE_ACTIONS}")
        except json.JSONDecodeError as je:
            print(f"[AI Chat] JSON parse error: {je}")
        except Exception as _ae:
            print(f"[AI Chat] Auto-execute error: {type(_ae).__name__}: {_ae}")

        # ---------- HALLUCINATION GUARD ----------
        # If the AI wrote a past-tense claim ("I added / created / removed / updated ...")
        # but no action block was emitted, append a warning so the user is not misled.
        if auto_action_executed is None and detected_plan is None:
            halluc_patterns = re.search(
                r"\b(I(?:'ve| have)?\s+(?:added|created|removed|updated|scheduled|assigned|submitted|deleted|modified|set|changed|logged|recorded|noted)|(?:was|is now|has been|have been|are now)\s+(?:added|created|removed|updated|submitted|scheduled|logged|recorded|saved|noted|in place))\b",
                ai_response_text,
                re.IGNORECASE,
            )
            if halluc_patterns:
                ai_response_text = (
                    ai_response_text.rstrip()
                    + "\n\n⚠️ **Note:** Nothing was actually saved. Please rephrase your request with specific details (project name, resource name, dates, etc.) so I can execute the action."
                )

        # Save messages to session (attach plan data to assistant message if present)
        new_messages = session.get("messages", [])
        new_messages.append({"role": "user", "content": user_message, "timestamp": datetime.now(timezone.utc).isoformat()})
        assistant_msg: dict = {"role": "assistant", "content": ai_response_text, "timestamp": datetime.now(timezone.utc).isoformat()}
        if detected_plan:
            assistant_msg["plan"] = detected_plan  # Store plan in session history
        new_messages.append(assistant_msg)

        # Keep last 50 messages
        if len(new_messages) > 50:
            new_messages = new_messages[-50:]

        await chat_sessions_collection.update_one(
            {"_id": session["_id"]},
            {"$set": {
                "messages": new_messages,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "title": user_message[:60],
                "last_undo": undo_spec,  # None if no action, else reversal spec for the most recent action
            }}
        )

        return {
            "session_id": str(session["_id"]),
            "response": ai_response_text,
            "message_count": len(new_messages),
            "auto_executed": auto_action_executed,
            "can_undo": bool(undo_spec),
            "undo_label": (undo_spec or {}).get("label"),
            "has_plan": detected_plan is not None,
            "plan": detected_plan,
            "specialist_mode": specialist_key if specialist_key else None,
        }

    except Exception as e:
        print(f"AI Chat error: {e}")
        return {
            "session_id": str(session["_id"]),
            "response": f"Sorry, I encountered an error: {str(e)[:200]}",
            "message_count": len(session.get("messages", [])),
        }



@router.post("/api/ai/chat/execute-plan")
async def execute_action_plan(
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    """Execute a multi-step action plan sequentially.
    Each step goes through the full dispatch_action flow (permission checks, confirmation tokens, etc.)
    Returns per-step results.
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

    for i, step in enumerate(steps):
        try:
            result = await dispatch_action(step, current_user)
            step_result = {
                "step": i + 1,
                "action": step.get("action"),
                "description": step.get("description", step.get("action")),
                "success": result.get("success", False),
                "message": result.get("message", ""),
                "needs_confirmation": result.get("needs_confirmation", False),
            }
            results.append(step_result)
            if not result.get("success") and stop_on_error:
                break
        except Exception as e:
            results.append({
                "step": i + 1,
                "action": step.get("action"),
                "success": False,
                "message": str(e)[:200],
            })
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


@router.post("/api/ai/health-monitor/run")
async def run_health_monitor_endpoint(
    current_user: dict = Depends(require_admin),
):
    """Run a proactive portfolio health analysis (admin only)."""
    from services.health_monitor import run_health_monitor
    report = await run_health_monitor(triggered_by=current_user.get("email", "admin"), save_report=True)
    return report


@router.get("/api/ai/health-monitor/report")
async def get_latest_health_report(
    current_user: dict = Depends(require_admin),
):
    """Get the most recently saved health report."""
    from services.health_monitor import get_latest_report
    report = await get_latest_report()
    if not report:
        return {"message": "No health report yet. Run a health check first.", "findings": []}
    return report


@router.post("/api/ai/chat/execute-action")
async def execute_chat_action(action: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Execute an action proposed by the AI chat agent. Routes through the
    registry (with permission + confirmation flow + audit logging) and falls
    back to the legacy executor for old action types."""
    return await dispatch_action(action, current_user)


# NOTE: AUTO_EXECUTE_ACTIONS, execute_ai_action, capture_pre_state, build_undo_spec, apply_undo
# are all imported from services.ai_actions (line 25-27). Do not duplicate them here.


# ==================== UNDO ENDPOINT ====================

@router.post("/api/ai/chat/undo")
async def undo_last_action(
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    """Undo the last auto-executed action in a chat session."""
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    session = await chat_sessions_collection.find_one({"_id": ObjectId(session_id), "user_email": current_user["email"]})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    spec = session.get("last_undo")
    if not spec:
        return {"success": False, "message": "Nothing to undo"}

    result = await apply_undo(spec)

    # Clear the undo slot regardless of outcome (single-level undo)
    await chat_sessions_collection.update_one(
        {"_id": session["_id"]},
        {"$unset": {"last_undo": ""}},
    )

    # Append a system message so the chat history reflects the undo
    if result.get("success"):
        sys_note = f"↩️ **Undo applied.** {result.get('message','')}"
        messages = session.get("messages", [])
        messages.append({"role": "assistant", "content": sys_note, "timestamp": datetime.now(timezone.utc).isoformat()})
        await chat_sessions_collection.update_one(
            {"_id": session["_id"]},
            {"$set": {"messages": messages, "updated_at": datetime.now(timezone.utc).isoformat()}},
        )

    return result


@router.get("/api/ai/chat/sessions")
async def get_chat_sessions(current_user: dict = Depends(get_current_user)):
    """Get user's chat sessions (most recent first)."""
    cursor = chat_sessions_collection.find(
        {"user_email": current_user["email"]},
        {"messages": 0}  # Exclude message content for list
    ).sort("updated_at", -1).limit(20)
    sessions = await cursor.to_list(length=20)
    return serialize_doc(sessions)


@router.get("/api/ai/chat/sessions/{session_id}")
async def get_chat_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific chat session with full message history."""
    session = await chat_sessions_collection.find_one({
        "_id": ObjectId(session_id), "user_email": current_user["email"]
    })
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return serialize_doc(session)


@router.delete("/api/ai/chat/sessions/{session_id}")
async def delete_chat_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a chat session."""
    result = await chat_sessions_collection.delete_one({
        "_id": ObjectId(session_id), "user_email": current_user["email"]
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deleted"}


# ==================== SECURE DATA EXPORT (ZIP) ====================
