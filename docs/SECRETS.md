# Secure Secret Management

To ensure successful CI/CD deployments via GitHub Actions, the following repository secrets must be configured.

You can add these secrets by navigating to your repository on GitHub:
**Settings** -> **Security** -> **Secrets and variables** -> **Actions** -> **New repository secret**.

## 1. FIREBASE_TOKEN
**Purpose**: Used by `.github/workflows/deploy_frontend.yml` to deploy the frontend assets to Firebase Hosting.
**Required for**: Frontend Auto-Deployment
**How to get it**:
1. Open your local terminal.
2. Run `npx firebase-tools login:ci`.
3. Follow the browser prompt to log in with your Google account.
4. Copy the token string printed in the terminal (starts with `1//`).

## 2. GCP_SA_KEY
**Purpose**: Used by `.github/workflows/deploy_backend.yml` to authenticate with Google Cloud and deploy the FastAPI container to Cloud Run.
**Required for**: Backend Auto-Deployment
**How to get it**:
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Navigate to **IAM & Admin** -> **Service Accounts**.
3. Create a service account (e.g., `github-actions-deployer`).
4. Grant it the following roles:
   - **Cloud Run Admin**
   - **Service Account User**
   - **Artifact Registry Writer** (if using Artifact Registry) or **Storage Admin** (if using GCR).
5. Click on the newly created service account, go to the **Keys** tab, click **Add Key** -> **Create new key**, and select **JSON**.
6. The JSON file will download. Copy the *entire contents* of this file and paste it as the secret value.

## 3. DATABASE_URL (Staging - Optional)
**Purpose**: Used by backend unit tests and E2E tests if they ever need to connect to a real staging database. Currently, tests run using a dummy local mock, but this is reserved for true staging integration.
**How to get it**:
1. Get the connection string for your staging PostgreSQL instance.
2. Format: `postgresql://<username>:<password>@<host>:5432/<dbname>`
