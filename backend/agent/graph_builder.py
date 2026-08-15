from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from agent.edges import route_after_agent_response, route_after_escalation_review
from agent.nodes import agent_node, escalate, escalation_check, tool_node
from agent.state import AgentState
from infra.logger import get_logger

logger = get_logger("graph_builder")

_compiled_graph = None


def get_graph():
    return _compiled_graph


def set_graph(g):
    global _compiled_graph
    _compiled_graph = g


def build_graph():
    checkpointer = MemorySaver()

    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("escalation_check", escalation_check)
    graph.add_node("escalate", escalate)

    # Entry: go straight to the agent LLM
    graph.set_entry_point("agent")

    # After agent: call tools or move to escalation check
    graph.add_conditional_edges(
        "agent", route_after_agent_response, {"tools": "tools", "escalation_check": "escalation_check"}
    )

    # After tools: loop back to agent (ReAct loop)
    graph.add_edge("tools", "agent")

    # After escalation check: escalate or end
    graph.add_conditional_edges(
        "escalation_check", route_after_escalation_review, {"escalate": "escalate", "end": END}
    )
    graph.add_edge("escalate", END)

    compiled = graph.compile(checkpointer=checkpointer)
    set_graph(compiled)
    return compiled
