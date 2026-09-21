#!/usr/bin/env python3
"""
Investigation script for 502 Bad Gateway issue when accessing /projects/{id}/report?period=whole-project
Tests all potential crash points in the backend routes.
"""

import asyncio
import sys
from bson import ObjectId
from datetime import datetime

# Add backend to path
sys.path.insert(0, '/app/backend')

from database import (
    projects_collection, timesheets_collection, allocations_collection,
    resources_collection, risks_collection, status_updates_collection,
    wbs_tasks_collection
)

# Test project IDs
TEST_PROJECT_IDS = [
    "6a81afb545f7c98ef63971fd",  # Specific ID mentioned in the task
]

async def test_invalid_objectid():
    """Test 1: Invalid ObjectId handling"""
    print("\n=== TEST 1: Invalid ObjectId ===")
    invalid_ids = [
        "invalid123",
        "zzzzzzzzzzzzzzzzzzzzzzzz",
        "6a81afb545f7c98ef63971fz",  # Invalid character 'z'
        "",
        None
    ]
    
    for invalid_id in invalid_ids:
        if invalid_id is None:
            continue
        try:
            is_valid = ObjectId.is_valid(invalid_id)
            print(f"  {invalid_id}: Valid={is_valid}")
            if is_valid:
                try:
                    obj_id = ObjectId(invalid_id)
                    print(f"    ✓ Can create ObjectId: {obj_id}")
                except Exception as e:
                    print(f"    ✗ Cannot create ObjectId: {e}")
        except Exception as e:
            print(f"  {invalid_id}: Error checking validity: {e}")


async def test_project_exists(project_id: str):
    """Test 2: Check if project exists"""
    print(f"\n=== TEST 2: Project Exists ({project_id}) ===")
    try:
        if not ObjectId.is_valid(project_id):
            print(f"  ✗ Invalid ObjectId format: {project_id}")
            return None
            
        project = await projects_collection.find_one({"_id": ObjectId(project_id)})
        if project:
            print(f"  ✓ Project found: {project.get('name', 'Unknown')}")
            print(f"    - Client: {project.get('client_name', 'N/A')}")
            print(f"    - Status: {project.get('status', 'N/A')}")
            print(f"    - Budget: {project.get('budgeted_hours', 'N/A')} hours")
            print(f"    - Phases: {len(project.get('phases', []))}")
            return project
        else:
            print(f"  ✗ Project NOT found with ID: {project_id}")
            return None
    except Exception as e:
        print(f"  ✗ Error finding project: {type(e).__name__}: {e}")
        return None


