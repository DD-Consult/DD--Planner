"""
Public tenant sign-up endpoint (Step 8 of MULTITENANT_PLAN.md).

Allows anyone to create a new tenant workspace via a public form. Unlike the
platform-admin-scoped `POST /api/platform/tenants`, this endpoint:

  - Requires NO authentication
  - Applies stricter validation (slug format, password strength, email format)
  - Rate-limits via IP (deferred to reverse proxy in production; noted here)
  - Optionally requires email verification via Resend (Step 8.2)
  - Creates a "Welcome Project" so the tenant has something to explore
  - Emits `tenant.self_signup` audit event

Endpoints:
    GET  /api/signup/check-slug?slug=X   — public: is this slug available?
    POST /api/signup                      — public: create tenant + owner + welcome project

Response includes a login URL suggesting the tenant's subdomain workspace.
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import uuid
import re
import logging

from platform_db import (
    tenants_collection,
    tenant_modules_collection,
    memberships_collection,
    platform_audit_log_collection,
    tenant_db_name,
    MODULES_CATALOG,
    MULTI_TENANT_ENABLED,
)
from auth.dependencies import get_password_hash
from middleware.tenant_resolver import invalidate_tenant_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/signup", tags=["signup"])

# Reserved slugs that can never be used by tenants
_RESERVED_SLUGS = {
    "admin", "www", "api", "app", "docs", "status", "help",
    "static", "cdn", "mail", "smtp", "support", "billing",
    "root", "system", "platform", "public", "private",
    "test", "demo", "sample", "example",
    "auth", "login", "signup", "logout", "register",
}

# Slug pattern: lowercase alphanumeric with dashes/underscores allowed inside
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,30}[a-z0-9]$")


class SignupRequest(BaseModel):
    slug: str = Field(..., min_length=3, max_length=32)
    company_name: str = Field(..., min_length=2, max_length=100)
    admin_email: EmailStr
    admin_password: str = Field(..., min_length=8, max_length=100)
    admin_name: Optional[str] = Field(None, max_length=100)
    timezone: Optional[str] = "UTC"
    seed_welcome_project: bool = True

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        # Strict validation: reject any non-lowercase input rather than
        # auto-normalizing. This keeps the API contract explicit and prevents
        # confusion where a user sends 'AcmeCorp' but a tenant named 'acmecorp'
        # is silently created.
        v_stripped = v.strip()
        if v_stripped != v_stripped.lower():
            raise ValueError("Slug must be lowercase (letters, digits, dashes, underscores only)")
        if not _SLUG_RE.match(v_stripped):
            raise ValueError(
                "Slug must be 3-32 chars, lowercase letters/digits/dashes/underscores, "
                "starting and ending with alphanumeric."
            )
        if v_stripped in _RESERVED_SLUGS:
            raise ValueError(f"'{v_stripped}' is a reserved slug and cannot be used.")
        return v_stripped

    @field_validator("admin_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        # Basic strength check: at least one letter and one digit
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        return v


class SlugAvailability(BaseModel):
    slug: str
    available: bool
    reason: Optional[str] = None


class SignupResponse(BaseModel):
    tenant_id: str
    tenant_slug: str
    tenant_name: str
    admin_email: str
    login_url: str
    message: str
    verification_required: bool = False


@router.get("/check-slug", response_model=SlugAvailability)
async def check_slug_availability(slug: str):
    """Public endpoint: check if a slug is available for a new tenant.
    
    Applies the same strict validation rules as the POST /api/signup endpoint
    so that users see the same errors here as at submit time.
    """
    original = slug or ""
    slug_stripped = original.strip()
    if not slug_stripped:
        return SlugAvailability(slug=slug_stripped, available=False, reason="Slug cannot be empty")
    # Case check first: uppercase not allowed
    if slug_stripped != slug_stripped.lower():
        return SlugAvailability(
            slug=slug_stripped,
            available=False,
            reason="Slug must be lowercase (letters, digits, dashes, underscores only)",
        )
    if slug_stripped in _RESERVED_SLUGS:
        return SlugAvailability(slug=slug_stripped, available=False, reason=f"'{slug_stripped}' is a reserved slug")
    if not _SLUG_RE.match(slug_stripped):
        return SlugAvailability(
            slug=slug_stripped,
            available=False,
            reason="Slug must be 3-32 chars, lowercase letters/digits/dashes/underscores",
        )
    existing = await tenants_collection.find_one({"slug": slug_stripped})
    if existing:
        return SlugAvailability(slug=slug_stripped, available=False, reason="Already taken")
    return SlugAvailability(slug=slug_stripped, available=True)


def _login_url_for(request: Request, slug: str) -> str:
    """Build a login URL for the newly-created tenant.
    
    In production this points to `https://<slug>.ddplanner.io/login`.
    In dev (no subdomain routing), uses the current origin with a hint header.
    """
    # Prefer X-Forwarded-Proto/Host for accuracy behind Cloud Load Balancer
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    forwarded_host = request.headers.get("x-forwarded-host", "").split(",")[0].strip()
    host = forwarded_host or request.headers.get("host", "")

    # If the host looks like a top-level ddplanner-style domain, swap subdomain
    parts = host.split(":")
    hostname = parts[0]
    port_suffix = f":{parts[1]}" if len(parts) > 1 else ""

    # If hostname already has 3+ dot-parts (i.e., looks like a subdomain),
    # replace the first segment with the new tenant slug.
    if hostname.count(".") >= 2:
        segments = hostname.split(".")
        segments[0] = slug
        new_host = ".".join(segments)
        return f"{scheme}://{new_host}{port_suffix}/login"

    # Fallback: same host + login (dev/preview flow)
    return f"{scheme}://{host}/login"


@router.post("", response_model=SignupResponse, status_code=201)
async def signup_tenant(payload: SignupRequest, request: Request):
    """Public tenant self-service sign-up.
    
    Creates:
      1. Tenant record in `platform_db.tenants`
      2. Full module catalog enabled by default (17 modules) in `tenant_modules`
      3. Owner user (super_admin) in the new `tenant_<slug>` database
      4. Membership record in `platform_db.memberships`
      5. Welcome project in the tenant DB (if seed_welcome_project=True)
      6. Audit log entry (`tenant.self_signup`)
    
    Idempotency: if the slug already exists, returns 409. If the same email
    signed up before (in any tenant), no restriction — emails are scoped per tenant.
    """
    from database import get_db_for_tenant_slug

    slug = payload.slug.lower()

    # Duplicate-slug check (Pydantic doesn't hit DB; validator only handles format)
    existing = await tenants_collection.find_one({"slug": slug})
    if existing:
        raise HTTPException(status_code=409, detail=f"Tenant slug '{slug}' already exists")

    now = datetime.now(timezone.utc)
    tenant_id = str(uuid.uuid4())

    tenant_doc = {
        "_id": tenant_id,
        "slug": slug,
        "name": payload.company_name,
        "db_name": tenant_db_name(slug),
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "owner_email": payload.admin_email,
        "is_default": False,
        "signup_source": "self_service",
        "signup_ip": request.client.host if request.client else None,
        "branding": {
            "logo_url": None,
            "primary_color": "#1B2A47",
            "accent_color": "#C9A84C",
        },
        "settings": {
            "work_week_hours": 40,
            "timezone": payload.timezone or "UTC",
            "work_days": [0, 1, 2, 3, 4],
        },
    }
    await tenants_collection.insert_one(tenant_doc)

    # Enable all modules by default for self-service signup tenants
    tm_docs = [
        {
            "tenant_id": tenant_id,
            "tenant_slug": slug,
            "module_key": m["key"],
            "enabled": True,
            "enabled_at": now,
            "enabled_by": "self_signup",
            "updated_at": now,
        }
        for m in MODULES_CATALOG
    ]
    if tm_docs:
        await tenant_modules_collection.insert_many(tm_docs)

    # Seed the tenant DB with the owner user
    tenant_db = get_db_for_tenant_slug(slug)
    owner_user_doc = {
        "email": payload.admin_email,
        "password_hash": get_password_hash(payload.admin_password),
        "role": "super_admin",
        "allowed_project_ids": [],
        "must_change_password": False,  # they just set it during signup
        "created_at": now,
        "signup_source": "self_service",
    }
    if payload.admin_name:
        owner_user_doc["name"] = payload.admin_name
    result = await tenant_db.users.insert_one(owner_user_doc)
    owner_user_id = str(result.inserted_id)

    # Membership record for platform-level user->tenant tracking
    membership_doc = {
        "_id": str(uuid.uuid4()),
        "user_id": owner_user_id,
        "user_email": payload.admin_email,
        "tenant_id": tenant_id,
        "tenant_slug": slug,
        "role": "super_admin",
        "created_at": now,
        "source": "self_signup",
    }
    await memberships_collection.insert_one(membership_doc)

    # Welcome project — a gentle onboarding cue
    if payload.seed_welcome_project:
        try:
            welcome_project = {
                "name": "Welcome to DD Planner 🎉",
                "client_name": payload.company_name,
                "status": "Active",
                "start_date": now,
                "end_date": now + timedelta(days=30),
                "project_objective": (
                    "This is your first project. Explore the Projects, WBS, and Team tabs "
                    "to see how DD Planner works. Feel free to delete it when you're ready "
                    "to add your own projects."
                ),
                "created_at": now,
                "phases": [
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Getting Started",
                        "start_date": now,
                        "end_date": now + timedelta(days=30),
                        "status": "Active",
                    }
                ],
                "budgeted_hours": 40.0,
                "_seed": "welcome",
            }
            await tenant_db.projects.insert_one(welcome_project)
        except Exception as e:
            # Non-fatal — don't roll back the whole signup for a welcome-project glitch
            logger.warning(f"[SIGNUP] Welcome project seed failed for tenant {slug}: {e}")

    # Audit log
    try:
        await platform_audit_log_collection.insert_one({
            "_id": str(uuid.uuid4()),
            "actor_email": payload.admin_email,
            "action": "tenant.self_signup",
            "tenant_slug": slug,
            "target": None,
            "details": {
                "company_name": payload.company_name,
                "signup_ip": request.client.host if request.client else None,
                "seed_welcome_project": payload.seed_welcome_project,
            },
            "created_at": now,
        })
    except Exception as e:
        logger.warning(f"[SIGNUP] Audit log write failed for tenant {slug}: {e}")

    invalidate_tenant_cache()

    return SignupResponse(
        tenant_id=tenant_id,
        tenant_slug=slug,
        tenant_name=payload.company_name,
        admin_email=payload.admin_email,
        login_url=_login_url_for(request, slug),
        message=(
            f"Welcome to DD Planner, {payload.admin_name or payload.admin_email}! "
            f"Your workspace '{payload.company_name}' is ready. "
            f"Sign in at your workspace URL."
        ),
        verification_required=False,  # Email verification deferred; noted in Step 8.2
    )
