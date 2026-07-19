# DD Planner - Production Data Sync Guide

## 🚨 ISSUE IDENTIFIED

You're experiencing a **data synchronization issue** between environments:

- **Preview/Development Environment:** 8 projects (what I'm connected to)
- **Production Environment:** 20+ projects including "FX1 - Injury Management Module" and "Keyton Retirement Living"

This explains why:
- Phase selection doesn't work for certain projects (they don't exist in preview DB)
- Data appears different between what you see and what I analyze
- The production database has more recent, real data

---

## 📊 CURRENT DATABASE STATUS

### Preview Environment (localhost):
```
users:           5 documents
resources:       4 documents  
projects:        8 documents ⚠️ (Missing production projects!)
allocations:     23 documents (5 are orphaned)
timesheets:      2 documents
status_updates:  19 documents
risks:           4 documents
holidays:        3 documents
leaves:          1 document
```

### Data Issues Found:
- ⚠️ 5 allocations reference non-existent projects (orphaned data)
- ⚠️ Missing production projects (FX1 - Injury Management Module, Keyton, etc.)

---

## 🔧 SOLUTION OPTIONS

### Option 1: Export Production Data → Import to Preview (RECOMMENDED)

This ensures your preview environment matches production for testing.

#### Steps:

1. **On Production Server**, export the data:
```bash
cd /app
python data_sync.py --export
# Creates: dd_planner_export_YYYYMMDD_HHMMSS.json
```

2. **Download the export file** to your local machine

3. **Upload to Preview Environment** and import:
```bash
cd /app
# Dry run first (safe - no changes)
python data_sync.py --import-file dd_planner_export_YYYYMMDD_HHMMSS.json

# If looks good, actually import
python data_sync.py --import-file dd_planner_export_YYYYMMDD_HHMMSS.json --no-dry-run
```

**⚠️ WARNING:** This will replace ALL data in preview with production data!

---

### Option 2: Connect Preview to Production Database Directly

Instead of copying data, point preview environment to production MongoDB Atlas.

#### Steps:

1. Get your **production MongoDB Atlas connection string**

2. Update preview environment:
```bash
# Edit backend/.env
nano /app/backend/.env

# Change MONGO_URL to:
MONGO_URL=mongodb+srv://username:password@cluster.mongodb.net/resource_planner
```

3. Restart backend:
```bash
supervisorctl restart backend
```

**⚠️ WARNING:** Preview will read/write directly to production database! Be careful with testing.

---

### Option 3: Database Comparison & Selective Sync

Compare databases and sync only specific collections.

#### Steps:

1. **Compare databases:**
```bash
python data_sync.py --compare "mongodb+srv://username:password@prod-cluster.mongodb.net/"
```

2. This shows differences between local and production

3. **Manually sync** specific data if needed

---

## 🛠️ DATA SYNC TOOL USAGE

### Available Commands:

```bash
# Check current database for issues
python data_sync.py --check

# Export current database to JSON
python data_sync.py --export

# Import data (dry run - safe)
python data_sync.py --import-file backup.json

# Import data (actual import - DANGEROUS!)
python data_sync.py --import-file backup.json --no-dry-run

# Compare local vs production
python data_sync.py --compare "mongodb+srv://prod-url"

# Use custom MongoDB URL
python data_sync.py --check --mongo-url "mongodb://custom:27017"
```

---

## 📋 RECOMMENDED WORKFLOW

### For Your Case:

1. **First, understand what's in production:**
   - Ask your production environment admin for a data export
   - Or get production MongoDB Atlas connection string

2. **Compare environments:**
   ```bash
   python data_sync.py --compare "YOUR_PROD_MONGO_URL"
   ```

3. **Export production data:**
   ```bash
   # On production server
   python data_sync.py --export
   ```

4. **Import to preview:**
   ```bash
   # On preview environment  
   python data_sync.py --import-file production_export.json --no-dry-run
   ```

5. **Verify the import:**
   ```bash
   python data_sync.py --check
   ```

6. **Test the app:**
   - Login and navigate to Projects page
   - Verify "FX1 - Injury Management Module" exists
   - Try creating a timesheet for that project
   - Verify phase selection works

---

## 🔍 DIAGNOSING THE PHASE SELECTION ISSUE

Now that we know it's a data sync issue, here's why phase selection fails:

### Root Cause:
1. User tries to create timesheet for "FX1 - Injury Management Module"
2. **That project doesn't exist in preview database**
3. Frontend shows it (cached from production login)
4. Backend can't find it when you select phases
5. Phase dropdown fails because project lookup returns null

