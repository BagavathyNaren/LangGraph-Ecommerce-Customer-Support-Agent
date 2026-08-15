# Gemini Context & Memory

## Summary Checklist for a "Zero-Cost" Architecture

To keep your monthly bill at ₹0.00 after your trial ends, you should aim to stay within these parameters:

| Service | Always Free Limit | Tip for Keeping it Free |
| :--- | :--- | :--- |
| **VM (e2-micro)** | 1 instance, 30 GB Standard Disk | Ensure disk type is "Standard" (not SSD/Balanced). |
| **Cloud Run** | ~180k vCPU-sec, ~360k GiB-sec | Keep traffic low; it scales to zero when idle. |
| **Firebase Hosting** | 10 GB Storage / ~360 GB Transfer | Generally free for low-traffic personal apps. |
| **Artifact Registry** | 0.5 GB Storage | Regularly delete old, unused container images. |
| **Cloud Logging** | 50 GB Ingestion/month | You likely won't hit this, but monitor if logs spike. |

---

## ⚠️ STRICT RULES & COMMITMENTS

1. **Explicit Permission Required**: ALWAYS ask the user for explicit confirmation before pushing any code to **GitHub, GCP Cloud Run, Firebase, or Hugging Face**.
2. **Model Selection for Simple Tasks**:
I want to conserve resources and avoid unnecessary token usage. Before running the simple tasks or commands below, always stop and let me approve it to run
3. **Follow user instructions**:
Before implementing the steps, make a plan, create a md file named implementation.md and give it to the user to review. Then wait for the user to approve the plan. Once the user approves the plan, implement it. After implementing one step in the plan, update the implementation.md file with the changes made and give it back to the user to review along with the test steps in the chat to test the particular step. Then wait for the user to test the changes. Once the user test the changes and approve the changes after testing, implement the next step.
4. **Cloud Run Memory Constraint**: Always use exactly **4GB (`4Gi`) memory** when deploying to Cloud Run to avoid connection problems (such as spaCy/Presidio startup OOM crashes).
5. **No Key Overwriting**: Never overwrite or delete the API Keys/environment variables stored in the Google Cloud Run Service.
6. **Automated Artifact Registry Cleanup**: Applied a cleanup policy to both repository `mcp-cloud-run-deployments` and `cloud-run-source-deploy` which automatically deletes revisions older than 14 days, while strictly preserving the 3 most recent images of each package at all times to ensure rollbacks are active and we never run out of free storage capacity.


7. **Project Roadmap & Context Navigation**:
ALWAYS refer to **[Blueprint.md](Blueprint.md)** for the master project roadmap and overall trajectory. ALWAYS refer to **[implementation.md](implementation.md)** for current execution steps to avoid deviating from the context and roadmap.

Command 1 : firebase deploy --only hosting --project my-agentic-lab

Command 2: gcloud run deploy ecommerce-support-agent --source . --region us-central1 --project my-agentic-lab --memory 4Gi


## Deployment Configuration
- Project ID: my-agentic-lab
- Region: us-central1
- Service name: ecommerce-support-agent

# Firebase Deployment Instruction
- To ensure the static frontend is up to date, run:
  ```
  firebase deploy --only hosting --project my-agentic-lab
  ```
