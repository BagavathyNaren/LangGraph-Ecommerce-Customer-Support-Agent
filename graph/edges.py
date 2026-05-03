from graph.state import AgentState

def route_intent(state: AgentState) -> str:
    intent = state["intent"]
    valid_intents = [
        "order_status", "return_request", "refund_status",
        "cancel_order", "product_query"
    ]
    if intent in valid_intents:
        return "handle_tool"
    return "respond"

def route_escalation(state: AgentState) -> str:
    if state["escalated"]:
        return "escalate"
    return "respond"