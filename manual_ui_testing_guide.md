# 🧪 Manual UI Testing Guide — Phase 4 Verification

This guide outlines the extensive, step-by-step verification procedures to test all the newly implemented Phase 4 features and bug fixes directly in the E-Commerce Customer Support Agent UI.

---

## 🛠️ Prerequisites & Setup

Ensure the application is running locally or deployed.
- **Local Development URL:** `http://localhost:5173`
- **Production Staging URL:** [https://my-agentic-lab.web.app](https://my-agentic-lab.web.app)

---

## 🎯 Test Scenarios Checklist

| Scenario ID | Target Feature | Key Focus | Status |
| :--- | :--- | :--- | :--- |
| **TC-01** | **Jarvis Mode Activation & continuous voice flow** | Toggle Jarvis, voice commands, auto-listening without clicks | 📋 Pending |
| **TC-02** | **India Context Isolation** | Inputting "I am from India" without triggering massive product list | 📋 Pending |
| **TC-03** | **Order Cancellation Logic & Escalation** | Requires cancellation reason; negative reasons trigger escalation ticket | 📋 Pending |
| **TC-04** | **Name Parsing with Spaced Letters** | Parsing name introductions like "a h i l a" -> "Ahila" | 📋 Pending |
| **TC-05** | **Orb & Soundwave Visual Feedback** | Glowing ORB visual pulse, continuous dynamic soundwave animation | 📋 Pending |
| **TC-06** | **Caching & Response Validation** | Zero latency repeat queries; visual drawer animation stability | 📋 Pending |
| **TC-07** | **Vibrant Confetti & Skeleton Loaders** | Skeletal loader presence during search; confetti celebration on order | 📋 Pending |

---

## 📘 Step-by-Step Test Procedures

### 🎙️ TC-01: Jarvis Mode Activation & Continuous Voice Flow

> [!IMPORTANT]
> Jarvis Mode introduces a hands-free conversational flow where the microphone automatically starts listening again once the AI finishes speaking.

1. **Via Chat Input:**
   - Open the web application.
   - In the text box, type exactly `"Jarvis"` or `"Activate Jarvis"` and press **Enter**.
   - **Expected Behavior:** 
     - The chat box clears, and the interface morphs into the dark, glassmorphic **Jarvis UI**.
     - An agent message is added: `"J.A.R.V.I.S online. How may I assist you?"`.
     - The voice output says the same phrase.
2. **Via Voice Toggle:**
   - Refresh the page to start clean.
   - Click the **Jarvis** button or the floating blue **ORB** in the bottom right corner.
   - **Expected Behavior:** 
     - Interface enters Jarvis Mode instantly.
     - Pulsating glow surrounds the ORB.
3. **No-Click Continuous Listening:**
   - Speak into your microphone: `"Who is the customer ORD6015?"` (or type it if microphone access is blocked).
   - Once the agent finishes reading the order details, watch the microphone state.
   - **Expected Behavior:** 
     - The mic state transitions automatically back to `"Listening..."` without requiring any clicks.
     - The soundwave starts moving, ready for your next voice query.

---

### 🇮🇳 TC-02: India Context Isolation (Bug #1 Fix)

> [!NOTE]
> Previously, inputting location statements like "I am from India" caused the agent to dump all available products from Croma, Amazon, and Flipkart.

1. **Step:**
   - Enter standard Normal UI or Jarvis Mode.
   - In the chat box, type or speak exactly: `"I am from India"` and press **Enter**.
2. **Expected Behavior:**
   - The agent should **NOT** print any list of products.
   - The agent should respond conversationally, acknowledging your location context.
   - **Example Correct Response:** `"Acknowledged. You are located in India. How can I assist you with your orders, returns, or product inquiries today?"`

---

### ❌ TC-03: Order Cancellation Logic & Escalation (Bug #2 Fix)

> [!WARNING]
> Cancellations must verify reasons and route frustrated customers to live human support.

1. **Attempting Immediate Cancellation (No Reason):**
   - In the chat box, type: `"Cancel my order ORD3561"` and press **Enter**.
   - **Expected Behavior:** 
     - The agent must **NOT** cancel the order immediately.
     - The agent should request a valid reason: `"To process the cancellation for order ORD3561, could you please provide a reason for the request?"`
2. **Providing a Friendly/Standard Reason:**
   - Reply to the agent: `"I bought it by mistake."`
   - **Expected Behavior:** 
     - The agent processes the cancellation successfully.
     - Database status updates to Canceled.
     - A confirmation is shown with refund details.
3. **Providing a Negative/Frustrated Reason (Escalation Trigger):**
   - Start a fresh session.
   - Type: `"Cancel my order ORD3561"`
   - When the agent asks for the reason, reply: `"The item is broken, horrible quality, I am extremely angry!"`
   - **Expected Behavior:** 
     - The cancellation is halted.
     - The agent triggers the escalation node.
     - A high-priority Support Ticket is automatically generated.
     - The agent replies with the ticket details: `"I have escalated this issue to our human support team. Your Ticket ID is TKT-XXXXX."`

---

### 📛 TC-04: Name Parsing with Spaced Letters (Bug #4 Fix)

1. **Step:**
   - In the chat box, type: `"My name is a h i l a"` and press **Enter**.
2. **Expected Behavior:**
   - The regex name-parser extracts and normalizes the letters.
   - The agent should greet you using your normalized name.
   - **Example Correct Response:** `"Hello Ahila! How can I assist you today?"`

---

### 🌌 TC-05: Orb & Soundwave Visual Feedback

1. **Step:**
   - Switch to **Jarvis Mode**.
   - Trigger a conversation or let the AI speak.
2. **Expected Behavior:**
   - **ORB:** The central JARVIS circular avatar exhibits a smooth, pulsating glow (`animate-pulse` or similar CSS transform scale transitions).
   - **Soundwave Visualizer:** A multi-colored high-fidelity digital waveform canvas renders in real-time, matching microphone input capture and synthetic speech output frequencies.

---

### ⚡ TC-06: Caching & Response Validation

1. **Step:**
   - Type a query like: `"Search for PlayStations in UK"` and press **Enter**.
   - Note the response time (which executes live tools, taking 1.5s - 3s).
   - In the same or a new chat session, type or speak exactly the same query: `"Search for PlayStations in UK"` and press **Enter**.
2. **Expected Behavior:**
   - The response renders **instantly** (under 50ms) from the database cache.
   - **⚡ Cached Badge:** A beautiful, glowing gold/amber pill badge containing the label `⚡ Cached` will appear on the bot's response message card, indicating that the cache was successfully hit!
   - The **Live Store Matches** drawer on the right side transitions smoothly and displays cached products instantly without flickering or layout shifts.


---

### 🎉 TC-07: Vibrant Confetti & Skeleton Loaders

1. **Skeleton Loaders:**
   - Type: `"Search for laptops in UK"`
   - Watch the right-hand panel while the agent works.
   - **Expected Behavior:** Clean modern skeleton card placeholders shimmer (animate-pulse) to bridge perceived delay before live cards render.
2. **Vibrant Confetti:**
   - Finish checking out a new product (e.g. Chanel perfume in UK or PlayStation in India).
   - Provide email for registration if unregistered, then confirm checkout.
   - **Expected Behavior:** A colorful burst of confetti explodes across the entire viewport upon rendering the Order Confirmation panel!

---

## 📈 Verification Checklist Completion

Once you have verified these manual steps, you can approve transitioning to **Phase 5 (CI/CD Deployment Pipelines)**!
