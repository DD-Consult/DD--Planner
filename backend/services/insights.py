"""
Project Insights & Predictive Analytics Engine
===============================================
Computes health scores, predictions, and trend data from real project metrics.
No AI calls — pure data-driven computation.
"""
from datetime import datetime, date, timedelta, timezone
from bson import ObjectId
from typing import Dict, List, Optional
import logging

from database import (
    projects_collection, timesheets_collection, allocations_collection,
    risks_collection, wbs_tasks_collection, status_updates_collection,
    resources_collection, SYDNEY_TZ
)
from utils import serialize_doc, count_business_days

logger = logging.getLogger(__name__)


def _safe_date_conversion(dt):
    """Convert datetime/date to date object safely."""
    if isinstance(dt, datetime):
        return dt.date()
    elif isinstance(dt, date):
        return dt
    elif isinstance(dt, str):
        try:
            return datetime.fromisoformat(dt.replace('Z', '+00:00')).date()
        except (ValueError, AttributeError):
            return datetime.strptime(dt[:10], '%Y-%m-%d').date()
    return None


def _get_grade_from_score(score: float) -> str:
    """Convert numeric score to letter grade."""
    if score >= 90:
        return "A"
    elif score >= 75:
        return "B"
    elif score >= 60:
        return "C"
    elif score >= 40:
        return "D"
    else:
        return "F"


