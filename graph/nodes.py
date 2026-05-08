from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic  
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from graph.state import AgentState
from tools.real_tools import (
    get_order_status, initiate_return, get_refund_status,
    cancel_order, search_knowledge_base, create_support_ticket
)
import uuid
import json
from logger import get_logger

logger = get_logger("ecommerce-agent")

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, streaming=True)
classifier_llm = ChatAnthropic(model="claude-haiku-4-5", temperature=0)

INTENT_SYSTEM_PROMPT = """You are an intent classifier for an e-commerce support agent.
Extract the intent and order_id from the customer message.
Return ONLY valid JSON. No extra text, no markdown, no explanation.
Format: {"intent": "<intent>", "order_id": "<order_id or null>"}
Valid intents: order_status, return_request, refund_status, cancel_order, unclear"""

RESPONSE_SYSTEM_PROMPT = """You are an e-commerce customer support agent.
You ONLY handle: order status, returns, refunds, cancellations.
If question is unrelated to these topics, say: 'I can only help with order status, returns, refunds, and cancellations.'
Use tool result if provided. 2-3 sentences max."""

def classify_intent(state: AgentState) -> AgentState:
    state["tool_result"] = None  # reset FIRST, before LLM call
    last_message = state["messages"][-1].content
    response = classifier_llm.invoke([
        SystemMessage(content=INTENT_SYSTEM_PROMPT),
        HumanMessage(content=last_message)
    ])
    state["tool_result"] = None
    try:
        raw = response.content.strip()
        # Strip markdown fences Haiku adds despite instructions
        # logger.info("Classifier raw output", extra={"event": "classifier_debug", "raw": raw})
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        data = json.loads(raw)
        state["intent"] = data.get("intent", "unclear")
        state["order_id"] = data.get("order_id") or state.get("order_id")
    except json.JSONDecodeError:
        state["intent"] = "unclear"
    return state

def handle_tool(state: AgentState) -> AgentState:
    intent = state["intent"]
    order_id = state.get("order_id") or "UNKNOWN"
    # print(f">>> HANDLE_TOOL: intent={intent} order_id={order_id}", flush=True)

    if intent == "order_status":
        result = get_order_status(order_id)
    elif intent == "return_request":
        result = initiate_return(order_id, "customer request")
    elif intent == "refund_status":
        result = get_refund_status(order_id)
        state["refund_amount"] = result.get("amount", 0)
    elif intent == "cancel_order":
        result = cancel_order(order_id)
    else:
        result = {"answer": "I could not understand your request."}
        state["retry_count"] = state.get("retry_count", 0) + 1

    # print(f">>> TOOL_RESULT: {result}", flush=True)
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
    last_user_message = state["messages"][-1].content
    current_intent = state.get("intent", "unclear")
    tool_result = state.get("tool_result", None)

    if current_intent == "unclear" or tool_result is None:
        context = "No tool result available. Respond helpfully based on the message alone."
    else:
        context = f"Tool result: {tool_result}"

    response = llm.invoke([
        SystemMessage(content=RESPONSE_SYSTEM_PROMPT),
        HumanMessage(content=f"Customer message: {last_user_message}\n{context}")
    ])
    state["messages"].append(AIMessage(content=response.content))
    return state