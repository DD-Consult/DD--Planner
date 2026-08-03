# Test Credentials

## Super Admin (Production)
- Email: `don@ddconsult.tech`
- Password: `@Ddplanner2026`

## Resource Accounts (set by testing agent for lead testing)
- Email: `dhruti@ddconsult.tech` / Password: `Test@2026` (leads ServAI project)
- Email: `akshaya@ddconsult.tech` / Password: `Test@2026` (non-lead resource)

## Notes
- Production data has been migrated from MongoDB Atlas to this preview environment
- 9 resources, 32 projects, 134 allocations, 120 WBS tasks
- Auth uses OAuth2PasswordRequestForm — form-encoded login at /api/auth/login (username=email&password=pwd)
