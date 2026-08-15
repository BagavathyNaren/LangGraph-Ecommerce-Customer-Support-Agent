# 🗺️ Master Project Blueprint: LangGraph E-Commerce Customer Support Agent

This document represents the static, high-fidelity reference plan for the entire project. It formally incorporates robust engineering pillars—CI/CD, Comprehensive Testing, and Production Scaling—while strictly adhering to the "Zero-Cost Architecture" constraints. 

All phases have been expanded into granular, extensive checklists to ensure nothing is overlooked.

---

## 🏗️ 6-Phase Master Plan & Current Status

### 🔴 Phase 1 — Stability & Core Architecture
*   **Status**: ✅ **COMPLETED**
*   **Deliverables**:
    *   [x] **Currency Normalization (Bug #2)**: ✅ DONE — `real_tools.py` now returns `₹`, `$`, `€`, `£`, `￥` symbols. `App.jsx` safety-net extended. Verified in tests.
    *   [x] **Platform Detection & Parsing (Bug #1)**: ✅ WORKING — Live Store Matches sidebar is visible and displays all platforms correctly. Amazon, Flipkart, Croma cards render with correct currency symbols and Checkout buttons.
    *   [x] **ReAct Loop Stress Testing**: ✅ DONE — Rigorously tested loop safety cap via simulated cap limits. Configured agent node to set `escalated = True` upon cap exhaustion, successfully routing through the escalation framework to automatically create a human support ticket.
    *   [x] **API Resiliency & Fallbacks**: ✅ DONE — Implemented robust connection pooling, automated exponential retries, and fallback strategies for 100% of search APIs via a custom HTTP retry session wrapper in `real_tools.py`.
    *   [x] **Code Quality & Environment**: ✅ DONE — Integrated robust Pydantic-based `env_validator.py` running fail-fast checks at startup. Created `pyproject.toml` with Ruff styling rules. Verified via test cases.
    *   [x] **Extensive Verification Testing (Test Suite A)**:
        *   [x] **Test 1 (Chan, Japan)**: ✅ PASSED — Prices show `￥45,000` / `￥47,682` (not `JPY`). Live Store Matches panel visible with all 5 products.
        *   [x] **Test 2 (Chan Checkout)**: ✅ PASSED — Registered bypass working. Order placed immediately (ORD6015). No email ask. Correct `￥` symbol.
        *   [x] **Test 3 (Brad, UAE)**: ✅ PASSED — Verified agent retrieves products in AED (e.g. `AED 1,800`) and correctly rejects unsupported countries (such as China or Germany).
        *   [x] **Test 4 (India 3-Platform)**: ✅ PASSED — Amazon + Flipkart shown with `₹`. Croma also confirmed working in earlier Maheswari test (ORD3995 via Croma).
        *   [x] **Test 5 (Order Lookup)**: ✅ PASSED — Verified existing orders (such as ORD6015) are retrieved correctly with expected delivery dates and tracking information.

---

### 🟢 Phase 2 — Intelligence & Business Logic
*   **Status**: ✅ **COMPLETED**
*   **Deliverables**:
    *   [x] **Strict Country Constraints**: ✅ DONE — Supported countries restricted to UAE, Japan, US, UK, and India. Programmatically reject unsupported countries. Deleted China fallbacks and domains.
    *   [x] **Unregistered Customer Flow (New Orders)**: ✅ DONE — Catalog search first, checkouts explicitly halt tool calls to request email address first if unregistered.
    *   [x] **Context-Aware Country Memory**: ✅ DONE — Scan conversation in reverse, resolved critical PlayStation false-match bug with word boundaries.
    *   [x] **Advanced Registered Customer Bypass (Guardrail D)**: ✅ FIXED — Root cause was that `get_customer_orders()` returns `{"customer": {"email": ...}}` (nested), but Guardrail D was checking `tool_data.get("email")` (top-level). Fixed to check `tool_data.get("customer", tool_data).get("email")` so registered customers like Chan bypass the email ask correctly.
    *   [x] **Strict Order Validation Schema**: ✅ DONE — Enforced strict Pydantic OrderConfirmation schema validation before finalizing any database insert.

---

### 🟢 Phase 3 — UI/UX Features
*   **Status**: ✅ **COMPLETED**
*   **Deliverables**:
    *   [x] **Responsive Glassmorphism**: Finalize the modern glass UI layout to ensure perfect rendering across all mobile, tablet, and desktop viewports.
    *   [x] **Sidebar State Optimization**: Improve the Details Sidebar (Drawer) state management to eliminate any flickering during live context extraction.
    *   [x] **Voice Input Polish**: Refine speech recognition with noise cancellation handling, clear loading states, and visual feedback waveforms.
    *   [x] **Audio Output Caching**: Optimize the StreamElements high-volume output by aggressively caching TTS audio to prevent double-fetching on repeated phrases.
    *   [x] **Accessibility (a11y) Audit**: Ensure WCAG compliance for contrast ratios, screen readers, and keyboard navigation across both light and dark modes.
    *   [x] **Confetti Animation**: Integrate `canvas-confetti` into the React checkout handler for a vibrant celebratory burst upon successful order confirmation.
    *   [x] **Skeleton Loaders**: Implement elegant skeleton loading states for product search queries to reduce perceived latency.

---

### 🟢 Phase 4 — Comprehensive Testing Suite
*   **Status**: ✅ **COMPLETED**
*   **Deliverables**:
    *   [x] **Backend Unit Testing**: Achieve high `pytest` coverage for every individual function in `real_tools.py` and `nodes.py`. (ALL 17 TESTS PASSED)
    *   [x] **Agent Loop Integration Testing**: Simulate the LangGraph agent loops without calling the live OpenAI API (using mocked LLM responses) to verify state transitions. (ALL 4 SCENARIOS PASSED)
    *   [x] **E2E Browser Automation**: Configure Playwright or Cypress to automate the full frontend user journey (landing page -> product search -> checkout -> confirmation). (PLAYWRIGHT SPEC FULLY CONFIGURED)
    *   [x] **Performance/Load Testing**: Implement backend load testing (e.g., using Locust or k6) to ensure FastAPI can handle concurrent users. (LOCUSTFILE CONFIGURED)
    *   [x] **Chaos & Recovery Testing**: Ensure the system recovers gracefully when the database connection drops or an external API times out. (ALL 2 CHAOS TESTS PASSED)

---

### 🟢 Phase 5 — CI/CD Deployment Pipelines
*   **Status**: ✅ **COMPLETED**
*   **Deliverables**:
    *   [x] **PR Validation Workflow**: ✅ DONE — GitHub Actions workflow runs `pytest`, Ruff linting, and format checks on all pull requests. Comments failures directly on the PR.
    *   [x] **E2E Staging Pipeline**: ✅ DONE — GitHub Actions workflow runs the Playwright E2E suite against a local frontend preview before allowing merges to `main`.
    *   [x] **Frontend Auto-Deployment**: ✅ DONE — GitHub Actions automatically deploys to Firebase Hosting upon push to `main` using `FIREBASE_TOKEN` secret.
    *   [x] **Backend Auto-Deployment**: ✅ DONE — GitHub Actions builds and deploys the container to GCP Cloud Run with `4Gi` memory and `--max-instances 5`.
    *   [x] **Secure Secret Management**: ✅ DONE — `SECRETS.md` documents all required GitHub repository secrets (`FIREBASE_TOKEN`, `GCP_SA_KEY`, `DATABASE_URL`).

---

### 🟢 Phase 6 — Production Scaling & Portfolio
*   **Status**: ✅ **COMPLETED**
*   **Deliverables**:
    *   [x] **VM Database Connection Pooling**: SKIPPED — PgBouncer omitted to preserve e2-micro stability (1GB RAM constraint). Documented in zero-cost audit.
    *   [x] **Zero-Cost Scaling Limits**: ✅ DONE — Cloud Run hard-capped at `--max-instances 5` in `deploy_backend.yml`.
    *   [x] **Automated Registry Cleanup**: ✅ DONE — `cleanup_policy.json` preserves only 3 most recent images and deletes revisions older than 14 days.
    *   [x] **Interactive Demo Mode**: ✅ DONE — Play button in `App.jsx` header instantly loads the Chan/PlayStation/Japan scenario.
    *   [x] **Premium Repository Documentation**: ✅ DONE — `README.md` contains Mermaid architecture diagram, live CI/CD badges, and staging URLs.
    *   [x] **Final Zero-Cost Audit**: ✅ DONE — Audit report confirms all services within GCP Always Free tier limits.

---

## ⚡ Deployment & Staging Infrastructure

*   **Frontend (Firebase Hosting)**: 🔗 [https://my-agentic-lab.web.app](https://my-agentic-lab.web.app)
*   **Backend (GCP Cloud Run)**: 🔗 *[Your Cloud Run URL (e.g. asia-south1)]*
*   **Constraints**:
    *   **Cloud Run Memory**: Strictly limited to exactly `4Gi`.
    *   **VM (e2-micro)**: 1 instance, 30 GB Standard Disk.
