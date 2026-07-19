"""WBS Task Comments API routes."""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from datetime import datetime, timezone
from bson import ObjectId
import uuid

from database import (
    wbs_tasks_collection, wbs_comments_collection,
    users_collection, notifications_collection,
)
from models.schemas import (
    WBSCommentCreate, WBSCommentUpdate, WBSCommentResponse,
)
from auth.dependencies import get_current_user, require_admin
from utils import serialize_doc

router = APIRouter()


# ============================================================
# Helper Functions
# ============================================================

async def get_user_name(email: str) -> str:
    """Get user's display name from email or users collection."""
    user = await users_collection.find_one({"email": email})
    if user:
        # Try to get name from linked resource
        resource_id = user.get("resource_id")
        if resource_id:
            from database import resources_collection
            resource = await resources_collection.find_one({"_id": ObjectId(resource_id)})
            if resource and resource.get("name"):
                return resource["name"]
    # Fall back to email prefix
    return email.split("@")[0].title()


async def create_mention_notifications(comment_id: str, task_id: str, project_id: str,
                                        author_email: str, author_name: str,
                                        task_name: str, mentions: List[str]):
    """Create notifications for mentioned users."""
    for mentioned_email in mentions:
        if mentioned_email == author_email:
            # Don't notify yourself
            continue
        
        mentioned_user = await users_collection.find_one({"email": mentioned_email})
        if not mentioned_user:
            continue
        
        notification = {
            "id": str(uuid.uuid4()),
            "user_id": serialize_doc(mentioned_user)["id"],
            "type": "wbs_comment_mention",
            "title": "You were mentioned in a comment",
            "message": f"{author_name} mentioned you in task '{task_name}'",
            "related_id": task_id,
            "priority": "normal",
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await notifications_collection.insert_one(notification)


# ============================================================
# Comment Endpoints
# ============================================================

@router.get("/api/wbs/tasks/{task_id}/comments", response_model=List[WBSCommentResponse])
async def get_task_comments(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """List all comments for a task, ordered by created_at ascending."""
    # Verify task exists
    try:
        task = await wbs_tasks_collection.find_one({"_id": ObjectId(task_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID format")
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get all comments for this task
    cursor = wbs_comments_collection.find({"task_id": task_id}).sort("created_at", 1)
    comments = await cursor.to_list(length=1000)
    
    # Resolve author names
    result = []
    for comment in comments:
        comment_doc = serialize_doc(comment)
        # Get author name
        author_name = await get_user_name(comment_doc["author_email"])
        comment_doc["author_name"] = author_name
        result.append(comment_doc)
    
    return result


@router.post("/api/wbs/tasks/{task_id}/comments", response_model=WBSCommentResponse)
async def create_task_comment(
    task_id: str,
    comment_data: WBSCommentCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new comment on a task."""
    # Verify task exists and get task details
    try:
        task = await wbs_tasks_collection.find_one({"_id": ObjectId(task_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID format")
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_doc = serialize_doc(task)
    project_id = task_doc.get("project_id", "")
    task_name = task_doc.get("name", "Untitled Task")
    
    # Create comment document
    comment = {
        "id": str(uuid.uuid4()),
        "task_id": task_id,
        "project_id": project_id,
        "author_email": current_user["email"],
        "content": comment_data.content,
        "mentions": comment_data.mentions or [],
        "is_edited": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": None
    }
    
    await wbs_comments_collection.insert_one(comment)
    
    # Create notifications for mentioned users
    if comment_data.mentions:
        author_name = await get_user_name(current_user["email"])
        await create_mention_notifications(
            comment["id"], task_id, project_id,
            current_user["email"], author_name,
            task_name, comment_data.mentions
        )
    
    # Return comment with author name
    result = serialize_doc(comment)
    result["author_name"] = await get_user_name(current_user["email"])
    
    return result


@router.put("/api/wbs/comments/{comment_id}", response_model=WBSCommentResponse)
async def update_comment(
    comment_id: str,
    comment_data: WBSCommentUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Edit a comment. Only the original author can edit."""
    # Find the comment
    comment = await wbs_comments_collection.find_one({"id": comment_id})
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    comment_doc = serialize_doc(comment)
    
    # Check if current user is the author
    if comment_doc["author_email"] != current_user["email"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own comments"
        )
    
    # Update the comment
    update_data = {
        "content": comment_data.content,
        "is_edited": True,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await wbs_comments_collection.update_one(
        {"id": comment_id},
        {"$set": update_data}
    )
    
    # Get updated comment
    updated_comment = await wbs_comments_collection.find_one({"id": comment_id})
    result = serialize_doc(updated_comment)
    result["author_name"] = await get_user_name(result["author_email"])
    
    return result


@router.delete("/api/wbs/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a comment. Only the original author or admin can delete."""
    # Find the comment
    comment = await wbs_comments_collection.find_one({"id": comment_id})
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    comment_doc = serialize_doc(comment)
    
    # Check if current user is the author or admin
    is_author = comment_doc["author_email"] == current_user["email"]
    is_admin = current_user.get("role") in ["admin", "super_admin"]
    
    if not is_author and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own comments or must be an admin"
        )
    
    # Delete the comment
    await wbs_comments_collection.delete_one({"id": comment_id})
    
    return None


@router.get("/api/wbs/tasks/{task_id}/comments/count")
async def get_task_comment_count(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Return just the count of comments for a task. Lightweight for badge display."""
    count = await wbs_comments_collection.count_documents({"task_id": task_id})
    return {"task_id": task_id, "count": count}


@router.get("/api/projects/{project_id}/wbs/comments/counts")
async def get_project_comment_counts(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Return comment counts for ALL tasks in a project (for showing badges in the task list)."""
    # Get all tasks for this project
    cursor = wbs_tasks_collection.find({"project_id": project_id})
    tasks = await cursor.to_list(length=10000)
    
    if not tasks:
        return {}
    
    # Get task IDs
    task_ids = [serialize_doc(task)["id"] for task in tasks]
    
    # Get comment counts for all tasks in one aggregation
    pipeline = [
        {"$match": {"task_id": {"$in": task_ids}}},
        {"$group": {"_id": "$task_id", "count": {"$sum": 1}}}
    ]
    
    counts_cursor = wbs_comments_collection.aggregate(pipeline)
    counts_list = await counts_cursor.to_list(length=10000)
    
    # Build result dict: {task_id: count}
    result = {item["_id"]: item["count"] for item in counts_list}
    
    # Ensure all tasks have an entry (even if 0 comments)
    for task_id in task_ids:
        if task_id not in result:
            result[task_id] = 0
    
    return result
