from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date, timedelta, timezone
from bson import ObjectId
import os
import uuid
import io
import json
import zipfile
import asyncio
import logging

from database import (
    projects_collection, resources_collection, allocations_collection,
    timesheets_collection, risks_collection, status_updates_collection,
    users_collection, settings_collection, leaves_collection,
    holidays_collection, notifications_collection, chat_sessions_collection,
    EXPORT_API_KEY, SYDNEY_TZ,
)
from models.schemas import UserRole, ProjectStatus, NotificationResponse
from auth.dependencies import get_current_user, require_admin, require_admin_or_above, get_password_hash
from utils import serialize_doc, ensure_phase_ids
from services.email import (
    create_notification, send_email_notification,
    get_timesheet_reminder_email, get_allocation_ending_email,
)

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/api/admin/export-database")
async def export_database(current_user: dict = Depends(get_current_user)):
    """
    Export entire database - SUPER ADMIN ONLY
    Use this to sync data between environments
    """
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")
    
    from datetime import datetime, timezone
    
    data = {
        "export_metadata": {
            "export_date": datetime.now(timezone.utc).isoformat(),
            "exported_by": current_user.get("email"),
            "database": "smartplanning-resource_planner"
        },
        "collections": {}
    }
    
    # Collections to export
    collection_names = [
        'users', 'resources', 'projects', 'allocations', 
        'timesheets', 'status_updates', 'risks', 
        'holidays', 'leaves', 'allocation_roles'
    ]
    
    for coll_name in collection_names:
        try:
            cursor = db[coll_name].find()
            docs = await cursor.to_list(length=100000)
            data["collections"][coll_name] = [serialize_doc(d) for d in docs]
            print(f"Exported {len(docs)} documents from {coll_name}")
        except Exception as e:
            print(f"Error exporting {coll_name}: {e}")
            data["collections"][coll_name] = []
    
    return data


# ==================== MIGRATION API ====================


