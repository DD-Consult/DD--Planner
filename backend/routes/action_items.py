from fastapi import APIRouter, Depends
from datetime import datetime, timedelta
from typing import List, Optional
import uuid

from database import (
    timesheets_collection,
    projects_collection,
    status_updates_collection,
    allocations_collection,
    wbs_tasks_collection,
    resources_collection,
    users_collection,
    notifications_collection,
    SYDNEY_TZ
)
from auth.dependencies import get_current_user, require_admin
from utils import serialize_doc

router = APIRouter()


def get_current_week_start() -> str:
    """Get the Monday of the current week in Sydney timezone as YYYY-MM-DD string"""
    sydney_now = datetime.now(SYDNEY_TZ)
    days_since_monday = sydney_now.weekday()
    week_start = (sydney_now - timedelta(days=days_since_monday)).date()
    return week_start.strftime("%Y-%m-%d")


@router.get("/api/dashboard/action-items")
async def get_action_items(current_user: dict = Depends(get_current_user)):
    """
    Get real-time action items for the current user.
    Returns different items based on user role.
    """
    action_items = []
    sydney_now = datetime.now(SYDNEY_TZ)
    today = sydney_now.date()
    week_start_str = get_current_week_start()
    
    user_role = current_user.get("role", "")
    is_admin = user_role in ["admin", "super_admin"]
    
    # === ACTION ITEMS FOR ALL USERS (including resource role) ===
    
    # 1. Missing timesheet this week
    resource_id = current_user.get("resource_id")
    if resource_id:
        # Check if user has submitted timesheet for current week
        existing_timesheet = await timesheets_collection.find_one({
            "resource_id": resource_id,
            "week_start_date": week_start_str,
            "status": {"$in": ["submitted", "Submitted"]}
        })
        
        if not existing_timesheet:
            action_items.append({
                "id": str(uuid.uuid4()),
                "type": "missing_timesheet",
                "severity": "high",
                "title": "Missing Timesheet",
                "message": f"Your timesheet for week of {week_start_str} has not been submitted",
                "action_url": "/dashboard",
                "related_id": None,
                "created_at": sydney_now.isoformat()
            })
    
    # 2. Timesheets in Draft
    if resource_id:
        draft_timesheets_cursor = timesheets_collection.find({
            "resource_id": resource_id,
            "status": {"$in": ["draft", "Draft"]}
        })
        draft_timesheets = await draft_timesheets_cursor.to_list(length=100)
        
        for timesheet in draft_timesheets:
            timesheet = serialize_doc(timesheet)
            week_start = timesheet.get("week_start_date", "")
            action_items.append({
                "id": str(uuid.uuid4()),
                "type": "draft_timesheet",
                "severity": "medium",
                "title": "Draft Timesheet",
                "message": f"You have a draft timesheet for week of {week_start}",
                "action_url": "/dashboard",
                "related_id": timesheet.get("id"),
                "created_at": sydney_now.isoformat()
            })
    
    # === ADDITIONAL ACTION ITEMS FOR ADMIN USERS ===
    
    if is_admin:
        # 3. Projects without status update this week
        active_projects_cursor = projects_collection.find({
            "status": {"$in": ["Active", "active"]}
        })
        active_projects = await active_projects_cursor.to_list(length=500)
        
        for project in active_projects:
            project = serialize_doc(project)
            project_id = project.get("id")
            
            # Check if project has status update for this week
            status_update = await status_updates_collection.find_one({
                "project_id": project_id,
                "week_start_date": week_start_str
            })
            
            if not status_update:
                action_items.append({
                    "id": str(uuid.uuid4()),
                    "type": "status_update_due",
                    "severity": "medium",
                    "title": f"Status Update Due: {project.get('name', 'Unknown Project')}",
                    "message": f"No status update submitted this week for {project.get('name', 'Unknown Project')}",
                    "action_url": f"/projects/{project_id}",
                    "related_id": project_id,
                    "created_at": sydney_now.isoformat()
                })
        
        # 4. Budget alerts
        for project in active_projects:
            project = serialize_doc(project)
            project_id = project.get("id")
            budgeted_hours = project.get("budgeted_hours")
            
            if budgeted_hours and budgeted_hours > 0:
                # Calculate actual hours from timesheets
                timesheets_cursor = timesheets_collection.find({
                    "project_id": project_id,
                    "status": {"$in": ["submitted", "Submitted"]}
                })
                timesheets = await timesheets_cursor.to_list(length=10000)
                
                actual_hours = 0
                for timesheet in timesheets:
                    actual_hours += timesheet.get("actual_hours", 0)
                
                usage_percentage = (actual_hours / budgeted_hours) * 100
                
                # Alert if over 80% (at risk) or over 100% (over budget)
                if usage_percentage > 100:
                    action_items.append({
                        "id": str(uuid.uuid4()),
                        "type": "budget_alert",
                        "severity": "high",
                        "title": f"Budget Alert: {project.get('name', 'Unknown Project')}",
                        "message": f"Project is over budget ({int(usage_percentage)}% - {int(actual_hours)}h / {int(budgeted_hours)}h)",
                        "action_url": f"/projects/{project_id}",
                        "related_id": project_id,
                        "created_at": sydney_now.isoformat()
                    })
                elif usage_percentage > 80:
                    action_items.append({
                        "id": str(uuid.uuid4()),
                        "type": "budget_alert",
                        "severity": "high",
                        "title": f"Budget Alert: {project.get('name', 'Unknown Project')}",
                        "message": f"Project has used {int(usage_percentage)}% of its budget ({int(actual_hours)}h / {int(budgeted_hours)}h)",
                        "action_url": f"/projects/{project_id}",
                        "related_id": project_id,
                        "created_at": sydney_now.isoformat()
                    })
        
        # 5. Allocations ending soon (within next 7 days)
        seven_days_later = today + timedelta(days=7)
        
        allocations_cursor = allocations_collection.find({})
        allocations = await allocations_cursor.to_list(length=10000)
        
        for allocation in allocations:
            allocation = serialize_doc(allocation)
            end_date_str = allocation.get("end_date")
            
            if end_date_str:
                try:
                    # Handle different date formats
                    if isinstance(end_date_str, str):
                        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00')).date()
                    else:
                        end_date = end_date_str
                    
                    # Check if ending within next 7 days but not already ended
                    if today <= end_date <= seven_days_later:
                        days_remaining = (end_date - today).days
                        
                        # Get resource and project details
                        resource_id_str = allocation.get("resource_id")
                        project_id_str = allocation.get("project_id")
                        
                        resource = await resources_collection.find_one({"id": resource_id_str})
                        project = await projects_collection.find_one({"id": project_id_str})
                        
                        if resource and project:
                            resource = serialize_doc(resource)
                            project = serialize_doc(project)
                            
                            resource_name = resource.get("name", "Unknown Resource")
                            project_name = project.get("name", "Unknown Project")
                            
                            action_items.append({
                                "id": str(uuid.uuid4()),
                                "type": "allocation_ending",
                                "severity": "low" if days_remaining > 3 else "medium",
                                "title": f"Allocation Ending: {resource_name}",
                                "message": f"{resource_name}'s allocation to {project_name} ends on {end_date.strftime('%b %d, %Y')} ({days_remaining} days)",
                                "action_url": f"/projects/{project.get('id')}",
                                "related_id": allocation.get("id"),
                                "created_at": sydney_now.isoformat()
                            })
                except Exception:
                    # Skip malformed dates
                    continue
        
        # 6. Overdue milestones
        overdue_milestones_cursor = wbs_tasks_collection.find({
            "is_milestone": True,
            "milestone_completed": {"$ne": True}
        })
        overdue_milestones = await overdue_milestones_cursor.to_list(length=1000)
        
        for milestone in overdue_milestones:
            milestone = serialize_doc(milestone)
            milestone_date_str = milestone.get("milestone_date")
            
            if milestone_date_str:
                try:
                    # Handle different date formats
                    if isinstance(milestone_date_str, str):
                        milestone_date = datetime.fromisoformat(milestone_date_str.replace('Z', '+00:00')).date()
                    else:
                        milestone_date = milestone_date_str
                    
                    # Check if overdue
                    if milestone_date < today:
                        days_overdue = (today - milestone_date).days
                        
                        # Get project details
                        project_id = milestone.get("project_id")
                        project = None
                        if project_id:
                            project = await projects_collection.find_one({"id": project_id})
                            if project:
                                project = serialize_doc(project)
                        
                        project_name = project.get("name", "Unknown Project") if project else "Unknown Project"
                        milestone_name = milestone.get("name", "Unnamed Milestone")
                        
                        action_items.append({
                            "id": str(uuid.uuid4()),
                            "type": "overdue_milestone",
                            "severity": "high" if days_overdue > 7 else "medium",
                            "title": f"Overdue Milestone: {milestone_name}",
                            "message": f"{milestone_name} in {project_name} was due {days_overdue} days ago",
                            "action_url": f"/projects/{project_id}" if project_id else "/dashboard",
                            "related_id": milestone.get("id"),
                            "created_at": sydney_now.isoformat()
                        })
                except Exception:
                    # Skip malformed dates
                    continue
    
    # Calculate summary
    summary = {
        "total": len(action_items),
        "high": sum(1 for item in action_items if item["severity"] == "high"),
        "medium": sum(1 for item in action_items if item["severity"] == "medium"),
        "low": sum(1 for item in action_items if item["severity"] == "low")
    }
    
    return {
        "action_items": action_items,
        "summary": summary
    }


