"""
DD Planner API — slim entrypoint.
All route handlers live in /routes/*.py; shared logic in /services/, /models/, /auth/, /utils.py, /database.py.
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import uuid
import logging

from database import (
    allocations_collection, projects_collection, users_collection, resources_collection,
    client as mongo_client,
    set_current_tenant_db, reset_current_tenant_db, get_db_for_tenant_slug,
)
from models.schemas import UserRole, ProjectStatus
from auth.dependencies import get_password_hash
from utils import ensure_phase_ids
from middleware.tenant_resolver import resolve_tenant_from_request

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
from routes.ai_memory import router as ai_memory_router
from routes.integrations import router as integrations_router
from routes.mcp_server import router as mcp_router
from routes.knowledge_base import router as knowledge_base_router
from routes.ai_intelligence import router as ai_intelligence_router
from routes.ai_productivity import router as ai_productivity_router
from routes.ai_resource import router as ai_resource_router
from routes.search import router as search_router
from routes.platform import router as platform_router
from routes.platform_auth import router as platform_auth_router
from routes.platform_ops import router as platform_ops_router
from routes.tenant import router as tenant_router
from routes.tenant_signup import router as tenant_signup_router

# Multi-tenant platform layer (Step 1 of MULTITENANT_PLAN.md)
from platform_db import seed_platform_if_empty, create_platform_indexes, MULTI_TENANT_ENABLED

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


# ============================================================================
# STEP 4: Tenant-context middleware
# ----------------------------------------------------------------------------
# For every incoming request, resolve the tenant from the Host header and bind
# the tenant's DB into a ContextVar. LazyCollection objects in database.py
# read this ContextVar at every attribute access, so all downstream code
# automatically operates on the correct tenant's data.
#
# When MULTI_TENANT_ENABLED=false, this middleware is a no-op (the ContextVar
# is never set, and LazyCollection falls back to the default DB).
#
# Paths starting with /api/platform/ are exempted from tenant DB binding —
# they operate directly on platform_db, not any tenant's DB.
# ============================================================================
@app.middleware("http")
async def tenant_context_middleware(request: Request, call_next):
    if not MULTI_TENANT_ENABLED:
        # Backward-compat fast path: never touch ContextVar
        return await call_next(request)

    # Platform admin portal & platform APIs use platform_db directly.
    # Do not bind a tenant DB for these — but still expose the tenant on
    # request.state so introspection endpoints (whoami-tenant) work.
    path = request.url.path or ""
    is_platform_path = path.startswith("/api/platform/")

    try:
        resolution = await resolve_tenant_from_request(request)
    except HTTPException as he:
        # Middleware cannot rely on FastAPI's automatic HTTPException handler,
        # so we surface it as a JSONResponse ourselves.
        logger.info(f"[TENANT MW] {he.status_code} for {path} host={request.headers.get('host', '')}: {he.detail}")
        return JSONResponse(status_code=he.status_code, content={"detail": he.detail})
    except Exception as e:
        logger.warning(f"[TENANT MW] Unexpected resolution error for {path}: {e}")
        return JSONResponse(status_code=500, content={"detail": "Tenant resolution failed"})

    tenant = resolution.get("tenant")
    request.state.tenant = tenant
    request.state.tenant_resolution = resolution

    if is_platform_path or not tenant:
        # No tenant DB binding for platform routes or unresolved requests.
        return await call_next(request)

    # Bind the tenant DB into the ContextVar for the duration of this request.
    tenant_db = get_db_for_tenant_slug(tenant.get("slug"))
    token = set_current_tenant_db(tenant_db)
    try:
        response = await call_next(request)
    finally:
        reset_current_tenant_db(token)
    return response

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
app.include_router(ai_memory_router)
app.include_router(integrations_router)
app.include_router(mcp_router)
app.include_router(knowledge_base_router)
app.include_router(ai_intelligence_router)
app.include_router(ai_productivity_router)
app.include_router(ai_resource_router)
app.include_router(search_router)
app.include_router(platform_router)
app.include_router(platform_auth_router)
app.include_router(platform_ops_router)
app.include_router(tenant_router)
app.include_router(tenant_signup_router)


# ============================================================================
# Readiness flag — set to True after startup_event completes.
# /health returns 503 if not yet ready, so Cloud Run/K8s treat the instance as
# unhealthy during boot and route traffic to warm instances instead. This
# prevents 502s from requests that arrive during the startup window.
# ============================================================================
_app_ready = False


@app.on_event("startup")
async def startup_event():
    """Ultra-fast startup event — spawn everything as background tasks so
    uvicorn starts accepting connections in <1 second.
    
    This is critical on GCP Cloud Run + MongoDB Atlas: each blocking DB
    operation adds ~1s of network latency. Doing dozens of them inline caused
    uvicorn to take 35+ seconds to start serving traffic, during which nginx
    returned 502 for every request.
    
    Now: startup_event returns immediately. All DB initialisation (indexes,
    migrations, seeding, baseline backfill, KB, health monitor) runs in a
    single background task. Requests arriving before the background task
    completes will hit collections that may not have indexes yet (queries
    still work, just slower for the first few) but will NEVER get 502.
    """
    global _app_ready
    import asyncio

    # Flip the readiness flag IMMEDIATELY so /health returns 200 as soon as
    # uvicorn accepts the first connection. Background init happens after.
    _app_ready = True
    print("[STARTUP] Application marked READY — uvicorn will start serving now")

    async def _full_startup_init():
        """All the heavy startup work — runs in background so it doesn't
        block uvicorn from accepting connections."""
        try:
            # --- Core indexes ---
            await allocations_collection.create_index("resource_id")
            await allocations_collection.create_index("project_id")
            await allocations_collection.create_index("start_date")
            await allocations_collection.create_index("end_date")
            try:
                from database import pending_actions_collection
                await pending_actions_collection.create_index("expires_at", expireAfterSeconds=0)
                await pending_actions_collection.create_index("token")
            except Exception as _e:
                print(f"[STARTUP-BG] pending_actions index skipped: {_e}")
            print("[STARTUP-BG] Database indexes created successfully")

            # --- Platform DB layer (multi-tenant) ---
            try:
                await create_platform_indexes()
                platform_seed_result = await seed_platform_if_empty()
                if platform_seed_result.get("already_initialized"):
                    print("[STARTUP-BG] Platform DB already initialized")
                else:
                    print(f"[STARTUP-BG] Platform DB seeded: {platform_seed_result}")
                print(f"[STARTUP-BG] MULTI_TENANT_ENABLED = {MULTI_TENANT_ENABLED} (feature flag)")
            except Exception as pe:
                print(f"[STARTUP-BG] Platform DB init skipped: {pe}")

            # --- Phase migrations & auto-fixes (idempotent) ---
            try:
                projects_without_phases = await projects_collection.count_documents({"phases": {"$exists": False}})
                if projects_without_phases > 0:
                    print(f"[STARTUP-BG] Migrating {projects_without_phases} projects to add default Execution Phase...")
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
                    print(f"[STARTUP-BG] Migration complete: {projects_without_phases} projects updated")

                # Auto-fix phase UUIDs
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
                    print(f"[STARTUP-BG] Auto-fixed phase IDs in {phases_fixed} projects")
            except Exception as pe:
                print(f"[STARTUP-BG] Phase migration skipped: {pe}")

            # --- Seed data if empty (first-time deploys only) ---
            try:
                user_count = await users_collection.count_documents({})
                if user_count == 0:
                    print("[STARTUP-BG] Seeding database with demo data...")
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
                    print("[STARTUP-BG] Database seeded successfully!")
                else:
                    print(f"[STARTUP-BG] Database already contains {user_count} users, skipping seed")
            except Exception as pe:
                print(f"[STARTUP-BG] Seed step skipped: {pe}")

            # --- Baseline backfill (idempotent) ---
            try:
                from services.baselines import backfill_baselines
                n = await backfill_baselines()
                if n:
                    print(f"[STARTUP-BG] Created initial baselines for {n} project(s)")
            except Exception as e:
                print(f"[STARTUP-BG] Baseline backfill skipped due to error: {e}")

            # --- Knowledge base indexing ---
            try:
                from services.knowledge_base import reindex as _kb_reindex, status as _kb_status
                existing = await _kb_status()
                if not existing.get("total_sections"):
                    result = await _kb_reindex()
                    print(f"[STARTUP-BG] AI knowledge base indexed: {result.get('indexed_sections')} sections")
                else:
                    print(f"[STARTUP-BG] AI knowledge base already has {existing.get('total_sections')} sections")
            except Exception as e:
                print(f"[STARTUP-BG] Knowledge base indexing skipped: {e}")

            print("[STARTUP-BG] Full initialisation complete")
        except Exception as e:
            print(f"[STARTUP-BG] Unexpected error during background init: {e}")

    async def _prewarm_playwright():
        try:
            from services.exports.renderer import _ensure_chromium_installed, _get_browser
            _ensure_chromium_installed()
            await _get_browser()
            print("[STARTUP-BG] Playwright Chromium pre-warmed")
        except Exception as e:
            print(f"[STARTUP-BG] Playwright pre-warm failed (retries on demand): {e}")

    async def _periodic_health_monitor():
        """Daily portfolio health check."""
        await asyncio.sleep(3600)
        while True:
            try:
                from services.health_monitor import run_health_monitor
                report = await run_health_monitor(triggered_by="scheduler", save_report=True)
                findings_count = report.get("summary", {}).get("total_findings", 0)
                print(f"[HEALTH MONITOR] Daily check complete — {findings_count} findings")
            except Exception as _hme:
                print(f"[HEALTH MONITOR] Error: {_hme}")
            await asyncio.sleep(24 * 60 * 60)

    # Fire everything as background tasks — none block startup
    asyncio.create_task(_full_startup_init())
    asyncio.create_task(_prewarm_playwright())
    asyncio.create_task(_periodic_health_monitor())


@app.get("/health")
async def health_check():
    """Basic health check. Returns 200 as soon as uvicorn accepts connections.
    
    Because we now flip _app_ready=True BEFORE spawning background init tasks,
    /health returns 200 immediately once uvicorn is serving. Background init
    (DB indexes, seeding, KB) continues in parallel. If DB init hasn't finished
    yet, queries will still work — they'll just be slower on the first call.
    """
    from database import db
    if not _app_ready:
        return JSONResponse(
            status_code=503,
            content={"status": "starting", "message": "Application is initialising, please retry shortly"},
        )
    try:
        await db.command("ping")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        # DB not ready yet — but uvicorn IS serving, so return 200 with degraded status
        # rather than 503 (which would kill Cloud Run's routing). App CAN serve static
        # assets and public endpoints while DB is still cold-starting.
        return {"status": "degraded", "database": str(e)}


@app.get("/api/health")
async def api_health_check():
    """API health check — mirrors /health so both the Cloud Run health probe
    (/health) and the frontend/monitoring pings (/api/health) get the readiness
    signal."""
    from database import db
    if not _app_ready:
        return JSONResponse(
            status_code=503,
            content={"status": "starting", "api": "not_ready"},
        )
    try:
        await db.command("ping")
        return {"status": "healthy", "database": "connected", "api": "operational"}
    except Exception as e:
        # DB not connected yet during background init — still 200 so LB keeps us in rotation
        return {"status": "degraded", "database": str(e), "api": "operational"}
