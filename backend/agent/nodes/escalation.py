import json
import re as _re
import uuid
from datetime import date

from langchain_core.messages import AIMessage

from agent.nodes.guardrails.helpers import (
    _create_ticket_sync,
    _get_order_delivery_date_from_history,
    extract_customer_name,
)
from agent.state import AgentState
from infra.logger import get_logger
from tools.real_tools import create_support_ticket as _real_create_support_ticket

logger = get_logger("ecommerce-agent")


def escalation_check(state: AgentState) -> AgentState:
    """Check if the conversation should be escalated to a human."""
    human_messages = [m for m in state["messages"] if isinstance(m, HumanMessage)]
    if not human_messages:
        return state

    last_message = human_messages[-1].content.lower()

    # Standard anger keywords
    anger_words = [
        "angry", "furious", "terrible", "worst", "useless", "refund now", "escalate",
        "unacceptable", "outrageous", "disgusting", "ridiculous", "horrible", "pathetic",
        "demand", "lawsuit", "never again", "frustrated", "incompetent", "disgraceful",
    ]

    anger_count = state.get("anger_count", 0)
    retry_count = state.get("retry_count", 0)
    refund_amount = state.get("refund_amount", 0.0)
    already_escalated = state.get("escalated", False)

    if not already_escalated:
        # Find the AI message just before the last HumanMessage
        is_cancelling = False
        human_idx = -1
        for i, m in enumerate(state["messages"]):
            if isinstance(m, HumanMessage) and m == human_messages[-1]:
                human_idx = i
                break

        if human_idx > 0:
            for m in reversed(state["messages"][:human_idx]):
                if isinstance(m, AIMessage) and m.content:
                    last_ai = m.content.lower()
                    if (
                        "reason for cancel" in last_ai
                        or "reason for request" in last_ai
                        or "reason for the cancellation" in last_ai
                    ):
                        is_cancelling = True
                    break

        has_anger = any(word in last_message for word in anger_words)
        if has_anger:
            if "cancel" in last_message or is_cancelling:
                pass  # DO NOT escalate! Let the agent handle cancellation.
            else:
                anger_count += 1

        if anger_count >= 2 or retry_count >= 3 or refund_amount > 5000:
            state["escalated"] = True

    state["anger_count"] = anger_count
    state["retry_count"] = retry_count
    state["refund_amount"] = refund_amount
    return state


