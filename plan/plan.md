# DD Planner — Secure Proposal Module (AI-Guided)

An AI-guided way to build a polished, client-facing proposal, send it as a secure private link, and — once the client accepts and DD confirms — automatically spin up the project and a read-only client login for their reports.
The whole journey (draft → send → client views & accepts → DD confirms → project + client access) lives inside DD Planner, with an AI assistant walking the PM through each step.

## Who it's for

- **DD project managers / principals** who prepare and send proposals today by hand-editing a template and JSON file, then sharing a link.
- **Prospective clients** who receive a private proposal link, read it, pick an option, and signal acceptance — no account or login needed to view it.
- **DD admins** who want accepted proposals to turn into real projects and client reporting access without manual re-keying.

## Core features and experience

1. **AI-guided proposal builder (chat + live form, side by side).**
   - A chat panel where the PM describes the deal in plain English or pastes their notes. The AI asks follow-up questions and fills the proposal section by section (the nine-chapter narrative from the existing template: Understanding, Vision, Approach, Options, Plan, Success, Investment, Why DD, Next steps).
   - Alongside the chat, a structured form shows every field the AI has filled. The PM can edit any field directly at any time; edits and chat stay in sync. Nothing is sent until the PM is satisfied.
   - The AI enforces the existing brand/content guardrails (wording, option/pricing presentation, credential order) so output stays on-brand.

2. **Live proposal preview.** At any point the PM can preview the rendered client-facing proposal exactly as the client will see it — the full styled nine-chapter page produced from the current data.

3. **Secure private sharing.** Each proposal gets a unique, hard-to-guess private link. The page is set to not be indexed by search engines. Links can be set to expire on the proposal's validity date. The PM can copy the link to share, and (if email is enabled) send it to the client directly.

4. **Client view with engagement tracking.** When the client opens the link they see the polished proposal. The system records engagement events already designed into the template — opened, which sections were viewed, which option they showed interest in, appendix opened, accept clicked — and surfaces this back to the PM ("Client opened the proposal", "Viewed Investment", "Interested in Path B").

5. **Accept as a recorded intent (not a binding contract).** The client enters their name and picks their preferred path, then clicks Accept. This is explicitly a soft go-ahead — the binding contract remains a separate services agreement. Acceptance notifies DD and records the chosen path and who accepted.

6. **DD confirmation → auto-provisioning.** After a client accepts, the proposal appears in DD Planner as "Accepted — awaiting confirmation." A DD user reviews and clicks Confirm. On confirmation the system automatically:
   - Creates a DD **Project** built from the accepted option (name, client, timeline/stages, and pricing/options carried over from the proposal).
   - Provisions a **read-only client login** scoped to only that project's reports.
   - Sends the client a **passwordless magic link** to access their reports.

7. **Proposal dashboard.** A list of all proposals with their status (Draft → Sent → Viewed → Accepted → Confirmed, plus Declined/Expired), last client activity, chosen path, and quick actions (open builder, preview, copy link, confirm).

## User flow

1. PM opens "Proposals" and starts a new one.
2. PM pastes notes / describes the deal in chat. The AI asks clarifying questions and fills sections; the form fills in alongside. PM edits anything as needed and previews.
3. PM marks the proposal ready; the system generates the private link. PM copies it (and/or emails it to the client).
4. Client opens the link, reads the proposal, explores options; DD sees engagement updates.
5. Client picks a path, enters their name, clicks Accept.
6. Proposal moves to "Accepted — awaiting confirmation"; DD is notified.
7. A DD user reviews and clicks Confirm.
8. System auto-creates the project and a read-only client login, and emails the client a magic link to their reports.
9. Client uses the magic link to view only their project's reports.

## UI/UX feel

- Matches DD Planner's existing clean, professional styling for all internal screens (builder, dashboard, confirm step).
- The client-facing proposal keeps the existing premium look from the v4 template — narrative chapters, charcoal/blue/bronze palette, display typography, section nav, and the Accept panel — unchanged in character.
- The builder feels like a guided conversation, not a long form: the PM is never staring at an empty template; the AI proposes content and the PM refines.
- Clear, low-pressure language around Accept ("Confirm your preferred path" / "This is not a binding contract") consistent with the README's intent.

## Implementation phases

**Phase 1 — MVP (built now):**
- ✅ SHIPPED & VERIFIED (backend 14/14, frontend 9/9). See /app/plan/plan.md for the full approved spec.
- AI-guided builder: chat + live editable form, section by section, from pasted notes / plain-English description (no external integrations).
- Live preview of the client-facing nine-chapter proposal.
- Secure private link per proposal (unguessable, no-index, optional expiry on validity date).
- Public client proposal view with engagement tracking (opened, section views, option interest, appendix, accept) surfaced to the PM.
- Accept flow (name + chosen path) recorded as soft intent; DD notified.
- DD Confirm step → auto-create Project from the accepted option + provision read-only client login scoped to that project's reports.
- Passwordless magic-link email to the client via Resend (see assumptions on sender/domain). If email isn't configured yet, the same magic link and proposal link are available to copy/share manually.
- Proposals dashboard with statuses and quick actions.

**Phase 2 — Source ingestion:**
- Pull source content from an existing DD project in the app to pre-fill a proposal.
- Google Doc ingestion (import a finalized doc as the starting brief).
- Reusable proposal templates with saved defaults (credentials, standard options, case-study library) so new proposals start further along.

**Phase 3 — CRM & automation:**
- HubSpot integration: assemble the brief from a deal and write engagement/acceptance back to the deal.
- Automated proposal lifecycle notifications (reminders, "viewed but not accepted" nudges).
- Deeper analytics on proposal engagement across the portfolio.

## Assumptions

- **Two answers resolved to the broader option:** the builder is chat **with** an always-visible editable form (not chat alone); and for V1 source content is **pasted notes / plain English only** — Google Doc and HubSpot ingestion are deferred to Phases 2–3.
- **Accept is a soft intent, and provisioning is gated behind a DD Confirm step** (not fully automatic on client accept). This matches the README's "accept ≠ binding contract" and your preference for DD to confirm before a project and client login are created.
- **Client login is passwordless magic link**, read-only, scoped strictly to the single project created from that proposal (reuses DD Planner's existing client read-only reporting access).
- **AI uses the app's existing LLM access** (the same AI capability already powering PM Assist) to draft and refine proposal content; no new paid AI key is required from you.
- **Email uses Resend.** To actually send proposal links and magic links, a Resend API key and a verified sender domain are needed. Until that's provided, the flow is fully usable via copyable secure links; email sending is the only piece that waits on the key. (Confirm you want Resend, or name another provider.)
- **The existing v4 client-facing design is adopted as-is** for the proposal page (nine chapters, styling, tracking events, Accept panel). Content is generated into that design rather than redesigning it.
- **The project created on confirmation** inherits name, client, timeline/stages, and the pricing of the accepted option; the PM can edit the project afterward like any other DD project.
- **Clients do not need an account to view a proposal** — only the private link. A login (magic link) is created only after DD confirms an acceptance.
- **Tracking is engagement-only** (views/interest/accept) for internal visibility; it is not used to gate or restrict the client's access to the proposal.
- **Declined / expired proposals** are supported as statuses; a client may optionally give a reason when declining.
