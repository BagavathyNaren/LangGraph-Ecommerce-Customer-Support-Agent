from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage, RemoveMessage
from graph.state import AgentState
from tools.agent_tools import AGENT_TOOLS
from tools.real_tools import create_support_ticket
import uuid
from logger import get_logger

logger = get_logger("ecommerce-agent")

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, streaming=True, request_timeout=30)
agent_llm = llm.bind_tools(AGENT_TOOLS)

AGENT_SYSTEM_PROMPT = """You are an e-commerce customer support agent.
You handle: order status, returns, refunds, cancellations, customer order lookups, new customer registration, and placing new orders.

RULES:
- If the question is unrelated to these topics, politely decline.
- If a customer provides their name, use lookup_customer_orders to find their orders.
- If they provide an order ID (like ORD001), use the appropriate tool.
- When showing customer orders, format them clearly with order ID, item, status, and delivery date.
- Keep responses concise and helpful.
- When a customer asks about their refund status, ALWAYS explicitly include the last updated date (e.g. "last updated on ...") and the refund reason (e.g., "reason: ...") from the tool's response in your reply.
- NEVER make up order data or customer info — always use tools to look up real information.
- STRICTLY FORBIDDEN: Do not promise or offer discounts, coupons, or free items under any circumstances.
- STRICTLY FORBIDDEN: Do not make up fake company policies, warranties, or shipping guarantees.
- STRICTLY FORBIDDEN: Do not hallucinate or suggest products that are not found in the tools or knowledge base.
- USE 'create_support_ticket' for ANY complaint, stolen item, or complex request you cannot solve yourself. ALWAYS pass the customer_name as stated by the user in the conversation.
- NEVER use 'create_new_order' for a support issue or complaint.
- If a user asks about something completely outside of e-commerce, state clearly that you cannot assist.
- TICKET ID RULE: Whenever a Ticket ID in the format TKT-XXXXX is present — either from a tool response OR mentioned earlier in this conversation — you MUST always include that exact Ticket ID verbatim in your reply. Never paraphrase, summarise, or omit it. Example: "Your Ticket ID is TKT-F03FFF."

VOICE INPUT ORDER ID RULE (CRITICAL):
- Users often speak their order ID via voice and speech recognition may mishear "ORD" as "ODD", "odd", "or d", "OR D", etc.
- If you receive an order ID that looks like "ODD001", "odd 002", "ODD 002" — treat it as ORD001, ORD002 etc. and pass it directly to the tool.
- The normalize_order_id function in the tool already handles this correction — just pass whatever the user gave you.
- NEVER tell the user their order ID format is wrong if it contains recognizable digits. Instead, try the tool first.
- Only ask for clarification if there are NO digits at all in the order ID.

NEW CUSTOMER / ORDER FLOW — FOLLOW THIS EXACTLY:
1. If a new customer provides their name, email, AND product all in ONE message:
   - Call register_customer AND create_new_order immediately in the same turn.
   - Reply with a confirmation including the order ID, item, and their email address.
   - Example: "You've been registered! Your order ORD1234 for LG TV has been placed and will be delivered within 5 business days. We'll send updates to user@email.com."

2. If a new customer wants to buy something but did NOT provide an email in their message:
   - DO NOT call any tool yet.
   - Reply asking for their email address. Example:
   "To place your order, I'll need your email address. Could you please share it so we can create your account and confirm your order?"

3. Once the customer provides a valid email in a follow-up message:
   - Call register_customer (with their name and the email) and create_new_order (with their name and item).
   - Reply with the full confirmation including their real email address.

4. NEVER register or place an order without a valid email address from the customer.
   If you cannot find an email in their message, ask again politely."""

# Map tool names to intent labels for badge display
TOOL_INTENT_MAP = {
    "check_order_status": "order_status",
    "check_refund_status": "refund_status",
    "process_return": "return_request",
    "process_cancellation": "cancel_order",
    "lookup_customer_orders": "customer_lookup",
    "register_customer": "new_customer",
    "create_new_order": "new_order",
}


def agent_node(state: AgentState) -> AgentState:
    """The agent LLM decides what to do — call tools or respond directly with pruning."""
    # Reset intent and order_id at the start of a new user turn
    new_intent = None
    new_order_id = None
    
    # If we are NOT in a new turn (e.g. still in a tool loop), keep existing values
    if not isinstance(state["messages"][-1], HumanMessage):
        new_intent = state.get("intent")
        new_order_id = state.get("order_id")

    # PERSISTENCE OPTIMIZATION: Keep only the last 15 messages in the DB state
    # We use a "Safe Cut" approach to ensure we don't break tool-call chains.
    messages_to_remove = []
    if len(state["messages"]) > 15:
        # Determine the cutoff point
        cutoff = len(state["messages"]) - 15
        
        # Find the nearest HumanMessage at or after the cutoff to ensure a clean start
        safe_cutoff = 0
        for i in range(cutoff, len(state["messages"])):
            if isinstance(state["messages"][i], HumanMessage):
                safe_cutoff = i
                break
        
        if safe_cutoff > 0:
            for i in range(safe_cutoff):
                m = state["messages"][i]
                messages_to_remove.append(RemoveMessage(id=m.id))

    messages = [SystemMessage(content=AGENT_SYSTEM_PROMPT)] + state["messages"]
    response = agent_llm.invoke(messages)
    
    # Return the AI response, removal instructions, and reset state
    return {
        "messages": [response] + messages_to_remove,
        "intent": new_intent,
        "order_id": new_order_id
    }


