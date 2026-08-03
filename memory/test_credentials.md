# Test Credentials

## Super Admin (Production)
- Email: `don@ddconsult.tech`
- Password: `@Ddplanner2026`

## Legacy Test Accounts (from seed, may not work after prod data migration)
- Email: `admin@test.com` / Password: `admin123`
- Email: `riley@test.com` / Password: `riley123`

## Notes
- Production data has been migrated from MongoDB Atlas to this preview environment
- 9 resources, 32 projects, 134 allocations, 120 WBS tasks
- Auth uses OAuth2PasswordRequestForm — form-encoded login at /api/auth/login (username=email&password=pwd)
