# Time Off Visibility — Tighten to Super-Admin-Only

Restrict who can see other people's time off so that staff (including regular admins) see only their own requests, while super admins keep the full organisation-wide view. This closes a gap where any admin — not just super admins — could see everyone's time off and their leave notes.

## Who it's for

- **Staff** (resources and contractors) — already see only their own time off; no change in what they see.
- **Regular admins** — today they can see everyone's time off; after this change they see only their own, like other staff.
- **Super admins** — keep the complete, organisation-wide view: everyone's requests, the approval queue, submission details and notes.

## Core features and experience

- **Own-only time off for everyone except super admin.** On the Time Off page, a staff member or regular admin sees a list containing only their own entries (past, pending, approved, rejected). A super admin continues to see all people's entries.
- **Private notes/reason.** The note attached to a request (e.g. "surgery", "family event") is only ever shown to the person who submitted it and to super admins. It is never returned to, or displayed for, anyone else.
- **Approvals stay super-admin-only.** The pending-approval queue and the ability to approve, reject, re-open, or change a decision remain visible and usable only to super admins (already the case) — this plan makes the surrounding list consistent with that.
- **Capacity view unchanged.** The team capacity heatmap keeps showing who is unavailable on which days so planning still works; it does not show personal leave reasons, so it is left exactly as-is.
- **No change to requesting.** Anyone can still submit their own time-off request; nothing about creating requests changes.

## User flow

1. A resource, contractor, or regular admin opens Time Off → sees only their own requests and only their own notes.
2. A super admin opens Time Off → sees everyone's requests, the pending-approval queue, submission info, and notes; can approve/reject/re-open/change any entry.
3. Everyone can still click "Request Time Off" to submit their own request, which goes to the super admin for approval.

## UI/UX feel

- Matches the existing Time Off page; this is a visibility tightening, not a redesign.
- For non-super-admins the page simply shows fewer rows (their own) and continues to read as "My Time Off"; the "who else is out" and approval controls are absent, as they are for staff today.
- No new screens, buttons, or steps.

## Implementation phases

**Phase 1 — MVP (built now):** Scope the Time Off list so only super admins see all entries; everyone else (resources, contractors, regular admins) sees only their own. Ensure leave notes/reason are returned only to the requester and super admins. Approvals and the capacity view are unchanged.

**Phase 2 (later, not built now):** An opt-in, organisation-wide "who's out this week" summary that shows names and dates (availability only, no reasons) to a configurable audience — if the team later wants lightweight shared visibility without exposing reasons.

**Phase 3 (later, not built now):** Per-team or per-manager visibility (e.g. a team lead sees their direct reports' time off) if role granularity beyond super-admin-vs-everyone is needed.

## Assumptions

- "Staff" for this change means everyone who is not a super admin — this explicitly includes **regular admins**, who will lose the all-people view and see only their own time off.
- The **capacity heatmap is left fully as-is**; it may still reveal that a given person is unavailable on certain days (without the reason), and staff/contractors retain their existing read-only access to it.
- **Leave notes/reason** are treated as private: visible only to the person who submitted the request and to super admins, everywhere they could otherwise appear.
- **Approval authority is unchanged** — only super admins can approve, reject, re-open, or change a decision; regular admins cannot (as already decided).
- **Historical/legacy entries** follow the same rule: a non-super-admin sees only the ones tied to their own profile.
- A person sees time off tied to **their own linked profile**; someone whose login is not linked to a staff profile sees an empty list (unchanged behaviour).
- No notification or email behaviour changes as part of this.