def tool_node(state: AgentState) -> AgentState:
    """Execute tool calls from the agent's last response, with Redis caching."""
    from cache.redis_cache import get_cached_tool_result, set_cached_tool_result
    import time

    last_message = state["messages"][-1]
    tool_map = {t.name: t for t in AGENT_TOOLS}

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        start = time.time()

        # Check tool cache first
        cached = get_cached_tool_result(tool_name, tool_args)
        if cached:
            result = cached
            duration_ms = round((time.time() - start) * 1000)
            logger.info("Tool executed (cached)", extra={
                "event": "tool_cached", "tool": tool_name,
                "tool_args": tool_args, "duration_ms": duration_ms
            })
        else:
            tool_fn = tool_map.get(tool_name)
            if tool_fn:
                result = tool_fn.invoke(tool_args)
                # Cache the result (skip if it contains an error)
                if "error" not in str(result).lower() or "not_found" in str(result).lower():
                    set_cached_tool_result(tool_name, tool_args, str(result))
            else:
                result = f"Tool {tool_name} not found."
            duration_ms = round((time.time() - start) * 1000)
            logger.info("Tool executed (live)", extra={
                "event": "tool_live", "tool": tool_name,
                "tool_args": tool_args, "duration_ms": duration_ms
            })

        state["messages"].append(
            ToolMessage(content=str(result), tool_call_id=tool_call["id"])
        )

        # Extract metadata for frontend badges
        if "order_id" in tool_args:
            state["order_id"] = tool_args["order_id"]
        if tool_name in TOOL_INTENT_MAP:
            state["intent"] = TOOL_INTENT_MAP[tool_name]

    return state


def escalation_check(state: AgentState) -> AgentState:
    """Check if the conversation should be escalated to a human."""
    human_messages = [m for m in state["messages"] if isinstance(m, HumanMessage)]
    if not human_messages:
        return state

    last_message = human_messages[-1].content.lower()
    anger_words = ["angry", "furious", "terrible", "worst", "useless", "refund now", "escalate"]

    anger_count = state.get("anger_count", 0)
    retry_count = state.get("retry_count", 0)
    refund_amount = state.get("refund_amount", 0.0)
    already_escalated = state.get("escalated", False)

    if not already_escalated:
        if any(word in last_message for word in anger_words):
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
    already_escalated = any("TKT-" in m.content for m in messages if isinstance(m, AIMessage))

    if already_escalated:
        reply = "Your case is already escalated. A human agent will contact you soon."
    else:
        ticket_id = f"TKT-{uuid.uuid4().hex[:6].upper()}"
        order_id = state.get("order_id")
        
        # Scan conversation history in REVERSE order for most recent order ID and customer name if not in state
        customer_name = None
        for m in reversed(messages):
            # Check AIMessage for tool calls containing order_id or customer_name
            if isinstance(m, AIMessage) and m.tool_calls:
                for tc in m.tool_calls:
                    tc_args = tc.get("args", {})
                    if not order_id and "order_id" in tc_args:
                        order_id = str(tc_args["order_id"]).upper()
                    if not customer_name and "customer_name" in tc_args:
                        customer_name = tc_args["customer_name"]
            
            if isinstance(m, HumanMessage):
                # Extract order IDs like ORD001, ORD 001, ORD1234
                if not order_id:
                    order_match = _re.search(r'\b(ORD\s*\d{3,10})\b', m.content, _re.IGNORECASE)
                    if order_match:
                        order_id = _re.sub(r'\s+', '', order_match.group(1)).upper()
                # Extract customer name from "I am X" or "my name is X" patterns
                if not customer_name:
                    name_match = _re.search(r'(?:I am|my name is|I\'m|this is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', m.content, _re.IGNORECASE)
                    if name_match:
                        customer_name = name_match.group(1).strip()
            elif isinstance(m, ToolMessage):
                # Extract customer info from tool responses
                if not order_id:
                    order_match = _re.search(r'\b(ORD\s*\d{3,10})\b', m.content, _re.IGNORECASE)
                    if order_match:
                        order_id = _re.sub(r'\s+', '', order_match.group(1)).upper()
        
        # Summarize the conversation to provide context for the human agent
        history_lines = [f"{'User' if isinstance(m, HumanMessage) else 'Agent'}: {m.content}" 
                         for m in messages[-4:] if isinstance(m, (HumanMessage, AIMessage))]
        history = "\n".join(history_lines)
        
        result = create_support_ticket(ticket_id, order_id, "Automated Escalation", history, customer_name)
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
            reply = f"I've flagged your case for immediate review. {result.get('message', 'A human agent will be in touch shortly.')} Reference: {ticket_id}"

    state["messages"].append(AIMessage(content=reply))
    return state