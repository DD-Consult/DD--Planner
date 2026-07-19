# Production Deployment Fix Guide

## Issues Found in Production

### Issue 1: Hours Duplicating Across Phases
**Symptom:** Every phase shows the same hours (1.43h planned, 4h actual) instead of unique values per phase.

**Root Cause:** Phase IDs were `None` in the database, causing timesheets to match ALL phases.

**Status:** ✅ Fixed in code, but migration NOT run in production database

---

### Issue 2: Active Projects Showing as "Not Started"
**Symptom:** Phases marked "Not Started" but showing progress (279.72%) and variance.

**Root Cause:** Phase status not being updated correctly, or display issue.

**Status:** ⚠️ Needs investigation

---

## Required Steps for Production Deployment

### Step 1: Backup Production Database
```bash
# MongoDB Atlas - Use built-in backup
# OR manual backup:
mongodump --uri="mongodb+srv://your-production-uri" --out=/backup/prod-backup-$(date +%Y%m%d)
```

### Step 2: Run Phase ID Migration on Production

**Important:** This script was already run in preview/dev, but MUST be run in production!

```bash
# Copy migration script to production server
scp /app/backend/fix_phase_ids.py production-server:/tmp/

# SSH to production
ssh production-server

# Set production MongoDB URL
export MONGO_URL="your-production-mongodb-url"
export MONGO_DB_NAME="resource_planner"

# Run migration
cd /tmp
python3 fix_phase_ids.py
```

**Expected Output:**
```
🔧 Starting Phase ID Migration...
============================================================

Found X projects
  ✓ Fixed phase 'Phase Name' in project 'Project Name': uuid-here
  ✓ Updated timesheet xxx to phase_id: uuid-here

============================================================
✅ Migration Complete!
   Projects updated: X
   Phases fixed: X
============================================================
```

### Step 3: Verify Migration Success

```bash
# Connect to production MongoDB
mongo "your-production-uri"

# Check phase IDs
use resource_planner
db.projects.find({}, {name: 1, "phases.id": 1, "phases.name": 1}).pretty()

# Verify no phases have null/None IDs
db.projects.find({"phases.id": null}).count()
# Should return: 0

# Check timesheets have valid phase_ids
db.timesheets.find({phase_id: null}).count()
# Should return: 0
```

### Step 4: Deploy Updated Code

**Files to Deploy:**
1. `/app/backend/server.py` - Updated with:
   - Phase UUID generation
   - Timesheet validation
   - Status update improvements
   - AI summary generation

2. `/app/frontend/src/pages/ProjectDetail.js` - Updated with:
   - Progress sync fix

3. `/app/frontend/src/components/ProjectStatusCheckin.js` - Updated with:
   - Current progress display

4. `/app/frontend/src/pages/ProjectReport.js` - Updated with:
   - Enhanced report structure

5. `/app/frontend/src/pages/ManageTimesheets.js` - NEW file

6. `/app/frontend/src/api.js` - Updated with:
   - Error interceptor
   - New endpoints

7. `/app/frontend/src/App.js` - Updated with:
   - ManageTimesheets route

8. `/app/frontend/src/components/Layout.js` - Updated with:
   - ManageTimesheets menu

9. `/app/frontend/src/pages/Dashboard.js` - Updated with:
   - Collapsible sections
   - Fixed filtering

**Deployment Commands:**
```bash
# Backend
cd /app/backend
sudo supervisorctl stop backend
git pull origin main  # or copy files
sudo supervisorctl start backend

# Frontend
cd /app/frontend
yarn build
sudo supervisorctl restart frontend

# Verify services
sudo supervisorctl status
curl http://localhost:8001/health
```

### Step 5: Post-Deployment Verification

**Test Checklist:**
- [ ] Login to production
- [ ] Navigate to a project with timesheets
- [ ] Check Time Tracking tab - hours should be unique per phase
- [ ] Check Recent Status Updates - should show correct phase statuses
- [ ] Submit a new status update - should work without errors
- [ ] Check Dashboard - Pipeline projects should show (not hidden)
- [ ] Check Manage Timesheets page (super admin only)
- [ ] Generate a project report - should show correct data

---

## Troubleshooting

### Issue: "Not Started" phases showing progress

**Diagnosis:**
```python
# Check project phases
from pymongo import MongoClient
client = MongoClient("your-production-uri")
db = client['resource_planner']

project = db.projects.find_one({"name": "Your Project Name"}, 
                                {"phases": 1})
for phase in project['phases']:
    print(f"Phase: {phase['name']}")
    print(f"  Status: {phase.get('status')}")
    print(f"  ID: {phase.get('id')}")
    print()
```

**Fix:** Update phase status manually if needed:
```python
db.projects.update_one(
    {"_id": project_id, "phases.name": "Phase Name"},
    {"$set": {"phases.$.status": "Active"}}
)
```

### Issue: Hours still duplicating after migration

**Diagnosis:**
```python
# Check if timesheets have valid phase_ids
timesheets = list(db.timesheets.find({"project_id": "project-id-here"}))
for ts in timesheets:
    print(f"Timesheet: {ts['_id']}")
    print(f"  Phase ID: {ts.get('phase_id')}")
    print(f"  Planned: {ts['planned_hours']}")
    print(f"  Actual: {ts['actual_hours']}")
```

**Fix:** If phase_ids are still None, re-run migration or manually fix:
```python
# Get project phases
project = db.projects.find_one({"_id": ObjectId("project-id")})
first_phase_id = project['phases'][0]['id']

# Update orphaned timesheets
db.timesheets.update_many(
    {"project_id": "project-id", "phase_id": None},
    {"$set": {"phase_id": first_phase_id}}
)
```

---

## Rollback Plan

If issues occur after deployment:

1. **Restore Database from Backup**
   ```bash
   mongorestore --uri="mongodb+srv://your-production-uri" /backup/prod-backup-YYYYMMDD
   ```

2. **Revert Code**
   ```bash
   cd /app/backend
   git revert HEAD
   sudo supervisorctl restart backend
   
   cd /app/frontend
   git revert HEAD
   yarn build
   sudo supervisorctl restart frontend
   ```

3. **Verify Services**
   ```bash
   sudo supervisorctl status
   curl http://localhost:8001/health
   ```

---

## Summary of Changes

### Backend Changes:
1. Phase creation now generates UUIDs
2. Timesheet validation rejects None phase_ids
3. Auto-fill logic properly resolves phases
4. Status updates generate AI summaries
5. Faster AI API timeouts (30s → 15s)
6. Better error handling

### Frontend Changes:
1. Global error interceptor with toasts
2. Progress uses actual_progress from status updates
3. Status update dialog shows current progress
4. Dashboard sections collapsible
5. Pipeline/Draft filtering fixed
6. New Manage Timesheets page (super admin)
7. Enhanced project reports with filters
8. Risks & Issues section in reports

### Database Changes:
1. All phases have UUIDs
2. Timesheets linked to specific phases
3. Status updates include AI summaries
4. Better field aliases for backward compatibility

---

## Contact & Support

If you encounter issues during deployment:
1. Check logs: `/var/log/supervisor/backend.err.log`
2. Check frontend logs: `/var/log/supervisor/frontend.err.log`
3. Review this guide's troubleshooting section
4. Contact development team with error messages
