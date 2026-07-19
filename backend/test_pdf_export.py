#!/usr/bin/env python3
"""
Quick test for PDF export endpoint.
"""
import asyncio
import sys
from datetime import datetime, timedelta
from bson import ObjectId

# Add backend to path
sys.path.insert(0, '/app/backend')

from database import projects_collection, allocations_collection, timesheets_collection, risks_collection
from routes.reports import export_project_pdf


async def test_pdf_export():
    """Test PDF export with a real project"""
    
    # Find an active project
    project = await projects_collection.find_one({"status": "Active"})
    
    if not project:
        print("❌ No active projects found in database")
        return False
    
    project_id = str(project["_id"])
    print(f"✅ Found project: {project.get('name')} (ID: {project_id})")
    
    # Create a mock current_user (admin role to bypass access checks)
    mock_user = {
        "role": "admin",
        "email": "admin@test.com",
        "allowed_project_ids": []
    }
    
    try:
        # Call the endpoint
        response = await export_project_pdf(project_id, mock_user)
        
        # Check response
        if response.media_type == "application/pdf":
            content_length = len(response.body)
            print(f"✅ PDF generated successfully!")
            print(f"   Size: {content_length:,} bytes ({content_length/1024:.1f} KB)")
            print(f"   Content-Type: {response.media_type}")
            
            # Check headers
            if "Content-Disposition" in response.headers:
                print(f"   Content-Disposition: {response.headers['Content-Disposition']}")
            
            # Save to file for manual inspection
            filename = f"/tmp/test-project-{project_id}.pdf"
            with open(filename, 'wb') as f:
                f.write(response.body)
            print(f"   Saved to: {filename}")
            
            return True
        else:
            print(f"❌ Unexpected media type: {response.media_type}")
            return False
            
    except Exception as e:
        print(f"❌ Error generating PDF: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("=" * 60)
    print("Testing PDF Export Endpoint")
    print("=" * 60)
    
    success = await test_pdf_export()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ Test PASSED: PDF export endpoint is working!")
    else:
        print("❌ Test FAILED: PDF export endpoint has issues")
    print("=" * 60)
    
    return success


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
