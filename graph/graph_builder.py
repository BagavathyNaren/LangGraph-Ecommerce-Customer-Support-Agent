from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from graph.state import AgentState
from graph.nodes import classify_intent, handle_tool, escalation_check, escalate, respond
from graph.edges import route_intent, route_escalation
from psycopg_pool import ConnectionPool
import os

def make_pool():
    db_url = os.environ["DATABASE_URL"]

    pool = ConnectionPool(
    db_url,
    min_size=1,
    max_size=5,
    open=True,
    max_idle=180,
    reconnect_timeout=30,
    kwargs={"autocommit": True, "connect_timeout": 10}
    )

pool = make_pool()

def build_graph():
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()

    graph = StateGraph(AgentState)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("handle_tool", handle_tool)
    graph.add_node("escalation_check", escalation_check)
    graph.add_node("escalate", escalate)
    graph.add_node("respond", respond)
    graph.set_entry_point("classify_intent")
    graph.add_conditional_edges("classify_intent", route_intent, {"handle_tool": "handle_tool", "respond": "escalation_check"})
    graph.add_edge("handle_tool", "escalation_check")
    graph.add_conditional_edges("escalation_check", route_escalation, {"escalate": "escalate", "respond": "respond"})
    graph.add_edge("escalate", END)
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=checkpointer)