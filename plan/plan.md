# Work a Public Holiday — Swap or Work-Only Process

A way for staff to record that they worked on a public holiday, and optionally
nominate a different day to take off instead. Requests are reviewed and approved
the same way as any other time-off request.

## Who it's for
- **Staff / resources** who are rostered or choose to work on a recognised public
  holiday and want it recorded — either with a day taken in lieu (a "swap") or
  with no day off at all.
- **Super Admins** (owners) who review and approve these requests.

## Core features and experience
- **Two request types in one place.** The existing "Request Time Off" form has a
  toggle: *Time Off* (normal leave) or *Work a Public Holiday*.
- **Holiday picker is pre-filled.** The public holiday list is populated
  automatically from the workspace's region (AU National / NSW / QLD), so staff
  select from real dates rather than typing them.
- **Swap is optional.** The person may nominate a *Replacement Date* (the day
  they'll take off instead) or leave it blank to record that they worked the
  holiday with nothing taken in lieu.
- **Approval required.** Every request — swap or no-swap — enters as *Pending* and
  must be approved by a Super Admin. Nothing is auto-approved. This matches the
  current time-off approval model exactly.
- **Clear labelling.** A swap request is recorded as "Public holiday (worked)";
  a no-swap request is recorded as "Public holiday (worked, no swap)" so the two
  cases are distinguishable in lists and the team calendar.
- **No separate lieu-day balance.** Working a holiday does **not** create a
  "+1 day owed" credit or ledger, and it does **not** auto-fill worked hours into
  timesheets. The request simply records the holiday worked and, if given, the
  replacement day taken off. (Confirmed: keep as-is.)

## User flow
1. Staff member opens the **Time Off** page and clicks **Request Time Off**.
2. In the dialog, they switch **Request Type** to **Work a Public Holiday**.
3. They **select the public holiday** they worked from the pre-filled dropdown.
4. **Replacement Date (optional):**
   - Pick a date → recorded as a **swap**; the time-off entry lands on that
     replacement day.
   - Leave blank → recorded as **worked, no swap**; the entry is logged against
     the holiday date itself.
5. They optionally add a note and submit.
6. The request appears as **Pending** in the Super Admin approval queue.
7. A **Super Admin approves or rejects** it. On approval it shows as an approved
   entry (on the replacement day for a swap, or on the holiday for no-swap) and
   appears in the team leave calendar.

## UI/UX feel
- Lives inside the current Time Off request dialog — no new screen to learn.
- Plain, form-style layout consistent with the rest of the planner: labelled
  fields, a single primary action, inline validation messages.
- The replacement field is explicitly marked **(Optional)** with a one-line hint
  explaining that leaving it blank means "worked the holiday with no swap."
- Worked/swap entries are visually tagged in lists and the calendar so they're
  easy to tell apart from ordinary leave.

## Implementation phases

### Phase 1 — MVP (the confirmed process)
- Request-type toggle (Time Off vs Work a Public Holiday).
- Region-filled public holiday picker (AU National / NSW / QLD).
- Optional replacement date: swap vs worked-no-swap, with the two distinct type
  labels.
- Pending-by-default with Super Admin approval; visible in the team calendar.
- This is the behaviour that exists and has been verified; Phase 1 is a
  confirmation and documentation of it, with no change to the approval model and
  no lieu-day balance.

### Phase 2 — Later (not in scope now)
- Optional "time-in-lieu" balance/ledger: working a holiday earns a credit that
  is spent when the replacement day is taken, with a visible balance.
- Optional guardrails: require the replacement day to fall within a set window of
  the worked holiday.

### Phase 3 — Future (not in scope now)
- Manager-level approval for work/swap requests (in addition to Super Admin).
- Regions/countries beyond Australia for the holiday picker.
- Auto-reflecting worked-holiday hours into timesheets.

## Assumptions
- **Approval stays Super-Admin-only** for work/swap requests, identical to the
  current time-off flow (confirmed).
- **No lieu-day balance or credit** is created by working a holiday; the request
  only records the worked holiday and the optional replacement day (confirmed —
  keep as-is).
- **Replacement day is optional**, and when provided it is a single day (the
  common case for a one-day public holiday); multi-day swaps are out of scope.
- The replacement day can be any valid date the staff member chooses; there is
  **no enforced window** tying it to the worked holiday in the MVP.
- The holiday picker continues to draw from the workspace's configured region
  (AU National / NSW / QLD) with no additional regions in the MVP.
- Worked-holiday entries are **not** pushed into timesheets automatically in the
  MVP.
