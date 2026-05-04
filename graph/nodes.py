from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from graph.state import AgentState
from tools.real_tools import (
    get_order_status, initiate_return, get_refund_status,
    cancel_order, search_knowledge_base, create_support_ticket
)
import uuid
import json

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

INTENT_SYSTEM_PROMPT = """You are an intent classifier for an e-commerce support agent.
Extract the intent and order_id from the customer message.
Return ONLY valid JSON. No extra text, no markdown, no explanation.
Format: {"intent": "<intent>", "order_id": "<order_id or null>"}
Valid intents: order_status, return_request, refund_status, cancel_order, product_query, unclear"""

RESPONSE_SYSTEM_PROMPT = """You are a helpful, professional e-commerce customer support agent.
Use the conversation history and tool result to give a clear, concise response.
Be empathetic but efficient. 2-3 sentences max."""

def classify_intent(state: AgentState) -> AgentState:
    last_message = state["messages"][-1].content
    response = llm.invoke([
        SystemMessage(content=INTENT_SYSTEM_PROMPT),
        HumanMessage(content=last_message)
    ])
    try:
        raw = response.content.strip()
        data = json.loads(raw)
        state["intent"] = data.get("intent", "unclear")
        state["order_id"] = data.get("order_id") or state.get("order_id")
    except json.JSONDecodeError:
        state["intent"] = "unclear"
    return state

def handle_tool(state: AgentState) -> AgentState:
    intent = state["intent"]
    order_id = state.get("order_id") or "UNKNOWN"

    if intent == "order_status":
        result = get_order_status(order_id)
    elif intent == "return_request":
        result = initiate_return(order_id, "customer request")
    elif intent == "refund_status":
        result = get_refund_status(order_id)
        state["refund_amount"] = result.get("amount", 0)
    elif intent == "cancel_order":
        result = cancel_order(order_id)
    elif intent == "product_query":
        last_message = state["messages"][-1].content
        result = search_knowledge_base(last_message)
    else:
        result = {"answer": "I could not understand your request."}
        state["retry_count"] = state.get("retry_count", 0) + 1

    state["tool_result"] = str(result)
    return state

def escalation_check(state: AgentState) -> AgentState:
    last_message = state["messages"][-1].content.lower()
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
    messages = state.get("messages", [])
    already_escalated = any("TKT-" in m.content for m in messages if isinstance(m, AIMessage))

    if already_escalated:
        reply = "Your case is already escalated. A human agent will contact you soon."
    else:
        ticket_id = f"TKT-{uuid.uuid4().hex[:6].upper()}"
        result = create_support_ticket(str(state.get("tool_result", "")))
        reply = f"I've escalated your case to a human agent. {result['message']} Ticket ID: {ticket_id}"

    state["messages"].append(AIMessage(content=reply))
    return state

def respond(state: AgentState) -> AgentState:
    conversation = state.get("messages", [])
    tool_result = state.get("tool_result", "No tool result available.")

    response = llm.invoke([
        SystemMessage(content=RESPONSE_SYSTEM_PROMPT),
        *conversation,
        HumanMessage(content=f"Tool result: {tool_result}")
    ])
    state["messages"].append(AIMessage(content=response.content))
    return state