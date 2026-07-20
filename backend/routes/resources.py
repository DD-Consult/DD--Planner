from fastapi import APIRouter, Depends, HTTPException
from typing import List
from bson import ObjectId

from database import (
    resources_collection, allocations_collection, timesheets_collection,
    projects_collection, users_collection,
)
from models.schemas import ResourceCreate, ResourceUpdate, ResourceResponse
from auth.dependencies import get_current_user, require_admin, require_super_admin
from utils import serialize_doc, deactivate_resource_core, reactivate_resource_core

router = APIRouter()

@router.get("/api/resources", response_model=List[ResourceResponse])
async def get_resources(current_user: dict = Depends(get_current_user)):
    cursor = resources_collection.find().limit(200)
    resources = await cursor.to_list(length=200)
    return serialize_doc(resources)


@router.post("/api/resources", response_model=ResourceResponse)
async def create_resource(resource: ResourceCreate, admin: dict = Depends(require_super_admin)):
    resource_doc = resource.dict()
    resource_doc["active"] = True
    result = await resources_collection.insert_one(resource_doc)
    resource_doc["_id"] = result.inserted_id
    return serialize_doc(resource_doc)


@router.put("/api/resources/{resource_id}", response_model=ResourceResponse)
async def update_resource(resource_id: str, resource: ResourceUpdate, admin: dict = Depends(require_admin)):
    update_data = {k: v for k, v in resource.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")
    
    result = await resources_collection.find_one_and_update(
        {"_id": ObjectId(resource_id)},
        {"$set": update_data},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Resource not found")
    return serialize_doc(result)


@router.post("/api/resources/{resource_id}/deactivate")
async def deactivate_resource(resource_id: str, admin: dict = Depends(require_admin)):
    """Soft-delete: preserves history, ends future allocations today, disables linked logins."""
    result = await deactivate_resource_core(resource_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message", "Resource not found"))
    return result


@router.post("/api/resources/{resource_id}/reactivate")
async def reactivate_resource(resource_id: str, admin: dict = Depends(require_admin)):
    """Reactivate a resource and re-enable linked login accounts."""
    result = await reactivate_resource_core(resource_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message", "Resource not found"))
    return result


@router.delete("/api/resources/{resource_id}")
async def delete_resource(resource_id: str, admin: dict = Depends(require_admin)):
    """Hard delete — only allowed for resources with NO history. Otherwise deactivate."""
    res = await resources_collection.find_one({"_id": ObjectId(resource_id)})
    if not res:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    alloc_count = await allocations_collection.count_documents({"resource_id": resource_id})
    ts_count = await timesheets_collection.count_documents({"resource_id": resource_id})
    lead_count = await projects_collection.count_documents({"project_lead_id": resource_id})
    if alloc_count or ts_count or lead_count:
        raise HTTPException(
            status_code=409,
            detail=(
                f"'{res.get('name')}' has history ({alloc_count} allocation(s), {ts_count} timesheet(s), "
                f"lead of {lead_count} project(s)). Deactivate instead to preserve history."
            ),
        )
    
    await resources_collection.delete_one({"_id": ObjectId(resource_id)})
    await users_collection.update_many({"resource_id": resource_id}, {"$unset": {"resource_id": ""}})
    return {"message": "Resource deleted"}
