# DD Planner — Reliable, Clean Report Export (PDF & PPTX)

Rebuild how the project report is turned into a PDF/PPTX so the output is always
clean and never errors. The on-screen app is not changed — only what gets exported.

## Who it's for
- Consultants/admins who send project status reports to clients.
- Clients who receive the exported PDF/PPTX.

## The problem being solved (why this plan exists)
The export currently produces the report by having a headless browser render the
exact interactive report page — including the on-screen Work Breakdown Structure
(WBS) table. That table was designed for a wide screen with horizontal scrolling
and ~11 columns. A fixed-width page cannot hold all of it, so the right-most
columns ("Actuals vs Est.", "Deps") are cut off at the page edge. Four rounds of
CSS/structural tweaks each looked fixed on light demo data but the real report
(with fuller cells: status badges, progress bars, "N timesheets") still overflows
and clips. Separately, heavy renders have caused server errors (502/503), and the
report contains near-empty pages.

The recurring failure has one cause: **the export reuses a screen-first component
for a fixed-size page.** This plan stops patching that and gives the export its
own print-first layout that is guaranteed to fit, plus removes the wasted pages
and confirms what is actually running in production so fixes stop "disappearing."

## Core features and experience
1. **Print-optimized WBS table (essential columns only).** In the exported
   report the WBS is rendered by a dedicated print layout showing: Task, Phase,
   Start, End, Duration, Status, % Complete, Actuals vs Est. The "Deps" column is
   removed from the client export. Column widths are fixed so the table always
   fits the page and long text wraps instead of overflowing — no clipping,
   regardless of how much data a project has.
2. **WBS detail vs. summary toggle for the client report.** When generating a
   client report, the user chooses whether the WBS appears as the full task table
   (print-optimized, above) or as a compact summary (phases with roll-up % and
   task counts). Default is the full table; the choice is remembered per report
   generation. Internal/admin views are unaffected.
3. **No wasted pages.** The near-blank pages that currently appear (a page
   containing only a footer) are removed. Sections flow so the report is tight;
   the cover page and closing footer remain intentional.
4. **No clipping anywhere else.** The timeline/Gantt and all other sections are
   confirmed to fit the page width in the export.
5. **Exports don't error (no 502/503).** Heavy renders are prevented from
   overloading the server so a request never brings the instance down; if the
   primary render is ever unavailable, the user still receives a clean file
   rather than an error.
6. **Honest deploy verification.** Before and after shipping, confirm exactly
   which build is live in production, so a fix is never assumed live when it
   isn't. The finished work is checked against a real, data-heavy report — not
   just light sample data — before it is called done.

## User flow
1. User opens a project and chooses Export (PDF or PPTX), or generates a client
   report / magic link.
2. If it's a client report, the user picks the WBS presentation: full task table
   or summary.
3. The file is produced and downloads. It opens as a clean, multi-page 16:9
   document: cover, status summary, timeline, overview, budget, risks, and the
   WBS in the chosen form — every column visible, no cut-off content, no blank
   pages.
4. If the server render is momentarily unavailable, the user still gets a clean
   file with a brief "preparing" message instead of an error.

## UI/UX feel
- Exported document keeps the current DD-branded look (navy/gold cover,
  section styling) — this plan does not restyle the report, it makes it render
  completely and reliably.
- The WBS in export form reads like a clean printed table: fixed columns,
  wrapped text, compact but legible.
- The only new on-screen element is the WBS "full vs summary" choice in the
  report/export step; everything else in the app stays exactly as it is today.

## Implementation phases

### Phase 1 — MVP (built now)
- Dedicated print-only WBS table for the export with the agreed essential
  columns (Task, Phase, Start, End, Duration, Status, % Complete, Actuals vs
  Est.), "Deps" removed, guaranteed to fit the page with wrapping.
- Remove the near-blank pages; verify no other section clips at the page edge.
- Prevent export renders from overloading the server (no 502/503); ensure a
  clean fallback file if the primary render is unavailable.
- Verify the live production build before and after, and validate against a
  data-heavy report (not just light demo data).
- Applies to the PDF export first; PPTX inherits the same clean layout.

### Phase 2 — WBS summary/detail toggle
- Add the client-report choice between full print WBS table and a compact
  phase-level summary, remembered per generation.

### Phase 3 — Scale hardening for many tenants
- Make exports resilient under many simultaneous users/tenants (e.g. dedicated
  render capacity), so report generation never competes with normal app usage.

## Assumptions
- "Deps" is dropped from the client-facing export; it remains visible in the
  on-screen interactive WBS.
- Essential export columns are exactly: Task, Phase, Start, End, Duration,
  Status, % Complete, Actuals vs Est. If any of these should also be dropped for
  space, that's a later tweak.
- The cover page and a single closing footer are intentional and kept; only the
  extra footer-only pages are removed.
- The exported report keeps its current visual style and section order; this is
  a rendering-reliability fix, not a redesign.
- Default WBS presentation in the client report is the full table (Phase 1);
  the summary option arrives in Phase 2.
- Scope is export/report generation only — the on-screen application behavior is
  unchanged.
- "No 502/503" means export requests no longer crash or overload the serving
  instance; extreme concurrent multi-tenant load is fully addressed in Phase 3.
- Production is updated by pushing to the existing GitHub → Cloud Build flow;
  each fix only takes effect in production after that deploy runs.
