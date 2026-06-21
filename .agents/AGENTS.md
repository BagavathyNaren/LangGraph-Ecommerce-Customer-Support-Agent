# LanGraph E-Commerce Agent — Workspace Rules

These rules govern all AI agent behavior when working on this project. They are derived from recurring failure patterns and are **non-negotiable**.

---

## Process Rules

### Rule 1: Source-of-Truth Workflow

Before starting ANY task:
1. Read **GEMINI.md** — for strict constraints, deployment commands, and commitments.
2. Read **Blueprint.md** — for the master project roadmap and current phase status.
3. Read **PRODUCTION_ARCHITECTURE.md** — for the system architecture and component boundaries.
4. Read **implementation.md** — for the current execution context and active step.

Never deviate from these files. If a conflict arises, ask the user.

### Rule 2: One-Step-at-a-Time Execution

1. Create/update `implementation.md` with the full plan.
2. Present the plan to the user and **WAIT** for explicit approval.
3. Implement exactly **ONE step** from the plan.
4. Update `implementation.md` marking the step complete.
5. Provide **EXTENSIVE testing steps** for that ONE step in the chat.
6. **STOP** and wait for the user to test and approve.
7. Only after approval, proceed to the next step.

Never implement more than one step without user testing and approval in between.

---

## Domain Rules

### Rule 3: Conversation History Scanning

When scanning conversation history for context:
- Always scan in **REVERSE** (most recent first).
- To find "the AI message that prompted the user," locate the latest `HumanMessage` and then find the `AIMessage` immediately **BEFORE** it (not the most recent `AIMessage` overall).
- Never assume the last `AIMessage` in the list is the one that prompted the current user input.

### Rule 4: State Isolation Between Customer Sessions

- Never carry over customer state (name, email, country, order history) from one session to another.
- When a new/unregistered customer is detected, the agent **MUST** explicitly ask for **BOTH** full name **AND** email address before placing any order.
- The LLM prompt **MUST** contain a negative constraint: *"Never reuse or assume a customer's name or email from a previous conversation turn or session."*

### Rule 5: Profile Country Enforcement

- When a registered customer's profile is loaded (via `lookup_customer_orders`), their profile country becomes the **ONLY** valid country for all subsequent search/order tool calls.
- If the user verbally requests a different country, the system **MUST** silently override the requested country with the profile country.
- This override must happen at the **programmatic guardrail level**, NOT rely on LLM compliance.

### Rule 6: Active Flow Priority Over Anger Detection

- If the user is in an active cancellation flow (`is_cancelling == True`), completely **bypass** anger accumulation in `escalation_check`.
- The cancellation flow takes **absolute priority** over the escalation pathway.
- Only trigger escalation for anger words **OUTSIDE** of an active order operation (cancellation, return, refund).
