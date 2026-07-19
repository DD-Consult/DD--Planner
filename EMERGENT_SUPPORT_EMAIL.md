# Email to Emergent Support

---

**Subject:** Request: Database Migration Script Execution for Production App - DD Planner

---

**To:** Emergent Support Team

**From:** [Your Name/Company]

**App Name:** DD Planner / [Your App Name on Emergent]

**Deployment URL:** [Your production URL, e.g., smartplanning.emergent.host]

---

## Issue Summary

We recently deployed updates to our resource planning application (DD Planner) on the Emergent platform. However, we're experiencing critical issues in production that require a database migration script to be executed:

**Production Issues:**
1. **Hours duplicating across project phases** - Every phase shows identical hours instead of unique values (e.g., all phases show 1.43h planned, 4h actual)
2. **Incorrect phase statuses** - Phases marked as "Not Started" but showing progress percentages (279%)

**Root Cause:** 
The database migration script that fixes phase IDs was successfully run in our preview environment but has NOT been executed on the production database. Our production database still has `NULL` phase IDs, causing timesheets to incorrectly match all phases instead of specific ones.

---

## What We Need

**Request:** Please execute the database migration script on our production MongoDB database.

**Script Location:** `/app/backend/fix_phase_ids.py` (attached below and in our repository)

**Estimated Time:** 2-3 minutes to execute

**Risk Level:** LOW - The script only adds UUIDs to existing data, does not delete anything, and is idempotent (safe to run multiple times)

---

## Migration Script

Please execute this Python script against our production MongoDB database:

**File:** `fix_phase_ids.py`

```python
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
```

---

## Execution Instructions

**Command to Run:**
```bash
cd /app/backend
python3 fix_phase_ids.py
```

**Environment Variables Needed:**
- `MONGO_URL` - Our production MongoDB connection string (Emergent-managed)
- `MONGO_DB_NAME` - Should be set to `resource_planner`

**Expected Output:**
```
🔧 Starting Phase ID Migration...
============================================================

Found 15 projects
  ✓ Fixed phase 'Discovery + Draft' in project 'ProjectX': abc-123-uuid
  ✓ Fixed phase 'Revision + Publish' in project 'ProjectX': def-456-uuid
  ✓ Updated timesheet 123 to phase_id: abc-123-uuid

============================================================
✅ Migration Complete!
   Projects updated: 15
   Phases fixed: 45
============================================================
```

---

## Pre-Migration Verification (Optional but Recommended)

To verify the issue exists before migration:

```bash
# Connect to production MongoDB
mongo $MONGO_URL

use resource_planner

# Check for phases with null IDs (should return count > 0)
db.projects.find({"phases.id": null}).count()

# Check for timesheets with null phase_ids (should return count > 0)
db.timesheets.find({phase_id: null}).count()
```

---

## Post-Migration Verification

To verify the migration succeeded:

```bash
# Check for phases with null IDs (should return 0)
db.projects.find({"phases.id": null}).count()

# Check for timesheets with null phase_ids (should return 0)
db.timesheets.find({phase_id: null}).count()

# View sample project with fixed phases
db.projects.findOne({}, {name: 1, "phases.id": 1, "phases.name": 1})
```

---

## Safety Notes

✅ **This migration is safe:**
- Does not delete any data
- Only adds UUID identifiers to existing phases
- Updates timesheet links to reference correct phases
- Idempotent - can be run multiple times without issues
- We successfully ran this in our preview environment with no problems

⚠️ **Backup recommendation:**
If possible, please create a database snapshot/backup before running the migration (standard best practice).

---

## Additional Context

**Why This Happened:**
- Our application creates project phases
- Initially, phases were created without UUID identifiers (id field was null)
- This caused timesheets to match ALL phases instead of specific ones
- The updated code now generates UUIDs for new phases automatically
- But existing production data needs this one-time migration to fix historical records

**Preview Environment:**
- We already ran this migration successfully in preview/staging
- Preview environment shows correct behavior (unique hours per phase)
- Production environment still has the old data structure

**Impact:**
- HIGH - Users cannot accurately track time per project phase
- Reporting is incorrect
- Project progress metrics are misleading

---

## Our Deployment Details

**Repository:** [Your Git repository URL]

**Branch:** main / production

**Recent Commits:**
- Fixed phase ID generation for new projects
- Added timesheet validation
- Enhanced reporting features
- Status update improvements

**Already Deployed:** Yes, code is deployed to production via Emergent's native deployment

**What's Missing:** Only the database migration execution

---

## Contact Information

**Primary Contact:** [Your Name]
**Email:** [Your Email]
**Phone:** [Your Phone] (optional)
**Timezone:** [Your Timezone]

**Best Time to Reach:** [Your availability]

**Preferred Communication:** Email / Emergent Support Portal / Slack

---

## Questions We're Happy to Answer

- Need to see the full codebase? It's in our repository
- Want to review the migration script in more detail? We can schedule a call
- Need access to our preview environment to see the working version? We can provide credentials
- Any security or compliance concerns? Happy to discuss

---

## Timeline

**Urgency:** HIGH - Affecting all users, incorrect reporting

**Ideal Execution Time:** ASAP / [Specify your preferred time if any]

**Expected Duration:** 2-3 minutes to execute the script

---

## Thank You

We appreciate Emergent's support with this. The platform has been great, and we're confident this migration will resolve the production issues completely. Please let us know if you need any additional information or clarification.

Best regards,
[Your Name]
[Your Company]

---

**Attachments:**
- Migration script: `fix_phase_ids.py` (included in email body above)
- Full deployment guide: `PRODUCTION_FIX_GUIDE.md` (available in our repository)