@router.post("/api/notifications/generate")
async def generate_notifications(admin: dict = Depends(require_admin)):
    """
    Manually trigger notification generation for all users.
    Creates in-app notifications for:
    - Missing timesheets (for each resource without a submitted timesheet this week)
    - Overdue milestones
    - Budget alerts for project leads
    
    Does not create duplicate notifications for the same type on the same day.
    """
    from routes.admin import create_notification
    
    sydney_now = datetime.now(SYDNEY_TZ)
    today = sydney_now.date()
    week_start_str = get_current_week_start()
    today_start = datetime.combine(today, datetime.min.time()).isoformat()
    
    notifications_created = 0
    
    # 1. Missing timesheets
    # Get all resources
    resources_cursor = resources_collection.find({})
    resources = await resources_cursor.to_list(length=1000)
    
    for resource in resources:
        resource = serialize_doc(resource)
        resource_id = resource.get("id")
        
        if not resource_id:
            continue
        
        # Check if timesheet submitted for this week
        existing_timesheet = await timesheets_collection.find_one({
            "resource_id": resource_id,
            "week_start_date": week_start_str,
            "status": {"$in": ["submitted", "Submitted"]}
        })
        
        if not existing_timesheet:
            # Find user for this resource
            user = await users_collection.find_one({"resource_id": resource_id})
            if user:
                user = serialize_doc(user)
                user_id = user.get("id")
                
                # Check if we already sent this notification today
                existing_notification = await notifications_collection.find_one({
                    "user_id": user_id,
                    "type": "missing_timesheet",
                    "created_at": {"$gte": today_start}
                })
                
                if not existing_notification:
                    await create_notification(
                        user_id=user_id,
                        notification_type="missing_timesheet",
                        title="Missing Timesheet",
                        message=f"Your timesheet for week of {week_start_str} has not been submitted",
                        priority="high"
                    )
                    notifications_created += 1
    
    # 2. Overdue milestones
    overdue_milestones_cursor = wbs_tasks_collection.find({
        "is_milestone": True,
        "milestone_completed": {"$ne": True}
    })
    overdue_milestones = await overdue_milestones_cursor.to_list(length=1000)
    
    admin_users_cursor = users_collection.find({"role": {"$in": ["admin", "super_admin"]}})
    admin_users = await admin_users_cursor.to_list(length=100)
    
    for milestone in overdue_milestones:
        milestone = serialize_doc(milestone)
        milestone_date_str = milestone.get("milestone_date")
        
        if milestone_date_str:
            try:
                # Handle different date formats
                if isinstance(milestone_date_str, str):
                    milestone_date = datetime.fromisoformat(milestone_date_str.replace('Z', '+00:00')).date()
                else:
                    milestone_date = milestone_date_str
                
                # Check if overdue
                if milestone_date < today:
                    days_overdue = (today - milestone_date).days
                    milestone_name = milestone.get("name", "Unnamed Milestone")
                    project_id = milestone.get("project_id")
                    
                    # Get project details
                    project = None
                    if project_id:
                        project = await projects_collection.find_one({"id": project_id})
                        if project:
                            project = serialize_doc(project)
                    
                    project_name = project.get("name", "Unknown Project") if project else "Unknown Project"
                    
                    # Notify admins
                    for admin_user in admin_users:
                        admin_user = serialize_doc(admin_user)
                        admin_id = admin_user.get("id")
                        
                        # Check if we already sent this notification today
                        existing_notification = await notifications_collection.find_one({
                            "user_id": admin_id,
                            "type": "overdue_milestone",
                            "related_id": milestone.get("id"),
                            "created_at": {"$gte": today_start}
                        })
                        
                        if not existing_notification:
                            await create_notification(
                                user_id=admin_id,
                                notification_type="overdue_milestone",
                                title=f"Overdue Milestone: {milestone_name}",
                                message=f"{milestone_name} in {project_name} was due {days_overdue} days ago",
                                related_id=milestone.get("id"),
                                priority="high" if days_overdue > 7 else "normal"
                            )
                            notifications_created += 1
            except Exception:
                # Skip malformed dates
                continue
    
    # 3. Budget alerts
    active_projects_cursor = projects_collection.find({
        "status": {"$in": ["Active", "active"]}
    })
    active_projects = await active_projects_cursor.to_list(length=500)
    
    for project in active_projects:
        project = serialize_doc(project)
        project_id = project.get("id")
        budgeted_hours = project.get("budgeted_hours")
        
        if budgeted_hours and budgeted_hours > 0:
            # Calculate actual hours from timesheets
            timesheets_cursor = timesheets_collection.find({
                "project_id": project_id,
                "status": {"$in": ["submitted", "Submitted"]}
            })
            timesheets = await timesheets_cursor.to_list(length=10000)
            
            actual_hours = 0
            for timesheet in timesheets:
                actual_hours += timesheet.get("actual_hours", 0)
            
            usage_percentage = (actual_hours / budgeted_hours) * 100
            
            # Alert if over 80%
            if usage_percentage > 80:
                project_name = project.get("name", "Unknown Project")
                
                # Notify admins
                for admin_user in admin_users:
                    admin_user = serialize_doc(admin_user)
                    admin_id = admin_user.get("id")
                    
                    # Check if we already sent this notification today
                    existing_notification = await notifications_collection.find_one({
                        "user_id": admin_id,
                        "type": "budget_alert",
                        "related_id": project_id,
                        "created_at": {"$gte": today_start}
                    })
                    
                    if not existing_notification:
                        if usage_percentage > 100:
                            message = f"{project_name} is over budget ({int(usage_percentage)}% - {int(actual_hours)}h / {int(budgeted_hours)}h)"
                        else:
                            message = f"{project_name} has used {int(usage_percentage)}% of its budget ({int(actual_hours)}h / {int(budgeted_hours)}h)"
                        
                        await create_notification(
                            user_id=admin_id,
                            notification_type="budget_alert",
                            title=f"Budget Alert: {project_name}",
                            message=message,
                            related_id=project_id,
                            priority="high"
                        )
                        notifications_created += 1
    
    return {
        "success": True,
        "message": f"Generated {notifications_created} notifications",
        "notifications_created": notifications_created,
        "week": week_start_str
    }
