from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime, date, timedelta, timezone
from bson import ObjectId
import json
import re
import uuid as uuid_module

from database import (
    projects_collection, timesheets_collection, allocations_collection,
    resources_collection, risks_collection, status_updates_collection,
    wbs_tasks_collection, EMERGENT_LLM_KEY,
)
from auth.dependencies import get_current_user, require_admin
from utils import serialize_doc
from services.ai_providers import call_emergent_fallback

router = APIRouter()


@router.get("/api/reports/planned-vs-actual/project/{project_id}")
async def get_project_time_report(project_id: str, current_user: dict = Depends(get_current_user)):
    """
    Get comprehensive planned vs actual time report for a project.
    Includes project-level summary, phase breakdown, and resource breakdown.
    """
    # Get the project
    project = await projects_collection.find_one({"_id": ObjectId(project_id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get all allocations for this project
    cursor = allocations_collection.find({"project_id": project_id})
    allocations = await cursor.to_list(length=1000)
    
    # Get all timesheets for this project
    cursor = timesheets_collection.find({"project_id": project_id})
    timesheets = await cursor.to_list(length=10000)
    
    # Calculate project-level totals
    total_planned_hours = 0.0
    total_actual_hours = 0.0
    
    for timesheet in timesheets:
        total_planned_hours += timesheet.get("planned_hours", 0)
        total_actual_hours += timesheet.get("actual_hours", 0)
    
    variance_hours = total_actual_hours - total_planned_hours
    variance_percentage = (variance_hours / total_planned_hours * 100) if total_planned_hours > 0 else 0
    completion_rate = (total_actual_hours / total_planned_hours * 100) if total_planned_hours > 0 else 0
    
    # Calculate Project Budget Variance (NEW)
    project_budget = project.get("budgeted_hours")
    budget_variance = (total_actual_hours - float(project_budget)) if project_budget else None
    budget_used_percentage = (total_actual_hours / float(project_budget) * 100) if project_budget and float(project_budget) > 0 else 0

    # Phase breakdown
    phases = project.get("phases", [])
    phase_breakdown = []
    
    for phase in phases:
        phase_id = phase.get("id")
        phase_timesheets = [t for t in timesheets if t.get("phase_id") == phase_id]
        
        phase_planned = sum(t.get("planned_hours", 0) for t in phase_timesheets)
        phase_actual = sum(t.get("actual_hours", 0) for t in phase_timesheets)
        phase_variance = phase_actual - phase_planned
        
        # Budget for this phase
        phase_budget = phase.get("budgeted_hours")
        phase_budget_val = float(phase_budget) if phase_budget else 0
        phase_budget_variance = (phase_actual - phase_budget_val) if phase_budget else None
        phase_budget_used_pct = (phase_actual / phase_budget_val * 100) if phase_budget_val > 0 else 0
        
        phase_breakdown.append({
            "phase_id": phase_id,
            "phase_name": phase.get("name", "Unknown"),
            "planned_hours": round(phase_planned, 2),
            "actual_hours": round(phase_actual, 2),
            "variance_hours": round(phase_variance, 2),
            "completion_rate": round((phase_actual / phase_planned * 100) if phase_planned > 0 else 0, 2),
            "status": phase.get("status", "Not Started"),
            # New fields
            "budgeted_hours": phase_budget,
            "budget_variance": round(phase_budget_variance, 2) if phase_budget_variance is not None else None,
            "budget_used_percentage": round(phase_budget_used_pct, 2)
        })
    
    # Resource breakdown
    resource_breakdown = {}
    
    for timesheet in timesheets:
        resource_id = timesheet.get("resource_id")
        
        if resource_id not in resource_breakdown:
            resource_breakdown[resource_id] = {
                "resource_id": resource_id,
                "planned_hours": 0.0,
                "actual_hours": 0.0
            }
        
        resource_breakdown[resource_id]["planned_hours"] += timesheet.get("planned_hours", 0)
        resource_breakdown[resource_id]["actual_hours"] += timesheet.get("actual_hours", 0)
    
    # Get resource names
    resources_cursor = resources_collection.find()
    all_resources = await resources_cursor.to_list(length=1000)
    resource_map = {str(r["_id"]): r.get("name", "Unknown") for r in all_resources}
    
    resource_breakdown_list = []
    for resource_id, data in resource_breakdown.items():
        variance = data["actual_hours"] - data["planned_hours"]
        utilization_rate = (data["actual_hours"] / data["planned_hours"] * 100) if data["planned_hours"] > 0 else 0
        
        resource_breakdown_list.append({
            "resource_id": resource_id,
            "resource_name": resource_map.get(resource_id, "Unknown"),
            "planned_hours": round(data["planned_hours"], 2),
            "actual_hours": round(data["actual_hours"], 2),
            "variance_hours": round(variance, 2),
            "utilization_rate": round(utilization_rate, 2)
        })
    
    # Sort by actual hours (descending)
    resource_breakdown_list.sort(key=lambda x: x["actual_hours"], reverse=True)
    
    return {
        "project": {
            "id": project_id,
            "name": project.get("name", "Unknown"),
            "planned_hours": round(total_planned_hours, 2),
            "actual_hours": round(total_actual_hours, 2),
            "variance_hours": round(variance_hours, 2),
            "variance_percentage": round(variance_percentage, 2),
            "completion_rate": round(completion_rate, 2),
            # New fields
            "budgeted_hours": project_budget,
            "budget_variance": round(budget_variance, 2) if budget_variance is not None else None,
            "budget_used_percentage": round(budget_used_percentage, 2)
        },
        "phases": phase_breakdown,
        "resources": resource_breakdown_list
    }


@router.get("/api/reports/time-tracking/summary")
async def get_time_tracking_summary(current_user: dict = Depends(get_current_user)):
    """
    Get dashboard-level time tracking summary.
    Includes team utilization, pending timesheets, projects at risk.
    """
    # Get current week start
    today = datetime.now()
    day_of_week = today.weekday()
    week_start = today - timedelta(days=day_of_week)
    week_start_str = week_start.strftime("%Y-%m-%d")
    
    # Count pending timesheet submissions (Draft status)
    pending_count = await timesheets_collection.count_documents({
        "status": "Draft",
        "week_start_date": datetime.strptime(week_start_str, "%Y-%m-%d")
    })
    
    # Get this week's timesheets for utilization calculation
    cursor = timesheets_collection.find({
        "week_start_date": datetime.strptime(week_start_str, "%Y-%m-%d")
    })
    this_week_timesheets = await cursor.to_list(length=10000)
    
    total_actual_hours = sum(t.get("actual_hours", 0) for t in this_week_timesheets)
    total_planned_hours = sum(t.get("planned_hours", 0) for t in this_week_timesheets)
    
    team_utilization = (total_actual_hours / total_planned_hours * 100) if total_planned_hours > 0 else 0
    
    # Get projects with high variance (>20%)
    cursor = projects_collection.find({"status": "Active"})
    active_projects = await cursor.to_list(length=1000)
    
    projects_at_risk = []
    
    for project in active_projects:
        project_id = str(project["_id"])
        
        # Get timesheets for this project
        cursor = timesheets_collection.find({"project_id": project_id})
        project_timesheets = await cursor.to_list(length=10000)
        
        if not project_timesheets:
            continue
        
        planned = sum(t.get("planned_hours", 0) for t in project_timesheets)
        actual = sum(t.get("actual_hours", 0) for t in project_timesheets)
        variance_pct = ((actual - planned) / planned * 100) if planned > 0 else 0
        
        if abs(variance_pct) > 20:  # More than 20% variance
            projects_at_risk.append({
                "project_id": project_id,
                "project_name": project.get("name", "Unknown"),
                "variance_percentage": round(variance_pct, 2)
            })
    
    # Get resource with highest utilization
    resource_utilization = {}
    
    for timesheet in this_week_timesheets:
        resource_id = timesheet.get("resource_id")
        
        if resource_id not in resource_utilization:
            resource_utilization[resource_id] = {
                "planned": 0.0,
                "actual": 0.0
            }
        
        resource_utilization[resource_id]["planned"] += timesheet.get("planned_hours", 0)
        resource_utilization[resource_id]["actual"] += timesheet.get("actual_hours", 0)
    
    top_performer = None
    max_utilization = 0
    
    if resource_utilization:
        resources_cursor = resources_collection.find()
        all_resources = await resources_cursor.to_list(length=1000)
        resource_map = {str(r["_id"]): r.get("name", "Unknown") for r in all_resources}
        
        for resource_id, data in resource_utilization.items():
            utilization = (data["actual"] / data["planned"] * 100) if data["planned"] > 0 else 0
            if utilization > max_utilization:
                max_utilization = utilization
                top_performer = {
                    "resource_name": resource_map.get(resource_id, "Unknown"),
                    "utilization_rate": round(utilization, 2)
                }
    
    return {
        "week_start": week_start_str,
        "team_utilization": round(team_utilization, 2),
        "pending_timesheet_count": pending_count,
        "projects_at_risk_count": len(projects_at_risk),
        "projects_at_risk": projects_at_risk[:5],  # Top 5
        "top_performer": top_performer
    }


@router.get("/api/reports/planned-vs-actual/overview")
async def get_planned_vs_actual_overview(current_user: dict = Depends(get_current_user)):
    """
    Cross-project planned vs actual overview. Aggregates budget health across all active projects.
    Reuses per-project calculation logic.
    """
    cursor = projects_collection.find({"status": {"$in": ["Active", "Pipeline"]}})
    projects = await cursor.to_list(length=500)

    all_timesheets = await timesheets_collection.find().to_list(length=50000)
    ts_by_project = {}
    for t in all_timesheets:
        pid = t.get("project_id", "")
        ts_by_project.setdefault(pid, []).append(t)

    total_budget = 0.0
    total_actual = 0.0
    total_planned = 0.0
    project_rows = []
    at_risk = []

    for project in projects:
        pid = str(project["_id"])
        budget = float(project.get("budgeted_hours") or 0)
        ts_list = ts_by_project.get(pid, [])
        actual = sum(t.get("actual_hours", 0) for t in ts_list)
        planned = sum(t.get("planned_hours", 0) for t in ts_list)
        variance = actual - budget if budget > 0 else 0
        pct_used = round(actual / budget * 100, 1) if budget > 0 else 0

        # Health assessment
        if budget > 0 and pct_used > 100:
            health = "over_budget"
        elif budget > 0 and pct_used > 80:
            health = "at_risk"
        elif budget > 0:
            health = "on_track"
        else:
            health = "no_budget"

        total_budget += budget
        total_actual += actual
        total_planned += planned

        row = {
            "project_id": pid,
            "project_name": project.get("name", "Unknown"),
            "client_name": project.get("client_name", ""),
            "status": project.get("status", ""),
            "budgeted_hours": budget,
            "planned_hours": round(planned, 1),
            "actual_hours": round(actual, 1),
            "variance_hours": round(variance, 1),
            "budget_used_pct": pct_used,
            "health": health,
            "phase_count": len(project.get("phases", [])),
            "start_date": str(project.get("start_date", "")),
            "end_date": str(project.get("end_date", "")),
        }
        project_rows.append(row)

        if health in ("over_budget", "at_risk"):
            at_risk.append(row)

    project_rows.sort(key=lambda x: x["budget_used_pct"], reverse=True)
    at_risk.sort(key=lambda x: x["budget_used_pct"], reverse=True)

    overall_variance = total_actual - total_budget if total_budget > 0 else 0
    overall_pct = round(total_actual / total_budget * 100, 1) if total_budget > 0 else 0

    return {
        "summary": {
            "total_projects": len(projects),
            "total_budget": round(total_budget, 1),
            "total_actual": round(total_actual, 1),
            "total_planned": round(total_planned, 1),
            "overall_variance": round(overall_variance, 1),
            "overall_pct_used": overall_pct,
            "projects_on_track": sum(1 for r in project_rows if r["health"] == "on_track"),
            "projects_at_risk": sum(1 for r in project_rows if r["health"] == "at_risk"),
            "projects_over_budget": sum(1 for r in project_rows if r["health"] == "over_budget"),
            "projects_no_budget": sum(1 for r in project_rows if r["health"] == "no_budget"),
        },
        "projects": project_rows,
        "at_risk_projects": at_risk,
    }


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




@router.get("/api/reports/timesheets/range")
async def get_timesheet_range_report(
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format"),
    group_by: str = Query(..., description="Group by dimension: resource, project, client, or week"),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    client_name: Optional[str] = Query(None, description="Filter by client name (exact match)"),
    status: Optional[str] = Query(None, description="Filter by status: Draft, Submitted, or Approved"),
    current_user: dict = Depends(require_admin)
):
    """
    Get timesheet range report with flexible grouping and filtering.
    Admin and super_admin only.
    Returns summary stats, grouped data, and detailed entries (max 500).
    """
    
    # Validate group_by parameter
    valid_group_by = ["resource", "project", "client", "week"]
    if group_by not in valid_group_by:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid group_by value. Must be one of: {', '.join(valid_group_by)}"
        )
    
    # Parse and validate dates
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use YYYY-MM-DD"
        )
    
    if start_dt > end_dt:
        raise HTTPException(
            status_code=400,
            detail="start_date must be before or equal to end_date"
        )
    
    # Build MongoDB query
    query = {
        "week_start_date": {"$gte": start_dt},
        "week_end_date": {"$lte": end_dt}
    }
    
    # Apply optional filters
    if resource_id:
        query["resource_id"] = resource_id
    if project_id:
        query["project_id"] = project_id
    if status:
        query["status"] = status
    
    # Fetch matching timesheets
    cursor = timesheets_collection.find(query)
    timesheets = await cursor.to_list(length=10000)
    
    # If client_name filter is provided, we need to filter after enrichment
    # So we'll store it and apply later
    client_filter_needed = client_name is not None
    
    # Bulk-fetch resources and projects for enrichment
    resource_ids = list(set(t.get("resource_id") for t in timesheets if t.get("resource_id")))
    project_ids = list(set(t.get("project_id") for t in timesheets if t.get("project_id")))
    
    # Fetch resources
    resources_map = {}
    if resource_ids:
        resources_cursor = resources_collection.find({"_id": {"$in": [ObjectId(rid) for rid in resource_ids if rid]}})
        resources = await resources_cursor.to_list(length=1000)
        resources_map = {
            str(r["_id"]): {
                "name": r.get("name", "Unknown"),
                "role": r.get("role", "Unknown")
            }
            for r in resources
        }
    
    # Fetch projects
    projects_map = {}
    if project_ids:
        projects_cursor = projects_collection.find({"_id": {"$in": [ObjectId(pid) for pid in project_ids if pid]}})
        projects = await projects_cursor.to_list(length=1000)
        projects_map = {
            str(p["_id"]): {
                "name": p.get("name", "Unknown"),
                "client_name": p.get("client_name", "Unknown")
            }
            for p in projects
        }
    
    # Enrich timesheets with related data
    enriched_entries = []
    for ts in timesheets:
        resource_id_val = ts.get("resource_id")
        project_id_val = ts.get("project_id")
        
        resource_info = resources_map.get(resource_id_val, {"name": "Unknown", "role": "Unknown"})
        project_info = projects_map.get(project_id_val, {"name": "Unknown", "client_name": "Unknown"})
        
        # Apply client_name filter if needed
        if client_filter_needed and project_info["client_name"] != client_name:
            continue
        
        planned = ts.get("planned_hours", 0)
        actual = ts.get("actual_hours", 0)
        variance = actual - planned
        
        entry = {
            "id": str(ts.get("_id", "")),
            "resource_id": resource_id_val,
            "resource_name": resource_info["name"],
            "resource_role": resource_info["role"],
            "project_id": project_id_val,
            "project_name": project_info["name"],
            "client_name": project_info["client_name"],
            "phase_id": ts.get("phase_id"),
            "week_start_date": ts.get("week_start_date").strftime("%Y-%m-%d") if ts.get("week_start_date") else None,
            "week_end_date": ts.get("week_end_date").strftime("%Y-%m-%d") if ts.get("week_end_date") else None,
            "planned_hours": round(planned, 2),
            "actual_hours": round(actual, 2),
            "variance_hours": round(variance, 2),
            "status": ts.get("status", "Unknown"),
            "task_name": ts.get("task_name", "")
        }
        enriched_entries.append(entry)
    
    # Calculate summary stats
    total_entries = len(enriched_entries)
    total_planned = sum(e["planned_hours"] for e in enriched_entries)
    total_actual = sum(e["actual_hours"] for e in enriched_entries)
    total_variance = total_actual - total_planned
    unique_resources = len(set(e["resource_id"] for e in enriched_entries if e["resource_id"]))
    unique_projects = len(set(e["project_id"] for e in enriched_entries if e["project_id"]))
    
    summary = {
        "total_entries": total_entries,
        "total_planned_hours": round(total_planned, 2),
        "total_actual_hours": round(total_actual, 2),
        "total_variance_hours": round(total_variance, 2),
        "unique_resources": unique_resources,
        "unique_projects": unique_projects
    }
    
    # Group by requested dimension
    groups_dict = {}
    
    for entry in enriched_entries:
        if group_by == "resource":
            key = entry["resource_id"]
            label = entry["resource_name"]
            subtitle = entry["resource_role"]
        elif group_by == "project":
            key = entry["project_id"]
            label = entry["project_name"]
            subtitle = entry["client_name"]
        elif group_by == "client":
            key = entry["client_name"]
            label = entry["client_name"]
            subtitle = None
        elif group_by == "week":
            key = entry["week_start_date"]
            label = entry["week_start_date"]
            subtitle = None
        else:
            continue
        
        if key not in groups_dict:
            groups_dict[key] = {
                "key": label,
                "group_id": key,
                "label": label,
                "subtitle": subtitle,
                "planned_hours": 0.0,
                "actual_hours": 0.0,
                "variance_hours": 0.0,
                "entries_count": 0
            }
        
        groups_dict[key]["planned_hours"] += entry["planned_hours"]
        groups_dict[key]["actual_hours"] += entry["actual_hours"]
        groups_dict[key]["variance_hours"] += entry["variance_hours"]
        groups_dict[key]["entries_count"] += 1
    
    # Convert groups dict to list and round values
    groups = []
    for group_data in groups_dict.values():
        group_data["planned_hours"] = round(group_data["planned_hours"], 2)
        group_data["actual_hours"] = round(group_data["actual_hours"], 2)
        group_data["variance_hours"] = round(group_data["variance_hours"], 2)
        groups.append(group_data)
    
    # Sort groups by actual_hours descending
    groups.sort(key=lambda x: x["actual_hours"], reverse=True)
    
    # Limit entries to 500 (most recent first by week_start_date)
    enriched_entries.sort(
        key=lambda x: x["week_start_date"] if x["week_start_date"] else "",
        reverse=True
    )
    entries_limited = enriched_entries[:500]
    
    return {
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
            "group_by": group_by,
            "resource_id": resource_id,
            "project_id": project_id,
            "client_name": client_name,
            "status": status
        },
        "summary": summary,
        "groups": groups,
        "entries": entries_limited
    }