def escalate(state: AgentState) -> AgentState:
    """Escalate to a human agent by creating a support ticket."""
    import re as _re

    messages = state.get("messages", [])
    human_messages = [m for m in messages if isinstance(m, HumanMessage)]
    # Check if a REAL ticket was already created (ignore hallucinated "TKT-XXXXX" placeholder)
    already_escalated = any(
        _re.search(r"TKT-[0-9A-F]{6}\b", m.content)
        for m in messages
        if isinstance(m, AIMessage)
    )

    if already_escalated:
        reply = "Your case is already escalated. A human agent will contact you soon."
    else:
        ticket_id = f"TKT-{uuid.uuid4().hex[:6].upper()}"
        order_id = state.get("order_id")

        # Scan conversation history for order ID and customer name.
        # Priority order (most → least reliable):
        #   1. lookup_customer_orders ToolMessage (DB-verified name)
        #   2. AIMessage tool_call args (e.g., create_new_order, register_customer)
        #   3. HumanMessage regex (last resort — prone to false matches like "this is unacceptable")
        customer_name = None
        for m in reversed(messages):
            # 1. Best source: lookup_customer_orders ToolMessage (name=tool_name now set in tool_node)
            #    Also detect by content format as a fallback in case name is not set.
            is_lookup_tool = isinstance(m, ToolMessage) and (
                m.name == "lookup_customer_orders"
                or (m.content and '"customer"' in m.content and '"name"' in m.content)
            )
            if is_lookup_tool:
                try:
                    import json as _json_e
                    parsed = _json_e.loads(m.content)
                    customer_data = parsed.get("customer", {}) if isinstance(parsed, dict) else {}
                    if isinstance(customer_data, dict) and customer_data.get("name"):
                        customer_name = customer_data["name"]
                        # Also extract order_id from customer orders if needed
                        if not order_id and isinstance(parsed.get("orders"), list):
                            for o in parsed["orders"]:
                                if o.get("order_id"):
                                    order_id = str(o["order_id"]).upper()
                                    break
                        break
                except Exception:
                    pass

            # 2. AIMessage tool call args (register_customer, create_new_order contain name)
            if not customer_name and isinstance(m, AIMessage) and m.tool_calls:
                for tc in m.tool_calls:
                    tc_args = tc.get("args", {})
                    if not order_id and "order_id" in tc_args:
                        order_id = str(tc_args["order_id"]).upper()
                    # Only use customer_name from tool args if it looks like a real name
                    if "customer_name" in tc_args and not customer_name:
                        candidate = str(tc_args["customer_name"]).strip()
                        # Real names: 1-5 words, no common complaint words
                        complaint_words = {"unacceptable", "terrible", "horrible", "disgusting", "furious"}
                        candidate_lower_words = set(candidate.lower().split())
                        if candidate and len(candidate.split()) <= 5 and not candidate_lower_words.intersection(complaint_words):
                            customer_name = candidate

            if customer_name and order_id:
                break

        # 3. Last resort: regex on HumanMessages for introduction phrases only
        # (intentionally NOT matching "this is" to avoid "this is unacceptable" → name)
        if not customer_name:
            for m in reversed(messages):
                if isinstance(m, HumanMessage):
                    intro_match = _re.search(
                        r"(?:my\s+(?:full\s+)?name\s+is|I\s+am|I\'m)\s*[,:]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
                        m.content,
                    )
                    if intro_match:
                        customer_name = intro_match.group(1).strip()
                        break
                    if not order_id:
                        order_match = _re.search(r"\b(ORD\s*\d{3,10})\b", m.content, _re.IGNORECASE)
                        if order_match:
                            order_id = _re.sub(r"\s+", "", order_match.group(1)).upper()

        # Summarize the conversation to provide context for the human agent
        history_lines = [
            f"{'User' if isinstance(m, HumanMessage) else 'Agent'}: {m.content}"
            for m in messages[-4:]
            if isinstance(m, (HumanMessage, AIMessage))
        ]
        history = "\n".join(history_lines)

        # ═══ DELIVERY DATE GUARD for escalate() node ═══
        # Before creating a ticket, check if the complaint is about delivery
        # and whether the expected delivery date has actually passed.
        _delivery_keywords = [
            "never arrived", "not arrived", "hasn't arrived", "not delivered",
            "didn't arrive", "didn't receive", "never received", "missing",
            "delayed", "been weeks", "been days", "where is my", "still waiting",
        ]
        last_human = human_messages[-1].content.lower() if human_messages else ""
        _is_delivery_complaint = any(kw in last_human for kw in _delivery_keywords)
        delivery_date = _get_order_delivery_date_from_history(messages, order_id)
        today = date.today()

        if _is_delivery_complaint and delivery_date and delivery_date >= today:
            # Delivery date hasn't passed — don't create a ticket
            logger.info(
                "escalate(): blocked ticket — delivery date not yet passed",
                extra={
                    "event": "escalate_delivery_date_not_passed",
                    "order_id": order_id,
                    "expected_delivery": str(delivery_date),
                    "today": str(today),
                },
            )
            reply = (
                f"I understand your frustration. However, your order {order_id or ''} "
                f"has an expected delivery date of {delivery_date.strftime('%B %d, %Y')}, "
                f"which {'is today' if delivery_date == today else 'has not passed yet'}. "
                f"Your order is still within its delivery window. "
                f"If it hasn't arrived after the expected date, please reach out and "
                f"we will immediately escalate it for you."
            )
        else:
            result = _real_create_support_ticket(ticket_id, order_id, "Automated Escalation", history, customer_name)
            # Use the actual ticket ID from result (handles duplicate case where existing ticket was found)
            actual_ticket_id = result.get("ticket_id", ticket_id)
            if result.get("duplicate"):
                reply = (
                    f"Your case already has an open support ticket. "
                    f"Ticket ID: {actual_ticket_id}. "
                    f"A human agent will review it and contact you within 2 hours."
                )
            elif result.get("success"):
                reply = (
                    f"I've escalated your case to a human agent. "
                    f"Ticket ID: {actual_ticket_id}. "
                    f"A human agent will contact you within 2 hours."
                )
            else:
                reply = f"I've flagged your case for immediate review. {result.get('message', 'A human agent will be in touch shortly.')}"

    state["messages"].append(AIMessage(content=reply))
    state["escalated"] = False
    state["anger_count"] = 0
    return state
