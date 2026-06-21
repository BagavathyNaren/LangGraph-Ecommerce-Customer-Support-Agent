from dotenv import load_dotenv

load_dotenv()

import os
import sys

sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from graph.graph_builder import build_graph

# Compile the graph
graph = build_graph()

# Get state from checkpointer
config = {"configurable": {"thread_id": "thread-xk74p50fe"}}
state = graph.get_state(config)
print("State values keys:", state.values.keys())
print("\n--- MESSAGES IN STATE ---")
for i, m in enumerate(state.values.get("messages", [])):
    print(f"Message {i} | Type: {type(m).__name__} | Content: {repr(m.content)}")
    if hasattr(m, "tool_calls") and m.tool_calls:
        print(f"  Tool Calls: {m.tool_calls}")
    if hasattr(m, "tool_call_id") and m.tool_call_id:
        print(f"  Tool Call ID: {m.tool_call_id}")
    print("-" * 50)
