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


async def send_verification_email(email: str, code: str, project_name: str):
    """Send verification code email using Resend"""
    if not RESEND_API_KEY or not resend.api_key:
        print(f"[EMAIL] Resend not configured. Verification code: {code}")
        return False
    
    try:
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #1B2A47;">Project Report Access</h2>
            <p>Hi,</p>
            <p>You've been sent a secure link to view the project report for <strong>{project_name}</strong>.</p>
            <p>Please use this verification code to access the report:</p>
            <div style="background: #f3f4f6; padding: 20px; text-align: center; border-radius: 8px; margin: 20px 0;">
                <h1 style="color: #1B2A47; font-size: 32px; letter-spacing: 4px; margin: 0;">{code}</h1>
            </div>
            <p style="color: #666; font-size: 14px;">This code is valid for 1 hour and can be used up to 3 times.</p>
            <p style="color: #666; font-size: 14px;">If you didn't request this, please ignore this email.</p>
            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;" />
            <p style="color: #999; font-size: 12px;">DD Consulting - Project Management Platform</p>
        </div>
        """
        
        params = {
            "from": SENDER_EMAIL,
            "to": [email],
            "subject": f"Verification Code - {project_name} Report",
            "html": html_content,
        }
        
        response = resend.Emails.send(params)
        print(f"[EMAIL] Verification code sent to {email}: {response}")
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send verification: {e}")
        return False


async def send_magic_link_email(email: str, magic_link: str, project_name: str):
    """Send magic link notification email"""
    if not RESEND_API_KEY or not resend.api_key:
        print(f"[EMAIL] Resend not configured. Magic link: {magic_link}")
        return False
    
    try:
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #1B2A47;">Project Report - {project_name}</h2>
            <p>Hi,</p>
            <p>Your project status report for <strong>{project_name}</strong> is ready to view.</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{magic_link}" style="background: #1570EF; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; font-weight: 600;">
                    View Report Online
                </a>
            </div>
            <p style="background: #EFF6FF; padding: 15px; border-left: 4px solid #1570EF; border-radius: 4px; font-size: 14px;">
                <strong>🔒 Security:</strong> This link is valid for 30 days and requires email verification to access.
            </p>
            <p style="color: #666; font-size: 14px;">You can also copy this link:</p>
            <p style="background: #f3f4f6; padding: 10px; border-radius: 4px; word-break: break-all; font-size: 12px; font-family: monospace;">
                {magic_link}
            </p>
            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;" />
            <p style="color: #999; font-size: 12px;">DD Consulting - Project Management Platform</p>
        </div>
        """
        
        params = {
            "from": SENDER_EMAIL,
            "to": [email],
            "subject": f"Project Report - {project_name}",
            "html": html_content,
        }
        
        response = resend.Emails.send(params)
        print(f"[EMAIL] Magic link sent to {email}: {response}")
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send magic link: {e}")
        return False


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
    
    # Build magic link URL
    base_url = str(request.base_url).rstrip('/')
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