@router.get("/api/reports/resource-utilization")
async def get_resource_utilization(
    start_date: str = Query(..., description="Start date YYYY-MM-DD"),
    end_date: str = Query(..., description="End date YYYY-MM-DD"),
    current_user: dict = Depends(require_admin)
):
    """
    Resource Utilization Report: Allocated hours vs Actual hours per resource.
    
    Allocated hours are computed from the allocations collection,
    prorated to the requested date range using business days (Mon-Fri).
    Actual hours come from timesheet entries in the date range.
    """
    from utils import count_business_days
    
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    if start_dt > end_dt:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")
    
    # 1) Fetch all allocations that overlap with the date range
    allocs = await allocations_collection.find({
        "start_date": {"$lte": datetime.combine(end_dt, datetime.max.time())},
        "end_date": {"$gte": datetime.combine(start_dt, datetime.min.time())},
    }).to_list(length=5000)
    
    # 2) Fetch all timesheets in the date range
    timesheets = await timesheets_collection.find({
        "week_start_date": {"$lte": datetime.combine(end_dt, datetime.max.time())},
        "week_end_date": {"$gte": datetime.combine(start_dt, datetime.min.time())},
    }).to_list(length=10000)
    
    # 3) Bulk-fetch resource and project info
    all_resource_ids = set()
    all_project_ids = set()
    for a in allocs:
        if a.get("resource_id"): all_resource_ids.add(a["resource_id"])
        if a.get("project_id"): all_project_ids.add(a["project_id"])
    for t in timesheets:
        if t.get("resource_id"): all_resource_ids.add(t["resource_id"])
        if t.get("project_id"): all_project_ids.add(t["project_id"])
    
    resources_map = {}
    if all_resource_ids:
        res_cursor = resources_collection.find({"_id": {"$in": [ObjectId(rid) for rid in all_resource_ids]}})
        for r in await res_cursor.to_list(1000):
            resources_map[str(r["_id"])] = {"name": r.get("name", "Unknown"), "role": r.get("role", "")}
    
    projects_map = {}
    if all_project_ids:
        prj_cursor = projects_collection.find({"_id": {"$in": [ObjectId(pid) for pid in all_project_ids]}})
        for p in await prj_cursor.to_list(1000):
            projects_map[str(p["_id"])] = {"name": p.get("name", "Unknown"), "client_name": p.get("client_name", "")}
    
    # 4) Build allocated hours per resource per project
    #    Prorate each allocation to the overlap with the requested date range
    alloc_map = {}  # resource_id -> { project_id -> allocated_hours }
    for a in allocs:
        rid = a.get("resource_id")
        pid = a.get("project_id")
        if not rid or not pid:
            continue
        
        a_start = a.get("start_date")
        a_end = a.get("end_date")
        if isinstance(a_start, datetime): a_start = a_start.date()
        if isinstance(a_end, datetime): a_end = a_end.date()
        if not a_start or not a_end:
            continue
        
        # Calculate overlap
        overlap_start = max(a_start, start_dt)
        overlap_end = min(a_end, end_dt)
        if overlap_start > overlap_end:
            continue
        
        biz_days = count_business_days(overlap_start, overlap_end)
        pct = a.get("percentage", 0) / 100.0
        hours = biz_days * 8.0 * pct
        
        if rid not in alloc_map:
            alloc_map[rid] = {}
        alloc_map[rid][pid] = alloc_map[rid].get(pid, 0) + hours
    
    # 5) Build actual hours per resource per project from timesheets
    actual_map = {}  # resource_id -> { project_id -> actual_hours }
    for t in timesheets:
        rid = t.get("resource_id")
        pid = t.get("project_id")
        if not rid:
            continue
        actual_hrs = t.get("actual_hours", 0)
        if rid not in actual_map:
            actual_map[rid] = {}
        actual_map[rid][pid or "unassigned"] = actual_map[rid].get(pid or "unassigned", 0) + actual_hrs
    
    # 6) Merge into per-resource response
    all_rids = set(list(alloc_map.keys()) + list(actual_map.keys()))
    
    resource_rows = []
    for rid in all_rids:
        info = resources_map.get(rid, {"name": "Unknown", "role": ""})
        
        # Collect all project IDs for this resource
        project_ids_for_resource = set(
            list(alloc_map.get(rid, {}).keys()) + list(actual_map.get(rid, {}).keys())
        )
        
        total_allocated = 0.0
        total_actual = 0.0
        projects_breakdown = []
        
        for pid in project_ids_for_resource:
            alloc_hrs = alloc_map.get(rid, {}).get(pid, 0)
            actual_hrs = actual_map.get(rid, {}).get(pid, 0)
            variance = actual_hrs - alloc_hrs
            prj_info = projects_map.get(pid, {"name": "Unassigned", "client_name": ""})
            
            projects_breakdown.append({
                "project_id": pid,
                "project_name": prj_info["name"],
                "client_name": prj_info["client_name"],
                "allocated_hours": round(alloc_hrs, 1),
                "actual_hours": round(actual_hrs, 1),
                "variance": round(variance, 1),
            })
            total_allocated += alloc_hrs
            total_actual += actual_hrs
        
        # Sort projects by allocated hours desc
        projects_breakdown.sort(key=lambda x: x["allocated_hours"], reverse=True)
        
        utilization = round((total_actual / total_allocated * 100) if total_allocated > 0 else 0, 1)
        
        resource_rows.append({
            "resource_id": rid,
            "resource_name": info["name"],
            "resource_role": info["role"],
            "total_allocated_hours": round(total_allocated, 1),
            "total_actual_hours": round(total_actual, 1),
            "variance": round(total_actual - total_allocated, 1),
            "utilization_pct": utilization,
            "projects": projects_breakdown,
        })
    
    # Sort by allocated hours desc
    resource_rows.sort(key=lambda x: x["total_allocated_hours"], reverse=True)
    
    grand_allocated = sum(r["total_allocated_hours"] for r in resource_rows)
    grand_actual = sum(r["total_actual_hours"] for r in resource_rows)
    
    return {
        "start_date": start_date,
        "end_date": end_date,
        "summary": {
            "total_resources": len(resource_rows),
            "total_allocated_hours": round(grand_allocated, 1),
            "total_actual_hours": round(grand_actual, 1),
            "total_variance": round(grand_actual - grand_allocated, 1),
            "overall_utilization_pct": round((grand_actual / grand_allocated * 100) if grand_allocated > 0 else 0, 1),
        },
        "resources": resource_rows,
    }