async def test_allocations_fetch(project_id: str):
    """Test 3: Fetch allocations for project"""
    print(f"\n=== TEST 3: Allocations ({project_id}) ===")
    try:
        cursor = allocations_collection.find({"project_id": project_id})
        allocations = await cursor.to_list(length=1000)
        print(f"  ✓ Allocations fetched: {len(allocations)} records")
        
        if allocations:
            for i, alloc in enumerate(allocations[:3], 1):
                print(f"    {i}. Resource: {alloc.get('resource_id')}, "
                      f"Percentage: {alloc.get('percentage')}%, "
                      f"Start: {alloc.get('start_date')}, "
                      f"End: {alloc.get('end_date')}")
        return allocations
    except Exception as e:
        print(f"  ✗ Error fetching allocations: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return []


async def test_timesheets_fetch(project_id: str):
    """Test 4: Fetch timesheets for project (potential timeout with 10,000 limit)"""
    print(f"\n=== TEST 4: Timesheets ({project_id}) ===")
    try:
        cursor = timesheets_collection.find({"project_id": project_id})
        timesheets = await cursor.to_list(length=10000)
        print(f"  ✓ Timesheets fetched: {len(timesheets)} records")
        
        if timesheets:
            total_planned = sum(t.get("planned_hours", 0) for t in timesheets)
            total_actual = sum(t.get("actual_hours", 0) for t in timesheets)
            print(f"    - Total Planned: {total_planned} hours")
            print(f"    - Total Actual: {total_actual} hours")
            print(f"    - Variance: {total_actual - total_planned} hours")
        
        return timesheets
    except Exception as e:
        print(f"  ✗ Error fetching timesheets: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return []


async def test_division_by_zero(timesheets):
    """Test 5: Division by zero scenarios"""
    print(f"\n=== TEST 5: Division By Zero Protection ===")
    
    total_planned = sum(t.get("planned_hours", 0) for t in timesheets)
    total_actual = sum(t.get("actual_hours", 0) for t in timesheets)
    
    print(f"  Total Planned: {total_planned}")
    print(f"  Total Actual: {total_actual}")
    
    # Test variance percentage calculation
    try:
        variance_hours = total_actual - total_planned
        variance_percentage = (variance_hours / total_planned * 100) if total_planned > 0 else 0
        print(f"  ✓ Variance %: {variance_percentage:.2f}%")
    except Exception as e:
        print(f"  ✗ Variance calculation failed: {e}")
    
    # Test completion rate calculation
    try:
        completion_rate = (total_actual / total_planned * 100) if total_planned > 0 else 0
        print(f"  ✓ Completion Rate: {completion_rate:.2f}%")
    except Exception as e:
        print(f"  ✗ Completion rate calculation failed: {e}")


async def test_budget_conversion(project):
    """Test 6: Budget type conversion"""
    print(f"\n=== TEST 6: Budget Type Conversion ===")
    
    if not project:
        print("  ⊗ Skipped: No project data")
        return
    
    project_budget = project.get("budgeted_hours")
    print(f"  Project Budget (raw): {project_budget} (type: {type(project_budget).__name__})")
    
    try:
        budget_variance = (100 - float(project_budget)) if project_budget else None
        print(f"  ✓ Budget conversion successful: {budget_variance}")
    except Exception as e:
        print(f"  ✗ Budget conversion failed: {type(e).__name__}: {e}")
    
    # Test phase budgets
    phases = project.get("phases", [])
    print(f"\n  Phase Budget Conversions:")
    for i, phase in enumerate(phases, 1):
        phase_budget = phase.get("budgeted_hours")
        print(f"    Phase {i} ({phase.get('name', 'Unknown')}): {phase_budget} (type: {type(phase_budget).__name__ if phase_budget else 'None'})")
        try:
            phase_budget_val = float(phase_budget) if phase_budget else 0
            print(f"      ✓ Converted to: {phase_budget_val}")
        except Exception as e:
            print(f"      ✗ Conversion failed: {e}")


async def test_resources_fetch(resource_ids):
    """Test 7: Fetch resources and check for invalid IDs"""
    print(f"\n=== TEST 7: Resources Fetch ===")
    
    if not resource_ids:
        print("  ⊗ No resource IDs to fetch")
        return {}
    
    print(f"  Resource IDs to fetch: {len(resource_ids)}")
    
    valid_oids = []
    invalid_ids = []
    
    for rid in resource_ids:
        if ObjectId.is_valid(rid):
            valid_oids.append(ObjectId(rid))
        else:
            invalid_ids.append(rid)
    
    if invalid_ids:
        print(f"  ⚠ Invalid resource IDs found: {invalid_ids}")
    
    try:
        resources_cursor = resources_collection.find({"_id": {"$in": valid_oids}})
        all_resources = await resources_cursor.to_list(length=1000)
        print(f"  ✓ Resources fetched: {len(all_resources)}")
        
        resource_map = {str(r["_id"]): r.get("name", "Unknown") for r in all_resources}
        inactive_ids = {str(r["_id"]) for r in all_resources if r.get("active") is False}
        
        print(f"    - Active resources: {len(all_resources) - len(inactive_ids)}")
        print(f"    - Inactive resources: {len(inactive_ids)}")
        
        return resource_map
    except Exception as e:
        print(f"  ✗ Error fetching resources: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {}


async def test_risks_fetch(project_id: str):
    """Test 8: Fetch risks"""
    print(f"\n=== TEST 8: Risks ({project_id}) ===")
    try:
        cursor = risks_collection.find({"project_id": project_id})
        risks = await cursor.to_list(length=1000)
        print(f"  ✓ Risks fetched: {len(risks)} records")
        return risks
    except Exception as e:
        print(f"  ✗ Error fetching risks: {type(e).__name__}: {e}")
        return []


async def test_status_updates_fetch(project_id: str):
    """Test 9: Fetch status updates"""
    print(f"\n=== TEST 9: Status Updates ({project_id}) ===")
    try:
        cursor = status_updates_collection.find({"project_id": project_id})
        updates = await cursor.to_list(length=100)
        print(f"  ✓ Status updates fetched: {len(updates)} records")
        
        if updates:
            latest = max(updates, key=lambda u: u.get('created_at', datetime.min))
            print(f"    Latest update: {latest.get('update_date', 'N/A')}")
            print(f"    Health: {latest.get('health', 'N/A')}")
            print(f"    Progress: {latest.get('actual_progress', 'N/A')}%")
        
        return updates
    except Exception as e:
        print(f"  ✗ Error fetching status updates: {type(e).__name__}: {e}")
        return []


async def test_aggregation_pipeline(project_id: str):
    """Test 10: Aggregation pipeline for actual hours"""
    print(f"\n=== TEST 10: Aggregation Pipeline ({project_id}) ===")
    try:
        pipeline = [
            {"$match": {"project_id": project_id}},
            {"$group": {
                "_id": "$phase_id",
                "total_hours": {"$sum": "$actual_hours"}
            }}
        ]
        
        timesheet_data = await timesheets_collection.aggregate(pipeline).to_list(length=1000)
        print(f"  ✓ Aggregation successful: {len(timesheet_data)} phase groups")
        
        phase_hours_map = {doc["_id"]: doc["total_hours"] for doc in timesheet_data}
        total_project_hours = sum(phase_hours_map.values())
        print(f"    - Total project hours: {total_project_hours}")
        
        for phase_id, hours in list(phase_hours_map.items())[:5]:
            print(f"    - Phase {phase_id}: {hours} hours")
        
        return phase_hours_map
    except Exception as e:
        print(f"  ✗ Aggregation failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {}


async def test_response_size(project_id: str):
    """Test 11: Estimate response size"""
    print(f"\n=== TEST 11: Response Size Estimation ===")
    
    try:
        import json
        
        # Simulate the full response
        project = await projects_collection.find_one({"_id": ObjectId(project_id)})
        allocations = await allocations_collection.find({"project_id": project_id}).to_list(length=1000)
        timesheets = await timesheets_collection.find({"project_id": project_id}).to_list(length=10000)
        risks = await risks_collection.find({"project_id": project_id}).to_list(length=1000)
        updates = await status_updates_collection.find({"project_id": project_id}).to_list(length=100)
        
        # Create mock response
        from utils import serialize_doc
        
        response_data = {
            "project": serialize_doc(project) if project else {},
            "allocations": [serialize_doc(a) for a in allocations],
            "timesheets_count": len(timesheets),
            "risks": [serialize_doc(r) for r in risks],
            "status_updates": [serialize_doc(u) for u in updates],
        }
        
        response_json = json.dumps(response_data, default=str)
        response_size_kb = len(response_json.encode('utf-8')) / 1024
        
        print(f"  Estimated response size: {response_size_kb:.2f} KB")
        
        if response_size_kb > 1024:
            print(f"  ⚠ Large response (> 1 MB): {response_size_kb / 1024:.2f} MB")
        else:
            print(f"  ✓ Response size is reasonable")
        
    except Exception as e:
        print(f"  ✗ Error estimating response size: {type(e).__name__}: {e}")


async def run_all_tests():
    """Run all tests"""
    print("=" * 70)
    print("502 BAD GATEWAY INVESTIGATION")
    print("Testing /projects/{id}/report?period=whole-project endpoint")
    print("=" * 70)
    
    await test_invalid_objectid()
    
    for project_id in TEST_PROJECT_IDS:
        print(f"\n\n{'=' * 70}")
        print(f"TESTING PROJECT: {project_id}")
        print(f"{'=' * 70}")
        
        project = await test_project_exists(project_id)
        allocations = await test_allocations_fetch(project_id)
        timesheets = await test_timesheets_fetch(project_id)
        
        await test_division_by_zero(timesheets)
        await test_budget_conversion(project)
        
        # Extract resource IDs
        resource_ids = list(set(t.get("resource_id") for t in timesheets if t.get("resource_id")))
        resource_map = await test_resources_fetch(resource_ids)
        
        await test_risks_fetch(project_id)
        await test_status_updates_fetch(project_id)
        await test_aggregation_pipeline(project_id)
        await test_response_size(project_id)
    
    print("\n" + "=" * 70)
    print("INVESTIGATION COMPLETE")
    print("=" * 70)
    
    # Check for all projects in database
    print("\n=== BONUS: All Projects in Database ===")
    try:
        all_projects = await projects_collection.find().to_list(length=100)
        print(f"Total projects in database: {len(all_projects)}")
        
        if all_projects:
            print("\nFirst 5 projects:")
            for i, p in enumerate(all_projects[:5], 1):
                print(f"  {i}. ID: {p['_id']}, Name: {p.get('name', 'Unknown')}, "
                      f"Client: {p.get('client_name', 'N/A')}, Status: {p.get('status', 'N/A')}")
    except Exception as e:
        print(f"Error fetching all projects: {e}")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
