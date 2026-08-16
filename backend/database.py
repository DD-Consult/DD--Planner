"""
DD Planner database access layer.

STEP 4 of MULTITENANT_PLAN.md — tenant-aware database access.

DESIGN — ContextVar + LazyCollection Proxy Pattern
----------------------------------------------------
This module exposes 20+ collection references (e.g. `projects_collection`,
`users_collection`) that are imported by every route file. In single-tenant
mode these historically pointed directly at the global `resource_planner`
database. In multi-tenant mode we need every collection access to route to
the correct tenant's database instead.

Rather than changing 25 route files (surgical risk), we use a proxy pattern:

    projects_collection = LazyCollection('projects')

`LazyCollection` is a thin proxy: every attribute access (`.find_one`,
`.update_one`, etc.) resolves to the current-request tenant's collection AT
CALL TIME via a `ContextVar`. The `ContextVar` is set by tenant-context
middleware (server.py) on every request based on the resolved tenant, and
`reset` at the end of the request.

Fallback logic (backward compatible with pre-Step-4 code):
    - If MULTI_TENANT_ENABLED is false      -> use the DEFAULT_DB (resource_planner)
    - If ContextVar not set (e.g. startup)  -> use the DEFAULT_DB
    - If ContextVar is set (per-request)    -> use the tenant DB

This means:
    - Zero changes needed in any route file that already uses `X_collection`
    - Startup seeding continues to work (contextvar unset -> default DB)
    - Enabling MULTI_TENANT_ENABLED=true swaps behaviour on a per-request basis

The old global `db` variable is preserved as a module-level attribute
(`_default_db`) for the one file that imports it directly
(`services/knowledge_base.py`). That module will be migrated separately.
"""
from motor.motor_asyncio import AsyncIOMotorClient
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection
from dotenv import load_dotenv
from contextvars import ContextVar
from typing import Optional, Any
load_dotenv()
import os
import pytz
import resend
import logging

logger = logging.getLogger(__name__)

# Sydney timezone for timesheet restrictions
SYDNEY_TZ = pytz.timezone('Australia/Sydney')

# --- Database Configuration ---
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
MONGO_DB_NAME = os.environ.get('DB_NAME') or os.environ.get('MONGO_DB_NAME', 'resource_planner')
MULTI_TENANT_ENABLED = os.environ.get('MULTI_TENANT_ENABLED', 'false').lower() == 'true'

# --- MongoDB Client (shared across default DB + all tenant DBs) ---
# Timeouts tuned for GCP Cloud Run cold-start:
#   - serverSelectionTimeoutMS=3000 fails fast if Atlas is unreachable at boot,
#     preventing the startup event from hanging past Cloud Run's readiness window.
#   - connectTimeoutMS=5000 mirrors the same intent for the initial TCP handshake.
try:
    client = AsyncIOMotorClient(
        MONGO_URL,
        serverSelectionTimeoutMS=3000,
        connectTimeoutMS=5000,
        socketTimeoutMS=30000,
        maxPoolSize=50,
        minPoolSize=0,
        retryWrites=True,
        w='majority'
    )
    _default_db = client[MONGO_DB_NAME]
    logger.info(f"[DB] Client created. Default DB: {MONGO_DB_NAME}. Multi-tenant: {MULTI_TENANT_ENABLED}")
except Exception as e:
    logger.error(f"[DB FATAL] Failed to create MongoDB client: {e}")
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    _default_db = client[MONGO_DB_NAME]

# Public alias for the default DB, kept for backward compatibility with any
# code that does `from database import db`.
db = _default_db

# --- Per-request tenant DB context ---
# Set by tenant middleware (server.py) at the start of each request.
# Auto-propagates across asyncio await boundaries. Auto-reset at end of request.
_current_tenant_db: ContextVar[Optional[AsyncIOMotorDatabase]] = ContextVar(
    "current_tenant_db",
    default=None,
)


def set_current_tenant_db(tenant_db: Optional[AsyncIOMotorDatabase]) -> object:
    """Bind the tenant DB for the current request context.
    
    Returns a token that must be passed to `reset_current_tenant_db` to clean up.
    Typically called by middleware:
    
        token = set_current_tenant_db(client['tenant_ddconsult'])
        try:
            response = await call_next(request)
        finally:
            reset_current_tenant_db(token)
    """
    return _current_tenant_db.set(tenant_db)


def reset_current_tenant_db(token: object) -> None:
    """Restore the previous value of the tenant DB contextvar."""
    _current_tenant_db.reset(token)


