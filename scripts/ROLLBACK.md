# Migration Rollback Procedures

## Rollback from Step 3 (Data Migration)

If anything looks wrong after running the migration, follow these steps.

### Level 1 — App-level rollback (30 seconds)

The migration didn't modify the source DB. The app is still pointing at
`resource_planner` because `MULTI_TENANT_ENABLED=false`. Nothing needs to be
rolled back at the app level.

To confirm no impact:
```bash
curl -s http://localhost:8001/api/platform/status | python3 -m json.tool
curl -s http://localhost:8001/api/projects -H "Authorization: Bearer <TOKEN>"
```

### Level 2 — Drop the migrated tenant DB (2 minutes)

If you want to start fresh (e.g., migration ran with wrong parameters):

```bash
mongosh --eval "db.getSiblingDB('tenant_ddconsult').dropDatabase()"
```

This is safe:
- Source DB `resource_planner` unchanged
- Platform DB `platform_db` unchanged (tenant registry intact)
- App continues working from `resource_planner`

Then re-run the migration when ready:
```bash
python3 /app/scripts/migrate_to_multitenant.py --commit --with-indexes --yes
```

### Level 3 — Restore from mongodump backup (15 minutes)

If catastrophic — e.g., source DB was accidentally modified:

```bash
# List available backups
ls -lh /app/backups/

# Restore (this ADDS to existing DB; use --drop to replace)
mongorestore --archive=/app/backups/pre_multitenant_YYYYMMDD_HHMMSS.archive --gzip --drop
```

Then verify:
```bash
mongosh --quiet resource_planner --eval "
  print('Users: ' + db.users.countDocuments({}));
  print('Projects: ' + db.projects.countDocuments({}));
  print('Resources: ' + db.resources.countDocuments({}));
"
```

Expected in fresh dev DB: 2 users, 4 projects, 5 resources.

### Level 4 — Nuke everything and start over (5 minutes)

Only use if platform_db is corrupted too:

```bash
mongosh --eval "db.getSiblingDB('platform_db').dropDatabase()"
mongosh --eval "db.getSiblingDB('tenant_ddconsult').dropDatabase()"
sudo supervisorctl -c /etc/supervisor/supervisord.conf restart backend
# Backend startup will re-seed platform_db with fresh tenant, admin, modules.
# Then re-run migration.
```

## Rollback Checklist Before Enabling `MULTI_TENANT_ENABLED=true` (Step 4+)

Before flipping the feature flag in production, verify:

- [ ] Backup exists in `/app/backups/pre_multitenant_*.archive`
- [ ] `python3 scripts/migrate_to_multitenant.py --verify-only` → all counts match
- [ ] `mongosh tenant_ddconsult --eval "db.projects.countDocuments({})"` matches source
- [ ] `mongosh platform_db --eval "db.memberships.countDocuments({})"` == number of users
- [ ] `curl /api/platform/status` returns `platform_db_ready: true`
- [ ] Full regression test suite passes on tenant_ddconsult (Step 4 gate)