# ============================================================
# Export Endpoints — Playwright-rendered HTML to PDF/PPT
# ============================================================
# These endpoints generate exports that are VISUALLY IDENTICAL to
# the on-screen React report at /projects/:id/report, using a
# headless Chromium browser to render the React UI and convert
# to PDF (or screenshot → PPT).
#
# The actual rendering is implemented in services/exports/.
import os
from fastapi import Request
from fastapi.responses import Response

from services.exports import (
    build_project_pdf,
    build_wbs_pdf,
    build_project_ppt,
    build_wbs_ppt,
)
from auth.dependencies import create_access_token


def _extract_or_mint_token(request: Request, current_user: dict) -> str:
    """Extract Bearer token from Authorization header. If absent, mint a fresh
    short-lived token for the current user (so Playwright can authenticate)."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token:
            return token
    # Fallback: mint a token using the same secret
    return create_access_token({"sub": current_user["email"]})


def _frontend_base_url() -> str:
    """Internal URL where the React app is served. In dev mode the React
    dev-server is on :3000; in production the nginx-served bundle is on :8080
    on the same container. Try env var first, then auto-detect."""
    explicit = os.environ.get("FRONTEND_INTERNAL_URL")
    if explicit:
        return explicit.rstrip("/")
    # Production single-container layout — nginx on :8080
    if os.environ.get("K_SERVICE") or os.environ.get("GAE_APPLICATION") or os.path.exists("/app/frontend/build"):
        return "http://localhost:8080"
    # Dev fallback
    return "http://localhost:3000"


def _safe_filename(project_name: str) -> str:
    """Sanitize a project name for use in a filename."""
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", project_name or "project")[:60]
    return name.strip("_") or "project"


async def _find_project(project_id: str):
    """Find a project by either its MongoDB ObjectId or its UUID 'id' field."""
    if ObjectId.is_valid(project_id):
        proj = await projects_collection.find_one({"_id": ObjectId(project_id)})
        if proj:
            return proj
    return await projects_collection.find_one({"id": project_id})


@router.get("/api/projects/{project_id}/export/pdf")
async def export_project_pdf(
    project_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Export the project report as a pixel-perfect PDF.

    Uses Playwright (headless Chromium) to render the same React UI shown at
    /projects/:id/report and save it as a single landscape A4 PDF.
    """
    project = await _find_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    token = _extract_or_mint_token(request, current_user)
    base = _frontend_base_url()

    try:
        pdf_bytes = await build_project_pdf(project_id, token, base)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

    fname = _safe_filename(project.get("name", "project")) + "-Report.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/api/projects/{project_id}/export/ppt")