def get_current_db() -> AsyncIOMotorDatabase:
    """Return the DB for the current request context.
    
    Resolution:
      1. If MULTI_TENANT_ENABLED and contextvar is set -> tenant DB
      2. Otherwise -> the default (legacy) DB
    
    This is called by LazyCollection on every attribute access. Its behaviour
    is what makes the transition backward-compatible: when the flag is off or
    no tenant is bound (e.g. during startup seeding), everything falls back to
    the current `_default_db` — which is `resource_planner`.
    """
    if MULTI_TENANT_ENABLED:
        tenant_db = _current_tenant_db.get()
        if tenant_db is not None:
            return tenant_db
    return _default_db


def get_db_for_tenant_slug(slug: Optional[str]) -> AsyncIOMotorDatabase:
    """Return an AsyncIOMotorDatabase for a given tenant slug.

    Used by middleware to look up the tenant DB after resolving the tenant
    from the request host. Returns the default DB if slug is None or empty.
    """
    if not slug:
        return _default_db
    # Sanitize the slug -> DB name (mirrors platform_db.tenant_db_name)
    safe = "".join(c if c.isalnum() or c == "_" else "_" for c in slug.lower())
    tenant_prefix = os.environ.get("TENANT_DB_PREFIX", "tenant_")
    return client[f"{tenant_prefix}{safe}"]


class LazyCollection:
    """Proxy that resolves to the current-request tenant's collection on access.
    
    Preserves the async iterator protocol used by Motor cursors and behaves
    identically to a real AsyncIOMotorCollection for every code path the app
    currently uses.
    
    Example:
        projects_collection = LazyCollection('projects')
        
        # This resolves projects_collection to the current tenant's DB right now:
        doc = await projects_collection.find_one({"_id": pid})
    """
    __slots__ = ("_name",)

    def __init__(self, name: str):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def _resolve(self) -> AsyncIOMotorCollection:
        return get_current_db()[self._name]

    def __getattr__(self, attr: str) -> Any:
        # Delegate every attribute/method call to the resolved live collection.
        return getattr(self._resolve(), attr)

    def __getitem__(self, key: Any) -> Any:
        # Support subcollection access, e.g. collection['sub']
        return self._resolve()[key]

    def __repr__(self) -> str:
        return f"<LazyCollection name={self._name!r}>"


# --- Collection references (unchanged interface, now tenant-aware) ---
# All existing `from database import X_collection` imports continue to work.
# Each of these will resolve to the CURRENT request's tenant DB.
users_collection = LazyCollection('users')
resources_collection = LazyCollection('resources')
projects_collection = LazyCollection('projects')
allocations_collection = LazyCollection('allocations')
risks_collection = LazyCollection('risks')
leaves_collection = LazyCollection('leaves')
holidays_collection = LazyCollection('holidays')
status_updates_collection = LazyCollection('status_updates')
timesheets_collection = LazyCollection('timesheets')
settings_collection = LazyCollection('settings')
chat_sessions_collection = LazyCollection('chat_sessions')
notifications_collection = LazyCollection('notifications')
wbs_tasks_collection = LazyCollection('wbs_tasks')
baselines_collection = LazyCollection('baselines')
change_log_collection = LazyCollection('change_log')
pending_actions_collection = LazyCollection('pending_actions')
report_links_collection = LazyCollection('report_links')
wbs_comments_collection = LazyCollection('wbs_comments')
ai_instructions_collection = LazyCollection('ai_instructions')
ai_feedback_collection = LazyCollection('ai_feedback')
ai_memory_collection = LazyCollection('ai_memory')
ai_health_reports_collection = LazyCollection('ai_health_reports')
integration_settings_collection = LazyCollection('integration_settings')
integration_sync_logs_collection = LazyCollection('integration_sync_logs')
ai_knowledge_base_collection = LazyCollection('ai_knowledge_base')

# --- Email Configuration (unchanged) ---
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

# --- Security Configuration (unchanged) ---
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-only-change-in-production')

if 'mongodb+srv' in MONGO_URL or 'mongodb.net' in MONGO_URL:
    if SECRET_KEY == 'dev-only-change-in-production':
        print(
            "WARNING: Production deployment detected but SECRET_KEY is using default value. "
            "Set a secure SECRET_KEY environment variable for security."
        )
        import hashlib
        SECRET_KEY = hashlib.sha256(MONGO_URL.encode()).hexdigest()

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')
EXPORT_API_KEY = os.environ.get('EXPORT_API_KEY')
