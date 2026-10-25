# Send Emails via Your Own Mailbox (SMTP) — No Email Vendor Required

Add a second way to send proposal and client-report emails: directly through your own existing email account over SMTP, so no third-party email service is needed. Keep the existing Resend option and let a workspace pick which one is active in Settings.

## Who it's for

- **Workspace administrators (super admins)** who would rather send from the company's own mailbox (e.g. a Google Workspace / Gmail address) than sign up for an email-sending vendor.
- **DD project managers / principals** who send proposals and client reports and want them delivered from the firm's real address.
- **Clients** who receive the proposal link and their report-access link as an email coming from the firm's own domain.

## Core features and experience

- **An "Email method" choice in Settings → Integrations.** The Email area now offers two methods — **SMTP (your own mailbox)** and **Resend (API)** — with a single selector for which one is "active". Only the active method is used when emails are sent. Nothing about the existing Resend panel is lost.
- **A new SMTP panel** sitting alongside the others, holding: the **SMTP host**, **port**, **username**, **password** (entered once, then shown masked), a **"from" address**, and an optional **"reply-to"** address. Saving stores it for that workspace.
  - **Gmail / Google Workspace helper text** built into the panel: a short note that Gmail requires 2‑Step Verification plus a 16‑character **App Password** (not the normal account password), with the standard host/port prefilled as sensible defaults (host `smtp.gmail.com`, port `587`) that can be changed for any other provider.
- **A "Send test email" button** for the SMTP panel (mirroring the existing Resend test), so an admin can confirm the mailbox connects and delivers before relying on it — and immediately see a readable error if the host/port/credentials are wrong or the provider blocks the login.
- **Same send points, now method-aware.** Sending a proposal, confirming an accepted proposal, and the client-report magic-link all use whichever method is active (SMTP or Resend).
- **Copy/share never breaks.** If no method is configured, the active method is off, or a send fails, the link is still shown on screen to copy and share by hand — exactly as today. Email stays a best-effort add-on.
- **Honest status back to the user.** After sending a proposal or confirming, the screen states whether the email actually went out or that the link should be shared manually, and why.
- **Secrets stay secret.** The SMTP password is write-once and returned only as a masked placeholder afterwards; saving an empty password keeps the previously stored one — matching how the Resend key and other integration secrets already behave.

## User flow

1. A super admin opens Settings → Integrations → Email, picks **SMTP (your own mailbox)** as the method, enters host/port/username/password and the "from" address, saves, and clicks **Send test email** to confirm delivery.
   - For a Gmail/Workspace mailbox they use an **App Password** generated from their Google account (the panel explains this); for any other provider they enter that provider's SMTP details.
2. A PM sends a proposal; the client receives an email from the firm's own address with the secure link. The PM sees "email sent".
3. The client accepts; a DD user confirms; the client receives an email with their report access link.
4. If the active method is off or misconfigured, every one of those steps still shows the link on screen to copy and share, with a note that email wasn't sent.

## UI/UX feel

- Matches the existing Integrations panels exactly (selector, masked-secret fields, save button, inline test result) — no new screens or navigation.
- The two methods read as siblings: choose one, fill it in, test it. Switching methods later is a single selection and a save.
- Gmail setup friction is reduced by the inline App Password explanation and prefilled standard host/port, while the fields stay generic enough for Microsoft 365, a hosting provider's SMTP, or any other server.
- Honest status messaging so a PM is never unsure whether the client was emailed.

## Implementation phases

**Phase 1 — MVP (built now):** Add the SMTP email method (host, port, username, password, from, optional reply-to, masked secret, test-send) with Gmail/Workspace App Password guidance and prefilled defaults. Add a method selector (SMTP or Resend) that controls which path is used at send time. Route all proposal and client-report emails through the active method. Keep every copy/share link working when email is off or fails, with clear "sent / not sent" status.

**Phase 2 (later, not built now):** Customisable email content — editable subject/body templates and workspace branding (logo, colours) on the proposal and report emails, shared across whichever send method is active.

**Phase 3 (later, not built now):** Delivery visibility — a log of what was emailed to whom and when, plus reminders (e.g. "proposal viewed but not accepted"), building on the existing engagement tracking.

## Assumptions

- **SMTP is added as an alternative, not a replacement.** The existing Resend option stays; a per-workspace selector chooses the active method, and only the active one sends. (Confirmed.)
- **The SMTP panel is generic** (host, port, username, password, from, reply-to) so it works with Google Workspace/Gmail, Microsoft 365, or any SMTP server — with Gmail defaults prefilled and App Password guidance shown. (Confirmed direction.)
- **Sending is from the workspace's own business-domain mailbox at low volume** (proposals + report links, not bulk). Deliverability relies on the domain's normal SPF/DKIM, which business Google/Microsoft domains generally already have; no domain-authentication UI is built here. (Confirmed.)
- **Gmail/Workspace requires an App Password** (2‑Step Verification enabled); ordinary account passwords and "less secure app" sign-in are not supported by Google. The panel surfaces this; generating the App Password is the admin's step in their Google account.
- **Common secure-port defaults** are offered (587 with STARTTLS as the default, 465 for implicit TLS) and can be overridden; the panel does not try to auto-detect a provider.
- **Configuring email is a super-admin action**, consistent with the other integration panels; sending itself happens automatically as part of existing PM actions and needs no special permission.
- **Credentials are stored in the application's settings store**, shown masked after first save, with empty-on-save meaning "keep existing" — matching the current Resend/HubSpot/Google Drive panels.
- **Email is best-effort and never blocks the core action**: a failed or unconfigured send still completes the proposal-send or confirm and returns the shareable link.
- **Email body/subject are the current built-in formats** for this phase; editable templates and branding are deferred to Phase 2.
- **If neither method is configured, behaviour is unchanged from today** — links are generated and shown for manual sharing; nothing is auto-sent.
- **No new third-party account is introduced** by this plan; SMTP uses credentials the workspace already owns.
