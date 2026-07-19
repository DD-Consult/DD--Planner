"""Email notification service and templates."""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import resend

from database import RESEND_API_KEY, SENDER_EMAIL, notifications_collection

logger = logging.getLogger(__name__)


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


async def send_email_notification(to_email: str, subject: str, html_content: str):
    """Send an email notification via Resend"""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not configured, skipping email")
        return None

    try:
        params = {
            "from": SENDER_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html_content
        }
        result = await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Email sent to {to_email}: {result.get('id')}")
        return result
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return None


def get_timesheet_reminder_email(user_name: str, week_start: str):
    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f5f5f5;">
        <div style="max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px;">
            <h2 style="color: #1570EF;">Timesheet Reminder</h2>
            <p>Hi {user_name},</p>
            <p>This is a friendly reminder that your timesheet for the week of <strong>{week_start}</strong> has not been submitted yet.</p>
            <p>Please submit your timesheet before the deadline (Monday 12:00 PM Sydney time).</p>
            <p style="margin-top: 30px;">
                <a href="#" style="background: #1570EF; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
                    Submit Timesheet
                </a>
            </p>
            <p style="color: #666; font-size: 12px; margin-top: 30px;">
                This is an automated reminder from DD Planner.
            </p>
        </div>
    </body>
    </html>
    """


def get_allocation_ending_email(user_name: str, project_name: str, end_date: str, days_remaining: int):
    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f5f5f5;">
        <div style="max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px;">
            <h2 style="color: #F4B740;">Allocation Ending Soon</h2>
            <p>Hi {user_name},</p>
            <p>Your allocation to <strong>{project_name}</strong> will end on <strong>{end_date}</strong> ({days_remaining} days remaining).</p>
            <p>Please coordinate with your manager regarding your next assignment.</p>
            <p style="color: #666; font-size: 12px; margin-top: 30px;">
                This is an automated notification from DD Planner.
            </p>
        </div>
    </body>
    </html>
    """
