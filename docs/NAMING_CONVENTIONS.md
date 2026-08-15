# Naming Conventions and Migration Process

This project uses names that explain an action, the business object affected, and—where helpful—the result. Names must be easy to find with repository search and safe to change without breaking an API, a LangGraph checkpoint, or an LLM tool call.

## Conventions

Python code follows PEP 8:

| Item | Convention | Example |
| --- | --- | --- |
| Functions and variables | `snake_case` | `process_due_order_updates` |
| Classes | `PascalCase` | `ChatRequest` |
| Constants | `UPPER_SNAKE_CASE` | `ORDER_ID_PATTERN` |
| Boolean variables | `is_`, `has_`, `can_`, or `should_` prefix | `is_configured` |
| Route handlers | HTTP verb plus business result | `get_service_health` |
| Side-effecting services/tools | Verb plus domain object | `create_support_ticket` |
| Query services/tools | Retrieval verb plus domain object | `search_product_catalog` |

Avoid generic names such as `data`, `result`, `handler`, `process`, `helper`, `run`, or `manage` unless their narrow scope makes the purpose obvious. Short loop variables are acceptable only in a small, obvious scope.

## Changes applied

Internal HTTP and routing functions now use explicit names without changing public endpoint paths:

| Previous internal name | Current name |
| --- | --- |
| `tts_proxy` | `generate_speech_audio` |
| `process_etas` | `process_due_order_updates` |
| `root` | `get_service_overview` |
| `health` | `get_service_health` |
| `chat` | `create_chat_response` |
| `chat_stream` | `stream_chat_response` |
| `shipping_webhook` | `handle_shipping_update_webhook` |
| `evaluate` | `run_agent_evaluation` |
| `should_continue` | `route_after_agent_response` |
| `route_escalation` | `route_after_escalation_review` |

The URLs and LangGraph node IDs deliberately remain unchanged. They are external contracts.

## Tool naming

LangChain tool names are more than Python function names: prompts, guardrails, saved tool messages, cached values, and tests refer to them directly. Treat them as versioned API names.

Use these preferred forms for new tools:

| Purpose | Preferred tool name |
| --- | --- |
| Fetch an order's delivery information | `get_order_status` |
| Fetch refund information | `get_refund_status` |
| Start a return | `request_order_return` |
| Cancel an order | `cancel_customer_order` |
| Find a customer's orders | `get_customer_orders` |
| Search in-house products | `search_product_catalog` |
| Place a purchase | `place_customer_order` |

## Safe rename process for an existing tool

1. Search for the old identifier in Python files, prompts, tests, cache keys, documentation, and deployment configuration.
2. Add a new tool with the preferred name and keep the old tool as a thin, deprecated compatibility wrapper.
3. Update prompts and guardrails to call the new tool. Accept both names when reading historical `ToolMessage` records.
4. Update the tool-intent map, cache policy, test fixtures, and integration tests.
5. Deploy the compatibility version and monitor for old-name calls or saved workflow resumes.
6. Remove the old alias only after its declared support window and after relevant checkpoint/cache data has expired.

Do not rename a tool only in `tools/agent_tools.py`; doing so leaves LangGraph routing and LLM instructions out of sync.

## Review checklist

- Is the name specific enough to understand without reading its body?
- Does the verb match the effect (`get`, `search`, `create`, `update`, `delete`, `request`)?
- Does it identify the business object it affects?
- Is it consistent with the existing domain vocabulary: customer, order, refund, product, ticket, and shipment?
- If it is public or model-facing, has the compatibility migration process been followed?
