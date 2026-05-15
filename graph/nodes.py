from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
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
- If a new customer wants to register or place an order without an account, use register_customer to create their profile (ask for their full name and email first).
- If a customer wants to place an order, use create_new_order.
- If a customer provides their name, use lookup_customer_orders to find their orders.
- If they provide an order ID (like ORD001), use the appropriate tool.
- Emails are allowed for registration, but for order lookups, suggest they search by name if the lookup fails.
- You can call MULTIPLE tools in one turn if needed (e.g., register a user AND place an order).
- When showing customer orders, format them clearly with order ID, item, status, and delivery date.
- Keep responses concise and helpful.
- NEVER make up order data or customer info — always use tools to look up real information.
- STRICTLY FORBIDDEN: Do not promise or offer discounts, coupons, or free items under any circumstances.
- STRICTLY FORBIDDEN: Do not make up fake company policies, warranties, or shipping guarantees.
- STRICTLY FORBIDDEN: Do not hallucinate or suggest products that are not found in the tools or knowledge base.
- USE 'create_support_ticket' for ANY complaint, stolen item, or complex request you cannot solve yourself.
- NEVER use 'create_new_order' for a support issue or complaint.
- If a user asks about something completely outside of e-commerce, state clearly that you cannot assist. """

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
    """The agent LLM decides what to do — call tools or respond directly."""
    # Reset metadata at the start of a new user turn (not during ReAct tool loop)
    if isinstance(state["messages"][-1], HumanMessage):
        state["intent"] = None
        state["order_id"] = None

    messages = [SystemMessage(content=AGENT_SYSTEM_PROMPT)] + state["messages"]
    response = agent_llm.invoke(messages)
    state["messages"].append(response)
    return state


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
    messages = state.get("messages", [])
    already_escalated = any("TKT-" in m.content for m in messages if isinstance(m, AIMessage))

    if already_escalated:
        reply = "Your case is already escalated. A human agent will contact you soon."
    else:
        ticket_id = f"TKT-{uuid.uuid4().hex[:6].upper()}"
        order_id = state.get("order_id")
        
        # Summarize the conversation to provide context for the human agent
        history_lines = [f"{'User' if isinstance(m, HumanMessage) else 'Agent'}: {m.content}" 
                         for m in messages[-4:] if isinstance(m, (HumanMessage, AIMessage))]
        history = "\n".join(history_lines)
        
        result = create_support_ticket(ticket_id, order_id, "Automated Escalation", history)
        reply = f"I've escalated your case to a human agent. {result['message']} Ticket ID: {ticket_id}"

    state["messages"].append(AIMessage(content=reply))
    return state