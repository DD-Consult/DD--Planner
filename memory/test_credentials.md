# Test Credentials (current workspace / preview environment)

Auth uses OAuth2PasswordRequestForm — form-encoded login at POST /api/auth/login (fields: username=email, password=pwd). Token is in `access_token`.

## Working accounts in THIS environment (resource_planner DB)
- Super Admin: `superadmin@test.com` / `Super@2026`  (role super_admin — can approve/manage time off, see all)
- Admin:       `admin@test.com` / `admin123`          (role admin — linked to resource "Alice Johnson")
- Resource:    `qa_resource@test.com` / `Test@2026`    (role resource — linked to resource "Bob Smith")
- Client:      `client@test.com` (role client)

## Notes
- The old production creds (don@ddconsult.tech etc.) are NOT present in this preview DB. Use the accounts above.
- Demo: public demo at /demo (no login) issues a read-only demo session; demo data lives in an isolated `ddplanner_demo` DB.
