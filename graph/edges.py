from graph.state import AgentState

def route_intent(state: AgentState) -> str:
    intent = state.get("intent", "unclear")
    valid_intents = [
        "order_status", "return_request", "refund_status",
        "cancel_order"
    ]
    if intent in valid_intents:
        return "handle_tool"
    return "respond"

def route_escalation(state: AgentState) -> str:
    if state.get("escalated", False):
        return "escalate"
    return "respond"