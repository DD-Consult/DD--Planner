# AWS Bedrock for DD Planner's AI — plus smarter, self‑improving guidance

Add AWS Bedrock as the AI engine behind every assistant feature in DD Planner, configured once from Settings with a Bedrock API key, and make that AI noticeably sharper by feeding it more of the workspace's real data and by learning from thumbs‑up/down feedback over time.

## Who it's for

- **Workspace administrators (super admins)** who want to point all of DD Planner's AI at their own AWS Bedrock account (their model, their region, their billing, their data‑handling terms) instead of the built‑in default.
- **Project managers / principals** who use the AI every day — PM Assist chat, work‑breakdown generation, status summaries, rescheduling, proposal drafting, portfolio insights — and want answers grounded in the actual state of their projects.
- **The business**, which wants the guidance to get better over time rather than stay static.

## Core features and experience

- **An "AWS Bedrock" choice in Settings → AI.** The existing AI‑provider setting gains Bedrock as an option alongside what's there today. Selecting it reveals a Bedrock API key field (entered once, then shown masked), an AWS region, and a model selection (with a sensible current Claude model prefilled, editable for any Bedrock‑supported model). Saving stores it for the workspace.
- **A "Test Bedrock" button** so an admin can confirm the key, region and model actually work before relying on it — and immediately see a readable error if the region has no model access, the key is wrong, or the model id isn't available.
- **Bedrock powers everything once active.** When Bedrock is the selected provider, every AI feature in the app routes through it: PM Assist chat, WBS generation, status‑update drafting, smart reschedule, proposal drafting/refinement, document‑ and project‑sourced proposals, and portfolio insights. Nothing about how those features look or are triggered changes — only the engine behind them.
- **Graceful fallback, never a dead end.** If Bedrock is misconfigured or a call fails, the feature degrades the same way it does today (clear message, the action still completes where it can) rather than erroring out. Switching providers later is a single selection and a save.
- **Richer, automatic context (sharper answers).** The AI is given more of the real workspace picture relevant to each request — e.g. a project's history, open risks, recent status updates, timesheet/actuals, team capacity, and related past proposals — so its guidance is specific rather than generic. This happens behind the scenes; there is no new screen and no extra step for the user.
- **A feedback / learning loop (self‑improving guidance).** Wherever the AI produces something, the user can mark it helpful or not and optionally say why. Those signals, together with the workspace's written AI instructions, are fed back into future prompts so the assistant trends toward what this team actually wants. Admins can see what feedback has been captured.
- **Secrets stay secret.** The Bedrock API key is write‑once and shown only as a masked placeholder afterwards; saving an empty key keeps the previously stored one — matching how the other integration secrets already behave.

## User flow

1. A super admin opens Settings → AI, picks **AWS Bedrock**, pastes the Bedrock API key, sets the region and model, saves, and clicks **Test Bedrock** to confirm it works.
2. From then on every AI action in the app (chat, WBS, summaries, reschedule, proposals, insights) runs on Bedrock — with the extra real‑project context automatically included — so the output is more specific and on‑point.
3. After an AI result appears, the user clicks thumbs‑up or thumbs‑down (and can add a quick note). Over time those signals plus the workspace's AI instructions nudge future responses toward the team's preferences.
4. If Bedrock isn't configured or a call fails, the feature behaves exactly as it does today (clear status, no hard failure); an admin can switch the provider back at any time.

## UI/UX feel

- Matches the existing Settings → AI and Integrations panels precisely (provider selector, masked‑secret field, region/model fields, inline test result) — no new navigation.
- The feedback control is a small, unobtrusive thumbs‑up/down that sits next to AI output and never gets in the way; leaving feedback is optional.
- Richer context is invisible by design: same screens, better answers.
- Honest messaging throughout, so an admin always knows whether Bedrock is connected and a PM is never guessing why an answer was generic.

## Implementation phases

**Phase 1 — MVP (built now):** Add AWS Bedrock as a selectable AI provider in Settings (API‑key auth + region + model, masked secret, test button), and route all AI features through it when selected, with graceful fallback. Expand the context passed into AI prompts with the most relevant real workspace data per feature. Add the thumbs‑up/down feedback control on AI outputs, store the signals, and feed recent feedback plus workspace AI instructions into subsequent prompts so guidance starts improving.

**Phase 2 (later, not built now):** A one‑click "generate realistic sample data" tool for admins (believable projects, allocations, WBS, proposals) to seed demos, trials and training — distinct from the read‑only public demo.

**Phase 3 (later, not built now):** Deeper learning and analytics — trends in AI feedback across features, prompt/version tracking, and automated suggestions to refine the workspace's AI instructions based on what's been rated well or poorly.

## Assumptions

- **Authentication is the Bedrock API key** (the `AWS_BEARER_TOKEN_BEDROCK` style) plus an AWS region — not classic access‑key/secret pairs. (Confirmed.)
- **Bedrock, once selected, is the single app‑wide provider for all AI features**, replacing the current default across the board; the existing providers remain available to switch back to. (Confirmed.)
- **The default model is a current Claude model on Bedrock**, editable by the admin; the admin must have model access enabled in their chosen region, and the panel's test button surfaces it if they don't.
- **Configuring Bedrock is a super‑admin action** in Settings → AI, consistent with the other integration/secret panels; using the AI happens automatically inside existing features and needs no special permission.
- **The credential is stored in the application's settings store**, shown masked after first save, with empty‑on‑save meaning "keep existing."
- **"Improve the AI guidance" for the MVP means two things together:** automatically richer real‑data context in prompts, and a thumbs‑up/down feedback loop whose signals (with the workspace's written AI instructions) steer future prompts. Generating mock/sample data is deferred to Phase 2. (Confirmed direction.)
- **AI remains best‑effort:** a Bedrock failure or missing configuration never blocks the underlying action; the feature falls back to its current behaviour with a clear message.
- **Feedback is captured per AI feature and visible to admins;** it influences prompts in a lightweight way in this phase (recent relevant feedback + instructions included as guidance), with heavier analytics/auto‑tuning deferred to Phase 3.
- **Region availability and billing are the workspace's responsibility;** no AWS account setup, model‑access request, or cost controls are built here beyond surfacing errors from Bedrock.
- **No change to how any AI feature is triggered or displayed** — only the engine and the quality/grounding of its output change.
