# Remediation Plan: Resolving Production PDF/PPT Report Export (503 Error)

## 1. Problem Diagnosis
In production on Google Cloud Run (`https://ddplan-502760053858.australia-southeast1.run.app`), clicking "Export as PDF" or "Export as PPTX" fails with `HTTP 503 Service Unavailable`.

### Root Cause Factors
1. **Server-Side Headless Browser Constraints on Cloud Run**:
   - The current export mechanism relies on launching an internal headless Chromium browser via Playwright inside the Cloud Run container.
   - Cloud Run containers operate in a constrained virtualized sandbox with ephemeral filesystem limits (`/tmp`), restricted shared memory (`/dev/shm`), and CPU throttling when background child processes spawn.
   - When Playwright attempts to launch Chromium or render canvas/SVG charts in the background, the subprocess fails or crashes immediately, triggering Cloud Run's HTTP 503 error.
2. **Missing Dual-Layer Fallback Architecture**:
   - Currently, if the server-side headless browser encounters an issue, the system throws an unhandled failure instead of failing over to an instant server-side PDF generator (ReportLab) or a client-side direct exporter.

---

## 2. Proposed Solution

We will implement a **Two-Tier Resilient Export Architecture**:

### Tier 1: Client-Side Direct High-Fidelity PDF Export (Instant & 100% Cloud-Proof)
- Because the project report is already fully fetched, rendered, and visible in the user's browser, the report page will generate and download the PDF directly using client-side rendering.
- **Benefits**:
  - Zero server load and zero reliance on server-side browser binaries.
  - Generates the exact 16:9 widescreen presentation layout instantly without roundtrips.
  - Immune to Cloud Run timeouts, cold starts, memory limits, and container sandbox restrictions.

### Tier 2: Resilient Server-Side Fallback (Lightweight Engine + Failover)
- Update the server export endpoint (`/api/projects/{id}/export/pdf`) to:
  1. Attempt headless Chromium execution with `--single-process=false`, `--disable-dev-shm-usage`, and `/tmp` scratch storage.
  2. If Chromium fails or is terminated by Cloud Run, automatically fall back to **ReportLab** (already installed in the backend) to assemble and return a structured PDF report containing all project metrics, status updates, risks, and timeline summaries.
  3. Ensure the endpoint never emits an unhandled 503.

### Tier 3: Deployment & Infrastructure Alignment
- Verify that Cloud Run deployment configuration on `ddplan`:
  - Allocates 2GiB memory and 2 vCPUs.
  - Has `PLAYWRIGHT_BROWSERS_PATH=/pw-browsers` set in container environment variables.
  - Ensures `--execution-environment=gen2` (Cloud Run second generation, which provides a full Linux kernel and `/dev/shm` support).

---

## 3. Decisions & Choices for User Approval

1. **Primary Export Trigger**:
   - **Option A (Recommended)**: The "Export as PDF" button will immediately generate and download the high-fidelity PDF directly in the browser, with an option to request a server-compiled archive if needed.
   - **Option B**: Continue attempting the server-side Playwright rendering first, with an automatic instant client-side download fallback if the server returns any non-200 status.
   - *Default Assumption*: Option B (preserves existing server flow while guaranteeing that the user always receives their file).

2. **ReportLab Server Fallback Scope**:
   - When server fallback engages, generate a clean branded PDF report containing Project Overview, Timeline, Financials, Risks, and Status Updates.

---

## 4. Acceptance Criteria
- Clicking "Export as PDF" on any project (including `TradesX Phase 2 Production Build`) successfully downloads a PDF file on production.
- Zero 503 error toasts displayed to users.
- Export works reliably regardless of container cold-starts, memory limits, or headless browser status.
