from fastapi import APIRouter, Depends, HTTPException
from typing import List
from bson import ObjectId

from database import resources_collection
from models.schemas import ResourceCreate, ResourceUpdate, ResourceResponse
from auth.dependencies import get_current_user, require_admin, require_super_admin
from utils import serialize_doc

router = APIRouter()

@router.get("/api/resources", response_model=List[ResourceResponse])
async def get_resources(current_user: dict = Depends(get_current_user)):
    cursor = resources_collection.find().limit(200)
    resources = await cursor.to_list(length=200)
    return serialize_doc(resources)


@router.post("/api/resources", response_model=ResourceResponse)
async def create_resource(resource: ResourceCreate, admin: dict = Depends(require_super_admin)):
    resource_doc = resource.dict()
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


@router.delete("/api/resources/{resource_id}")
async def delete_resource(resource_id: str, admin: dict = Depends(require_admin)):
    result = await resources_collection.delete_one({"_id": ObjectId(resource_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Resource not found")
    return {"message": "Resource deleted"}

