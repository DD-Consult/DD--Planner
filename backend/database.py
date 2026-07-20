from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
load_dotenv()
import os
import pytz
import resend
import logging

logger = logging.getLogger(__name__)

# Sydney timezone for timesheet restrictions
SYDNEY_TZ = pytz.timezone('Australia/Sydney')

# Database Configuration
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
MONGO_DB_NAME = os.environ.get('DB_NAME') or os.environ.get('MONGO_DB_NAME', 'resource_planner')

# MongoDB Connection with Atlas-compatible settings
# Use try/except to prevent a broken MONGO_URL from crashing the entire server at startup
try:
    client = AsyncIOMotorClient(
        MONGO_URL,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=10000,
        socketTimeoutMS=30000,
        maxPoolSize=50,
        minPoolSize=0,  # Don't pre-connect — let connections be created on demand
        retryWrites=True,
        w='majority'
    )
    db = client[MONGO_DB_NAME]
    logger.info(f"[DB] AsyncIOMotorClient created for: {MONGO_DB_NAME}")
except Exception as e:
    logger.error(f"[DB FATAL] Failed to create MongoDB client: {e}")
    logger.error("[DB FATAL] Falling back to localhost MongoDB (most operations will fail in production)")
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client[MONGO_DB_NAME]

# Collections
users_collection = db.users
resources_collection = db.resources
projects_collection = db.projects
allocations_collection = db.allocations
risks_collection = db.risks
leaves_collection = db.leaves
holidays_collection = db.holidays
status_updates_collection = db.status_updates
timesheets_collection = db.timesheets
settings_collection = db.settings
chat_sessions_collection = db.chat_sessions
notifications_collection = db.notifications
wbs_tasks_collection = db.wbs_tasks
baselines_collection = db.baselines
change_log_collection = db.change_log
pending_actions_collection = db.pending_actions  # AI confirmation tokens (TTL-cleaned)
report_links_collection = db.report_links  # Magic links for client portal
wbs_comments_collection = db.wbs_comments
ai_instructions_collection = db.ai_instructions
ai_feedback_collection = db.ai_feedback
ai_memory_collection = db.ai_memory            # Agent memory (decisions, preferences, context)
ai_health_reports_collection = db.ai_health_reports  # Proactive health monitor reports

# Email Configuration
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

# Security Configuration
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