@router.post("/api/admin/migrate-phase-ids")
async def migrate_phase_ids(current_user: dict = Depends(get_current_user)):
    """
    Migration API endpoint to fix phase IDs in batches.
    Only accessible by super_admin.
    Processes database in batches of 10 projects to avoid overloading.
    """
    # Verify user is super admin
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only super admins can run migrations")
    
    import asyncio
    
    migration_log = []
    
    def log_message(msg):
        """Helper to log messages"""
        print(msg)
        migration_log.append(msg)
    
    log_message("🔧 Starting Phase ID Migration (Batch Mode)...")
    log_message("=" * 60)
    
    try:
        # Get all projects
        all_projects = await projects_collection.find().to_list(length=None)
        total_projects = len(all_projects)
        log_message(f"Found {total_projects} projects")
        
        if total_projects == 0:
            return {
                "success": True,
                "message": "No projects found in database",
                "log": migration_log
            }
        
        # Process in batches
        batch_size = 10
        projects_updated = 0
        phases_fixed = 0
        timesheets_updated = 0
        
        for batch_start in range(0, total_projects, batch_size):
            batch_end = min(batch_start + batch_size, total_projects)
            batch_projects = all_projects[batch_start:batch_end]
            
            log_message(f"\n📦 Processing batch {batch_start//batch_size + 1}: Projects {batch_start + 1}-{batch_end}")
            
            for project in batch_projects:
                phases = project.get('phases', [])
                if not phases:
                    continue
                
                updated_phases = []
                needs_update = False
                phase_name_to_id = {}
                
                # Check and fix phase IDs
                for phase in phases:
                    phase_id = phase.get('id')
                    phase_name = phase.get('name', 'Unknown')
                    
                    # If phase has no ID or ID is None, generate new UUID
                    if not phase_id or phase_id == 'None' or phase_id == '':
                        new_id = str(uuid.uuid4())
                        phase['id'] = new_id
                        phase_name_to_id[phase_name] = new_id
                        needs_update = True
                        phases_fixed += 1
                        log_message(f"  ✓ Fixed phase '{phase_name}' in '{project.get('name', 'Unknown')}': {new_id[:8]}...")
                    else:
                        phase_name_to_id[phase_name] = phase_id
                    
                    updated_phases.append(phase)
                
                # Update project if needed
                if needs_update:
                    await projects_collection.update_one(
                        {'_id': project['_id']},
                        {'$set': {'phases': updated_phases}}
                    )
                    projects_updated += 1
                    
                    # Update orphaned timesheets for this project
                    project_id_str = str(project['_id'])
                    orphaned_timesheets = await timesheets_collection.find({
                        'project_id': project_id_str,
                        '$or': [
                            {'phase_id': None},
                            {'phase_id': 'None'},
                            {'phase_id': ''}
                        ]
                    }).to_list(length=None)
                    
                    for timesheet in orphaned_timesheets:
                        # Try to match by date range
                        week_start = timesheet.get('week_start_date')
                        matched_phase_id = None
                        
                        if week_start and updated_phases:
                            # Try to match based on dates
                            for phase in updated_phases:
                                phase_start = phase.get('start_date')
                                phase_end = phase.get('end_date')
                                
                                if phase_start and phase_end:
                                    try:
                                        # Convert to datetime for comparison
                                        from datetime import datetime
                                        
                                        if isinstance(week_start, str):
                                            week_start_dt = datetime.fromisoformat(week_start.replace('Z', '+00:00'))
                                        else:
                                            week_start_dt = week_start
                                        
                                        if isinstance(phase_start, str):
                                            phase_start_dt = datetime.fromisoformat(phase_start.replace('Z', '+00:00'))
                                        else:
                                            phase_start_dt = phase_start
                                        
                                        if isinstance(phase_end, str):
                                            phase_end_dt = datetime.fromisoformat(phase_end.replace('Z', '+00:00'))
                                        else:
                                            phase_end_dt = phase_end
                                        
                                        if phase_start_dt <= week_start_dt <= phase_end_dt:
                                            matched_phase_id = phase.get('id')
                                            break
                                    except:
                                        continue
                        
                        # Fallback to first phase if no date match
                        if not matched_phase_id and updated_phases:
                            matched_phase_id = updated_phases[0].get('id')
                        
                        if matched_phase_id:
                            await timesheets_collection.update_one(
                                {'_id': timesheet['_id']},
                                {'$set': {'phase_id': matched_phase_id}}
                            )
                            timesheets_updated += 1
            
            # Small delay between batches to avoid overload
            if batch_end < total_projects:
                await asyncio.sleep(0.5)
        
        log_message("\n" + "=" * 60)
        log_message("✅ Migration Complete!")
        log_message(f"   Total projects: {total_projects}")
        log_message(f"   Projects updated: {projects_updated}")
        log_message(f"   Phases fixed: {phases_fixed}")
        log_message(f"   Timesheets updated: {timesheets_updated}")
        log_message("=" * 60)
        
        return {
            "success": True,
            "message": "Migration completed successfully",
            "stats": {
                "total_projects": total_projects,
                "projects_updated": projects_updated,
                "phases_fixed": phases_fixed,
                "timesheets_updated": timesheets_updated
            },
            "log": migration_log
        }
        
    except Exception as e:
        error_msg = f"❌ Migration failed: {str(e)}"
        log_message(error_msg)
        log_message("=" * 60)
        
        return {
            "success": False,
            "message": str(e),
            "log": migration_log
        }

# ==================== DATA CLEANUP (Admin) ====================


@router.get("/api/admin/data-cleanup/scan")
async def scan_orphaned_data(admin: dict = Depends(require_admin)):
    """Scan for orphaned records that reference deleted resources/projects."""
    # Get all valid resource and project IDs
    all_resources = await resources_collection.find({}, {"_id": 1}).to_list(length=10000)
    all_projects = await projects_collection.find({}, {"_id": 1}).to_list(length=10000)
    valid_resource_ids = {str(r["_id"]) for r in all_resources}
    valid_project_ids = {str(p["_id"]) for p in all_projects}

    # Scan allocations
    all_allocations = await allocations_collection.find({}).to_list(length=10000)
    orphaned_allocations = []
    for a in all_allocations:
        rid = a.get("resource_id", "")
        pid = a.get("project_id", "")
        reasons = []
        if rid not in valid_resource_ids:
            reasons.append("resource deleted")
        if pid not in valid_project_ids:
            reasons.append("project deleted")
        if reasons:
            orphaned_allocations.append({
                "id": str(a["_id"]),
                "resource_id": rid,
                "project_id": pid,
                "reason": ", ".join(reasons)
            })

    # Scan timesheets
    all_timesheets = await timesheets_collection.find({}).to_list(length=10000)
    orphaned_timesheets = []
    for t in all_timesheets:
        rid = t.get("resource_id", "")
        pid = t.get("project_id", "")
        reasons = []
        if rid and rid not in valid_resource_ids:
            reasons.append("resource deleted")
        if pid and pid not in valid_project_ids:
            reasons.append("project deleted")
        if reasons:
            orphaned_timesheets.append({
                "id": str(t["_id"]),
                "resource_id": rid,
                "project_id": pid,
                "reason": ", ".join(reasons)
            })

    # Scan status_updates
    all_status = await status_updates_collection.find({}).to_list(length=10000)
    orphaned_status = []
    for s in all_status:
        pid = s.get("project_id", "")
        if pid and pid not in valid_project_ids:
            orphaned_status.append({
                "id": str(s["_id"]),
                "project_id": pid,
                "reason": "project deleted"
            })

    return {
        "orphaned_allocations": len(orphaned_allocations),
        "orphaned_timesheets": len(orphaned_timesheets),
        "orphaned_status_updates": len(orphaned_status),
        "total_orphaned": len(orphaned_allocations) + len(orphaned_timesheets) + len(orphaned_status),
        "details": {
            "allocations": orphaned_allocations[:50],
            "timesheets": orphaned_timesheets[:50],
            "status_updates": orphaned_status[:50],
        }
    }