async def compute_health_score(project_id: str) -> dict:
    """
    Computes a composite health score (0-100) for a project based on 5 dimensions:
    - Schedule (30%): Compare time elapsed vs actual progress
    - Budget (25%): Compare actual hours vs budgeted hours
    - Risk (20%): Based on active risks count and severity
    - Team (15%): Allocation coverage and health
    - WBS (10%): Task completion rate
    
    Returns:
        dict: Complete health score breakdown with overall score, grade, and dimension details
    """
    try:
        # Get project
        project = await projects_collection.find_one({"_id": ObjectId(project_id)})
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        today = datetime.now(SYDNEY_TZ).date()
        
        # Get project dates
        start_date = _safe_date_conversion(project.get("start_date"))
        end_date = _safe_date_conversion(project.get("end_date"))
        actual_progress = project.get("actual_progress", 0)
        
        dimensions = {}
        
        # ===========================
        # 1. SCHEDULE SCORE (30% weight)
        # ===========================
        schedule_score = 70  # default neutral
        schedule_detail = "No date information available"
        
        if start_date and end_date:
            total_days = (end_date - start_date).days
            if total_days > 0:
                elapsed_days = max(0, (today - start_date).days)
                time_elapsed_pct = min(100, (elapsed_days / total_days) * 100)
                
                if actual_progress >= time_elapsed_pct:
                    schedule_score = 100
                    schedule_detail = f"On track: {actual_progress:.0f}% progress vs {time_elapsed_pct:.0f}% time elapsed"
                else:
                    gap = time_elapsed_pct - actual_progress
                    schedule_score = max(0, 100 - (gap * 2))
                    schedule_detail = f"Behind schedule: {actual_progress:.0f}% progress vs {time_elapsed_pct:.0f}% time elapsed"
        
        dimensions["schedule"] = {
            "score": round(schedule_score, 1),
            "weight": 30,
            "detail": schedule_detail
        }
        
        # ===========================
        # 2. BUDGET SCORE (25% weight)
        # ===========================
        budgeted_hours = project.get("budgeted_hours")
        
        # Sum actual hours from timesheets
        timesheet_pipeline = [
            {"$match": {"project_id": project_id, "status": "approved"}},
            {"$group": {"_id": None, "total_hours": {"$sum": "$hours"}}}
        ]
        timesheet_result = await timesheets_collection.aggregate(timesheet_pipeline).to_list(length=1)
        actual_hours = timesheet_result[0]["total_hours"] if timesheet_result else 0
        
        budget_score = 70  # default neutral
        budget_detail = "No budget set"
        
        if budgeted_hours and budgeted_hours > 0:
            budget_usage_pct = (actual_hours / budgeted_hours) * 100
            
            # Check if project is complete
            is_complete = project.get("status") == "Completed"
            
            if is_complete:
                if budget_usage_pct <= 100:
                    budget_score = 100
                    budget_detail = f"Under budget: {actual_hours:.1f}/{budgeted_hours:.1f} hours used ({budget_usage_pct:.0f}%)"
                else:
                    over_pct = budget_usage_pct - 100
                    budget_score = max(0, 100 - (over_pct * 2))
                    budget_detail = f"Over budget: {actual_hours:.1f}/{budgeted_hours:.1f} hours used ({budget_usage_pct:.0f}%)"
            else:
                # Compare budget usage with time elapsed
                if start_date and end_date:
                    total_days = (end_date - start_date).days
                    if total_days > 0:
                        elapsed_days = max(0, (today - start_date).days)
                        time_elapsed_pct = min(100, (elapsed_days / total_days) * 100)
                        
                        if budget_usage_pct <= time_elapsed_pct:
                            budget_score = 100
                            budget_detail = f"Budget on track: {budget_usage_pct:.0f}% used vs {time_elapsed_pct:.0f}% time elapsed"
                        else:
                            gap = budget_usage_pct - time_elapsed_pct
                            budget_score = max(0, 100 - (gap * 2))
                            budget_detail = f"Budget ahead of schedule: {budget_usage_pct:.0f}% used vs {time_elapsed_pct:.0f}% time elapsed"
                else:
                    budget_score = 80 if budget_usage_pct <= 70 else 60
                    budget_detail = f"Budget usage: {actual_hours:.1f}/{budgeted_hours:.1f} hours ({budget_usage_pct:.0f}%)"
        
        dimensions["budget"] = {
            "score": round(budget_score, 1),
            "weight": 25,
            "detail": budget_detail
        }
        
        # ===========================
        # 3. RISK SCORE (20% weight)
        # ===========================
        # Count active risks by severity
        active_risks = await risks_collection.find({
            "project_id": project_id,
            "status": {"$in": ["Open", "In Progress"]}
        }).to_list(length=1000)
        
        impact_weights = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
        risk_weight = sum(impact_weights.get(r.get("impact", "Low"), 1) for r in active_risks)
        
        risk_score = max(0, 100 - (risk_weight * 10))
        
        risk_counts = {}
        for r in active_risks:
            impact = r.get("impact", "Low")
            risk_counts[impact] = risk_counts.get(impact, 0) + 1
        
        if not active_risks:
            risk_detail = "No active risks"
        else:
            risk_parts = [f"{count} {level}" for level, count in sorted(risk_counts.items(), key=lambda x: impact_weights.get(x[0], 0), reverse=True)]
            risk_detail = f"{len(active_risks)} active risk(s): {', '.join(risk_parts)}"
        
        dimensions["risk"] = {
            "score": round(risk_score, 1),
            "weight": 20,
            "detail": risk_detail
        }
        
        # ===========================
        # 4. TEAM SCORE (15% weight)
        # ===========================
        project_allocations = await allocations_collection.find({
            "project_id": project_id
        }).to_list(length=1000)
        
        team_score = 50  # default neutral
        team_detail = "No team allocated"
        
        if project_allocations:
            team_score = 100
            unique_resources = len(set(a.get("resource_id") for a in project_allocations if a.get("resource_id")))
            
            # Check if project has a lead
            has_lead = project.get("project_lead_id") is not None
            if not has_lead:
                team_score -= 20
            
            # Check for over-allocations across all projects
            resource_ids = [a.get("resource_id") for a in project_allocations if a.get("resource_id")]
            over_allocated = 0
            
            for resource_id in set(resource_ids):
                # Get all allocations for this resource that overlap with today
                all_allocations = await allocations_collection.find({
                    "resource_id": resource_id,
                    "start_date": {"$lte": datetime.combine(today, datetime.max.time())},
                    "end_date": {"$gte": datetime.combine(today, datetime.min.time())}
                }).to_list(length=1000)
                
                total_allocation = sum(a.get("percentage", 0) for a in all_allocations)
                if total_allocation > 100:
                    over_allocated += 1
            
            if over_allocated > 0:
                team_score -= (over_allocated * 10)
                team_score = max(0, team_score)
            
            team_parts = [f"{unique_resources} team member(s) allocated"]
            if has_lead:
                team_parts.append("lead assigned")
            else:
                team_parts.append("no lead assigned")
            if over_allocated > 0:
                team_parts.append(f"{over_allocated} over-allocated")
            
            team_detail = ", ".join(team_parts)
        
        dimensions["team"] = {
            "score": round(team_score, 1),
            "weight": 15,
            "detail": team_detail
        }
        
        # ===========================
        # 5. WBS SCORE (10% weight)
        # ===========================
        wbs_tasks = await wbs_tasks_collection.find({
            "project_id": project_id
        }).to_list(length=1000)
        
        wbs_score = 70  # default neutral
        wbs_detail = "No tasks defined"
        
        if wbs_tasks:
            total_tasks = len(wbs_tasks)
            done_tasks = sum(1 for t in wbs_tasks if t.get("status") == "Done")
            task_completion_pct = (done_tasks / total_tasks * 100) if total_tasks > 0 else 0
            
            if start_date and end_date:
                total_days = (end_date - start_date).days
                if total_days > 0:
                    elapsed_days = max(0, (today - start_date).days)
                    time_elapsed_pct = min(100, (elapsed_days / total_days) * 100)
                    
                    if task_completion_pct >= time_elapsed_pct:
                        wbs_score = 100
                        wbs_detail = f"Tasks on track: {done_tasks}/{total_tasks} completed ({task_completion_pct:.0f}%)"
                    else:
                        gap = time_elapsed_pct - task_completion_pct
                        wbs_score = max(0, 100 - (gap * 2))
                        wbs_detail = f"Tasks behind: {done_tasks}/{total_tasks} completed ({task_completion_pct:.0f}%)"
            else:
                wbs_score = 100 if task_completion_pct >= 50 else 70
                wbs_detail = f"{done_tasks}/{total_tasks} tasks completed ({task_completion_pct:.0f}%)"
        
        dimensions["wbs"] = {
            "score": round(wbs_score, 1),
            "weight": 10,
            "detail": wbs_detail
        }
        
        # ===========================
        # CALCULATE OVERALL SCORE
        # ===========================
        overall_score = (
            dimensions["schedule"]["score"] * 0.30 +
            dimensions["budget"]["score"] * 0.25 +
            dimensions["risk"]["score"] * 0.20 +
            dimensions["team"]["score"] * 0.15 +
            dimensions["wbs"]["score"] * 0.10
        )
        
        grade = _get_grade_from_score(overall_score)
        
        # Determine trend (placeholder for now - would need historical data)
        trend = "stable"
        
        return {
            "project_id": project_id,
            "overall_score": round(overall_score, 1),
            "grade": grade,
            "dimensions": dimensions,
            "trend": trend,
            "computed_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error computing health score for project {project_id}: {e}")
        raise


