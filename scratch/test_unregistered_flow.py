import os
import sys

from dotenv import load_dotenv

# Reconfigure stdout to support UTF-8 printing
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# Ensure local path is in import path
sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))

load_dotenv()

import random

from langchain_core.messages import AIMessage, HumanMessage

from graph.graph_builder import build_graph
from tools.db import get_pool


def main():
    print("Building graph...")
    graph = build_graph()

    random_num = random.randint(10000, 99999)
    name = f"AlexTest{random_num}"
    email = f"alex_test_{random_num}@example.com"
    thread_id = f"test-unreg-flow-{random_num}"
    config = {"configurable": {"thread_id": thread_id}}

    print("\n" + "=" * 60)
    print(f"STARTING MULTI-TURN UNREGISTERED CUSTOMER FLOW FOR {name}")
    print("=" * 60)

    try:
        # -------------------------------------------------------------
        # TURN 1: Name and purchase intent (no country, no email)
        # -------------------------------------------------------------
        msg1 = f"My name is {name}. I want to buy a Sony PlayStation"
        print(f"\n[Turn 1] User: {msg1}")
        res1 = graph.invoke({"messages": [HumanMessage(content=msg1)]}, config=config)

        last_msg1 = res1["messages"][-1]
        print(f"[Turn 1] Agent: {last_msg1.content}")

        # Verify: Must have called lookup_customer_orders
        has_lookup = False
        for m in res1["messages"]:
            if isinstance(m, AIMessage) and m.tool_calls:
                for tc in m.tool_calls:
                    if tc["name"] == "lookup_customer_orders":
                        has_lookup = True
                        break
        assert has_lookup, "FAIL: Agent should have called lookup_customer_orders in Turn 1"
        print("✅ SUCCESS: Agent checked registration status via lookup.")

        # Verify: Must ask for country, NOT email
        assert "country" in last_msg1.content.lower(), "FAIL: Agent should ask for the country first."
        assert "email" not in last_msg1.content.lower(), "FAIL: Agent should NOT ask for the email yet."
        print("✅ SUCCESS: Agent asked for the country first and did not mention/request email.")

        # -------------------------------------------------------------
        # TURN 2: Provide country
        # -------------------------------------------------------------
        msg2 = "I am in Japan"
        print(f"\n[Turn 2] User: {msg2}")
        res2 = graph.invoke({"messages": [HumanMessage(content=msg2)]}, config=config)

        last_msg2 = res2["messages"][-1]
        print(f"[Turn 2] Agent: {last_msg2.content[:300]}...")

        # Verify: Must search the Japan platforms
        has_search = False
        for m in res2["messages"]:
            # Find only the messages produced in Turn 2
            if isinstance(m, AIMessage) and m.tool_calls:
                for tc in m.tool_calls:
                    if (
                        tc["name"] in ["search_catalog", "search_retailer_platform"]
                        and tc["args"].get("country", "").lower() == "japan"
                    ):
                        has_search = True
                        break
        assert has_search, "FAIL: Agent should search the Japan catalogs in Turn 2"
        print("✅ SUCCESS: Agent searched local catalogs for Japan.")

        # Verify: Must list products with JPY currency and NOT ask for email yet
        assert "￥" in last_msg2.content or "JPY" in last_msg2.content, (
            "FAIL: Agent should display products with Japanese Yen currency."
        )
        assert "email" not in last_msg2.content.lower(), "FAIL: Agent should NOT ask for the email in Turn 2."
        print("✅ SUCCESS: Products listed in JPY currency and email is still not requested.")

        # -------------------------------------------------------------
        # TURN 3: Checkout button click simulation
        # -------------------------------------------------------------
        # Simulate selection string sent by checkout button:
        msg3 = 'I choose the Amazon option: "PlayStation 5 Console" at price "￥60,480"'
        print(f"\n[Turn 3] User (Checkout): {msg3}")
        res3 = graph.invoke({"messages": [HumanMessage(content=msg3)]}, config=config)

        last_msg3 = res3["messages"][-1]
        print(f"[Turn 3] Agent: {last_msg3.content}")

        # Verify: Must now ask for email
        assert "email" in last_msg3.content.lower(), "FAIL: Agent should ask for the email address at checkout."
        assert not last_msg3.tool_calls, "FAIL: Agent should not place an order without email registration."
        print("✅ SUCCESS: Agent successfully halted checkout to ask for unregistered email address.")

        # -------------------------------------------------------------
        # TURN 4: Provide email address to complete registration and order
        # -------------------------------------------------------------
        msg4 = f"My email is {email}"
        print(f"\n[Turn 4] User: {msg4}")
        res4 = graph.invoke({"messages": [HumanMessage(content=msg4)]}, config=config)

        last_msg4 = res4["messages"][-1]
        print(f"[Turn 4] Agent: {last_msg4.content}")

        # Verify: Must register the customer and place the order
        has_register_tool = False
        has_order_tool = False
        for m in res4["messages"]:
            if isinstance(m, AIMessage) and m.tool_calls:
                for tc in m.tool_calls:
                    if tc["name"] == "register_customer":
                        has_register_tool = True
                    if tc["name"] == "create_new_order":
                        has_order_tool = True

        assert has_register_tool, "FAIL: Agent should register the new customer."
        assert has_order_tool, "FAIL: Agent should place the order."
        print("✅ SUCCESS: Agent called register_customer and create_new_order tools.")

        # Verify: Order confirmation block is displayed in the final message
        assert "ORD" in last_msg4.content, "FAIL: Response must contain Order ID."
        assert "tracking" in last_msg4.content.lower(), "FAIL: Response must contain Tracking ID."
        print("✅ SUCCESS: Order placed and confirmation details displayed to the user!")
        print("\n🎉 ALL TESTS IN MULTI-TURN FLOW PASSED 100% CORRECTLY! 🎉")

    finally:
        pool = get_pool()
        pool.close()
        print("\nConnection pool closed.")


if __name__ == "__main__":
    main()
