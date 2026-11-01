# Public Holidays & a Smarter Leave Component

Auto-fill public holidays by region (Australia — National, NSW, QLD) and let staff choose to work or swap a holiday for another nominated day. Also a first round of upgrades to the leave/time-off component.

## Who it's for

- **Workspace administrators (super admins)** who set the workspace's region and want public holidays to appear automatically each year and feed capacity planning — without typing them in by hand.
- **Staff (resources/contractors) and regular admins** who are affected by public holidays, and who may want to work a public holiday (e.g. for operational reasons) and take a different day off instead.
- **Approvers (super admins)** who sign off time off and now also sign off "I'll work the holiday and take this other day" requests.

## Core features and experience

### 1. Public holidays by region (automatic)
- A workspace-wide **region setting** in Settings: **Australia**, with a sub-choice of **National only**, **NSW**, or **QLD** (NSW/QLD each include the national holidays plus that state's holidays).
- On setting/confirming the region, the app **auto-populates that year's public holidays** (and can refresh/advance to the next year). Holidays are sourced from a free public-holidays service for Australia; no account or key is required.
- Each holiday shows its **date and name** and is clearly marked as a public holiday. Admins can still **manually add, edit, or delete** a holiday (e.g. a one-off regional holiday or a correction) — the automatic list and manual entries live together.
- Public holidays **count as non-working days in capacity/planning** exactly as company holidays do today (they reduce available capacity and are excluded from timesheet auto-fill), so plans stay accurate.
- A **"Refresh public holidays"** action re-pulls the official list for the selected region/year in case dates change.

### 2. Work-or-swap a public holiday (staff choice)
- For an upcoming public holiday, a staff member can raise a **"I'll work this holiday"** request. At the same time they **must nominate the replacement day** they'll take off instead (no open-ended "in-lieu balance" — the alternate day is chosen up front).
- This goes through the **same approval flow as other time off** (super-admin approves/rejects; nothing is auto-approved). On approval: the person is treated as **available on the public holiday** and **off on their nominated replacement day** for capacity/planning.
- The request clearly records: which holiday, the nominated replacement date, who requested it, when, and who approved it — visible in the same place as other time-off requests.

### 3. A better leave component (first round)
Chosen must-haves for this build:
- **Leave types configuration** — a managed list of leave types (Annual, Sick, Personal, Unpaid, Parental, plus **custom** types an admin can add/rename/disable), used when requesting time off.
- **Half-day leave** — a request can be a full day or a **half day** (morning/afternoon), reflected proportionally in capacity.
- **Team leave calendar view** — a calendar showing approved (and, for approvers, pending) time off and public holidays across the team, respecting the existing visibility rules (who can see whose time off).

The remaining ideas — **per-person balances/accruals**, **attachments (e.g. medical certificate)**, and **blackout dates** — are planned for later phases (below), not this build.

## User flow

1. A super admin opens Settings → sets the workspace region (Australia → National / NSW / QLD) → public holidays for the current year auto-populate; they can refresh or add a manual one.
2. A staff member opening Time Off sees upcoming public holidays. For one of them they choose **"Work this holiday"**, nominate the replacement day they'll take instead, and submit.
3. A super admin reviews the request (same queue as other leave) and approves or rejects it. On approval, capacity updates: available on the holiday, off on the nominated day.
4. Anyone requesting normal time off picks a **leave type** and can mark it a **half day**; it still routes to the super admin for approval.
5. The team **leave calendar** shows public holidays plus approved/pending time off, scoped to what each person is allowed to see.

## UI/UX feel

- Matches the existing Settings and Time Off screens — a region selector and a "refresh holidays" action sit alongside the current holiday management; no new areas to learn.
- The work-or-swap request reuses the existing "Request Time Off" pattern with two extra fields (which holiday, which replacement day) and the same status badges and approval queue.
- The leave calendar reads like a normal month view: public holidays shaded, each person's approved time off as blocks, pending shown only to approvers.
- Honest, low-pressure wording throughout; nothing about requesting or approving changes in character — just more options and auto-filled holidays.

## Implementation phases

**Phase 1 — MVP (built now):**
- Workspace region setting (Australia: National / NSW / QLD) with automatic public-holiday population for the current year, a refresh action, and manual add/edit/delete retained.
- Public holidays reduce capacity and are excluded from timesheet auto-fill (consistent with today's company holidays).
- Work-or-swap-a-public-holiday request with mandatory nominated replacement day, routed through the existing super-admin approval; approved outcome flips availability (work the holiday, off the replacement day).
- Leave-component upgrades: configurable leave types (incl. custom), half-day leave, and a team leave calendar view honoring existing visibility rules.

**Phase 2 (later, not built now):**
- Per-person leave **balances and accruals** (e.g. annual-leave entitlement that draws down as leave is approved), with simple reporting.
- **Attachments** on a leave request (e.g. upload a medical certificate), visible to the requester and approvers only.

**Phase 3 (later, not built now):**
- **Blackout dates / capacity guardrails** (periods where leave is discouraged or requires extra sign-off), per-person or per-workspace **region override** (multi-country/state teams), and additional countries beyond Australia.

## Assumptions

- **Region scope for now is Australia only**, offered as **National / NSW / QLD**; NSW and QLD each include national holidays plus their state holidays. Other countries/states are deferred to Phase 3. (Confirmed country focus.)
- **Holidays apply workspace-wide** (one shared region for the whole team), not per-person. Per-person/region override is Phase 3. (Confirmed.)
- **Automatic holiday source** is a free public-holidays service for Australia that needs no account or API key and returns national vs state (NSW/QLD) holidays; if it's ever unreachable, holidays already loaded are kept and the admin can retry or add manually. (Confirmed automatic approach.)
- **Working a public holiday requires nominating the replacement day immediately** (no accrued time-off-in-lieu balance), and it uses the **same approval** as all other time off (super-admin approves; nothing auto-approved). (Confirmed.)
- **Approval authority and current time-off visibility rules are unchanged** — only super admins approve; who can see whose time off (and the "who's out" summary) stays as currently configured; the new leave calendar respects those same rules.
- **Capacity treatment:** public holidays and approved leave reduce available capacity and are excluded from timesheet auto-fill, matching how company holidays behave today; a half-day reduces capacity by half for that day.
- **Leave types** are a workspace-managed list seeded with Annual, Sick, Personal, Unpaid and Parental, plus admin-defined custom types; disabling a type keeps historical entries intact.
- **Team leave calendar** shows public holidays to everyone and time off according to existing visibility (a person sees their own; approvers/leads see per the current rules); reasons/notes remain private as they are today.
- **"Reset" is treated as starting a fresh planning cycle**, not deleting any existing data or configuration. If a data reset is actually wanted, it will be handled separately on explicit request.
- **Phase 2's balances/accruals, attachments, and Phase 3's blackout dates** are explicitly out of scope for this build, per the staged plan above.
