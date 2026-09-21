#!/usr/bin/env python3
"""Test with actual project IDs that exist"""
import asyncio
import sys
sys.path.insert(0, '/app/backend')

from bson import ObjectId
from database import projects_collection, timesheets_collection, allocations_collection

# Use actual project IDs from database
REAL_PROJECT_IDS = [
    "6aabe0a74ae432f22a77d69e",  # Has 3 phases, 200 budget
    "6aabd45b6023b8429321ad6c",  # Website Redesign
]

async def simulate_planned_vs_actual_endpoint(project_id: str):
    """Simulate the /api/reports/planned-vs-actual/project/{project_id} endpoint"""
    print(f"\n{'='*70}")
    print(f"SIMULATING: /api/reports/planned-vs-actual/project/{project_id}")
    print(f"{'='*70}")
    
    try:
        # Step 1: Get the project
        print(f"\n[1] Fetching project...")
        if not ObjectId.is_valid(project_id):
            print(f"  ✗ CRASH POINT: Invalid ObjectId format")
            return
        
        project = await projects_collection.find_one({"_id": ObjectId(project_id)})
        if not project:
            print(f"  ✗ CRASH POINT: Project not found (404 error)")
            return
        
        print(f"  ✓ Project: {project.get('name')}")
        
        # Step 2: Get allocations
        print(f"\n[2] Fetching allocations...")
        cursor = allocations_collection.find({"project_id": project_id})
        allocations = await cursor.to_list(length=1000)
        print(f"  ✓ Allocations: {len(allocations)}")
        
        # Step 3: Get timesheets
        print(f"\n[3] Fetching timesheets...")
        cursor = timesheets_collection.find({"project_id": project_id})
        timesheets = await cursor.to_list(length=10000)
        print(f"  ✓ Timesheets: {len(timesheets)}")
        
        # Step 4: Calculate totals
        print(f"\n[4] Calculating totals...")
        total_planned_hours = 0.0
        total_actual_hours = 0.0
        
        for timesheet in timesheets:
            total_planned_hours += timesheet.get("planned_hours", 0)
            total_actual_hours += timesheet.get("actual_hours", 0)
        
        print(f"  Total Planned: {total_planned_hours}")
        print(f"  Total Actual: {total_actual_hours}")
        
        # Step 5: Division operations (CRASH POINT)
        print(f"\n[5] Performing division operations...")
        variance_hours = total_actual_hours - total_planned_hours
        
        # POTENTIAL CRASH: Division by zero
        if total_planned_hours == 0:
            print(f"  ⚠ WARNING: total_planned_hours is 0 - division by zero protection needed")
        
        variance_percentage = (variance_hours / total_planned_hours * 100) if total_planned_hours > 0 else 0
        completion_rate = (total_actual_hours / total_planned_hours * 100) if total_planned_hours > 0 else 0
        
        print(f"  ✓ Variance %: {variance_percentage}")
        print(f"  ✓ Completion Rate: {completion_rate}")
        
        # Step 6: Budget calculations (CRASH POINT)
        print(f"\n[6] Budget calculations...")
        project_budget = project.get("budgeted_hours")
        print(f"  Project Budget: {project_budget} (type: {type(project_budget).__name__ if project_budget else 'None'})")
        
        # POTENTIAL CRASH: Type conversion
        try:
            budget_variance = (total_actual_hours - float(project_budget)) if project_budget else None
            print(f"  ✓ Budget Variance: {budget_variance}")
        except (TypeError, ValueError) as e:
            print(f"  ✗ CRASH POINT: Budget type conversion failed: {e}")
            return
        
        # POTENTIAL CRASH: Division by zero in percentage
        try:
            budget_used_percentage = (total_actual_hours / float(project_budget) * 100) if project_budget and float(project_budget) > 0 else 0
            print(f"  ✓ Budget Used %: {budget_used_percentage}")
        except (TypeError, ValueError, ZeroDivisionError) as e:
            print(f"  ✗ CRASH POINT: Budget percentage calculation failed: {e}")
            return
        
        # Step 7: Phase breakdown (CRASH POINT)
        print(f"\n[7] Phase breakdown...")
        phases = project.get("phases", [])
        print(f"  Phases: {len(phases)}")
        
        if not phases:
            print(f"  ⚠ WARNING: No phases defined - may cause issues if timesheets reference phase_id")
        
        phase_breakdown = []
        for i, phase in enumerate(phases):
            phase_id = phase.get("id")
            print(f"\n  Phase {i+1}: {phase.get('name')} (ID: {phase_id})")
            
            phase_timesheets = [t for t in timesheets if t.get("phase_id") == phase_id]
            
            phase_planned = sum(t.get("planned_hours", 0) for t in phase_timesheets)
            phase_actual = sum(t.get("actual_hours", 0) for t in phase_timesheets)
            phase_variance = phase_actual - phase_planned
            
            print(f"    Planned: {phase_planned}, Actual: {phase_actual}, Variance: {phase_variance}")
            
            # Phase budget
            phase_budget = phase.get("budgeted_hours")
            print(f"    Budget: {phase_budget} (type: {type(phase_budget).__name__ if phase_budget else 'None'})")
            
            # POTENTIAL CRASH: Type conversion
            try:
                phase_budget_val = float(phase_budget) if phase_budget else 0
                phase_budget_variance = (phase_actual - phase_budget_val) if phase_budget else None
                phase_budget_used_pct = (phase_actual / phase_budget_val * 100) if phase_budget_val > 0 else 0
                print(f"    ✓ Budget Used: {phase_budget_used_pct}%")
            except (TypeError, ValueError, ZeroDivisionError) as e:
                print(f"    ✗ CRASH POINT: Phase budget calculation failed: {e}")
                return
            
            # POTENTIAL CRASH: Division by zero
            try:
                completion_rate_phase = round((phase_actual / phase_planned * 100) if phase_planned > 0 else 0, 2)
                print(f"    ✓ Completion Rate: {completion_rate_phase}%")
            except ZeroDivisionError as e:
                print(f"    ✗ CRASH POINT: Phase completion rate calculation failed: {e}")
                return
        
        print(f"\n{'='*70}")
        print(f"✓ ENDPOINT SIMULATION SUCCESSFUL - No crashes detected")
        print(f"{'='*70}")
        
    except Exception as e:
        print(f"\n{'='*70}")
        print(f"✗ UNEXPECTED CRASH!")
        print(f"{'='*70}")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {e}")
        import traceback
        traceback.print_exc()