@router.post("/api/admin/data-cleanup/execute")
async def execute_data_cleanup(admin: dict = Depends(require_admin)):
    """Delete all orphaned records that reference deleted resources/projects."""
    valid_resource_ids = {str(r["_id"]) for r in await resources_collection.find({}, {"_id": 1}).to_list(length=10000)}
    valid_project_ids = {str(p["_id"]) for p in await projects_collection.find({}, {"_id": 1}).to_list(length=10000)}

    deleted = {"allocations": 0, "timesheets": 0, "status_updates": 0}

    # Clean allocations
    all_allocations = await allocations_collection.find({}).to_list(length=10000)
    ids_to_delete = []
    for a in all_allocations:
        rid = a.get("resource_id", "")
        pid = a.get("project_id", "")
        if rid not in valid_resource_ids or pid not in valid_project_ids:
            ids_to_delete.append(a["_id"])
    if ids_to_delete:
        result = await allocations_collection.delete_many({"_id": {"$in": ids_to_delete}})
        deleted["allocations"] = result.deleted_count

    # Clean timesheets
    all_timesheets = await timesheets_collection.find({}).to_list(length=10000)
    ids_to_delete = []
    for t in all_timesheets:
        rid = t.get("resource_id", "")
        pid = t.get("project_id", "")
        if (rid and rid not in valid_resource_ids) or (pid and pid not in valid_project_ids):
            ids_to_delete.append(t["_id"])
    if ids_to_delete:
        result = await timesheets_collection.delete_many({"_id": {"$in": ids_to_delete}})
        deleted["timesheets"] = result.deleted_count

    # Clean status_updates
    all_status = await status_updates_collection.find({}).to_list(length=10000)
    ids_to_delete = []
    for s in all_status:
        pid = s.get("project_id", "")
        if pid and pid not in valid_project_ids:
            ids_to_delete.append(s["_id"])
    if ids_to_delete:
        result = await status_updates_collection.delete_many({"_id": {"$in": ids_to_delete}})
        deleted["status_updates"] = result.deleted_count

    deleted["total"] = deleted["allocations"] + deleted["timesheets"] + deleted["status_updates"]
    return {"message": "Cleanup complete", "deleted": deleted}


# ==================== AI CHAT AGENT ====================


@router.get("/api/export")
async def export_all_data_zip(key: str = ""):
    """
    Download all database collections as a .zip of JSON files.
    Protected by a strong API key (passed as ?key= query param).
    No JWT required — designed for direct browser download.
    """
    import io
    import json as _json
    import zipfile
    from fastapi.responses import StreamingResponse

    if not EXPORT_API_KEY or not key or key != EXPORT_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")

    collection_map = {
        "users": users_collection,
        "resources": resources_collection,
        "projects": projects_collection,
        "allocations": allocations_collection,
        "timesheets": timesheets_collection,
        "status_updates": status_updates_collection,
        "risks": risks_collection,
        "holidays": holidays_collection,
        "leaves": leaves_collection,
        "settings": settings_collection,
        "chat_sessions": chat_sessions_collection,
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, coll in collection_map.items():
            try:
                docs = await coll.find().to_list(length=100000)
                serialized = [serialize_doc(d) for d in docs]
            except Exception:
                serialized = []
            zf.writestr(f"{name}.json", _json.dumps(serialized, indent=2, default=str))

        # Add export metadata
        meta = {
            "export_date": datetime.now(timezone.utc).isoformat(),
            "collections": list(collection_map.keys()),
            "record_counts": {},
        }
        for name, coll in collection_map.items():
            try:
                meta["record_counts"][name] = await coll.count_documents({})
            except Exception:
                meta["record_counts"][name] = 0
        zf.writestr("_metadata.json", _json.dumps(meta, indent=2, default=str))

    buf.seek(0)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="dd_planner_export_{timestamp}.zip"'},
    )


