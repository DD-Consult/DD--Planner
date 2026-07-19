#!/usr/bin/env python3
"""
Fix missing phase IDs in production database
Run this script to fix all projects with missing or invalid phase IDs
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import uuid
import os

# Production MongoDB connection
MONGO_URL = "mongodb+srv://smartplanning:d58t8nclqs2c73aeo68g@customer-apps.u4s6j6.mongodb.net/smartplanning-resource_planner?retryWrites=true&w=majority"

async def fix_phase_ids():
    """Fix all projects with missing phase IDs"""
    
    print("="*60)
    print("FIXING PHASE IDs IN PRODUCTION DATABASE")
    print("="*60)
    print()
    
    # Connect to production
    print(f"Connecting to production database...")
    client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=10000)
    
    try:
        await client.admin.command('ping')
        print("✓ Connected to production\n")
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        print("\nPlease check:")
        print("1. MongoDB Atlas IP whitelist includes this server")
        print("2. Connection string is correct")
        print("3. Network connectivity")
        return
    
    db = client['smartplanning-resource_planner']
    
    # Get all projects
    projects = await db.projects.find({}).to_list(length=1000)
    print(f"Found {len(projects)} projects\n")
    
    fixed_count = 0
    fixed_projects = []
    
    for project in projects:
        project_name = project.get('name', 'Unknown')
        phases = project.get('phases', [])
        
        if not phases:
            continue
        
        needs_fix = False
        fixed_phases = []
        
        for phase in phases:
            phase_id = phase.get('id')
            phase_name = phase.get('name', 'Unknown Phase')
            
            # Check if ID is missing, empty, or invalid
            if not phase_id or not str(phase_id).strip() or phase_id == 'null':
                # Generate new UUID
                new_id = str(uuid.uuid4())
                phase['id'] = new_id
                needs_fix = True
                
                print(f"Project: {project_name}")
                print(f"  Phase: {phase_name}")
                print(f"  Old ID: '{phase_id}'")
                print(f"  New ID: {new_id}")
                print()
                
            fixed_phases.append(phase)
        
        if needs_fix:
            # Update project with fixed phases
            result = await db.projects.update_one(
                {'_id': project['_id']},
                {'$set': {'phases': fixed_phases}}
            )
            
            if result.modified_count > 0:
                fixed_count += 1
                fixed_projects.append(project_name)
                print(f"  ✓ Fixed phases for: {project_name}\n")
    
    # Summary
    print("="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total projects checked: {len(projects)}")
    print(f"Projects fixed: {fixed_count}")
    
    if fixed_projects:
        print("\nFixed projects:")
        for name in fixed_projects:
            print(f"  - {name}")
    
    # Verify specific projects
    print("\n" + "="*60)
    print("VERIFICATION")
    print("="*60)
    
    # Check FX1 - Injury Management Module
    fx1 = await db.projects.find_one({"name": {"$regex": "Injury.*Management", "$options": "i"}})
    if fx1:
        print(f"\n✓ FX1 - Injury Management Module")
        phases = fx1.get('phases', [])
        for phase in phases:
            phase_id = phase.get('id', 'NO ID')
            print(f"  - {phase.get('name')}: {phase_id}")
    
    # Check Keyton/Home Care
    keyton = await db.projects.find_one({"name": {"$regex": "Home Care|Keyton", "$options": "i"}})
    if keyton:
        print(f"\n✓ {keyton['name']}")
        phases = keyton.get('phases', [])
        for phase in phases:
            phase_id = phase.get('id', 'NO ID')
            print(f"  - {phase.get('name')}: {phase_id}")
    
    client.close()
    
    print("\n" + "="*60)
    if fixed_count > 0:
        print("✓ PHASE IDs FIXED!")
        print("="*60)
        print("\nNow try creating a timesheet again.")
        print("Phase selection should work correctly.")
    else:
        print("✓ ALL PHASE IDs ARE VALID")
        print("="*60)
        print("\nNo fixes needed. All phases have valid IDs.")

if __name__ == '__main__':
    asyncio.run(fix_phase_ids())
