import os
import sys

from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))
load_dotenv()

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from graph.nodes import agent_node

# Construct the state exactly as it would be after Turn 1 lookup
messages = [
    HumanMessage(content="My name is AlexTest12345. I want to buy a Sony PlayStation"),
    AIMessage(
        content="",
        tool_calls=[
            {
                "name": "lookup_customer_orders",
                "args": {"customer_name": "AlexTest"},
                "id": "call_123",
                "type": "tool_call",
            }
        ],
    ),
    ToolMessage(content="Customer 'AlexTest' not found.", tool_call_id="call_123"),
]

state = {
    "messages": messages,
    "intent": None,
    "order_id": None,
    "anger_count": 0,
    "retry_count": 0,
    "refund_amount": 0.0,
    "escalated": False,
    "react_iterations": 1,
}

print("Running dry agent_node...")
res = agent_node(state)
response_msg = res["messages"][0]
print("\nAgent response text:", response_msg.content)
print("Agent response tool calls:", response_msg.tool_calls)