# ==================== HEALTH CHECK ====================


@router.get("/api/debug/db-status")
async def debug_db_status():
    """Debug endpoint to check database status"""
    try:
        user_count = await users_collection.count_documents({})
        project_count = await projects_collection.count_documents({})
        resource_count = await resources_collection.count_documents({})
        allocation_count = await allocations_collection.count_documents({})
        
        return {
            "status": "connected",
            "collections": {
                "users": user_count,
                "projects": project_count,
                "resources": resource_count,
                "allocations": allocation_count
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@router.post("/api/debug/seed-database")
async def debug_seed_database():
    """Manual database seeding endpoint for production"""
    try:
        # Check if already seeded
        user_count = await users_collection.count_documents({})
        if user_count > 0:
            return {
                "status": "skipped",
                "message": f"Database already contains {user_count} users. Delete users first to re-seed."
            }
        
        # Create users
        admin_user = {
            "email": "admin@test.com",
            "password_hash": get_password_hash("admin123"),
            "role": UserRole.ADMIN,
            "allowed_project_ids": []
        }
        client_user = {
            "email": "client@test.com",
            "password_hash": get_password_hash("client123"),
            "role": UserRole.CLIENT,
            "allowed_project_ids": []
        }
        await users_collection.insert_one(admin_user)
        await users_collection.insert_one(client_user)
        
        # Create resources first
        resources = [
            {"name": "Henry", "role": "Senior Developer", "standard_capacity": 100, "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=Henry"},
            {"name": "Amrit", "role": "Consultant", "standard_capacity": 100, "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=Amrit"},
            {"name": "Priya", "role": "Project Manager", "standard_capacity": 100, "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=Priya"},
            {"name": "Don", "role": "Manager", "standard_capacity": 100, "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=Don"},
        ]
        resource_results = await resources_collection.insert_many(resources)
        resource_ids = [str(rid) for rid in resource_results.inserted_ids]
        
        # Create users with roles and link to resources
        # Don = Super Admin
        don_user = {
            "email": "don@ddconsult.tech",
            "password_hash": get_password_hash("Welcome123!"),
            "role": UserRole.SUPER_ADMIN,
            "resource_id": resource_ids[3],  # Don resource
            "must_change_password": True,
            "allowed_project_ids": []
        }
        don_result = await users_collection.insert_one(don_user)
        
        # Priya = Admin
        priya_user = {
            "email": "priya@ddconsult.tech",
            "password_hash": get_password_hash("Welcome123!"),
            "role": UserRole.ADMIN,
            "resource_id": resource_ids[2],  # Priya resource
            "must_change_password": True,
            "allowed_project_ids": []
        }
        priya_result = await users_collection.insert_one(priya_user)
        
        # Amrit = Resource User
        amrit_user = {
            "email": "amrit@ddconsult.tech",
            "password_hash": get_password_hash("Welcome123!"),
            "role": UserRole.RESOURCE,
            "resource_id": resource_ids[1],  # Amrit resource
            "must_change_password": True,
            "allowed_project_ids": []
        }
        amrit_result = await users_collection.insert_one(amrit_user)
        
        # Henry = Resource User
        henry_user = {
            "email": "henry@ddconsult.tech",
            "password_hash": get_password_hash("Welcome123!"),
            "role": UserRole.RESOURCE,
            "resource_id": resource_ids[0],  # Henry resource
            "must_change_password": True,
            "allowed_project_ids": []
        }
        henry_result = await users_collection.insert_one(henry_user)
        
        # Demo Client User (no resource link)
        client_user = {
            "email": "client@test.com",
            "password_hash": get_password_hash("client123"),
            "role": UserRole.CLIENT,
            "must_change_password": False,
            "allowed_project_ids": []
        }
        client_result = await users_collection.insert_one(client_user)
        
        # Update resources with user_ids
        await resources_collection.update_one({"_id": resource_results.inserted_ids[3]}, {"$set": {"user_id": str(don_result.inserted_id)}})
        await resources_collection.update_one({"_id": resource_results.inserted_ids[2]}, {"$set": {"user_id": str(priya_result.inserted_id)}})
        await resources_collection.update_one({"_id": resource_results.inserted_ids[1]}, {"$set": {"user_id": str(amrit_result.inserted_id)}})
        await resources_collection.update_one({"_id": resource_results.inserted_ids[0]}, {"$set": {"user_id": str(henry_result.inserted_id)}})
        
        # Create projects with phases
        today = datetime.now()
        projects = [
            {
                "name": "Website Redesign",
                "client_name": "Internal",
                "status": ProjectStatus.ACTIVE,
                "start_date": today - timedelta(days=7),
                "end_date": today + timedelta(days=30),
                "phases": [{"name": "Discovery", "start_date": today - timedelta(days=7), "end_date": today + timedelta(days=30), "status": "Active"}],
                "is_draft": False
            },
            {
                "name": "MVP 1",
                "client_name": "Firerant",
                "status": ProjectStatus.ACTIVE,
                "start_date": today - timedelta(days=13),
                "end_date": today + timedelta(days=17),
                "phases": [{"name": "Execution Phase", "start_date": today - timedelta(days=13), "end_date": today + timedelta(days=17), "status": "Active"}],
                "is_draft": False
            },
            {
                "name": "ASKDD Chatbot",
                "client_name": "Internal",
                "status": ProjectStatus.ACTIVE,
                "start_date": today - timedelta(days=29),
                "end_date": today + timedelta(days=3),
                "phases": [{"name": "Execution Phase", "start_date": today - timedelta(days=29), "end_date": today + timedelta(days=3), "status": "Active"}],
                "is_draft": False
            },
            {
                "name": "FX1 - AI Auditing Module",
                "client_name": "FX1",
                "status": ProjectStatus.ACTIVE,
                "start_date": datetime(2025, 10, 12),
                "end_date": datetime(2026, 4, 24),
                "phases": [{"name": "Execution Phase", "start_date": datetime(2025, 10, 12), "end_date": datetime(2026, 4, 24), "status": "Active"}],
                "is_draft": False
            },
        ]
        project_results = await projects_collection.insert_many(projects)
        project_ids = [str(pid) for pid in project_results.inserted_ids]
        
        # Update client user with allowed projects
        await users_collection.update_one(
            {"email": "client@test.com"},
            {"$set": {"allowed_project_ids": project_ids[:2]}}
        )
        
        # Create allocations
        today_date = today.date()
        allocations = [
            {"resource_id": resource_ids[0], "project_id": project_ids[0], "start_date": datetime.combine(today_date - timedelta(days=7), datetime.min.time()), "end_date": datetime.combine(today_date + timedelta(days=13), datetime.min.time()), "percentage": 50, "confirmation_status": "Pending"},
            {"resource_id": resource_ids[0], "project_id": project_ids[1], "start_date": datetime.combine(today_date - timedelta(days=7), datetime.min.time()), "end_date": datetime.combine(today_date + timedelta(days=13), datetime.min.time()), "percentage": 50, "confirmation_status": "Pending"},
            {"resource_id": resource_ids[1], "project_id": project_ids[0], "start_date": datetime.combine(today_date - timedelta(days=7), datetime.min.time()), "end_date": datetime.combine(today_date + timedelta(days=13), datetime.min.time()), "percentage": 90, "confirmation_status": "Pending"},
            {"resource_id": resource_ids[2], "project_id": project_ids[1], "start_date": datetime.combine(today_date - timedelta(days=7), datetime.min.time()), "end_date": datetime.combine(today_date + timedelta(days=13), datetime.min.time()), "percentage": 60, "confirmation_status": "Pending"},
        ]
        await allocations_collection.insert_many(allocations)
        
        return {
            "status": "success",
            "message": "Database seeded successfully with resource-linked users",
            "counts": {
                "users": 5,
                "resources": len(resources),
                "projects": len(projects),
                "allocations": len(allocations)
            },
            "credentials": {
                "don": "don@ddconsult.tech / Welcome123! (Super Admin)",
                "priya": "priya@ddconsult.tech / Welcome123! (Admin)",
                "amrit": "amrit@ddconsult.tech / Welcome123! (Resource User)",
                "henry": "henry@ddconsult.tech / Welcome123! (Resource User)",
                "client": "client@test.com / client123 (Client Demo)"
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


@router.post("/api/debug/clear-and-reseed")
async def clear_and_reseed():
    """Clear all users and re-seed the database with new role-based users"""
    try:
        # Delete all existing users
        delete_result = await users_collection.delete_many({})
        print(f"[RESEED] Deleted {delete_result.deleted_count} existing users")
        
        # Create resources first
        resources = [
            {"name": "Henry", "role": "Senior Developer", "standard_capacity": 100, "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=Henry"},
            {"name": "Amrit", "role": "Consultant", "standard_capacity": 100, "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=Amrit"},
            {"name": "Priya", "role": "Project Manager", "standard_capacity": 100, "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=Priya"},
            {"name": "Don", "role": "Manager", "standard_capacity": 100, "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=Don"},
        ]
        
        # Check if resources exist, if not create them
        existing_resources = await resources_collection.count_documents({})
        if existing_resources == 0:
            resource_results = await resources_collection.insert_many(resources)
            resource_ids = [str(rid) for rid in resource_results.inserted_ids]
        else:
            # Get existing resource IDs
            cursor = resources_collection.find()
            existing = await cursor.to_list(length=100)
            resource_ids = [str(r["_id"]) for r in existing]
        
        # Create users with roles and link to resources
        # Don = Super Admin
        don_user = {
            "email": "don@ddconsult.tech",
            "password_hash": get_password_hash("Welcome123!"),
            "role": UserRole.SUPER_ADMIN,
            "resource_id": resource_ids[3] if len(resource_ids) > 3 else None,
            "must_change_password": True,
            "allowed_project_ids": []
        }
        don_result = await users_collection.insert_one(don_user)
        
        # Priya = Admin
        priya_user = {
            "email": "priya@ddconsult.tech",
            "password_hash": get_password_hash("Welcome123!"),
            "role": UserRole.ADMIN,
            "resource_id": resource_ids[2] if len(resource_ids) > 2 else None,
            "must_change_password": True,
            "allowed_project_ids": []
        }
        priya_result = await users_collection.insert_one(priya_user)
        
        # Amrit = Resource User
        amrit_user = {
            "email": "amrit@ddconsult.tech",
            "password_hash": get_password_hash("Welcome123!"),
            "role": UserRole.RESOURCE,
            "resource_id": resource_ids[1] if len(resource_ids) > 1 else None,
            "must_change_password": True,
            "allowed_project_ids": []
        }
        amrit_result = await users_collection.insert_one(amrit_user)
        
        # Henry = Resource User
        henry_user = {
            "email": "henry@ddconsult.tech",
            "password_hash": get_password_hash("Welcome123!"),
            "role": UserRole.RESOURCE,
            "resource_id": resource_ids[0] if len(resource_ids) > 0 else None,
            "must_change_password": True,
            "allowed_project_ids": []
        }
        henry_result = await users_collection.insert_one(henry_user)
        
        # Demo Client User (no resource link)
        client_user = {
            "email": "client@test.com",
            "password_hash": get_password_hash("client123"),
            "role": UserRole.CLIENT,
            "must_change_password": False,
            "allowed_project_ids": []
        }
        client_result = await users_collection.insert_one(client_user)
        
        # Update resources with user_ids if we have resource objects
        if existing_resources > 0:
            cursor = resources_collection.find()
            existing = await cursor.to_list(length=100)
            for i, resource in enumerate(existing):
                if i == 0 and henry_result:
                    await resources_collection.update_one({"_id": resource["_id"]}, {"$set": {"user_id": str(henry_result.inserted_id)}})
                elif i == 1 and amrit_result:
                    await resources_collection.update_one({"_id": resource["_id"]}, {"$set": {"user_id": str(amrit_result.inserted_id)}})
                elif i == 2 and priya_result:
                    await resources_collection.update_one({"_id": resource["_id"]}, {"$set": {"user_id": str(priya_result.inserted_id)}})
                elif i == 3 and don_result:
                    await resources_collection.update_one({"_id": resource["_id"]}, {"$set": {"user_id": str(don_result.inserted_id)}})
        
        return {
            "status": "success",
            "message": f"Database re-seeded successfully. Deleted {delete_result.deleted_count} old users, created 5 new users.",
            "users_created": 5,
            "credentials": {
                "don": "don@ddconsult.tech / Welcome123! (Super Admin)",
                "priya": "priya@ddconsult.tech / Welcome123! (Admin)",
                "amrit": "amrit@ddconsult.tech / Welcome123! (Resource User)",
                "henry": "henry@ddconsult.tech / Welcome123! (Resource User)",
                "client": "client@test.com / client123 (Client Demo)"
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


# ============== NOTIFICATION SYSTEM ==============


@router.get("/api/notifications")
async def get_notifications(current_user: dict = Depends(get_current_user)):
    """Get notifications for the current user"""
    cursor = notifications_collection.find(
        {"user_id": current_user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).limit(50)
    notifications = await cursor.to_list(length=50)
    return notifications

@router.get("/api/notifications/unread-count")
async def get_unread_count(current_user: dict = Depends(get_current_user)):
    """Get count of unread notifications"""
    count = await notifications_collection.count_documents({
        "user_id": current_user["id"],
        "read": False
    })
    return {"count": count}

@router.put("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, current_user: dict = Depends(get_current_user)):
    """Mark a notification as read"""
    await notifications_collection.update_one(
        {"id": notification_id, "user_id": current_user["id"]},
        {"$set": {"read": True}}
    )
    return {"success": True}

@router.put("/api/notifications/read-all")
async def mark_all_read(current_user: dict = Depends(get_current_user)):
    """Mark all notifications as read"""
    await notifications_collection.update_many(
        {"user_id": current_user["id"], "read": False},
        {"$set": {"read": True}}
    )
    return {"success": True}

@router.delete("/api/notifications/{notification_id}")
async def delete_notification(notification_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a notification"""
    await notifications_collection.delete_one({
        "id": notification_id,
        "user_id": current_user["id"]
    })
    return {"success": True}

# Helper function to create notification
async def create_notification(user_id: str, notification_type: str, title: str, message: str, 
                             related_id: Optional[str] = None, priority: str = "normal"):
    """Create an in-app notification"""
    notification = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": notification_type,
        "title": title,
        "message": message,
        "related_id": related_id,
        "priority": priority,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await notifications_collection.insert_one(notification)
    return notification


@router.post("/api/reminders/check-timesheets")
async def check_timesheet_reminders(admin: dict = Depends(require_admin)):
    """Check for missing timesheets and send reminders"""
    sydney_now = datetime.now(SYDNEY_TZ)
    
    # Only run on Thursday, Friday, or before Monday deadline
    if sydney_now.weekday() not in [3, 4, 5, 6, 0]:  # Thu, Fri, Sat, Sun, Mon
        return {"message": "Reminders only sent Thu-Mon", "reminders_sent": 0}
    
    # Get current week's Monday
    days_since_monday = sydney_now.weekday()
    week_start = (sydney_now - timedelta(days=days_since_monday)).date()
    week_start_str = week_start.strftime("%Y-%m-%d")
    
    # Get all resources
    resources_cursor = resources_collection.find({}, {"_id": 0})
    resources = await resources_cursor.to_list(length=200)
    
    reminders_sent = 0
    
    for resource in resources:
        resource_id = resource.get("id")
        if not resource_id:
            continue
            
        # Check if timesheet submitted for this week
        existing_timesheet = await timesheets_collection.find_one({
            "resource_id": resource_id,
            "week_start": week_start_str,
            "status": "submitted"
        })
        
        if not existing_timesheet:
            # Find user for this resource
            user = await users_collection.find_one({"resource_id": resource_id})
            if not user:
                # Try by email
                user = await users_collection.find_one({"email": resource.get("email")})
            
            if user:
                user = serialize_doc(user)
                user_id = user.get("id")
                user_email = user.get("email")
                user_name = resource.get("name", user_email)
                
                # Check if we already sent a reminder today
                today_start = datetime.combine(sydney_now.date(), datetime.min.time()).isoformat()
                existing_reminder = await notifications_collection.find_one({
                    "user_id": user_id,
                    "type": "timesheet_reminder",
                    "created_at": {"$gte": today_start}
                })
                
                if not existing_reminder:
                    # Create in-app notification
                    await create_notification(
                        user_id=user_id,
                        notification_type="timesheet_reminder",
                        title="Timesheet Reminder",
                        message=f"Your timesheet for week of {week_start_str} has not been submitted.",
                        priority="high"
                    )
                    
                    # Send email
                    if user_email:
                        await send_email_notification(
                            to_email=user_email,
                            subject=f"Timesheet Reminder - Week of {week_start_str}",
                            html_content=get_timesheet_reminder_email(user_name, week_start_str)
                        )
                    
                    reminders_sent += 1
    
    return {
        "message": f"Timesheet reminder check complete",
        "week": week_start_str,
        "reminders_sent": reminders_sent
    }

@router.post("/api/reminders/check-allocations")
async def check_allocation_reminders(admin: dict = Depends(require_admin)):
    """Check for allocations ending soon and send reminders"""
    sydney_now = datetime.now(SYDNEY_TZ)
    today = sydney_now.date()
    
    # Get allocations ending in the next 14 days
    two_weeks_later = today + timedelta(days=14)
    
    cursor = allocations_collection.find({}, {"_id": 0})
    allocations = await cursor.to_list(length=500)
    
    reminders_sent = 0
    
    for alloc in allocations:
        end_date_str = alloc.get("end_date", "")
        if not end_date_str:
            continue
            
        try:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00')).date()
        except:
            continue
        
        # Check if ending within 14 days but not already ended
        if today <= end_date <= two_weeks_later:
            days_remaining = (end_date - today).days
            
            resource_id = alloc.get("resource_id")
            project_id = alloc.get("project_id")
            
            # Get resource and project details
            resource = await resources_collection.find_one({"id": resource_id}, {"_id": 0})
            project = await projects_collection.find_one({"id": project_id}, {"_id": 0})
            
            if not resource or not project:
                continue
            
            # Find user for this resource
            user = await users_collection.find_one({"resource_id": resource_id})
            if not user:
                user = await users_collection.find_one({"email": resource.get("email")})
            
            if user:
                user = serialize_doc(user)
                user_id = user.get("id")
                user_email = user.get("email")
                user_name = resource.get("name", user_email)
                project_name = project.get("name", "Unknown Project")
                
                # Check if we already sent this specific reminder (same allocation, same week)
                week_start = (sydney_now - timedelta(days=sydney_now.weekday())).date().isoformat()
                existing_reminder = await notifications_collection.find_one({
                    "user_id": user_id,
                    "type": "allocation_ending",
                    "related_id": alloc.get("id"),
                    "created_at": {"$gte": week_start}
                })
                
                if not existing_reminder:
                    # Create in-app notification
                    await create_notification(
                        user_id=user_id,
                        notification_type="allocation_ending",
                        title="Allocation Ending Soon",
                        message=f"Your allocation to {project_name} ends on {end_date.strftime('%b %d, %Y')} ({days_remaining} days)",
                        related_id=alloc.get("id"),
                        priority="normal" if days_remaining > 7 else "high"
                    )
                    
                    # Send email
                    if user_email:
                        await send_email_notification(
                            to_email=user_email,
                            subject=f"Allocation Ending - {project_name}",
                            html_content=get_allocation_ending_email(
                                user_name, project_name, 
                                end_date.strftime('%B %d, %Y'), days_remaining
                            )
                        )
                    
                    reminders_sent += 1
                    
            # Also notify admins about ending allocations
            admin_cursor = users_collection.find({"role": {"$in": ["admin", "super_admin"]}})
            admins = await admin_cursor.to_list(length=20)
            
            for admin_user in admins:
                admin_user = serialize_doc(admin_user)
                admin_id = admin_user.get("id")
                if admin_id == (user.get("id") if user else None):
                    continue  # Don't double-notify if admin is the resource
                    
                existing_admin_reminder = await notifications_collection.find_one({
                    "user_id": admin_id,
                    "type": "allocation_ending_admin",
                    "related_id": alloc.get("id"),
                    "created_at": {"$gte": week_start}
                })
                
                if not existing_admin_reminder:
                    await create_notification(
                        user_id=admin_id,
                        notification_type="allocation_ending_admin",
                        title="Team Allocation Ending",
                        message=f"{resource.get('name')}'s allocation to {project.get('name')} ends on {end_date.strftime('%b %d')}",
                        related_id=alloc.get("id"),
                        priority="normal"
                    )
    
    return {
        "message": "Allocation reminder check complete",
        "reminders_sent": reminders_sent
    }

@router.get("/api/reminders/status")
async def get_reminder_status(admin: dict = Depends(require_admin)):
    """Get status of reminder system"""
    sydney_now = datetime.now(SYDNEY_TZ)
    today = sydney_now.date()
    
    # Count pending timesheets this week
    days_since_monday = sydney_now.weekday()
    week_start = (sydney_now - timedelta(days=days_since_monday)).date()
    week_start_str = week_start.strftime("%Y-%m-%d")
    
    # Get resources with allocations
    resources_cursor = resources_collection.find({}, {"_id": 0})
    resources = await resources_cursor.to_list(length=200)
    
    pending_timesheets = 0
    for resource in resources:
        resource_id = resource.get("id")
        if not resource_id:
            continue
        existing = await timesheets_collection.find_one({
            "resource_id": resource_id,
            "week_start": week_start_str,
            "status": "submitted"
        })
        if not existing:
            pending_timesheets += 1
    
    # Count allocations ending soon
    two_weeks_later = today + timedelta(days=14)
    cursor = allocations_collection.find({}, {"_id": 0})
    allocations = await cursor.to_list(length=500)
    
    ending_soon = 0
    for alloc in allocations:
        end_date_str = alloc.get("end_date", "")
        if not end_date_str:
            continue
        try:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00')).date()
            if today <= end_date <= two_weeks_later:
                ending_soon += 1
        except:
            continue
    
    return {
        "current_week": week_start_str,
        "pending_timesheets": pending_timesheets,
        "allocations_ending_soon": ending_soon,
        "email_configured": bool(RESEND_API_KEY),
        "sydney_time": sydney_now.isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
