# DD Planner — Auto-Update Framework (Config Inheritance + Fan-out Migrations)

Purpose: make it easy to update the "main build" once and have changes propagate
safely to ALL tenants. Built on top of the single-codebase + database-per-tenant
architecture.

## Two propagation mechanisms

### 1. Code / features / UI  →  ALREADY automatic
Single FastAPI app + single React build serve every tenant (subdomain routing
selects the tenant DB per request). A Cloud Run redeploy instantly updates all
tenants. No per-tenant action needed. DD Consulting is the flagship tenant.

### 2. Config / new modules / schema  →  handled by this framework
Because each tenant has its own Mongo DB, these do NOT auto-propagate on deploy.
Solved with:

**A) Config Inheritance (live)**
- Source of truth: `platform_db.platform_defaults` (doc `_id="global"`).
- Tenant effective config = deep_merge(platform_defaults, tenant_overrides).
- Editing a default in the Platform Portal → instantly updates every tenant that
  hasn't overridden that specific key.
- Edited via Platform Portal → "Defaults" page (GET/PUT /api/platform/defaults).
- DD Navy (#1B2A47) / Gold (#C9A84C), work_week_hours=40 are the defaults.

**B) Versioned Fan-out Migrations**
- Package: `/app/backend/migrations/` (base.py contract, runner.py engine, mNNNN_*.py).
- Each migration: `version:int`, `description`, `scope` ("platform"|"tenant"), `async up(ctx)`.
- Tracking: `_migrations` collection PER tenant DB + one in platform_db.
- Lock: `platform_db._migration_locks` (stale-expire 15 min) prevents concurrent runs.
- Runner discovers migrations by filename order, runs platform first then fans out
  to every active/suspended tenant. Idempotent + error-isolated per tenant.

Migrations currently shipped:
- m0001 (platform): upsert MODULES_CATALOG into modules_catalog (adds new modules on deploy) + ensure `default_enabled`.
- m0002 (tenant): backfill tenant_modules rows for every catalog module. NEW modules
  get enabled = catalog.default_enabled → this is how new features reach existing tenants.
- m0003 (tenant): ensure core indexes (allocations, pending_actions) on each tenant DB.

## How to add a NEW feature/module in future (playbook)
1. Add the module dict to `MODULES_CATALOG` in `backend/platform_db.py`
   (include `default_enabled: True/False`; core modules always on).
2. If it needs new collections/indexes/backfills, add a new migration file
   `backend/migrations/mNNNN_<name>.py` with the next version number.
3. Deploy. On startup, the background task auto-runs migrations (non-blocking,
   Cloud Run <5s safe). m0001 syncs the catalog; m0002 backfills toggles to all
   tenants; your new migration applies structural changes to every tenant DB.
4. Optionally trigger manually from Platform Portal → "System" → "Run all migrations".

## Per-tenant feature control
- Platform Portal → Tenants → <tenant> → Modules tab: per-module Switch + bulk save.
- API: PUT /api/platform/tenants/{slug}/modules/{key}?enabled=bool ; bulk PUT /modules {modules:{...}}.
- New-module default policy is configurable via `default_enabled` per module; admin
  can override per tenant anytime.

## Endpoints (all require platform admin bearer)
- GET  /api/platform/migrations/status
- POST /api/platform/migrations/run
- POST /api/platform/tenants/{slug}/migrations/run
- GET  /api/platform/defaults
- PUT  /api/platform/defaults  (validates #RRGGBB colors, work_week_hours 1..168)

## Startup wiring (server.py `_full_startup_init`, background task)
seed_platform_defaults_if_empty() → run_migrations(actor="startup_auto").
Wrapped in try/except; never blocks uvicorn startup.

## Verified
- Backend: 16/16 tests passed (idempotency, propagation to new tenant `mtest1`,
  per-tenant toggle, defaults validation, config inheritance).
- Frontend: 100% — System page (run all + per-tenant), Defaults page (edit/persist/revert),
  module toggle tab renders. No console errors.

## Gotchas for future agents
- Migrations run OUTSIDE request context → NEVER use LazyCollection there.
  Use `get_db_for_tenant_slug(slug)` for tenant DB; import `platform_db` for platform.
- Mongo reserves attributes starting with `_` → access `_migrations`/`_migration_locks`
  via bracket syntax: `db["_migrations"]`, NOT `db._migrations`.
- tenant_modules & modules_catalog live in platform_db, NOT the tenant DB.
- Only use UUID string _ids for new docs (no ObjectId).
