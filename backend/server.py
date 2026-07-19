"""
DD Planner API — slim entrypoint.
All route handlers live in /routes/*.py; shared logic in /services/, /models/, /auth/, /utils.py, /database.py.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import uuid
import logging

from database import (
    allocations_collection, projects_collection, users_collection, resources_collection,
)
from models.schemas import UserRole, ProjectStatus
from auth.dependencies import get_password_hash
from utils import ensure_phase_ids

# Route modules
from routes.auth import router as auth_router
from routes.resources import router as resources_router
from routes.projects import router as projects_router
from routes.allocations import router as allocations_router
from routes.timesheets import router as timesheets_router
from routes.reports import router as reports_router
from routes.ai import router as ai_router
from routes.admin import router as admin_router
from routes.wbs import router as wbs_router
from routes.comments import router as comments_router
from routes.baselines import router as baselines_router
from routes.budget_reconciliation import router as budget_reconciliation_router
from routes.client_portal import router as client_portal_router
from routes.action_items import router as action_items_router
from routes.ai_instructions import router as ai_instructions_router
from routes.insights import router as insights_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Resource Planning API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(auth_router)
app.include_router(resources_router)
app.include_router(projects_router)
app.include_router(allocations_router)
app.include_router(timesheets_router)
app.include_router(reports_router)
app.include_router(ai_router)
app.include_router(admin_router)
app.include_router(wbs_router)
app.include_router(comments_router)
app.include_router(baselines_router)
app.include_router(budget_reconciliation_router)
app.include_router(client_portal_router)
app.include_router(action_items_router)
app.include_router(ai_instructions_router)
app.include_router(insights_router)


@app.on_event("startup")
async def startup_event():
    """Startup: create indexes, run migrations, seed if empty."""
    try:
        await allocations_collection.create_index("resource_id")
        await allocations_collection.create_index("project_id")
        await allocations_collection.create_index("start_date")
        await allocations_collection.create_index("end_date")
        # AI agent: TTL index on pending_actions so expired confirmation tokens self-delete
        try:
            from database import pending_actions_collection
            await pending_actions_collection.create_index("expires_at", expireAfterSeconds=0)
            await pending_actions_collection.create_index("token")
        except Exception as _e:
            print(f"[STARTUP] pending_actions index skipped: {_e}")
        print("[STARTUP] Database indexes created successfully")

        # MIGRATION: Add default phase to existing projects without phases
        projects_without_phases = await projects_collection.count_documents({"phases": {"$exists": False}})
        if projects_without_phases > 0:
            print(f"[STARTUP] Migrating {projects_without_phases} projects to add default Execution Phase...")
            cursor = projects_collection.find({"phases": {"$exists": False}})
            projects_to_update = await cursor.to_list(length=10000)
            for project in projects_to_update:
                default_phase = {
                    "id": str(uuid.uuid4()),
                    "name": "Execution Phase",
                    "start_date": project["start_date"],
                    "end_date": project["end_date"],
                    "status": "Active"
                }
                await projects_collection.update_one(
                    {"_id": project["_id"]},
                    {"$set": {"phases": [default_phase]}}
                )
            print(f"[STARTUP] Migration complete: {projects_without_phases} projects updated")

        # AUTO-FIX: Ensure all existing phases have UUIDs
        all_projects = await projects_collection.find({"phases": {"$exists": True}}).to_list(length=10000)
        phases_fixed = 0
        for project in all_projects:
            phases = project.get("phases", [])
            needs_fix = any(not p.get("id") or p["id"] in ("", "None", None) for p in phases)
            if needs_fix:
                ensure_phase_ids(phases)
                await projects_collection.update_one(
                    {"_id": project["_id"]},
                    {"$set": {"phases": phases}}
                )
                phases_fixed += 1
        if phases_fixed > 0:
            print(f"[STARTUP] Auto-fixed phase IDs in {phases_fixed} projects")

        # Seed data if empty
        user_count = await users_collection.count_documents({})
        if user_count == 0:
            print("[STARTUP] Seeding database...")
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

            resources = [
                {"name": "Alice Johnson", "role": "Senior Developer", "standard_capacity": 100, "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=Alice"},
                {"name": "Bob Smith", "role": "Designer", "standard_capacity": 100, "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=Bob"},
                {"name": "Carol White", "role": "Project Manager", "standard_capacity": 100, "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=Carol"},
                {"name": "David Lee", "role": "Developer", "standard_capacity": 100, "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=David"},
                {"name": "Emma Davis", "role": "QA Engineer", "standard_capacity": 100, "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=Emma"},
            ]
            resource_results = await resources_collection.insert_many(resources)
            resource_ids = [str(rid) for rid in resource_results.inserted_ids]

            today = datetime.now()
            projects = [
                {"name": "Website Redesign", "client_name": "Acme Corp", "status": ProjectStatus.ACTIVE, "start_date": today, "end_date": today + timedelta(days=30)},
                {"name": "Mobile App", "client_name": "TechStart", "status": ProjectStatus.ACTIVE, "start_date": today, "end_date": today + timedelta(days=45)},
                {"name": "Data Migration", "client_name": "BigData Inc", "status": ProjectStatus.PIPELINE, "start_date": today + timedelta(days=10), "end_date": today + timedelta(days=40)},
                {"name": "Legacy System", "client_name": "OldTech", "status": ProjectStatus.COMPLETED, "start_date": today - timedelta(days=60), "end_date": today - timedelta(days=10)},
            ]
            project_results = await projects_collection.insert_many(projects)
            project_ids = [str(pid) for pid in project_results.inserted_ids]

            await users_collection.update_one(
                {"email": "client@test.com"},
                {"$set": {"allowed_project_ids": project_ids[:2]}}
            )

            today_date = today.date()
            allocations = [
                {"resource_id": resource_ids[0], "project_id": project_ids[0], "start_date": datetime.combine(today_date, datetime.min.time()), "end_date": datetime.combine(today_date + timedelta(days=14), datetime.min.time()), "percentage": 70},
                {"resource_id": resource_ids[0], "project_id": project_ids[1], "start_date": datetime.combine(today_date, datetime.min.time()), "end_date": datetime.combine(today_date + timedelta(days=14), datetime.min.time()), "percentage": 50},
                {"resource_id": resource_ids[1], "project_id": project_ids[0], "start_date": datetime.combine(today_date, datetime.min.time()), "end_date": datetime.combine(today_date + timedelta(days=14), datetime.min.time()), "percentage": 90},
                {"resource_id": resource_ids[2], "project_id": project_ids[1], "start_date": datetime.combine(today_date, datetime.min.time()), "end_date": datetime.combine(today_date + timedelta(days=14), datetime.min.time()), "percentage": 60},
                {"resource_id": resource_ids[3], "project_id": project_ids[0], "start_date": datetime.combine(today_date, datetime.min.time()), "end_date": datetime.combine(today_date + timedelta(days=7), datetime.min.time()), "percentage": 50},
                {"resource_id": resource_ids[3], "project_id": project_ids[2], "start_date": datetime.combine(today_date + timedelta(days=7), datetime.min.time()), "end_date": datetime.combine(today_date + timedelta(days=14), datetime.min.time()), "percentage": 100},
                {"resource_id": resource_ids[4], "project_id": project_ids[1], "start_date": datetime.combine(today_date + timedelta(days=5), datetime.min.time()), "end_date": datetime.combine(today_date + timedelta(days=14), datetime.min.time()), "percentage": 75},
                {"resource_id": resource_ids[1], "project_id": project_ids[2], "start_date": datetime.combine(today_date + timedelta(days=10), datetime.min.time()), "end_date": datetime.combine(today_date + timedelta(days=20), datetime.min.time()), "percentage": 40},
                {"resource_id": resource_ids[2], "project_id": project_ids[2], "start_date": datetime.combine(today_date + timedelta(days=8), datetime.min.time()), "end_date": datetime.combine(today_date + timedelta(days=14), datetime.min.time()), "percentage": 30},
                {"resource_id": resource_ids[4], "project_id": project_ids[0], "start_date": datetime.combine(today_date, datetime.min.time()), "end_date": datetime.combine(today_date + timedelta(days=5), datetime.min.time()), "percentage": 40},
            ]
            await allocations_collection.insert_many(allocations)
            print("[STARTUP] Database seeded successfully!")
        else:
            print(f"[STARTUP] Database already contains {user_count} users, skipping seed")

        print("[STARTUP] Application startup completed successfully")

        # BASELINE BACKFILL — give every existing project an initial baseline.
        # Idempotent: skips projects that already have one. Safe to re-run.
        try:
            from services.baselines import backfill_baselines
            n = await backfill_baselines()
            if n:
                print(f"[STARTUP] Created initial baselines for {n} project(s)")
        except Exception as e:
            print(f"[STARTUP] Baseline backfill skipped due to error: {e}")

        # PLAYWRIGHT PRE-WARM — install Chromium (if missing) and launch the
        # browser on startup so the first export request doesn't time out
        # waiting on a 30-second install + launch. Failures here are
        # non-fatal; the renderer will retry on first export.
        try:
            import asyncio
            from services.exports.renderer import _ensure_chromium_installed, _get_browser

            async def _prewarm():
                try:
                    _ensure_chromium_installed()
                    await _get_browser()
                    print("[STARTUP] Playwright Chromium pre-warmed")
                except Exception as e:
                    print(f"[STARTUP] Playwright pre-warm failed (will retry on demand): {e}")

            asyncio.create_task(_prewarm())
        except Exception as e:
            print(f"[STARTUP] Playwright pre-warm dispatch skipped: {e}")
    except Exception as e:
        print(f"[STARTUP ERROR] Failed to complete startup tasks: {str(e)}")
        print("[STARTUP] Application will continue to run, but database may not be fully initialized")


@app.get("/health")
async def health_check():
    """Basic health check"""
    from database import db
    try:
        await db.command("ping")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": str(e)}


@app.get("/api/health")
async def api_health_check():
    """API health check"""
    from database import db
    try:
        await db.command("ping")
        return {"status": "healthy", "database": "connected", "api": "operational"}
    except Exception as e:
        return {"status": "degraded", "database": str(e), "api": "operational"}
