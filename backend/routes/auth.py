from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from bson import ObjectId

from database import users_collection, resources_collection, projects_collection
from models.schemas import UserCreate, UserResponse, TokenWithUser, UserRole, AvatarUpdate, ClientUserCreate, ClientUserUpdate, ClientUserResponse
from auth.dependencies import (
    get_current_user, require_admin, require_admin_or_above,
    verify_password, get_password_hash, create_access_token,
)
from utils import serialize_doc, find_user_resource

router = APIRouter()

@router.post("/api/auth/register", response_model=UserResponse)
async def register(user_data: UserCreate, admin: dict = Depends(require_admin)):
    # Check if user exists
    existing = await users_collection.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_doc = {
        "email": user_data.email,
        "password_hash": get_password_hash(user_data.password),
        "role": user_data.role,
        "allowed_project_ids": user_data.allowed_project_ids
    }
    result = await users_collection.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id
    return serialize_doc(user_doc)


@router.post("/api/auth/login", response_model=TokenWithUser)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await users_collection.find_one({"email": form_data.username})
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user["email"]})
    user_data = serialize_doc(user)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_data
    }


@router.get("/api/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return current_user




@router.put("/api/auth/avatar")
async def update_avatar(
    avatar_update: AvatarUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update user's avatar URL"""
    # Update the user's avatar
    user = await users_collection.find_one({"email": current_user["email"]})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update user avatar
    await users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"avatar_url": avatar_update.avatar_url}}
    )
    
    # Also update the linked resource if exists
    resource = await resources_collection.find_one({"email": current_user["email"]})
    if resource:
        await resources_collection.update_one(
            {"_id": resource["_id"]},
            {"$set": {"avatar_url": avatar_update.avatar_url}}
        )
    
    return {"message": "Avatar updated successfully", "avatar_url": avatar_update.avatar_url}


@router.post("/api/auth/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    current_user: dict = Depends(get_current_user)
):
    """Change user password and clear must_change_password flag"""
    # Verify old password
    user = await users_collection.find_one({"email": current_user["email"]})
    if not verify_password(old_password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect current password"
        )
    
    # Validate new password
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )
    
    # Update password and clear flag
    await users_collection.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "password_hash": get_password_hash(new_password),
                "must_change_password": False
            }
        }
    )
    
    return {"message": "Password changed successfully"}


@router.get("/api/users/me/resource")
async def get_my_resource(current_user: dict = Depends(get_current_user)):
    """Get the resource linked to the current user"""
    # Try resource_id link first
    if current_user.get("resource_id"):
        resource = await resources_collection.find_one({"_id": ObjectId(current_user["resource_id"])})
        if resource:
            return serialize_doc(resource)
    
    # Fallback: try email/name matching (used by find_user_resource)
    resource = await find_user_resource(current_user)
    if resource:
        return serialize_doc(resource)
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No resource linked to this user"
    )


@router.post("/api/admin/create-resource-user")
async def create_resource_user(
    resource_id: str,
    email: str,
    password: str = "Welcome123!",
    admin: dict = Depends(require_admin_or_above)
):
    """Create a user account linked to a resource"""
    # Check if resource exists
    resource = await resources_collection.find_one({"_id": ObjectId(resource_id)})
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found"
        )
    
    # Check if user already exists
    existing = await users_collection.find_one({"email": email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Create user
    user_doc = {
        "email": email,
        "password_hash": get_password_hash(password),
        "role": UserRole.RESOURCE,
        "resource_id": resource_id,
        "must_change_password": True,
        "allowed_project_ids": []
    }
    result = await users_collection.insert_one(user_doc)
    
    # Update resource with user_id
    await resources_collection.update_one(
        {"_id": ObjectId(resource_id)},
        {"$set": {"user_id": str(result.inserted_id)}}
    )
    
    user_doc["_id"] = result.inserted_id
    return serialize_doc(user_doc)


@router.get("/api/admin/users")
async def get_all_users(admin: dict = Depends(require_admin_or_above)):
    """Get all users (admin only)"""
    cursor = users_collection.find({}, {"password_hash": 0}).limit(100)
    users = await cursor.to_list(length=100)
    return serialize_doc(users)


@router.put("/api/admin/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    new_role: str,
    admin: dict = Depends(require_admin_or_above)
):
    """Update user role (admin only)"""
    valid_roles = [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.RESOURCE, UserRole.CLIENT]
    if new_role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {valid_roles}"
        )
    
    result = await users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"role": new_role}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User role updated"}

