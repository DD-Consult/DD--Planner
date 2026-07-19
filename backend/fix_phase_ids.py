#!/usr/bin/env python3
"""
Migration script to fix phase IDs in existing projects.
Ensures all phases have unique UUID identifiers.
"""
import os
import uuid
from pymongo import MongoClient
from bson import ObjectId

# Connect to MongoDB
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
MONGO_DB_NAME = os.environ.get('MONGO_DB_NAME', 'resource_planner')

client = MongoClient(MONGO_URL)
db = client[MONGO_DB_NAME]
projects_collection = db.projects
timesheets_collection = db.timesheets
allocations_collection = db.allocations

def main():
    print("🔧 Starting Phase ID Migration...")
    print("=" * 60)
    
    # Get all projects
    projects = list(projects_collection.find())
    print(f"\nFound {len(projects)} projects")
    
    projects_updated = 0
    phases_fixed = 0
    
    for project in projects:
        phases = project.get('phases', [])
        if not phases:
            continue
        
        # Track old phase names to new IDs for this project
        phase_name_to_id = {}
        updated_phases = []
        needs_update = False
        
        for phase in phases:
            phase_id = phase.get('id')
            phase_name = phase.get('name', 'Unknown')
            
            # If phase has no ID or ID is None, generate new UUID
            if not phase_id or phase_id == 'None':
                new_id = str(uuid.uuid4())
                phase['id'] = new_id
                phase_name_to_id[phase_name] = new_id
                needs_update = True
                phases_fixed += 1
                print(f"  ✓ Fixed phase '{phase_name}' in project '{project.get('name')}': {new_id}")
            else:
                phase_name_to_id[phase_name] = phase_id
            
            updated_phases.append(phase)
        
        if needs_update:
            # Update the project
            projects_collection.update_one(
                {'_id': project['_id']},
                {'$set': {'phases': updated_phases}}
            )
            projects_updated += 1
            
            # Update timesheets that reference None phase_id for this project
            # Match by project_id and phase_id=None, then try to infer from dates
            timesheets = list(timesheets_collection.find({
                'project_id': str(project['_id']),
                'phase_id': None
            }))
            
            for timesheet in timesheets:
                # Try to match timesheet to a phase by checking if week falls within phase dates
                week_start = timesheet.get('week_start_date')
                matched_phase_id = None
                
                if week_start:
                    for phase in updated_phases:
                        phase_start = phase.get('start_date')
                        phase_end = phase.get('end_date')
                        
                        if phase_start and phase_end:
                            # Convert to comparable dates
                            from datetime import datetime
                            if isinstance(week_start, str):
                                week_start = datetime.fromisoformat(week_start.replace('Z', '+00:00'))
                            if isinstance(phase_start, str):
                                phase_start = datetime.fromisoformat(phase_start.replace('Z', '+00:00'))
                            elif not isinstance(phase_start, datetime):
                                phase_start = phase_start
                            if isinstance(phase_end, str):
                                phase_end = datetime.fromisoformat(phase_end.replace('Z', '+00:00'))
                            elif not isinstance(phase_end, datetime):
                                phase_end = phase_end
                            
                            if phase_start <= week_start <= phase_end:
                                matched_phase_id = phase.get('id')
                                break
                
                # If we found a match, update the timesheet
                # Otherwise, assign to first phase as fallback
                if not matched_phase_id and updated_phases:
                    matched_phase_id = updated_phases[0].get('id')
                
                if matched_phase_id:
                    timesheets_collection.update_one(
                        {'_id': timesheet['_id']},
                        {'$set': {'phase_id': matched_phase_id}}
                    )
                    print(f"  ✓ Updated timesheet {timesheet['_id']} to phase_id: {matched_phase_id}")
    
    print("\n" + "=" * 60)
    print(f"✅ Migration Complete!")
    print(f"   Projects updated: {projects_updated}")
    print(f"   Phases fixed: {phases_fixed}")
    print("=" * 60)

if __name__ == '__main__':
    main()
