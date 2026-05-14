from graph.state import AgentState
from langchain_core.messages import AIMessage

def should_continue(state: AgentState) -> str:
    """Route after the agent node: call tools or move to escalation check."""
    last_message = state["messages"][-1]

    # If the agent wants to call tools, route to tool_node
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"

    # Otherwise the agent is done — check for escalation
    return "escalation_check"

def route_escalation(state: AgentState) -> str:
    """Route after escalation check: escalate or end."""
    if state.get("escalated", False):
        return "escalate"
    return "end"