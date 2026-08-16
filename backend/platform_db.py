"""
Platform-level database module for multi-tenant SaaS.

This module manages the platform_db MongoDB database which contains cross-tenant
metadata: tenants registry, platform users, memberships, module catalog, and audit log.

STEP 1 of MULTITENANT_PLAN.md — non-destructive, feature-flag gated.
When MULTI_TENANT_ENABLED=false (default), this module is available but unused
by the application. When true, the tenant resolver middleware (Step 2) will
look up tenants here on every request.
"""
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os
import logging
from datetime import datetime, timezone
import uuid

load_dotenv()
logger = logging.getLogger(__name__)

# --- Configuration ---
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
PLATFORM_DB_NAME = os.environ.get('PLATFORM_DB_NAME', 'platform_db')
TENANT_DB_PREFIX = os.environ.get('TENANT_DB_PREFIX', 'tenant_')
MULTI_TENANT_ENABLED = os.environ.get('MULTI_TENANT_ENABLED', 'false').lower() == 'true'

# --- Client & DB ---
# Timeouts tuned for GCP Cloud Run cold-start behaviour so failed Atlas
# connections don't hang the startup event past the readiness window.
try:
    _platform_client = AsyncIOMotorClient(
        MONGO_URL,
        serverSelectionTimeoutMS=3000,
        connectTimeoutMS=5000,
        socketTimeoutMS=30000,
        maxPoolSize=25,
        minPoolSize=0,
        retryWrites=True,
        w='majority'
    )
    platform_db = _platform_client[PLATFORM_DB_NAME]
    logger.info(f"[PLATFORM_DB] Client created for: {PLATFORM_DB_NAME}")
except Exception as e:
    logger.error(f"[PLATFORM_DB FATAL] Failed to create client: {e}")
    _platform_client = AsyncIOMotorClient('mongodb://localhost:27017')
    platform_db = _platform_client[PLATFORM_DB_NAME]

# --- Platform Collections ---
tenants_collection = platform_db.tenants                    # Tenant registry
platform_users_collection = platform_db.platform_users      # Platform admins
memberships_collection = platform_db.memberships            # user -> tenant (with role)
modules_catalog_collection = platform_db.modules_catalog    # Available modules definition
tenant_modules_collection = platform_db.tenant_modules      # Per-tenant module toggles
platform_audit_log_collection = platform_db.platform_audit_log  # All platform-level actions
subscription_plans_collection = platform_db.subscription_plans  # Plan catalog (future billing)


# --- Tenant DB Factory ---
def tenant_db_name(slug: str) -> str:
    """Returns the MongoDB database name for a tenant slug."""
    # Enforce safe database name: lowercase, alphanumeric + underscore only
    safe_slug = ''.join(c if c.isalnum() or c == '_' else '_' for c in slug.lower())
    return f"{TENANT_DB_PREFIX}{safe_slug}"


def get_tenant_db(slug: str):
    """Returns a Motor database handle for the given tenant slug.
    
    Used by Step 2+ (tenant resolver middleware). In Step 1, this is available
    but unused because MULTI_TENANT_ENABLED=false.
    """
    return _platform_client[tenant_db_name(slug)]