async def export_project_ppt(
    project_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Export the project report as a PowerPoint (2 slides).

    Each slide embeds a high-resolution screenshot of a section of the
    on-screen report (Overview + Timeline), wrapped in a DD-branded slide
    header.
    """
    project = await _find_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    token = _extract_or_mint_token(request, current_user)
    base = _frontend_base_url()

    try:
        pptx_bytes = await build_project_ppt(project_id, token, base)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PPT generation failed: {e}")

    fname = _safe_filename(project.get("name", "project")) + "-Report.pptx"
    return Response(
        content=pptx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/api/projects/{project_id}/export/wbs/pdf")
async def export_project_wbs_pdf(
    project_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Export only the Work Breakdown Structure as a landscape A4 PDF."""
    project = await _find_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    token = _extract_or_mint_token(request, current_user)
    base = _frontend_base_url()

    try:
        pdf_bytes = await build_wbs_pdf(project_id, token, base)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"WBS PDF generation failed: {e}")

    fname = _safe_filename(project.get("name", "project")) + "-WBS.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/api/projects/{project_id}/export/wbs/ppt")
async def export_project_wbs_ppt(
    project_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Export only the Work Breakdown Structure as a PowerPoint slide."""
    project = await _find_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    token = _extract_or_mint_token(request, current_user)
    base = _frontend_base_url()

    try:
        pptx_bytes = await build_wbs_ppt(project_id, token, base)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"WBS PPT generation failed: {e}")

    fname = _safe_filename(project.get("name", "project")) + "-WBS.pptx"
    return Response(
        content=pptx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/api/portfolio")
async def get_portfolio_view(
    months: int = Query(default=3, ge=1, le=12, description="Timeline range in months (1, 3, 6, or 12)"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get portfolio-level view of all projects with timeline and hours analysis.
    Returns projects filtered by the specified timeline (1/3/6/12 months from today).
    Includes baseline vs actual hours tracking and pipeline vs active distinction.
    """
    from datetime import timezone
    
    # Calculate date range
    today = datetime.now(timezone.utc).date()
    end_date = today + timedelta(days=months * 30)  # Approximate month as 30 days
    
    # Get all projects (respecting user role permissions)
    query = {}
    user_role = current_user.get("role", "")
    
    if user_role == "client":
        # Clients only see their allowed projects
        allowed_ids = current_user.get("allowed_project_ids", [])
        query = {"_id": {"$in": [ObjectId(pid) for pid in allowed_ids]}}
    elif user_role in ["resource", "contractor"]:
        # Resources/contractors see projects they're allocated to
        resource_id = None
        # Find user's resource ID
        resource = await resources_collection.find_one({"user_id": current_user.get("id")})
        if resource:
            resource_id = str(resource["_id"])
            
            # Get allocated project IDs
            alloc_cursor = allocations_collection.find({"resource_id": resource_id})
            allocations = await alloc_cursor.to_list(length=1000)
            project_ids = list({ObjectId(a["project_id"]) for a in allocations})
            
            query = {"_id": {"$in": project_ids}} if project_ids else {"_id": None}
        else:
            query = {"_id": None}  # No access
    
    # Filter projects that overlap with the timeline
    query["$or"] = [
        # Project starts within timeline
        {"start_date": {"$gte": datetime.combine(today, datetime.min.time()), "$lte": datetime.combine(end_date, datetime.max.time())}},
        # Project ends within timeline
        {"end_date": {"$gte": datetime.combine(today, datetime.min.time()), "$lte": datetime.combine(end_date, datetime.max.time())}},
        # Project spans the entire timeline
        {
            "start_date": {"$lte": datetime.combine(today, datetime.min.time())},
            "end_date": {"$gte": datetime.combine(end_date, datetime.max.time())}
        }
    ]
    
    cursor = projects_collection.find(query)
    projects = await cursor.to_list(length=1000)
    
    # For each project, calculate baseline and actual hours
    portfolio_data = []
    
    for project in projects:
        project_id = str(project["_id"])
        
        # Calculate baseline hours (from allocations)
        # Baseline = sum of all allocation hours for the project
        alloc_cursor = allocations_collection.find({"project_id": project_id})
        allocations = await alloc_cursor.to_list(length=1000)
        
        baseline_hours = 0.0
        for alloc in allocations:
            # Calculate hours: percentage * 38 hours/week * number of weeks
            start = alloc.get("start_date")
            end = alloc.get("end_date")
            percentage = alloc.get("percentage", 0)
            
            if start and end:
                if isinstance(start, datetime):
                    start = start.date()
                if isinstance(end, datetime):
                    end = end.date()
                
                days = (end - start).days + 1
                # Use business days for baseline calculation
                from utils import count_business_days
                biz_days = count_business_days(start, end)
                weekly_hours = (percentage / 100.0) * 38.0  # 38 hours = 100%
                baseline_hours += weekly_hours * (biz_days / 5.0)  # 5 business days per week
        
        # Calculate actual hours (from timesheets)
        timesheet_cursor = timesheets_collection.find({"project_id": project_id})
        timesheets = await timesheet_cursor.to_list(length=10000)
        
        actual_hours = sum(ts.get("actual_hours", 0) for ts in timesheets)
        
        # Get project lead name
        lead_name = None
        if project.get("project_lead_id"):
            lead = await resources_collection.find_one({"_id": ObjectId(project["project_lead_id"])})
            lead_name = lead.get("name") if lead else None
        
        # Determine if pipeline or active
        status = project.get("status", "Active")
        is_pipeline = status.lower() == "pipeline"
        
        # Fetch WBS milestones for this project
        wbs_milestones = await wbs_tasks_collection.find({
            "project_id": project_id,
            "is_milestone": True
        }).to_list(length=100)
        
        milestones = [
            {
                "name": t.get("name", "Milestone"),
                "date": str(t.get("milestone_date") or t.get("start_date") or ""),
                "status": "Completed" if t.get("milestone_completed") else "Pending"
            }
            for t in wbs_milestones
        ]
        
        portfolio_data.append({
            "id": project_id,
            "name": project.get("name"),
            "client_name": project.get("client_name"),
            "status": status,
            "is_pipeline": is_pipeline,
            "start_date": project.get("start_date").isoformat() if project.get("start_date") else None,
            "end_date": project.get("end_date").isoformat() if project.get("end_date") else None,
            "health": project.get("health"),
            "schedule_status": project.get("schedule_status"),
            "actual_progress": project.get("actual_progress", 0),
            "project_lead_name": lead_name,
            "budgeted_hours": project.get("budgeted_hours"),
            "baseline_hours": round(baseline_hours, 2),
            "actual_hours": round(actual_hours, 2),
            "variance_hours": round(actual_hours - baseline_hours, 2),
            "variance_percentage": round(((actual_hours - baseline_hours) / baseline_hours * 100) if baseline_hours > 0 else 0, 2),
            "phases": project.get("phases", []),
            "milestones": milestones
        })
    
    # Sort by start date (pipeline projects first, then by date)
    portfolio_data.sort(key=lambda x: (not x["is_pipeline"], x["start_date"] or "9999-99-99"))
    
    return {
        "timeline_months": months,
        "date_range": {
            "start": today.isoformat(),
            "end": end_date.isoformat()
        },
        "total_projects": len(portfolio_data),
        "pipeline_count": sum(1 for p in portfolio_data if p["is_pipeline"]),
        "active_count": sum(1 for p in portfolio_data if not p["is_pipeline"]),
        "projects": portfolio_data
    }