async def test_nonexistent_project():
    """Test with the original non-existent project ID"""
    print(f"\n{'='*70}")
    print(f"TESTING NON-EXISTENT PROJECT: 6a81afb545f7c98ef63971fd")
    print(f"{'='*70}")
    
    project_id = "6a81afb545f7c98ef63971fd"
    
    try:
        project = await projects_collection.find_one({"_id": ObjectId(project_id)})
        if not project:
            print(f"\n✗ CRASH POINT IDENTIFIED!")
            print(f"   Project ID {project_id} does not exist")
            print(f"   This would return 404 from GET /api/projects/{project_id}")
            print(f"   Backend should handle this gracefully with HTTPException(status_code=404)")
            print(f"   But if the frontend calls /api/reports/planned-vs-actual/project/{project_id}")
            print(f"   without checking first, it will also return 404")
            print(f"\n   Root cause: Frontend trying to fetch report for non-existent project")
    except Exception as e:
        print(f"Error: {e}")


async def main():
    print("="*70)
    print("502 BAD GATEWAY - ENDPOINT SIMULATION TEST")
    print("="*70)
    
    # Test non-existent project first
    await test_nonexistent_project()
    
    # Test real projects
    for project_id in REAL_PROJECT_IDS:
        await simulate_planned_vs_actual_endpoint(project_id)


if __name__ == "__main__":
    asyncio.run(main())
