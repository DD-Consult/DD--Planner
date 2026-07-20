# Test Credentials

## Super Admin
- Email: `don@ddconsult.tech`
- Password: `Welcome123!`

## Admin (promoted to super_admin in local preview DB during iter-19 consistency testing)
- Email: `admin@test.com`
- Password: `admin123`
- Role in DB: **super_admin** (not regular admin)

## Resource Accounts
- Email: `amrit@ddconsult.tech`
- Password: `Welcome123!`

- Email: `henry@ddconsult.tech`
- Password: `Welcome123!`

## Demo Credentials (shown on login page)
- Admin: `admin@test.com` / `admin123`
- Client: `client@test.com` / `client123`

## AI Chat Test Accounts (local preview DB)
- Resource: `riley@test.com` / `riley123` (resource "Riley Resource", allocated to AND project lead of "Website Redesign")

## Notes
- `admin@test.com` behaves as super_admin in this env — for confirmation-gate tests requiring a regular admin, a temp `testadmin_iter24@test.com` (role=admin) was created and torn down by the iter-24 test harness.
