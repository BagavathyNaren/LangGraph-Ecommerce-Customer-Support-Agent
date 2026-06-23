# Phase 6: Production Scaling & Portfolio — Implementation Plan

> **Blueprint Reference**: Phase 6 (📋 PENDING)  
> **Source of Truth**: [GEMINI.md](GEMINI.md) | [Blueprint.md](Blueprint.md) | [PRODUCTION_ARCHITECTURE.md](PRODUCTION_ARCHITECTURE.md)

This plan implements Phase 6 one step at a time, per the approved workflow rules in `.agents/AGENTS.md`.

---

## Step 1: Zero-Cost Scaling Limits
**Status**: `[x]` DONE

**What**: Optimize the GCP Cloud Run configuration to prevent runaway scaling and avoid incurring charges.
**Files to modify**:
- `.github/workflows/deploy_backend.yml`
**Details**:
- Add `--max-instances 5` to the `gcloud run deploy` command to enforce a hard cap, ensuring it never scales beyond the Always Free limits.

---

## Step 2: Automated Registry Cleanup Verification
**Status**: `[x]` DONE

**What**: Verify and solidify the automated Artifact Registry cleanup policies to preserve storage capacity (0.5 GB Free Tier).
**Files to verify/modify**:
- `cleanup_policy.json`
**Details**:
- Confirm the policy preserves only the 3 most recent images and automatically deletes revisions older than 14 days (GEMINI.md Rule 6).

---

## Step 3: Interactive Demo Mode
**Status**: `[x]` DONE

**What**: Develop a "Demo Mode" toggle in the frontend allowing recruiters or guests to instantly load pre-recorded, flawless scenarios (e.g., the "Chan" flow).
**Files to modify**:
- `frontend/src/App.jsx`
- (And relevant CSS/components)
**Details**:
- Add a toggle in the UI.
- When toggled, pre-fill the chat with the standard Chan scenario for instant demonstration of the ReAct loop without waiting for live LLM responses.

---

## Step 4: Premium Repository Documentation
**Status**: `[x]` DONE

**What**: Write a high-quality `README.md` for the repository portfolio.
**Files to modify**:
- `README.md`
**Details**:
- Add dynamic architecture mermaid diagrams.
- Add live badges for CI/CD status (PR Validation, Frontend Deploy, Backend Deploy).
- Provide setup instructions and link to the live staging URLs (Firebase & Cloud Run).

---

## Step 5: Final Zero-Cost Audit
**Status**: `[x]` DONE

**What**: Run a final mathematical and configuration audit against GCP's Always Free tier limitations.
**Files to modify**:
- N/A (Produces an audit report artifact)
**Details**:
- Verify VM (e2-micro) disk type is Standard, Cloud Run memory is 4Gi, max instances capped at 5, and Artifact Registry policies are active.

*(Note: "VM Database Connection Pooling with PgBouncer" is skipped or simplified if the e2-micro cannot safely run PgBouncer alongside Postgres without OOMing, per Zero-Cost constraints, or it will be evaluated during the audit).*

---

## Current Execution Pointer

▶️ **Next Step**: 🎉 Phase 6 is COMPLETE! The project is fully finalized.