async def predict_completion(project_id: str) -> dict:
    """
    Predict when the project will actually complete based on velocity.
    
    Calculates:
    - Progress velocity (progress per day)
    - Predicted completion date
    - Variance from planned end date
    - Budget burn rate and prediction
    
    Returns:
        dict: Prediction data including dates, confidence, and budget forecast
    """
    try:
        # Get project
        project = await projects_collection.find_one({"_id": ObjectId(project_id)})
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        today = datetime.now(SYDNEY_TZ).date()
        
        # Get project dates
        start_date = _safe_date_conversion(project.get("start_date"))
        end_date = _safe_date_conversion(project.get("end_date"))
        actual_progress = project.get("actual_progress", 0)
        budgeted_hours = project.get("budgeted_hours")
        
        # Calculate elapsed business days
        if not start_date:
            raise ValueError("Project has no start date")
        
        elapsed_business_days = count_business_days(start_date, min(today, end_date) if end_date else today)
        
        # Calculate progress velocity
        progress_per_day = 0
        predicted_end_date = None
        variance_days = 0
        confidence = 0.5
        status = "unknown"
        
        if elapsed_business_days > 0:
            progress_per_day = actual_progress / elapsed_business_days
            
            if progress_per_day > 0:
                remaining_progress = 100 - actual_progress
                predicted_days_remaining = remaining_progress / progress_per_day
                
                # Convert to calendar date (approximate)
                predicted_end_date = today + timedelta(days=int(predicted_days_remaining * 1.4))  # Adjust for weekends
                
                # Confidence increases with more elapsed time
                confidence = min(0.95, 0.4 + (elapsed_business_days / 100) * 0.55)
                
                if end_date:
                    variance_days = (predicted_end_date - end_date).days
                    
                    if variance_days <= 0:
                        status = "on_track"
                    elif variance_days <= 5:
                        status = "at_risk"
                    else:
                        status = "critical"
        
        # Calculate WBS-based velocity
        wbs_tasks = await wbs_tasks_collection.find({
            "project_id": project_id
        }).to_list(length=1000)
        
        tasks_per_week = 0
        if wbs_tasks and elapsed_business_days > 0:
            done_tasks = sum(1 for t in wbs_tasks if t.get("status") == "Done")
            elapsed_weeks = elapsed_business_days / 5
            if elapsed_weeks > 0:
                tasks_per_week = done_tasks / elapsed_weeks
        
        # Budget prediction
        timesheet_pipeline = [
            {"$match": {"project_id": project_id, "status": "approved"}},
            {"$group": {"_id": None, "total_hours": {"$sum": "$hours"}}}
        ]
        timesheet_result = await timesheets_collection.aggregate(timesheet_pipeline).to_list(length=1)
        current_actual_hours = timesheet_result[0]["total_hours"] if timesheet_result else 0
        
        budget_prediction = {
            "budgeted_hours": budgeted_hours,
            "current_actual": round(current_actual_hours, 1),
            "burn_rate_per_week": 0,
            "predicted_total": None,
            "weeks_until_exhausted": None,
            "will_exceed_budget": False
        }
        
        if budgeted_hours and elapsed_business_days > 0:
            elapsed_weeks = elapsed_business_days / 5
            burn_rate_per_week = current_actual_hours / elapsed_weeks if elapsed_weeks > 0 else 0
            budget_prediction["burn_rate_per_week"] = round(burn_rate_per_week, 1)
            
            if progress_per_day > 0:
                remaining_progress = 100 - actual_progress
                predicted_days_remaining = remaining_progress / progress_per_day
                predicted_weeks_remaining = predicted_days_remaining / 5
                
                predicted_total_hours = current_actual_hours + (burn_rate_per_week * predicted_weeks_remaining)
                budget_prediction["predicted_total"] = round(predicted_total_hours, 1)
                budget_prediction["will_exceed_budget"] = predicted_total_hours > budgeted_hours
                
                if burn_rate_per_week > 0:
                    remaining_budget = budgeted_hours - current_actual_hours
                    weeks_until_exhausted = remaining_budget / burn_rate_per_week if remaining_budget > 0 else 0
                    budget_prediction["weeks_until_exhausted"] = round(weeks_until_exhausted, 1)
        
        return {
            "project_id": project_id,
            "planned_end_date": end_date.isoformat() if end_date else None,
            "predicted_end_date": predicted_end_date.isoformat() if predicted_end_date else None,
            "confidence": round(confidence, 2),
            "variance_days": variance_days,
            "status": status,
            "velocity": {
                "progress_per_day": round(progress_per_day, 2),
                "tasks_per_week": round(tasks_per_week, 2)
            },
            "budget_prediction": budget_prediction
        }
        
    except Exception as e:
        logger.error(f"Error predicting completion for project {project_id}: {e}")
        raise


async def get_portfolio_health_scores() -> List[dict]:
    """
    Get health scores for all active projects.
    
    Returns:
        List[dict]: List of health scores for all active projects
    """
    try:
        # Get all active projects
        active_projects = await projects_collection.find({
            "status": {"$in": ["Active", "Pipeline"]}
        }).to_list(length=1000)
        
        results = []
        for project in active_projects:
            project_id = str(project["_id"])
            try:
                health_score = await compute_health_score(project_id)
                health_score["project_name"] = project.get("name")
                health_score["client_name"] = project.get("client_name")
                results.append(health_score)
            except Exception as e:
                logger.error(f"Error computing health score for project {project_id}: {e}")
                continue
        
        # Sort by overall score (lowest first - most at risk)
        results.sort(key=lambda x: x["overall_score"])
        
        return results
        
    except Exception as e:
        logger.error(f"Error getting portfolio health scores: {e}")
        raise
