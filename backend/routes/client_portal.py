"""Client Portal Routes - Magic Links for secure report sharing"""
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timedelta, timezone
from typing import Optional
import secrets
import random
from bson import ObjectId

from database import (
    report_links_collection, projects_collection, resend, 
    SENDER_EMAIL, RESEND_API_KEY
)
from models.schemas import ReportLinkCreate, ReportLinkResponse, VerifyCodeRequest
from auth.dependencies import get_current_user, require_admin
from utils import serialize_doc

router = APIRouter()


# ============================================================
# Utility Functions
# ============================================================

def generate_secure_token(length: int = 64) -> str:
    """Generate a cryptographically secure random token"""
    return secrets.token_urlsafe(length)


def generate_verification_code() -> str:
    """Generate a 6-digit verification code"""
    return str(random.randint(100000, 999999))


def _public_base_url(request: Request) -> str:
    """Derive the public-facing base URL from forwarded headers (for ingress/proxy).
    
    Behind a Kubernetes ingress or proxy, request.base_url reflects the internal
    pod address. This helper reconstructs the public origin from x-forwarded-*
    headers set by the ingress.
    
    Falls back to request.base_url if headers are not present (local/test env).
    """
    proto = request.headers.get("x-forwarded-proto")
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    
    if host:
        # x-forwarded-host may contain comma-separated list; take the first
        host = host.split(",")[0].strip()
        proto = (proto.split(",")[0].strip() if proto else None) or "https"
        return f"{proto}://{host}"
    
    # Fallback to request.base_url if no headers present (e.g. local/tests)
    return str(request.base_url).rstrip('/')


async def send_verification_email(email: str, code: str, project_name: str):
    """Send verification code email via the active method + editable template/branding.
    Returns (sent, message). Best-effort."""
    from services.email_config import send_email, get_email_settings_block
    from services.email_templates import render_email
    email_block = await get_email_settings_block()
    subject, html = render_email(email_block, "report_code", {
        "project_name": project_name,
        "code": code,
    })
    return await send_email(email, subject, html, email_type="report_code", related_label=project_name)


async def send_magic_link_email(email: str, magic_link: str, project_name: str):
    """Send magic link email via the active method + editable template/branding.
    Returns (sent, message). Best-effort."""
    from services.email_config import send_email, get_email_settings_block
    from services.email_templates import render_email
    email_block = await get_email_settings_block()
    subject, html = render_email(email_block, "report_link", {
        "project_name": project_name,
        "link": magic_link,
    })
    return await send_email(email, subject, html, email_type="report_link", related_label=project_name)


# ============================================================
# API Endpoints
# ============================================================

