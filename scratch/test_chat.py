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

from langchain_core.messages import HumanMessage

from graph.graph_builder import build_graph

# Setup thread ID for state checking
thread_id = "test_naren_thread_1"
config = {"configurable": {"thread_id": thread_id}}


def run_chat(graph, message_text):
    print(f"\nUser: {message_text}")
    result = graph.invoke({"messages": [HumanMessage(content=message_text)]}, config=config)
    # Print the last message from agent
    for msg in reversed(result["messages"]):
        if msg.__class__.__name__ == "AIMessage" and msg.content and not msg.tool_calls:
            print(f"Agent: {msg.content}")
            break
    return result


def main():
    print("Building graph...")
    graph = build_graph()

    # 1. Start session by stating name and wanting to buy iPhone 16 Pro
    run_chat(graph, "My name is info naren. I want to buy an iPhone 16 Pro")


if __name__ == "__main__":
    main()
