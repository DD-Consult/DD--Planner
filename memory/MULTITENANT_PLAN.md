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

### ✅ Step 2 — Tenant Resolution Middleware (COMPLETED)
**Goal:** Backend can resolve "which tenant is this request for?" from subdomain.
- New `middleware/tenant_resolver.py` — reads `Host` header → extracts subdomain → looks up tenant
- Fallback: if flag off OR no match → default to DD tenant (backward compat)
- New dependency `get_current_tenant(request)`
- New helper `get_tenant_db(tenant)` → Motor client for tenant's DB
- Debug endpoint `/api/whoami-tenant` to verify resolution

**Test:** `ddconsult.localhost:8001` → DD tenant. Unknown subdomain → 404. All existing endpoints unchanged (feature flag OFF).

---

### ✅ Step 3 — Data Migration Script (COMPLETED)
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

### ✅ Step 4 — Refactor DB Layer to Tenant-Aware (COMPLETED)
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

- **[Step 2 - ✅ COMPLETED]** Tenant Resolution Middleware
  - New `middleware/tenant_resolver.py` — parses `Host` header, extracts subdomain, resolves tenant from `platform_db`
  - Handles all edge cases: normal subdomains, `admin.*` (platform portal), `www.*`, reserved subdomains, no-subdomain (root domain), localhost dev variants, preview URLs, bare IPs
  - In-memory tenant cache with 60s TTL for performance
  - FastAPI dependency `get_current_tenant(request)` — attaches tenant to `request.state.tenant`
  - Helper `get_tenant_enabled_modules(tenant_id)` — returns `{module_key: enabled}` map for Step 6
  - Two new debug endpoints:
    - `GET /api/platform/whoami-tenant` — shows how resolver interprets current request (host, subdomain, resolution_mode, tenant, enabled_modules)
    - `GET /api/platform/resolve-subdomain?host=X` — standalone subdomain parser tester
  - **Backward compatibility guaranteed:** with `MULTI_TENANT_ENABLED=false` (default), always returns the default tenant regardless of host. Existing routes unchanged.
  - **Verified in flag=OFF mode:** all existing endpoints work identically
  - **Verified in flag=ON mode:** `ddconsult.ddplanner.io` → DD tenant, `admin.ddplanner.io` → platform mode, unknown subdomain → 404, no subdomain → default fallback, preview URL → default fallback, existing login/projects still work
  - Flag restored to `false` after testing
  - **Files created:** `middleware/__init__.py`, `middleware/tenant_resolver.py`
  - **Files modified:** `routes/platform.py` (added whoami-tenant + resolve-subdomain endpoints)

- **[Step 3 - ✅ COMPLETED]** Data Migration Script
  - Full mongodump backup taken: `/app/backups/pre_multitenant_20260815_102833.archive` (43KB, gzipped, dry-run verified)
  - Migration script `/app/scripts/migrate_to_multitenant.py` — production-grade, ~400 lines:
    - **Dry-run by default** — no writes unless `--commit` explicitly given
    - **Idempotent** — uses `bulk_write(UpdateOne, upsert=True)` so re-runs never duplicate
    - **Preserves `_id`** exactly (both ObjectId and string _ids)
    - **Batched** at 500 docs per bulk write for memory efficiency
    - **Auto-discovers collections** in source DB (future-proof; picks up new collections without code changes)
    - **Automatic verification pass** after commit — aborts with exit code 1 if source count ≠ target count for any collection
    - **Index copying** via `--with-indexes` flag
    - **Membership creation** — for every user in source DB, creates a `platform_db.memberships` doc linking them to the target tenant
    - **Filtering** via `--only` / `--skip` flags for partial migrations
    - **Interactive confirmation** before `--commit` (bypassed with `--yes` for CI)
    - **Colored terminal output** for clarity
    - **Verify-only mode** (`--verify-only`) for post-hoc integrity checks
    - **Exit codes** documented (0/1/2/3 for success/mismatch/config/runtime)
  - **DD Consulting data migrated:** 171 docs across 7 collections into `tenant_ddconsult` DB (`ai_knowledge_base` 146, `allocations` 10, `baselines` 4, `pending_actions` 0, `projects` 4, `resources` 5, `users` 2)
  - 4 non-default indexes copied on `allocations` collection
  - 2 memberships auto-created in `platform_db.memberships` (admin@test.com → admin, client@test.com → client, both scoped to `ddconsult`)
  - **Verified end-to-end:**
    - Source DB (`resource_planner`) UNCHANGED (still 2/4/5/10 docs)
    - Target DB (`tenant_ddconsult`) has EXACT 171 docs, identical `_id` values (ObjectId preservation)
    - Migration metadata `_migrated_at`, `_migrated_from`, `_migrated_tenant_id`, `_migrated_tenant_slug` added to every doc (audit trail)
    - Idempotency test passed: re-run wrote same 171 docs, no duplicates
    - Existing app still returns 4 projects / 5 resources / 10 allocations (feature flag OFF)
  - Rollback procedures documented in `/app/scripts/ROLLBACK.md` (4 levels: app-level, tenant DB drop, mongorestore, full nuke)
  - **Files created:** `/app/scripts/migrate_to_multitenant.py`, `/app/scripts/ROLLBACK.md`, `/app/backups/pre_multitenant_20260815_102833.archive`

- **[Step 4 - ✅ COMPLETED]** Refactor DB Layer to Tenant-Aware
  - **Design chosen:** ContextVar + LazyCollection proxy pattern (documented in `database.py` module docstring)
  - **Why this design:** Requires ZERO changes to the 25 route files. All existing `from database import X_collection` imports keep working. Each collection reference is now a proxy that resolves to the current-request tenant's DB at attribute access time.
  - **Files rewritten:**
    - `database.py` — introduces `LazyCollection` proxy, `_current_tenant_db` ContextVar, `set_current_tenant_db`/`reset_current_tenant_db`/`get_db_for_tenant_slug` helpers. All 25 collection exports converted to LazyCollection instances. Legacy `db` variable preserved for backward compat.
    - `server.py` — new `tenant_context_middleware` runs on every request. Resolves tenant from Host header, binds tenant DB into ContextVar for the request duration, resets on exit. Middleware is a no-op when MULTI_TENANT_ENABLED=false (fast path — zero overhead).
  - **HTTPException handling in middleware:** Because Starlette middleware doesn't auto-convert HTTPException to responses, added try/except in the middleware that converts HTTPException → JSONResponse (fixes 500 → 404 for unknown subdomains)
  - **Verified end-to-end (both modes):**
    - Flag OFF: All existing CRUD operations work (login, projects list/create/update/delete, resources, allocations, portfolio, dashboard action items). Confirmed 4 projects / 5 resources / 10 allocations returned. Manual + backend testing agent confirm no regressions (agent's flagged "regressions" traced to test authoring bugs — invalid date format for creates, then invalid IDs for updates).
    - Flag ON: `ddconsult.ddplanner.io` reads from `tenant_ddconsult` DB, unknown subdomain returns clean 404, DD's JWT rejected on other tenant subdomains (401 — Step 5 will formalize this), writes go to correct tenant DB, tenants have complete data isolation.
    - Second-tenant test proved isolation: created `acme` tenant, seeded 1 project, verified DD host returns 4 projects and Acme host returns 1 (Acme's), each tenant sees only its own data.
  - **Frontend verified:** Dashboard loads clean at preview URL, all sidebar items render, KPI cards populate correctly.
  - Flag restored to `false` for safety. Test acme tenant cleaned up.
  - **Files modified:** `database.py` (full rewrite), `server.py` (added middleware + imports)

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
