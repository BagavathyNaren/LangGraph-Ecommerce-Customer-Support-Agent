import os
import sys

from dotenv import load_dotenv

# Reconfigure stdout to support UTF-8 printing of Indian Rupee symbol
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# Ensure local path is in import path
sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))

load_dotenv()

# Use a clean, unique thread ID for this test session to avoid interference
import random

from langchain_core.messages import HumanMessage

from graph.graph_builder import build_graph
from tools.db import get_pool

random_num = random.randint(1000, 9999)
new_name = f"naren fresh guest {random_num}"
new_email = f"naren_guest_{random_num}@info.com"

thread_id = f"test_naren_new_flow_{random_num}"
config = {"configurable": {"thread_id": thread_id}}


def run_chat(graph, message_text):
    print(f"\n---> User: {message_text}")
    result = graph.invoke({"messages": [HumanMessage(content=message_text)]}, config=config)
    # Print the last message from agent
    for msg in reversed(result["messages"]):
        if msg.__class__.__name__ == "AIMessage" and msg.content and not msg.tool_calls:
            print(f"Agent: {msg.content}")
            break
    # Print intent and registration status if helpful
    print(f"State Intent: {result.get('intent')}, Order ID: {result.get('order_id')}")
    return result


def main():
    print("Building graph...")
    graph = build_graph()

    try:
        # Step 1: Start session
        print(f"\n--- TESTING NEW UNREGISTERED CUSTOMER FLOW WITH Name: {new_name} ---")
        run_chat(graph, f"My name is {new_name}. I want to buy an iPhone 16 Pro")

        # Step 2: Choose the product
        run_chat(graph, "I choose option 1")

        # Step 3: Provide email address
        run_chat(graph, f"My email is {new_email}")

        # Step 4: Re-run lookup to verify bypass for existing customers
        # First, let's start a new thread for existing customer flow
        print("\n=== TESTING REGISTERED CUSTOMER BYPASS ===")
        registered_thread_id = f"test_naren_registered_flow_{random_num}"
        registered_config = {"configurable": {"thread_id": registered_thread_id}}

        print(f"\n---> User: My name is {new_name}. I want to buy an iPhone 16 Pro")
        result = graph.invoke(
            {"messages": [HumanMessage(content=f"My name is {new_name}. I want to buy an iPhone 16 Pro")]},
            config=registered_config,
        )
        for msg in reversed(result["messages"]):
            if msg.__class__.__name__ == "AIMessage" and msg.content and not msg.tool_calls:
                print(f"Agent: {msg.content}")
                break

        print("\n---> User: I choose option 1")
        result = graph.invoke({"messages": [HumanMessage(content="I choose option 1")]}, config=registered_config)
        for msg in reversed(result["messages"]):
            if msg.__class__.__name__ == "AIMessage" and msg.content and not msg.tool_calls:
                print(f"Agent: {msg.content}")
                break

    finally:
        # Close connection pool explicitly to prevent Python from hanging
        pool = get_pool()
        pool.close()
        print("\nConnection pool closed. Test finished.")


if __name__ == "__main__":
    main()
