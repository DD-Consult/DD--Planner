# Proposal & Report Emails via Resend — Configurable per Workspace

Turn the proposal link and client report magic-link from copy-and-share into real emails, with the email account set up inside the app's Settings by each workspace rather than baked into the server.

## Who it's for

- **DD project managers / principals** who send proposals and client reports and want them delivered straight to the client's inbox instead of pasting a link.
- **Workspace administrators (super admins)** who need to connect their own email-sending account once, from Settings, without any server/redeploy work.
- **Clients** who receive the proposal and their report-access link directly by email.

## Core features and experience

- **An "Email (Resend)" panel in Settings → Integrations**, sitting alongside the existing HubSpot, AI Agent, and Google Drive panels. It holds: an on/off toggle, the Resend API key (entered once, then shown masked), the "from" sender address, and an optional "reply-to" address. Saving stores it for that workspace.
- **A "Send test email" button** in the panel so an admin can confirm the setup works (and immediately see Resend's typical "verify your domain first / can only email yourself until then" message if the domain isn't verified yet).
- **Real emails on the actions that already produce links:**
  - Sending a proposal emails the secure proposal link to the client contact.
  - Confirming an accepted proposal emails the client their report magic-link.
  - The existing client-report magic-link flow uses the same configured sender.
- **Copy/share never breaks.** If email isn't configured, isn't enabled, or a send fails, the link is still returned on screen to copy and share by hand — exactly as today. Email is strictly an add-on.
- **Clear status back to the user.** After sending a proposal or confirming, the screen states whether the email actually went out or whether the link should be shared manually (and why, e.g. "email not configured").
- **Secrets stay secret.** The API key is write-once and returned only as a masked placeholder afterwards; saving an empty key keeps the previously stored one.

## User flow

1. A super admin opens Settings → Integrations → Email (Resend), turns it on, pastes the Resend API key and the "from" address, saves, and clicks "Send test email" to confirm delivery.
2. A PM sends a proposal; the client receives an email with the secure link. The PM sees "email sent".
3. The client accepts; a DD user confirms; the client receives an email with their report access link.
4. If email is off or misconfigured, every one of those steps still shows the link on screen to copy and share, with a note that email wasn't sent.

## UI/UX feel

- Matches the existing Integrations panels precisely (toggle, masked-secret field, save button, inline test result) — no new screens or navigation.
- Low-friction: set once, works everywhere email is sent from; nothing changes about how proposals or reports are created.
- Honest status messaging so a PM is never unsure whether the client was emailed.

## Implementation phases

**Phase 1 — MVP (built now):** Add the Email (Resend) settings panel (enable, API key, from, optional reply-to, masked secrets, test-send). Route all proposal and client-report emails through the per-workspace configuration, resolved at send time. Keep every copy/share link working when email is off or fails, with clear "sent / not sent" status.

**Phase 2 (later, not built now):** Customisable email content — editable subject/body templates and workspace branding (logo, colours) on the proposal and report emails.

**Phase 3 (later, not built now):** Delivery visibility — a log of what was emailed to whom and when, plus open/click tracking and automated reminders (e.g. "proposal viewed but not accepted") building on the existing engagement tracking.

## Assumptions

- **Provider is Resend** (the app already uses it); this change makes the account **per-workspace, configured in Settings**, instead of a single server-wide default.
- **Configuring email is a super-admin action**, consistent with the other integration panels; sending itself happens automatically as part of existing PM actions and needs no special permission.
- **A verified sender domain is the workspace's responsibility.** Until the domain is verified in Resend, sends are limited by Resend (typically only to the account owner's own address); the test-send surfaces this. No domain-verification UI is built here.
- **If no key is configured, behaviour is unchanged from today** — links are generated and shown for manual sharing; nothing is auto-sent.
- **Credentials are stored in the application's settings store**, shown masked after first save, with empty-on-save meaning "keep existing" — matching the current HubSpot/Google Drive panels.
- **Email is best-effort and never blocks the core action**: a failed send still completes the proposal-send or confirm and returns the shareable link.
- **Email body/subject are the current built-in formats** for this phase; editable templates and branding are deferred to Phase 2.
- **This is the next build; the other open items** (live Google Drive import, HubSpot Phase 3, and the Time Off "who's out" summary) remain deferred and are not part of this plan.
