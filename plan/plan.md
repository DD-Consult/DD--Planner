# Complete the Self‑Improving AI: Reactions, Learning, Real‑Data Grounding, and Best‑Practice Coaching

Finish what the AI upgrade set out to do and go one step further: make every AI result in DD Planner rate‑able with a thumbs‑up/down, feed those ratings (plus the workspace's written guidance) back into every answer, ground each feature in the project's real data, and have the AI also measure projects against established project‑management best practice and proactively suggest improvements.

## Who it's for

- **Project managers / principals** who use the AI daily (PM Assist chat, work‑breakdown generation, status summaries, rescheduling, proposal drafting, portfolio insights, risk polishing) and want consistently sharper, specific answers — plus a simple way to tell the app when an answer was good or bad, and concrete best‑practice suggestions to improve their projects.
- **Workspace administrators (super admins)** who set the AI provider and guidance, and want the thumbs‑up/down signals and best‑practice coaching to actually move the needle everywhere, not just on a few screens.

## Why this is needed (what's incomplete today)

The earlier AI work delivered the plumbing but not the coverage or depth the goal called for:

- **Reactions appear on only 3 AI surfaces** (project status summary, reschedule analysis, proposal builder chat). They are **missing** from the most‑used AI outputs: PM Assist chat / command bar, the AI work‑breakdown generator, Reports/Portfolio AI insights, risk polishing, and the AI Intelligence panels (anomaly, forecast, retrospective).
- **The learning loop only partially runs.** Feedback is captured on just those 3 surfaces, and the "use recent feedback to steer the answer" step is wired into only some prompts — so most features have nothing to learn from and don't improve when rated.
- **Real‑data grounding is shallow.** The "give the AI more of the real project picture" step was added to a single feature (project budget analysis); the chat, work‑breakdown, proposals, reschedule, and portfolio insights can still produce generic output.
- **There is no best‑practice lens.** Nothing today evaluates a project against recognised PM standards or suggests improvements beyond what the user asks for.

## Core features and experience

- **A reaction on every AI result.** Anywhere the app shows AI‑generated content, a small, unobtrusive "Was this helpful?" 👍/👎 appears beneath it, with an optional one‑line note. Covers PM Assist chat (on each AI reply), the AI work‑breakdown generator, Reports/Portfolio AI insights, risk polishing, the AI Intelligence panels, and the three places that already have it. Leaving feedback stays optional and never blocks the flow.
- **Ratings that actually improve answers, everywhere.** Recent thumbs‑up/down signals (especially written notes) plus the workspace's saved AI instructions are folded into the prompt for every AI feature — so repeated preferences ("too generic", "stop inventing numbers", "tasks too high‑level") shift future answers across the app.
- **Specific, grounded answers.** Each AI feature is given the real workspace context relevant to it — the project's open risks, recent status updates, budget vs. actual/time, team capacity and allocations, and related past proposals — so guidance references the actual situation. Invisible by design: same screens, better answers.
- **Best‑practice coaching (new).** The AI also assesses a project against established project‑management best practice and surfaces concrete, prioritised suggestions to improve it — not just answering what was asked. Examples of what it looks for: a clear objective and scope, defined phases/milestones, a maintained risk/RAID log with mitigations and owners, a resourcing/capacity plan that isn't over‑allocated, baselined vs. actual schedule and budget tracking (earned‑value‑style signals), recent status cadence, dependencies and critical‑path hygiene, and stakeholder/communication basics. Suggestions are specific to the project's real data (e.g. "3 high‑impact risks have no mitigation owner" or "no status update in 3 weeks; schedule a check‑in"), each with a short "why it matters" grounded in the relevant standard (PMI/PMBOK, PRINCE2, Agile, risk management). This appears as a per‑project "Best‑practice review" the PM can run, and the same lens informs portfolio insights.
- **The auto‑learn tuning now spans both sources.** The existing admin "suggest instruction improvements" tool draws on two things together: (1) the team's own thumbs‑up/down feedback, and (2) recognised PM best practice — so it recommends guidance that both matches what the team likes and nudges the AI to coach toward good project management.
- **Consistent, honest behaviour.** The reaction control looks and behaves the same everywhere; AI features degrade gracefully if unavailable/unconfigured; no triggers, layouts, or navigation change — only coverage, grounding, coaching depth, and output quality.

## User flow

1. A PM asks PM Assist a question, generates a WBS, views portfolio insights, polishes a risk, or drafts a proposal. The AI responds using the project's real data and, where relevant, flags best‑practice gaps.
2. The PM can also run a per‑project **Best‑practice review**, which returns prioritised, project‑specific suggestions each with a short rationale tied to a PM standard.
3. Beneath any AI result the PM clicks 👍 or 👎, optionally adding a note.
4. Those signals, plus the workspace's AI instructions, are automatically included next time that feature (and related ones) runs.
5. An admin opens the feedback analytics / tuning view and sees ratings from across every AI feature; the "suggest instruction improvements" tool proposes guidance informed by both the team's feedback and PM best practice, which the admin can save.

## UI/UX feel

- The reaction is the same small, muted "Was this helpful?" with thumbs already in use — reused verbatim so it feels native and unobtrusive; under each AI reply in chat, and just beneath generated content in panels/dialogs.
- The Best‑practice review reads as a clean, prioritised checklist/card list (High/Medium/Low), each item with a one‑line rationale and, where possible, the concrete data point that triggered it — matching the existing AI Intelligence/insights styling. It's launched from an obvious button on the project (and reflected in portfolio insights); it never auto‑changes anything.
- Grounding stays invisible: no new fields or steps, answers simply become more specific.
- Honest messaging throughout when AI isn't configured or a call fails.

## Implementation phases

**Phase 1 — MVP (built now):**
- Add the 👍/👎 reaction to every AI output that lacks it: PM Assist chat (per reply), AI work‑breakdown generator, Reports/Portfolio AI insights, risk polish, and the AI Intelligence panels (anomaly, forecast, retrospective).
- Wire the learning loop into every AI feature's prompt: recent relevant feedback + the workspace's AI instructions, so ratings measurably influence output across the app.
- Extend richer real‑data context to the features still producing generic answers (PM Assist chat, work‑breakdown, proposals, reschedule, portfolio insights).
- Add best‑practice coaching: a per‑project "Best‑practice review" that evaluates the project's real data against recognised PM standards and returns prioritised, grounded improvement suggestions; apply the same lens to portfolio insights; and make the admin "suggest instruction improvements" tool draw on both team feedback and best practice.

**Phase 2 (later, not built now):**
- Light admin controls/transparency: see per feature how much context is injected and toggle categories; a subtle "grounded in your project data" affordance on results; let admins tailor which best‑practice standards/weightings matter most to them.

**Phase 3 (later, not built now):**
- Deeper learning: trend reactions and best‑practice scores over time, track which injected context/instructions correlate with higher ratings and healthier projects, and auto‑propose refinements to the workspace's guidance; optional portfolio‑wide "maturity" trends.

## Assumptions

- **"Every AI output" means the user‑facing AI results:** PM Assist chat replies, the AI work‑breakdown generator, Reports/Portfolio AI insights/narrative, AI‑polished risks, proposal drafting, smart reschedule, status summaries, and the three AI Intelligence panels. Purely mechanical/non‑AI outputs are out of scope.
- **PM Assist chat shows the reaction per AI reply** (not once at the bottom).
- **The reaction control is reused as‑is** (existing thumbs‑up/down with optional note); no redesign; remains optional and non‑blocking.
- **Best‑practice coaching is advisory only** — it suggests, never auto‑changes a project — and draws on widely recognised PM standards (PMI/PMBOK, PRINCE2, Agile/Scrum, standard risk/RAID and earned‑value concepts). No specific paid framework/certification content is reproduced; guidance is expressed in general best‑practice terms.
- **Best‑practice suggestions are grounded in the project's real data** (risks, status cadence, allocations/capacity, schedule/budget baselines vs. actuals, dependencies), so they're specific rather than generic checklists.
- **The best‑practice review is run on demand** per project (and informs portfolio insights); it is not a background job in this phase.
- **Richer context and the best‑practice lens are best‑effort and scoped** — only relevant data is included, kept within reasonable size for speed; missing pieces are omitted; failures fall back to current behaviour with a clear message.
- **Auto‑tuning stays human‑approved** — the AI proposes instruction improvements (now informed by feedback + best practice); an admin reviews and saves them; nothing is auto‑applied.
- **No change to how any AI feature is triggered, displayed, or navigated.**
- **This builds on the existing feedback store, analytics, and "suggest instruction improvements" tooling**, which become more representative once capture is app‑wide; no separate analytics work is part of this phase.