### The Fix:
**Sync production data to preview** using the data_sync.py tool above.

---

## ⚠️ IMPORTANT NOTES

### About Data Exports:

- **Size:** Exports can be 10-100 MB depending on data
- **Format:** JSON with all collections
- **Includes:** All documents with full data
- **ObjectIDs:** Preserved during export/import

### About Imports:

- **⚠️ DESTRUCTIVE:** Import clears existing data first!
- **Dry Run:** Always test with dry run first
- **Backup:** Export current data before importing
- **Verify:** Check data after import

### About Production Access:

- **Never test on production directly** unless necessary
- **Use preview environment** for testing
- **Sync data regularly** to keep environments in sync
- **Backup before major changes**

---

## 🚀 DEPLOYMENT CONSIDERATIONS

### When Deploying to Production:

The deployment will use **MongoDB Atlas** (managed database), which means:

1. **Production already has data** - Don't overwrite it!
2. **Preview environment** should sync FROM production, not TO production
3. **Deployment process:**
   - Emergent builds your code
   - Connects to existing MongoDB Atlas
   - Uses existing production data
   - No data migration needed during deployment

### Post-Deployment:

After successful deployment:

1. **Verify connection:** Check app connects to Atlas
2. **Test data access:** Ensure all projects load
3. **Check phase selection:** Try creating timesheets
4. **Monitor logs:** Watch for database errors

---

## 🔒 SECURITY CONSIDERATIONS

### MongoDB URLs:

- **Never commit** MongoDB URLs to git
- **Keep production URLs secret**
- **Use environment variables** for all DB connections
- **Rotate credentials** regularly

### Data Exports:

- **Contains sensitive data** - handle carefully
- **Don't share exports** publicly
- **Delete old exports** after use
- **Encrypt if needed** for transfer

---

## 📝 MIGRATION SCRIPT BREAKDOWN

The `data_sync.py` tool provides:

### 1. Data Integrity Checks:
- Projects without phases
- Phases without valid IDs
- Orphaned allocations (pointing to deleted projects)
- Orphaned timesheets (pointing to deleted resources)
- Duplicate user emails

### 2. Export Functionality:
- Exports all collections to JSON
- Preserves ObjectIDs and relationships
- Includes metadata (date, source DB)
- Shows file size and summary

### 3. Import Functionality:
- Dry run mode (safe testing)
- Clears existing data first
- Converts string IDs back to ObjectIds
- Validates before import

### 4. Comparison Features:
- Compares local vs production
- Shows document count differences
- Identifies missing collections
- Highlights data gaps

---

## 🎯 NEXT STEPS FOR YOU

### Immediate Actions:

1. **Get production database access:**
   - Contact your production environment admin
   - Request MongoDB Atlas connection string
   - Or request a data export file

2. **Run comparison:**
   ```bash
   python data_sync.py --compare "PRODUCTION_MONGO_URL"
   ```

3. **Review differences:**
   - How many projects are missing?
   - What other data is out of sync?

4. **Decide on sync strategy:**
   - Full sync (easiest)
   - Selective sync (more control)
   - Direct connection (for testing)

5. **Execute sync:**
   - Export from production
   - Import to preview
   - Verify with --check

6. **Test the phase selection:**
   - Try creating timesheet for "FX1 - Injury Management Module"
   - Verify it works now

---

## 📞 NEED HELP?

If you're stuck:

1. **Share this information:**
   - Output of `python data_sync.py --check`
   - Whether you have production database access
   - What you want to achieve (testing, deployment, etc.)

2. **Common questions:**
   - "How do I get production database URL?" → Ask your admin
   - "Will this break production?" → No, we only read from production
   - "Can I test safely?" → Yes, use dry run mode
   - "What if import fails?" → You have the export file as backup

---

## ✅ SUCCESS CRITERIA

You'll know the sync worked when:

1. ✅ Preview environment has same project count as production
2. ✅ "FX1 - Injury Management Module" shows in Projects list
3. ✅ "Keyton Retirement Living" shows in Projects list  
4. ✅ Phase selection works when creating timesheets
5. ✅ No data integrity errors from `python data_sync.py --check`
6. ✅ All allocations and timesheets reference valid projects

---

**Tool Location:** `/app/data_sync.py`  
**Documentation:** This file  
**Support:** Share output of sync commands if you need help