# --- Module Catalog (17 modules per MULTITENANT_PLAN.md) ---
MODULES_CATALOG = [
    # Core (non-toggleable in practice, but present in catalog for completeness)
    {"key": "projects", "name": "Projects & Portfolio", "category": "core", "depends_on": [], "is_core": True,
     "description": "Project lifecycle, phases, portfolio view. Core module — always enabled."},
    {"key": "resources", "name": "Resources & Team", "category": "core", "depends_on": [], "is_core": True,
     "description": "Team member profiles, capacity settings. Core module — always enabled."},

    # PM modules
    {"key": "wbs", "name": "Work Breakdown Structure", "category": "pm", "depends_on": ["projects"], "is_core": False,
     "description": "Hierarchical task tree, milestones, dependencies, baselines."},
    {"key": "milestones", "name": "Milestones", "category": "pm", "depends_on": ["projects", "wbs"], "is_core": False,
     "description": "Zero-hour milestone tasks with diamond markers on Gantt."},
    {"key": "allocations", "name": "Allocations & Capacity", "category": "pm", "depends_on": ["resources", "projects"], "is_core": False,
     "description": "Assign resources to projects with % and date ranges. Capacity heatmaps."},
    {"key": "timesheets", "name": "Timesheets", "category": "pm", "depends_on": ["resources", "projects"], "is_core": False,
     "description": "Weekly timesheet entry, autofill from allocations, approval workflow."},
    {"key": "risks", "name": "Risk Management", "category": "pm", "depends_on": ["projects"], "is_core": False,
     "description": "Per-project risk register with AI polishing."},
    {"key": "status_updates", "name": "Status Updates", "category": "pm", "depends_on": ["projects"], "is_core": False,
     "description": "Weekly project status check-ins with health scoring."},
    {"key": "baselines", "name": "Baselines & Variance", "category": "pm", "depends_on": ["projects"], "is_core": False,
     "description": "Baseline snapshots and variance tracking against plan."},

    # Reporting & sharing
    {"key": "reports", "name": "Reports & Exports", "category": "reporting", "depends_on": ["projects"], "is_core": False,
     "description": "PDF/PPTX exports, budget reconciliation, capacity, utilization reports."},
    {"key": "client_portal", "name": "Client Portal", "category": "reporting", "depends_on": ["projects"], "is_core": False,
     "description": "Read-only client view with magic-link sharing."},

    # AI modules
    {"key": "ai_copilot", "name": "AI Copilot (Chat & Actions)", "category": "ai", "depends_on": [], "is_core": False,
     "description": "Conversational AI chat with role-scoped actions."},
    {"key": "ai_intelligence", "name": "AI Intelligence", "category": "ai", "depends_on": ["ai_copilot"], "is_core": False,
     "description": "Anomaly detection, portfolio forecasting, project retrospectives."},
    {"key": "ai_productivity", "name": "AI Productivity", "category": "ai", "depends_on": ["ai_copilot"], "is_core": False,
     "description": "Kickoff wizard, status drafter, similar projects finder."},
    {"key": "knowledge_base", "name": "AI Knowledge Base", "category": "ai", "depends_on": ["ai_copilot"], "is_core": False,
     "description": "Indexed docs for AI-powered how-to answers with citations."},

    # Integrations
    {"key": "hubspot_integration", "name": "HubSpot CRM Integration", "category": "integrations", "depends_on": ["projects"], "is_core": False,
     "description": "Bi-directional HubSpot deal sync: auto-create projects, push status notes."},
    {"key": "mcp_server", "name": "MCP Server (Agent API)", "category": "integrations", "depends_on": [], "is_core": False,
     "description": "JSON-RPC 2.0 endpoint for external AI agents (Gemini, Copilot)."},
]


