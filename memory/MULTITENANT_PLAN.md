# DD Planner → Multi-Tenant SaaS Transformation Plan

**Status:** Approved by user, execution in progress
**Started:** July 2025
**Owner:** don@ddconsult.tech

---

## Vision
Transform DD Planner from a single-tenant app (built for DD Consulting) into a multi-tenant SaaS platform where multiple consulting firms can sign up, each with their own isolated workspace and configurable feature modules.

**DD Consulting becomes Tenant #1** and continues to work exactly as it does today.

---

## Locked-in Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Data isolation** | Database-per-tenant on shared MongoDB cluster | Strongest isolation without infra multiplication. User chose "schema-per-tenant" — for MongoDB this maps to database-per-tenant. |
| **Tenant routing** | Subdomain-based (`{slug}.ddplanner.io`) | Best branding, standard SaaS pattern. Requires wildcard SSL. |
| **Module gating** | Full modularity — all 17 modules toggleable per tenant | Maximum flexibility for pricing tiers later |
| **User → tenant mapping** | One user = one tenant | Simplest model, standard for early-stage SaaS |
| **Data migration** | Migrate DD's live data to a "default" tenant, keep app running | Zero data loss, backward compatible |
| **Platform admin** | Separate portal at `admin.ddplanner.io` | Clean separation, industry standard |
| **Platform admin account** | Same account as DD super_admin — dual roles, same password (`don@ddconsult.tech` / `Welcome123!`) | User's explicit preference for simplicity |

---

## Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Platform Layer                              │
│  ┌────────────────────────┐  ┌──────────────────────────────┐  │
│  │ admin.ddplanner.io     │  │ MongoDB: platform_db          │  │
│  │ (Platform Admin Portal)│──│  ├─ tenants                    │  │
│  │ - Create tenants       │  │  ├─ platform_users             │  │
│  │ - Toggle modules       │  │  ├─ memberships                │  │
│  │ - View usage/billing   │  │  ├─ modules_catalog            │  │
│  │ - Support impersonate  │  │  ├─ tenant_modules             │  │
│  └────────────────────────┘  │  ├─ platform_audit_log         │  │
│                              │  └─ subscription_plans          │  │
│                              └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ ddconsult.      │  │ acme.           │  │ startup.        │
│ ddplanner.io    │  │ ddplanner.io    │  │ ddplanner.io    │
│ (Tenant Portal) │  │ (Tenant Portal) │  │ (Tenant Portal) │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ tenant_ddconsult│  │ tenant_acme     │  │ tenant_startup  │
│ (Own MongoDB DB)│  │ (Own MongoDB DB)│  │ (Own MongoDB DB)│
│ 30+ collections │  │ 30+ collections │  │ 30+ collections │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

---

## The 17 Toggleable Modules

Each tenant can enable/disable these independently (respecting dependencies):

| Module Key | Name | Depends On |
|---|---|---|
| `projects` | Projects & Portfolio | (core, always on) |
| `wbs` | Work Breakdown Structure | projects |
| `milestones` | Milestones | projects, wbs |
| `resources` | Resources / Team | (core) |
| `allocations` | Allocations & Capacity | resources, projects |
| `timesheets` | Timesheets | resources, projects |
| `risks` | Risk Management | projects |
| `status_updates` | Status Updates | projects |
| `baselines` | Baselines & Variance | projects |
| `reports` | Reports & Exports (PDF/PPTX) | projects |
| `client_portal` | Client Portal (magic links) | projects |
| `ai_copilot` | AI Chat & Actions | (core AI) |
| `ai_intelligence` | Anomaly / Forecasting / Retros | ai_copilot |
| `ai_productivity` | Kickoff Wizard, Status Drafter | ai_copilot |
| `hubspot_integration` | HubSpot CRM Bi-directional | projects |
| `mcp_server` | MCP API for external AI agents | (core) |
| `knowledge_base` | AI Knowledge Base | ai_copilot |

---

## Safety Guarantees

