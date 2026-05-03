from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from graph.state import AgentState
from tools.mock_tools import (
    get_order_status, initiate_return, get_refund_status,
    cancel_order, search_knowledge_base, create_support_ticket
)

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

def classify_intent(state: AgentState) -> AgentState:
    last_message = state["messages"][-1].content
    prompt = f"""Extract intent and order_id from this customer message.
Return ONLY a JSON like: {{"intent": "order_status", "order_id": "ORD001"}}

Intents: order_status, return_request, refund_status, cancel_order, product_query, unclear

Message: {last_message}"""

    response = llm.invoke([HumanMessage(content=prompt)])
    import json
    try:
        data = json.loads(response.content)
        state["intent"] = data.get("intent", "unclear")
        state["order_id"] = data.get("order_id")
    except:
        state["intent"] = "unclear"
    return state

def handle_tool(state: AgentState) -> AgentState:
    intent = state["intent"]
    order_id = state["order_id"] or "UNKNOWN"

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
        state["retry_count"] += 1

    state["tool_result"] = str(result)
    return state

def escalation_check(state: AgentState) -> AgentState:
    last_message = state["messages"][-1].content.lower()
    anger_words = ["angry", "furious", "terrible", "worst", "useless", "refund now", "escalate"]

    if any(word in last_message for word in anger_words):
        state["anger_count"] += 1

    if (
        state["anger_count"] >= 2 or
        state["retry_count"] >= 3 or
        state["refund_amount"] > 5000
    ):
        state["escalated"] = True

    return state

def escalate(state: AgentState) -> AgentState:
    result = create_support_ticket(str(state["tool_result"]))
    reply = f"I've escalated your case to a human agent. {result['message']} Ticket ID: {result['ticket_id']}"
    state["messages"].append(AIMessage(content=reply))
    return state

def respond(state: AgentState) -> AgentState:
    prompt = f"""You are a helpful e-commerce support agent.
Tool result: {state['tool_result']}
Respond naturally to the customer in 2-3 sentences."""

    response = llm.invoke([HumanMessage(content=prompt)])
    state["messages"].append(AIMessage(content=response.content))
    return state