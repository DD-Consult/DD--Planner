# Production Data Sync - Alternative Methods

## 🚨 IP Whitelisting Issue

The production MongoDB Atlas cluster has IP whitelisting enabled, preventing direct connection from this preview environment.

**Error:** `No replica set members found yet` (IP not in whitelist)

---

## 🔧 SOLUTION OPTIONS

### Option 1: Whitelist Preview Environment IP (RECOMMENDED)

1. **Get this environment's IP address:**
```bash
curl -s https://api.ipify.org
```

2. **Add IP to MongoDB Atlas whitelist:**
   - Login to MongoDB Atlas
   - Go to Network Access
   - Click "Add IP Address"
   - Add the IP from step 1
   - Wait 2-3 minutes for changes to propagate

3. **Run sync again:**
```bash
cd /app
python data_sync.py --mongo-url "mongodb+srv://smartplanning:d58t8nclqs2c73aeo68g@customer-apps.u4s6j6.mongodb.net/smartplanning-resource_planner?retryWrites=true&w=majority" --export

# Then import to local
python data_sync.py --import-file dd_planner_export_*.json --no-dry-run
```

---

### Option 2: Use Production Backend API as Proxy

Since your production deployment is already connected to Atlas, we can use it as a proxy.

**Steps:**

1. **Create an admin-only export endpoint in production:**

Add to `/app/backend/server.py`:

```python
@app.get("/api/admin/export-all-data")
async def export_all_data(current_user: dict = Depends(get_current_user)):
    """Export all data - SUPER ADMIN ONLY"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin only")
    
    data = {
        "export_date": datetime.now(timezone.utc).isoformat(),
        "collections": {}
    }
    
    # Export each collection
    collections = ['users', 'resources', 'projects', 'allocations', 
                   'timesheets', 'status_updates', 'risks', 'holidays', 'leaves']
    
    for coll_name in collections:
        cursor = db[coll_name].find()
        docs = await cursor.to_list(length=100000)
        data["collections"][coll_name] = [serialize_doc(d) for d in docs]
    
    return data
```

2. **Deploy this change to production**

3. **Download the data:**
```bash
# From your production URL
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://planner-plus-18.emergent.host/api/admin/export-all-data \
  > production_data.json
```

4. **Import to preview:**
```bash
python data_sync.py --import-file production_data.json --no-dry-run
```

---

### Option 3: Manual Export from Atlas UI

1. **Login to MongoDB Atlas**
2. **Go to your cluster → Collections**
3. **For each collection:**
   - Click on collection name
   - Click "Export Collection"
   - Download as JSON
4. **Combine all JSONs** into one file
5. **Import using data_sync.py**

---

### Option 4: Use mongoexport/mongoimport (CLI)

If you have MongoDB tools installed on a machine with Atlas access:

```bash
# Export from production
mongoexport --uri="mongodb+srv://smartplanning:d58t8nclqs2c73aeo68g@customer-apps.u4s6j6.mongodb.net/smartplanning-resource_planner" \
  --collection=projects --out=projects.json

# Repeat for each collection...

# Import to local
mongoimport --uri="mongodb://localhost:27017/resource_planner" \
  --collection=projects --file=projects.json
```

---

### Option 5: Temporary "Allow All IPs" (QUICK BUT RISKY)

⚠️ **Not recommended for production with sensitive data**

1. Go to MongoDB Atlas → Network Access
2. Add IP: `0.0.0.0/0` (allows all IPs)
3. Run the sync script
4. **IMMEDIATELY REMOVE** the 0.0.0.0/0 entry after sync

---

## 🎯 RECOMMENDED APPROACH FOR YOUR CASE

Given that this is a resource planning app with production data, I recommend:

### **Option 1 (Whitelist IP) - Best for security**

This maintains security while allowing automated sync.

**Steps:**
1. Get preview environment IP: `curl https://api.ipify.org`
2. Add to Atlas whitelist
3. Run: `python data_sync.py --export` (with production URL)
4. Run: `python data_sync.py --import-file ... --no-dry-run`

---

## 📋 QUICK REFERENCE

### Get Environment IP:
```bash
curl -s https://api.ipify.org
# Or
curl -s https://ifconfig.me
```

### Production MongoDB URL:
```
mongodb+srv://smartplanning:d58t8nclqs2c73aeo68g@customer-apps.u4s6j6.mongodb.net/smartplanning-resource_planner
```

### Database Names:
- Production: `smartplanning-resource_planner`
- Preview: `resource_planner`

### Collections to Sync:
- users
- resources
- projects (⚠️ This is what's missing!)
- allocations
- timesheets
- status_updates
- risks
- holidays
- leaves
- allocation_roles

---

## 🔒 SECURITY NOTES

- **Don't commit** MongoDB credentials to git
- **Remove temporary whitelist entries** after sync
- **Use specific IPs** instead of 0.0.0.0/0
- **Rotate credentials** if exposed
- **Monitor Atlas access logs** for suspicious activity

---

## ✅ VERIFICATION AFTER SYNC

Run these to verify successful sync:

```bash
# Check document counts
python data_sync.py --check

# Verify specific projects exist
mongo mongodb://localhost:27017/resource_planner --eval "db.projects.find({name: /FX1.*Injury/}).pretty()"

# Check phase data
mongo mongodb://localhost:27017/resource_planner --eval "db.projects.findOne({name: /FX1.*Injury/}).phases"
```

Expected results:
- Project count should match production
- "FX1 - Injury Management Module" should exist
- "Keyton Retirement Living" related project should exist
- All projects should have phases with valid IDs

---

## 📞 NEXT STEPS

**Choose one option above and let me know:**

1. **Option 1:** I can help whitelist the IP if you provide Atlas access
2. **Option 2:** I can add the export endpoint to backend
3. **Option 3-5:** You handle manually and provide the export file

Once we have production data in preview environment:
- ✅ Phase selection will work
- ✅ All projects will be visible
- ✅ Timesheet creation will work for all projects
- ✅ Testing will match production behavior

---

**Current Status:** Waiting for Atlas IP whitelisting or alternative export method