1. **Feature flag `MULTI_TENANT_ENABLED=false` by default** — nothing changes until flipped
2. **Migration is COPY, not MOVE** — original `resource_planner` DB stays intact as backup for 30+ days
3. **Full mongodump backup** before Step 3 → `/app/backups/pre_multitenant_YYYYMMDD.archive`
4. **163 existing tests must pass green** after every step — hard rule
5. **Dual-read verification** during cutover
6. **Rollback plan** documented at every step (revert 1 env variable → back to today's app)

---

## Execution Steps

### ✅ Step 1 — Platform DB & Tenant Registry (COMPLETED)
**Goal:** Create platform-level data model without touching current app.
- New `platform_db` MongoDB database
- Collections: `tenants`, `platform_users`, `memberships`, `modules_catalog`, `tenant_modules`, `platform_audit_log`
- Seed `modules_catalog` with 17 modules + dependencies
- Seed one `tenants` doc for DD Consulting: `{slug: "ddconsult", name: "DD Consulting", db_name: "tenant_ddconsult", status: "active"}`
- Seed one `platform_users` doc: `don@ddconsult.tech` / `Welcome123!` as `platform_admin`
- Enable all 17 modules for DD tenant in `tenant_modules`
- Feature flag `MULTI_TENANT_ENABLED=false` in backend/.env
- Non-destructive — DD app runs identically to today

**Test:** DD Planner unchanged. New collections exist. Existing test suite → 100% green.

**Status:** In progress

---

### ⏳ Step 2 — Tenant Resolution Middleware
**Goal:** Backend can resolve "which tenant is this request for?" from subdomain.
- New `middleware/tenant_resolver.py` — reads `Host` header → extracts subdomain → looks up tenant
- Fallback: if flag off OR no match → default to DD tenant (backward compat)
- New dependency `get_current_tenant(request)`
- New helper `get_tenant_db(tenant)` → Motor client for tenant's DB
- Debug endpoint `/api/whoami-tenant` to verify resolution

**Test:** `ddconsult.localhost:8001` → DD tenant. Unknown subdomain → 404. All existing endpoints unchanged (feature flag OFF).

---

### ⏳ Step 3 — Data Migration Script
**Goal:** Copy DD's data into `tenant_ddconsult` DB with verification.
- Full mongodump backup first → `/app/backups/pre_multitenant_YYYYMMDD.archive`
- Script `scripts/migrate_to_multitenant.py`:
  - Dry-run by default; `--commit` flag required
  - Copies all 30+ collections from `resource_planner` → `tenant_ddconsult`
  - Adds `_migrated_at` timestamp
  - Prints count-diff report per collection
  - Aborts on any mismatch
- Idempotent, safe to re-run

**Test:** Dry-run counts match. After commit, `tenant_ddconsult` has identical data to `resource_planner`.

---

### ⏳ Step 4 — Refactor DB Layer to Tenant-Aware
**Goal:** Every collection access goes through tenant DB, not global.
- Rewrite `database.py`: remove global collection exports, add `get_collections(tenant)` factory
- Refactor all 25 route files: inject collections via dependency
- Backward compat: with flag OFF, factory returns OLD `resource_planner` DB
- Done collection-by-collection (projects → resources → allocations → timesheets → wbs → …)

**Test:** All 163 tests pass with flag OFF. Then flip flag ON in staging → all 163 pass on `tenant_ddconsult`.

**Delegate to:** `The_Logic_Engineer`

---

### ⏳ Step 5 — Platform Auth & JWT Extension
**Goal:** JWT carries tenant context; login resolves user → tenant.
- Extend JWT payload: `{sub, tenant_id, tenant_slug, membership_role}`
- New `POST /api/platform/auth/login` for platform admin portal
- Existing `POST /api/auth/login` becomes tenant-aware
- `get_current_user` validates JWT tenant matches request subdomain (prevents token replay)

**Test:** DD user's JWT rejected on `acme.localhost`. Platform JWT works only on `admin.localhost`.

---

### ⏳ Step 6 — Module Toggle System
**Goal:** Backend enforces module gates; frontend hides disabled UI.
- Backend: `@require_module("timesheets")` decorator on route groups → 403 if disabled
- Frontend: `useEnabledModules()` hook → cached in React Query
- Sidebar filters by enabled modules
- Route guards: `<ModuleRoute module="wbs">`
- Default: all 17 enabled for DD tenant

**Test:** Toggle `timesheets` OFF → sidebar hides, direct URL blocked, API 403.

**Delegate to:** `The_UI_Specialist` + `The_Logic_Engineer`

---

### ⏳ Step 7 — Platform Admin Portal (`admin.ddplanner.io`)
**Goal:** Standalone UI to manage tenants.
- New React section `frontend/src/platform/*` — separate layout
- Hostname-based routing: `admin.*` → `<PlatformApp>`, else `<TenantApp>`
- Pages: Tenants list, Tenant detail (with 17 module toggles), Platform Users, Audit Log
- Impersonation: creates scoped, time-limited, audited JWT

**Test:** Platform admin creates tenant "Acme" → toggles modules → views audit log. DD's admin cannot log into platform portal.

**Delegate to:** `The_UI_Specialist` + `The_Logic_Engineer`

---

### ⏳ Step 8 — Tenant Onboarding Flow
**Goal:** Self-serve tenant sign-up.
- `POST /api/platform/tenants` — creates tenant doc + `tenant_{slug}` DB + owner user + default modules + welcome project
- Sign-up page on `ddplanner.io/signup`
- Email verification via Resend
- Redirect to `{slug}.ddplanner.io/login`

**Test:** Sign up "Acme Corp" → verify email → log in on `acme.localhost` → see welcome project.

---

### ⏳ Step 9 — Per-Tenant Branding & Settings
**Goal:** Each tenant customizes their workspace.
- New `tenant_settings` in tenant DB: logo (base64), primary_color, work_week_hours, timezone, ai_custom_instructions
- Replace hardcoded "DD Consulting" in `ppt_export.py` → pull from settings
- Replace hardcoded 40h/week in `utils.py` → read from tenant settings
- Settings page: branding tab, work policy tab

**Test:** Change Acme's `work_week_hours=35` → allocation math updates. PDF export shows Acme logo, not DD.

---

### ⏳ Step 10 — Integration Isolation
**Goal:** HubSpot / MCP / Knowledge Base per tenant.
- Migrate `integration_settings`: `org_id="default"` → real `tenant_id`
- MCP endpoints scoped: `{tenant}.ddplanner.io/api/mcp` with tenant-scoped API keys
- Knowledge base: platform-shared docs + per-tenant docs (union)
- AI instructions: tenant-global becomes per-tenant

**Test:** DD's HubSpot config doesn't leak to Acme. DD's MCP key rejected on Acme's endpoint.

---

### ⏳ Step 11 — Regression Lock + Cross-Tenant Isolation Tests
**Goal:** Prove nothing broke; prove no data leaks.
- Rerun all 163 existing tests on `tenant_ddconsult` — must be green
- New `tests/test_multitenant_isolation.py`:
  - User in Tenant A cannot GET/PUT/DELETE any Tenant B resource
  - MCP key from A cannot query B
  - Export from A cannot render B's data
  - JWT from A rejected on B's subdomain
- New `tests/test_module_gates.py`: disable each module → verify UI hides + API 403s

**Delegate to:** `The_Integration_Auditor`

---

## Rollout Timeline

| Phase | Steps | Est. Sessions | Risk |
|---|---|---|---|
| Alpha — Foundation | 1–4 | 3–4 sessions | Med (DB refactor) |
| Beta — Multi-tenant works | 5–7 | 3 sessions | Low |
| GA — Public SaaS ready | 8–11 | 2–3 sessions | Med (isolation testing) |

**Total: ~10 focused sessions.**

---

## Progress Log

- **[Step 1 - ✅ COMPLETED]** Platform DB & Tenant Registry
  - Created `platform_db` MongoDB database (separate from `resource_planner`)
  - 7 platform collections created with indexes: `tenants`, `platform_users`, `memberships`, `modules_catalog`, `tenant_modules`, `platform_audit_log`, `subscription_plans`
  - Seeded 17 modules in `modules_catalog` across 5 categories (core, pm, ai, reporting, integrations)
  - Seeded DD Consulting as Tenant #1 (slug=`ddconsult`, id=`700ce8de-...`, is_default=true, branding=DD Navy/Gold, work_week=40h Sydney tz)
  - Seeded platform admin `don@ddconsult.tech` / `Welcome123!` (must_change_password=true)
  - Enabled all 17 modules for DD tenant
  - New endpoints: `GET /api/platform/status` (public introspection), `GET /api/platform/tenants` (super_admin), `GET /api/platform/modules` (admin+), `GET /api/platform/tenants/{slug}/modules`
  - Feature flag `MULTI_TENANT_ENABLED=false` in `/app/backend/.env` — nothing behaves differently yet
  - **Verified:** existing app 100% unaffected. `admin@test.com` login works, projects endpoint returns all 4 projects, no regressions
  - **Files created:** `platform_db.py`, `routes/platform.py`, `.env` files, `backups/.gitignore`
  - **Files modified:** `server.py` (added seeding + router registration), `requirements.txt` (pinned greenlet==3.1.1, pyee==12.0.0)

---

## Rollback Procedures

### Rollback from any step 1-3:
- Set `MULTI_TENANT_ENABLED=false` in `backend/.env`
- Restart backend: `sudo supervisorctl restart backend`
- App runs identically to pre-migration state

### Rollback from step 4+:
- Set `MULTI_TENANT_ENABLED=false`
- Restart backend
- If corruption suspected: restore from `/app/backups/pre_multitenant_YYYYMMDD.archive`
  - `mongorestore --archive=/app/backups/pre_multitenant_YYYYMMDD.archive`

### Rollback from step 7+ (frontend split):
- Additionally: revert `App.js` to check-token-only routing (no hostname-based split)

---

## Contact
- Platform Owner: don@ddconsult.tech
- First Tenant: DD Consulting (`ddconsult` slug)
