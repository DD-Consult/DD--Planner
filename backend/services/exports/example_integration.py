"""
Example integration of ReportLab PDF export with FastAPI routes.

This file demonstrates how to integrate build_project_pdf_reportlab
into the existing DD Planner API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from typing import Optional
from datetime import datetime

from auth.dependencies import get_current_user
from database import get_db
from services.exports.reportlab_export import build_project_pdf_reportlab

router = APIRouter(prefix="/api/exports", tags=["exports"])


@router.get("/projects/{project_id}/reportlab")
async def export_project_reportlab_pdf(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Export a project report as PDF using ReportLab.
    
    This endpoint generates a professional, widescreen PDF report
    with DD Consulting branding and styling.
    
    Args:
        project_id: The project ID to export
        current_user: Authenticated user (from JWT token)
        db: Database connection
    
    Returns:
        PDF file download response
    """
    # Get tenant ID from current user
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Tenant ID not found")
    
    # Fetch project from database
    project_doc = await db.projects.find_one({
        "_id": project_id,
        "tenant_id": tenant_id
    })
    
    if not project_doc:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Convert MongoDB document to dict
    project = {
        'name': project_doc.get('name', 'Untitled Project'),
        'client_name': project_doc.get('client_name', 'N/A'),
        'status': project_doc.get('status', 'Active'),
        'health': project_doc.get('health', 'Green'),
        'start_date': project_doc.get('start_date'),
        'end_date': project_doc.get('end_date'),
        'budgeted_hours': project_doc.get('budgeted_hours'),
        'team_load': project_doc.get('team_load'),
        'executive_summary': project_doc.get('executive_summary'),
        'project_objective': project_doc.get('project_objective'),
    }
    
    # Fetch related data
    allocations = []
    allocations_cursor = db.allocations.find({
        "project_id": project_id,
        "tenant_id": tenant_id
    })
    async for alloc in allocations_cursor:
        # Fetch resource name
        resource_doc = await db.resources.find_one({"_id": alloc.get("resource_id")})
        resource_name = resource_doc.get("name", "Unknown") if resource_doc else "Unknown"
        
        allocations.append({
            'resource_name': resource_name,
            'role': resource_doc.get("role", "N/A") if resource_doc else "N/A",
            'allocation_percent': alloc.get('allocation_percent', 0)
        })
    
    # Fetch risks
    risks = []
    risks_cursor = db.risks.find({
        "project_id": project_id,
        "tenant_id": tenant_id,
        "status": {"$ne": "Closed"}  # Only active risks
    })
    async for risk in risks_cursor:
        risks.append({
            'description': risk.get('description', 'N/A'),
            'impact': risk.get('impact', 'Medium'),
            'probability': risk.get('probability', 'Medium'),
            'status': risk.get('status', 'Active')
        })
    
    # Fetch latest status update
    status_updates = []
    status_update = await db.status_updates.find_one(
        {
            "project_id": project_id,
            "tenant_id": tenant_id
        },
        sort=[("created_at", -1)]  # Most recent first
    )
    
    if status_update:
        status_updates.append({
            'accomplishments': status_update.get('accomplishments', ''),
            'next_steps': status_update.get('next_steps', ''),
        })
    
    # Generate PDF using ReportLab
    pdf_bytes = build_project_pdf_reportlab(
        project=project,
        risks=risks,
        allocations=allocations,
        status_updates=status_updates
    )
    
    # Create safe filename
    safe_project_name = project['name'].replace(' ', '_').replace('/', '_')[:50]
    filename = f"{safe_project_name}_Report_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    # Return PDF as downloadable file
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Length": str(len(pdf_bytes))
        }
    )


@router.get("/projects/{project_id}/reportlab/preview")
async def preview_project_reportlab_pdf(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Preview a project report PDF inline (without download).
    
    Same as export endpoint but with inline content disposition
    for preview in browser.
    
    Note: In production, you would reuse the same data fetching logic
    as export_project_reportlab_pdf. This is a simplified example.
    """
    # Fetch project and generate PDF (simplified for example)
    project_doc = await db.projects.find_one({
        "_id": project_id,
        "tenant_id": current_user.get("tenant_id")
    })
    
    if not project_doc:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project = {
        'name': project_doc.get('name', 'Untitled Project'),
        'client_name': project_doc.get('client_name', 'N/A'),
        'status': project_doc.get('status', 'Active'),
    }
    
    # Generate PDF
    pdf_bytes = build_project_pdf_reportlab(project=project)
    
    # Return PDF for inline viewing
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "inline",  # Display in browser instead of download
            "Content-Length": str(len(pdf_bytes))
        }
    )


# Example: Register this router in your main server.py
# from routes.reportlab_exports import router as reportlab_exports_router
# app.include_router(reportlab_exports_router)
