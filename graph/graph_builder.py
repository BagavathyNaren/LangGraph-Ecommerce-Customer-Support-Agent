from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from graph.state import AgentState
from graph.nodes import agent_node, tool_node, escalation_check, escalate
from graph.edges import should_continue, route_escalation
from tools.db import get_pool
from logger import get_logger
import os

logger = get_logger("graph_builder")

def build_graph():
    pool = get_pool()

    checkpointer = PostgresSaver(pool)
    try:
        checkpointer.setup()
    except Exception as e:
        logger.warning(
            f"Checkpointer setup warning: {e}. "
            "Application startup will continue. If tables are already initialized, queries will succeed."
        )

    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("escalation_check", escalation_check)
    graph.add_node("escalate", escalate)

    # Entry: go straight to the agent LLM
    graph.set_entry_point("agent")

    # After agent: call tools or move to escalation check
    graph.add_conditional_edges("agent", should_continue, {
        "tools": "tools",
        "escalation_check": "escalation_check"
    })

    # After tools: loop back to agent (ReAct loop)
    graph.add_edge("tools", "agent")

    # After escalation check: escalate or end
    graph.add_conditional_edges("escalation_check", route_escalation, {
        "escalate": "escalate",
        "end": END
    })
    graph.add_edge("escalate", END)

    return graph.compile(checkpointer=checkpointer)