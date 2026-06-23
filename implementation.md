# Phase 5: CI/CD Deployment Pipelines — Implementation Plan

> **Blueprint Reference**: Phase 5 (📋 PENDING)  
> **Source of Truth**: [GEMINI.md](GEMINI.md) | [Blueprint.md](Blueprint.md) | [PRODUCTION_ARCHITECTURE.md](PRODUCTION_ARCHITECTURE.md)

This plan implements Phase 5 one step at a time, per the approved workflow rules in `.agents/AGENTS.md`.

---

## Step 1: PR Validation Workflow
**Status**: `[x]` DONE

**What**: Create a GitHub Actions workflow (`.github/workflows/pr_validation.yml`) that automatically runs `ruff check`, `ruff format --check`, and `pytest` on all pull requests targeting `main`.

**Files to create/modify**:
- `[NEW]` `.github/workflows/pr_validation.yml`

**Details**:
- Trigger: `pull_request` targeting `main` branch
- Python version: `3.12`
- Jobs:
  1. `lint-and-format` — Install ruff, run `ruff check .` and `ruff format --check .`
  2. `test` — Install dependencies from `requirements.txt` + `pytest`, run `pytest tests/`
- Mocked DB: Tests use `conftest.py` fixtures (no real DB needed in CI)

---

## Step 2: Fix Ruff Violations (Auto-fixable)
**Status**: `[x]` DONE

**What**: Run `ruff check --fix .` and `ruff format .` to auto-fix the 498 auto-fixable violations (trailing whitespace, import sorting, blank line whitespace). Then manually fix remaining line-length violations.

**Files to modify**:
- `tools/real_tools.py` (majority of violations)
- `graph/nodes.py`
- `main.py`
- `logger.py`
- Various other Python files

---

## Step 3: E2E Staging Pipeline
**Status**: `[x]` DONE

**What**: Create a GitHub Actions workflow that runs the Playwright E2E suite against the staging environment before allowing merges to `main`.

**Files to create**:
- `[NEW]` `.github/workflows/e2e_staging.yml`

---

## Step 4: Frontend Auto-Deployment
**Status**: `[x]` DONE

**What**: Configure GitHub Actions to automatically deploy to Firebase Hosting upon a successful merge to `main`.

**Files to create**:
- `[NEW]` `.github/workflows/deploy_frontend.yml`

**Constraints (from GEMINI.md)**:
- Command: `firebase deploy --only hosting --project my-agentic-lab`
- Must use `FIREBASE_TOKEN` secret (not service account, to stay zero-cost)

---

## Step 5: Backend Auto-Deployment
**Status**: `[ ]` PENDING

**What**: Configure GitHub Actions to build and deploy the container to GCP Cloud Run.

**Files to create**:
- `[NEW]` `.github/workflows/deploy_backend.yml`

**Constraints (from GEMINI.md)**:
- Command: `gcloud run deploy ecommerce-support-agent --source . --region us-central1 --project my-agentic-lab --memory 4Gi`
- Must enforce `4Gi` memory (GEMINI.md Rule 4)
- Must NOT overwrite existing env vars (GEMINI.md Rule 5)

---

## Step 6: Secure Secret Management
**Status**: `[ ]` PENDING

**What**: Document and configure the required GitHub repository secrets for all workflows.

**Secrets needed**:
- `FIREBASE_TOKEN` — for Firebase Hosting deployment
- `GCP_SA_KEY` — GCP service account JSON for Cloud Run deployment
- `DATABASE_URL` — for E2E tests against staging DB (if applicable)

---

## Current Execution Pointer

▶️ **Next Step**: Step 5 (Backend Auto-Deployment)
