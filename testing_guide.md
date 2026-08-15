# 🧪 Extensive Manual UI Testing Guide — Bug Fixes Verification

All bug fixes have been successfully implemented, and the application has been deployed to **Firebase Staging** and **GCP Cloud Run**. Please follow these extensive testing steps to ensure everything works flawlessly before we proceed to Phase 5.

## 🛠️ Prerequisites & Setup
- **Production Staging URL:** [https://my-agentic-lab.web.app](https://my-agentic-lab.web.app)
- **Backend URL:** https://ecommerce-support-agent-93337753347.us-central1.run.app

---

### 📝 Test Case 1: Unregistered Checkout Registration (Bug #1 & #4 Fix)

> [!IMPORTANT]
> The agent must no longer hallucinate customer names (e.g., "Alis") and must explicitly ask for both the **full name** and **email address** when a new customer checks out.

1. **Step:** Start a new, fresh session (refresh the page). Do **NOT** introduce yourself.
2. **Step:** Type: `"Search for laptops in UK"`
3. **Step:** Select a product by clicking the **Checkout** button in the Live Store Matches drawer (or type `"I choose the Amazon option: [Product Name] at price [Price]"`).
4. **Expected AI Response:** 
   `"Could you please provide your full name and email address so I can register your account and place your order?"`
5. **Step:** Provide your details: `"My name is Naren and my email is narenbagavan@gmail.com"`
6. **Final Expected Behavior:** The order confirmation block will explicitly display `Customer Name: Naren` and `Registered Email: narenbagavan@gmail.com`.

---

### ❌ Test Case 2: Negative Cancellation Escalation (Bug #2 Fix)

> [!WARNING]
> Negative reasons like "broken" or "horrible quality" combined with anger words must trigger immediate escalation to a human support agent instead of just canceling the order.

1. **Step:** Refresh the page to start a new session.
2. **Step:** Input: `"Cancel my order ORD3926"` (or any valid Processing order ID).
3. **Step:** The agent will ask for the reason for the cancellation.
4. **Step:** Reply with explicit anger and negative reasons: `"The item is broken, horrible quality, and I am angry!"`
5. **Expected Behavior:** 
   - The agent should append an escalation response: `"I've escalated your case to a human agent. Ticket ID: TKT-XXXXX. A human agent will contact you within 2 hours."`
   - A ticket should be created in the system linking to the order.

---

### 🎙️ Test Case 3: Speech Recognition Latency & Cut-offs (Bug #3 Fix)

> [!NOTE]
> The timeouts have been recalibrated (`1.5s` for completed sentences, `3.5s` for pauses/interim speech).

1. **Step:** Click the microphone to start listening.
2. **Step:** Speak a sentence slowly, pausing briefly in the middle. Example: *"I want to search for [pause 2 seconds] PlayStations in the UK."*
3. **Expected Behavior:** 
   - The agent should **not** cut you off during the 2-second pause. 
   - After you completely finish the sentence, the agent should submit the message within ~1.5 seconds, significantly reducing the perceived latency.

---

### 🌌 Test Case 4: Jarvis Hands-Free Passive UI (Bug #5 Fix)

1. **Step:** Enter **Jarvis Mode** (click the ORB or type `"Jarvis"`).
2. **Step:** Stop speaking and just observe the UI after the AI finishes speaking.
3. **Expected Behavior:**
   - The `Listening...` text will **no longer** sit statically on the screen irritatingly.
   - The UI will remain completely hands-free. The microphone is actively listening in the background, but the text indicator will only appear when you actually begin speaking, making the interface feel completely "standby" and natural.

---

### 🚀 Next Steps
Once you have executed these test cases and are satisfied with the fixes, we are ready to advance to **Phase 5 (CI/CD Deployment Pipelines)**!