# --- Seeding ---
async def seed_platform_if_empty():
    """Idempotent platform DB seeder. Safe to call on every startup.
    
    Creates:
      1. modules_catalog (17 modules) — only if empty
      2. DD Consulting tenant — only if no tenants exist
      3. Default platform_admin (don@ddconsult.tech) — only if no platform users
      4. Enables all 17 modules for DD Consulting tenant — only if not set
    
    Returns a summary dict of what was seeded.
    """
    from auth.dependencies import get_password_hash
    
    summary = {
        "modules_seeded": 0,
        "tenants_seeded": 0,
        "platform_users_seeded": 0,
        "tenant_modules_seeded": 0,
        "already_initialized": False
    }
    now = datetime.now(timezone.utc)
    
    # 1. Seed modules_catalog
    existing_modules = await modules_catalog_collection.count_documents({})
    if existing_modules == 0:
        catalog_docs = []
        for m in MODULES_CATALOG:
            catalog_docs.append({**m, "created_at": now, "updated_at": now})
        if catalog_docs:
            await modules_catalog_collection.insert_many(catalog_docs)
        summary["modules_seeded"] = len(catalog_docs)
        logger.info(f"[PLATFORM_DB] Seeded {len(catalog_docs)} modules into catalog")
    else:
        logger.info(f"[PLATFORM_DB] modules_catalog already has {existing_modules} docs; skipping")
    
    # 2. Seed DD Consulting tenant
    existing_tenants = await tenants_collection.count_documents({})
    dd_tenant_id = None
    if existing_tenants == 0:
        dd_tenant = {
            "_id": str(uuid.uuid4()),
            "slug": "ddconsult",
            "name": "DD Consulting",
            "db_name": tenant_db_name("ddconsult"),
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "owner_email": "don@ddconsult.tech",
            "is_default": True,  # Backward-compat: this tenant receives all requests when flag=off
            "branding": {
                "logo_url": None,
                "primary_color": "#1B2A47",  # DD Navy (matches export cover)
                "accent_color": "#C9A84C"    # DD Gold
            },
            "settings": {
                "work_week_hours": 40,
                "timezone": "Australia/Sydney",
                "work_days": [0, 1, 2, 3, 4]  # Mon-Fri
            }
        }
        await tenants_collection.insert_one(dd_tenant)
        dd_tenant_id = dd_tenant["_id"]
        summary["tenants_seeded"] = 1
        logger.info(f"[PLATFORM_DB] Seeded DD Consulting tenant (slug=ddconsult, id={dd_tenant_id})")
    else:
        dd_doc = await tenants_collection.find_one({"slug": "ddconsult"})
        if dd_doc:
            dd_tenant_id = dd_doc["_id"]
        logger.info(f"[PLATFORM_DB] {existing_tenants} tenant(s) already exist; skipping DD seed")
    
    # 3. Seed default platform admin (Option B: same account as DD super_admin, dual role)
    existing_platform_users = await platform_users_collection.count_documents({})
    if existing_platform_users == 0:
        platform_admin = {
            "_id": str(uuid.uuid4()),
            "email": "don@ddconsult.tech",
            "password_hash": get_password_hash("Welcome123!"),
            "role": "platform_admin",
            "name": "Don (Platform Admin)",
            "must_change_password": True,
            "created_at": now,
            "updated_at": now,
            "disabled": False,
            "linked_tenant_slug": "ddconsult"  # Also has a tenant account in DD
        }
        await platform_users_collection.insert_one(platform_admin)
        summary["platform_users_seeded"] = 1
        logger.info("[PLATFORM_DB] Seeded platform admin: don@ddconsult.tech / Welcome123!")
    else:
        logger.info(f"[PLATFORM_DB] {existing_platform_users} platform user(s) already exist; skipping")
    
    # 4. Enable all modules for DD Consulting tenant
    if dd_tenant_id:
        existing_tenant_modules = await tenant_modules_collection.count_documents({"tenant_id": dd_tenant_id})
        if existing_tenant_modules == 0:
            tm_docs = []
            for m in MODULES_CATALOG:
                tm_docs.append({
                    "tenant_id": dd_tenant_id,
                    "tenant_slug": "ddconsult",
                    "module_key": m["key"],
                    "enabled": True,  # DD gets everything enabled (backward compat)
                    "enabled_at": now,
                    "enabled_by": "system_seed",
                    "updated_at": now
                })
            if tm_docs:
                await tenant_modules_collection.insert_many(tm_docs)
            summary["tenant_modules_seeded"] = len(tm_docs)
            logger.info(f"[PLATFORM_DB] Enabled all {len(tm_docs)} modules for DD Consulting")
        else:
            logger.info(f"[PLATFORM_DB] DD tenant already has {existing_tenant_modules} module entries; skipping")
    
    # Determine if this was a no-op
    summary["already_initialized"] = (
        summary["modules_seeded"] == 0 and
        summary["tenants_seeded"] == 0 and
        summary["platform_users_seeded"] == 0 and
        summary["tenant_modules_seeded"] == 0
    )
    
    return summary


async def create_platform_indexes():
    """Create indexes on platform collections. Idempotent."""
    try:
        await tenants_collection.create_index("slug", unique=True)
        await tenants_collection.create_index("status")
        await platform_users_collection.create_index("email", unique=True)
        await memberships_collection.create_index([("user_id", 1), ("tenant_id", 1)], unique=True)
        await memberships_collection.create_index("tenant_id")
        await modules_catalog_collection.create_index("key", unique=True)
        await tenant_modules_collection.create_index([("tenant_id", 1), ("module_key", 1)], unique=True)
        await tenant_modules_collection.create_index("tenant_id")
        await platform_audit_log_collection.create_index("created_at")
        await platform_audit_log_collection.create_index("tenant_id")
        logger.info("[PLATFORM_DB] Indexes created")
    except Exception as e:
        logger.warning(f"[PLATFORM_DB] Index creation warning (may be pre-existing): {e}")
