# DD Planner — Enhancements Roadmap (Planning only — not yet built)

Status: AWAITING OWNER CONFIRMATION. No code written yet.

## Sequence & effort
| # | Feature | Type | Effort | Notes |
|---|---------|------|--------|-------|
| 2.5 | Magic link re-check + config doc | verify | S | Mostly done earlier; confirm + document prod config |
| 1 | Portfolio "Meeting Mode" | net-new UX | M | Director walkthrough; shows client-report content per project |
| 2 | Easier allocation adding | UX | M | Streamlined quick-add from project view |
| 3 | WBS MS-Project enhancements | enhance | M–L | Gap-fill (critical path, task Gantt drag, indent/outdent) |
| 4 | Public view-only demo landing | net-new | L | New `/` landing + read-only live demo w/ seeded data |
| 5 | Proposal → approve → project + client login | net-new module | XL | Phased; Google Doc ingestion in later phase |

---

## #2.5 — Magic links (verify + config)
- Already fixed this session: portal link built from `x-forwarded-*` (public host), full flow verified (create→verify→confirm→report), 28/28 tests.
- To document for prod: (a) `RESEND_API_KEY` + `SENDER_EMAIL` must be set so verification-code & link emails actually send (else code only printed to logs); (b) ingress must forward `x-forwarded-host`/`-proto` (standard). 
- Action: re-run magic-link test, produce a short "prod config checklist".

## #1 — Portfolio "Meeting Mode"
- Full-screen present mode launched from Portfolio; Next/Prev steps through each project.
- Per project panel = client-report essentials: health & schedule status, latest status summary, open risks, upcoming milestones/timeline, budget vs actual, team on project.
- Reuse existing ProjectReport/section data; keyboard arrows for next/prev; "jump to project" list.
- Read-only; admin/director use.

## #2 — Easier allocation adding
- Today: 3 entry points (Allocations dialog, Projects via AllocationEditor, AllocationEditor component).
- Plan: a "Quick Add Allocation" on the project detail/allocations view — resource type-ahead + % (or hours) + date range prefilled to project dates + optional phase; inline validation (existing validateAllocation). Optional: add multiple resources in one dialog (multi-row).
- Keep existing math/validation; admin-only (writes already gated).

## #3 — WBS MS-Project gap-fill (REVIEW FIRST)
- Already present: dependencies + topological order, baseline vs revised slip, parent/child rollup, milestones, cascade dates, recalc, sync project dates, order field.
- Likely gaps to confirm via audit: critical-path highlighting, TASK-level Gantt bars with drag-to-reschedule (portfolio Gantt exists; task Gantt?), indent/outdent + drag-reorder UI, constraint types (Start-No-Earlier-Than / Finish-No-Later-Than).
- Action: audit WBSView + wbs.py, present a gap list, then build the agreed 2–3.

## #4 — Public view-only demo landing (option a)
- New public landing at `/` (marketing + "Try Live Demo" CTA). Move current Login to `/login`.
- "Try Live Demo" opens a READ-ONLY clickable tour of the real app using an isolated demo tenant / seeded sample data (no login). All writes disabled; session sandboxed.
- Security: demo must not touch real tenant data; read-only guards; isolated demo dataset.

## #5 — Secure customised HTML proposal → approval → project + client login (XL, phased)
Goal: send a secure, customised HTML proposal to a prospective client; on approval, auto-create the project AND a client login scoped to that project's reports.

**Phase A — Proposal data model + secure share (reuse magic-link infra)**
- New `proposals` collection: client info, proposal content (HTML), status (draft/sent/viewed/approved/declined), secure token, expiry, created_by, linked_project_id (null until approved).
- Secure delivery via the existing magic-link pattern (token + email verification). Public `/proposal/:token` page renders the customised HTML read-only.

**Phase B — Approval flow → project + client login**
- Client clicks **Approve** on the proposal page → backend creates a Project from proposal fields AND creates a `client` user (email + set-password invite) with `allowed_project_ids=[new project]`.
- Client then logs in to see their project report(s) via existing client portal.
- Decline path + audit trail + admin notification.

**Phase C — Proposal content sourcing (templates → Google Doc)**
- Start: template(s) with merge fields (owner provides templates) and/or AI-drafted HTML (Emergent/Gemini) from project details.
- Later: ingest from **Google Doc / external doc**:
  - Option 1: Google Docs API via a **service account** (share doc with the SA email) or OAuth — requires Google Cloud credentials.
  - Option 2: Published-to-web Google Doc URL → fetch exported HTML (no auth, simplest) — owner publishes the doc.
  - Option 3: Upload .docx/.pdf → parse → HTML.
  - Decision + credentials needed before building this sub-phase.

### Open decisions needed for #5
- Proposal creation: template+merge / AI-draft / both?
- Google Doc access method (service account vs published-URL vs upload)?
- Client login: email + set-password invite link (recommended)?
- Branding/signature/e-sign needed on approval, or simple Approve button?