@router.put("/api/admin/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: str,
    admin: dict = Depends(require_admin_or_above)
):
    """
    Reset a user's password to default 'Welcome123!' and force change on next login.
    Only admins can do this.
    """
    default_password = "Welcome123!"
    password_hash = get_password_hash(default_password)
    
    result = await users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "password_hash": password_hash,
            "must_change_password": True
        }}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
        
    return {"message": f"Password reset to '{default_password}'"}


@router.post("/api/admin/clients", response_model=ClientUserResponse)
async def create_client(
    client_data: ClientUserCreate,
    admin: dict = Depends(require_admin_or_above)
):
    """Create a client user (admin only)"""
    # Check if user already exists
    existing = await users_collection.find_one({"email": client_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create client user document
    client_doc = {
        "email": client_data.email,
        "password_hash": get_password_hash(client_data.password),
        "role": UserRole.CLIENT,
        "company_name": client_data.company_name,
        "allowed_project_ids": client_data.allowed_project_ids,
        "must_change_password": False
    }
    
    result = await users_collection.insert_one(client_doc)
    client_doc["_id"] = result.inserted_id
    
    # Return without password_hash
    client_response = serialize_doc(client_doc)
    client_response.pop("password_hash", None)
    return client_response


@router.get("/api/admin/clients")
async def list_clients(admin: dict = Depends(require_admin_or_above)):
    """Get all client users with project details (admin only)"""
    # Get all client users
    cursor = users_collection.find({"role": UserRole.CLIENT}, {"password_hash": 0})
    clients = await cursor.to_list(length=1000)
    
    # Enrich each client with project details
    enriched_clients = []
    for client_doc in clients:
        client = serialize_doc(client_doc)
        project_details = []
        
        if client.get("allowed_project_ids"):
            for project_id in client["allowed_project_ids"]:
                try:
                    project = await projects_collection.find_one({"_id": ObjectId(project_id)})
                    if project:
                        project_details.append({
                            "id": str(project["_id"]),
                            "name": project["name"]
                        })
                except Exception:
                    continue
        
        client["projects"] = project_details
        enriched_clients.append(client)
    
    return enriched_clients


@router.put("/api/admin/clients/{user_id}", response_model=ClientUserResponse)
async def update_client(
    user_id: str,
    client_update: ClientUserUpdate,
    admin: dict = Depends(require_admin_or_above)
):
    """Update a client user (admin only)"""
    # Check if user exists and is a client
    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.get("role") != UserRole.CLIENT:
        raise HTTPException(status_code=400, detail="User is not a client")
    
    # Build update document
    update_doc = {}
    
    if client_update.company_name is not None:
        update_doc["company_name"] = client_update.company_name
    
    if client_update.allowed_project_ids is not None:
        update_doc["allowed_project_ids"] = client_update.allowed_project_ids
    
    if client_update.password is not None:
        update_doc["password_hash"] = get_password_hash(client_update.password)
    
    if update_doc:
        await users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_doc}
        )
    
    # Get updated user
    updated_user = await users_collection.find_one({"_id": ObjectId(user_id)}, {"password_hash": 0})
    
    # Enrich with project details
    updated_user = serialize_doc(updated_user)
    project_details = []
    
    if updated_user.get("allowed_project_ids"):
        for project_id in updated_user["allowed_project_ids"]:
            try:
                project = await projects_collection.find_one({"_id": ObjectId(project_id)})
                if project:
                    project_details.append({
                        "id": str(project["_id"]),
                        "name": project["name"]
                    })
            except:
                continue
    
    updated_user["projects"] = project_details
    return updated_user


@router.delete("/api/admin/clients/{user_id}")
async def delete_client(
    user_id: str,
    admin: dict = Depends(require_admin_or_above)
):
    """Delete a client user (admin only)"""
    # Check if user exists and is a client
    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.get("role") != UserRole.CLIENT:
        raise HTTPException(status_code=400, detail="Can only delete client users")
    
    # Delete the user
    result = await users_collection.delete_one({"_id": ObjectId(user_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    
    return {"message": "Client deleted"}