@router.post("/api/reports/magic-link", response_model=ReportLinkResponse)
async def create_magic_link(
    data: ReportLinkCreate,
    request: Request,
    current_user: dict = Depends(require_admin)
):
    """Generate a secure magic link for client report access
    
    - Creates a unique token
    - Sends verification code to recipient email
    - Expires in 30 days
    - Tracks views and last access
    """
    # Verify project exists
    project = await projects_collection.find_one({"_id": ObjectId(data.project_id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Generate secure token and verification code
    token = generate_secure_token(64)
    verification_code = generate_verification_code()
    
    # Calculate expiry (30 days from now)
    created_at = datetime.now(timezone.utc)
    expires_at = created_at + timedelta(days=30)
    
    # Build magic link URL (using public-facing origin from forwarded headers)
    base_url = _public_base_url(request)
    magic_link = f"{base_url}/portal/{token}"
    
    # Create report link document
    link_doc = {
        "project_id": data.project_id,
        "token": token,
        "report_type": data.report_type,
        "report_period": data.report_period,
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "created_by": current_user.get("email", ""),
        "recipient_email": data.recipient_email,
        "verification_code": verification_code,
        "verification_attempts": 0,
        "is_active": True,
        "view_count": 0,
        "last_viewed_at": None,
    }
    
    result = await report_links_collection.insert_one(link_doc)
    link_doc["_id"] = result.inserted_id
    
    # Send verification code email
    await send_verification_email(
        data.recipient_email,
        verification_code,
        project.get("name", "Project")
    )
    
    # Send magic link email
    await send_magic_link_email(
        data.recipient_email,
        magic_link,
        project.get("name", "Project")
    )
    
    # Return response
    response_data = serialize_doc(link_doc)
    response_data["magic_link"] = magic_link
    return response_data


@router.get("/api/portal/verify/{token}")
async def verify_token(token: str):
    """Validate token and send verification code
    
    Returns project info if token is valid
    Does NOT grant access yet - requires verification code
    """
    link = await report_links_collection.find_one({"token": token})
    
    if not link:
        raise HTTPException(status_code=404, detail="Invalid link")
    
    # Check if expired
    expires_at = datetime.fromisoformat(link["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=410, detail="Link expired")
    
    # Check if still active
    if not link.get("is_active", True):
        raise HTTPException(status_code=403, detail="Link has been revoked")
    
    # Get project info
    project = await projects_collection.find_one({"_id": ObjectId(link["project_id"])})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Resend verification code
    await send_verification_email(
        link["recipient_email"],
        link["verification_code"],
        project.get("name", "Project")
    )
    
    return {
        "valid": True,
        "project_name": project.get("name"),
        "recipient_email": link["recipient_email"],
        "expires_at": link["expires_at"],
    }


@router.post("/api/portal/verify/{token}/confirm")
async def confirm_verification(token: str, data: VerifyCodeRequest):
    """Verify the 6-digit code and grant access
    
    Rate limiting: 3 attempts per hour
    Returns access token for fetching report
    """
    link = await report_links_collection.find_one({"token": token})
    
    if not link:
        raise HTTPException(status_code=404, detail="Invalid link")
    
    # Check rate limiting (3 attempts max)
    if link.get("verification_attempts", 0) >= 3:
        raise HTTPException(
            status_code=429, 
            detail="Too many verification attempts. Please request a new link."
        )
    
    # Verify code
    if link.get("verification_code") != data.verification_code:
        # Increment attempt counter
        await report_links_collection.update_one(
            {"_id": link["_id"]},
            {"$inc": {"verification_attempts": 1}}
        )
        raise HTTPException(status_code=401, detail="Invalid verification code")
    
    # Success! Reset attempts and mark as verified
    await report_links_collection.update_one(
        {"_id": link["_id"]},
        {"$set": {"verification_attempts": 0, "verified_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {
        "verified": True,
        "message": "Access granted"
    }


@router.get("/api/portal/report/{token}")
async def get_portal_report(token: str):
    """Fetch report data for verified token
    
    Increments view count and updates last_viewed_at
    Returns project data for report display
    """
    link = await report_links_collection.find_one({"token": token})
    
    if not link:
        raise HTTPException(status_code=404, detail="Invalid link")
    
    # Check if verified (must have verified_at timestamp)
    if not link.get("verified_at"):
        raise HTTPException(status_code=403, detail="Email verification required")
    
    # Check if expired
    expires_at = datetime.fromisoformat(link["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=410, detail="Link expired")
    
    # Check if active
    if not link.get("is_active", True):
        raise HTTPException(status_code=403, detail="Link has been revoked")
    
    # Get project data
    project = await projects_collection.find_one({"_id": ObjectId(link["project_id"])})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Update view count and last viewed
    await report_links_collection.update_one(
        {"_id": link["_id"]},
        {
            "$inc": {"view_count": 1},
            "$set": {"last_viewed_at": datetime.now(timezone.utc).isoformat()}
        }
    )
    
    # Return project data (serialized)
    project_data = serialize_doc(project)
    
    return {
        "project": project_data,
        "report_type": link.get("report_type"),
        "report_period": link.get("report_period"),
        "view_count": link.get("view_count", 0) + 1,
        "created_at": link.get("created_at"),
        "expires_at": link.get("expires_at"),
    }


@router.get("/api/admin/report-links")
async def list_report_links(
    project_id: Optional[str] = None,
    current_user: dict = Depends(require_admin)
):
    """List all report links (admin only)
    
    Optionally filter by project_id
    """
    query = {}
    if project_id:
        query["project_id"] = project_id
    
    links = await report_links_collection.find(query).sort("created_at", -1).to_list(length=100)
    
    return [serialize_doc(link) for link in links]


@router.delete("/api/admin/report-links/{link_id}")
async def revoke_report_link(
    link_id: str,
    current_user: dict = Depends(require_admin)
):
    """Revoke a report link (admin only)
    
    Sets is_active to False, preventing further access
    """
    result = await report_links_collection.update_one(
        {"_id": ObjectId(link_id)},
        {"$set": {"is_active": False, "revoked_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Link not found")
    
    return {"message": "Link revoked successfully"}
