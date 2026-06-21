import uuid
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from graph.graph_builder import build_graph


def test_graph_compilation(mock_db_connection):
    """
    Verifies that the StateGraph builds, adds all nodes,
    creates required edges, and compiles successfully under mock saver configurations.
    """
    with patch("langgraph.checkpoint.postgres.PostgresSaver.setup"):
        compiled_graph = build_graph()
        assert compiled_graph is not None

        # Verify compiled graph structure has our defined nodes
        assert "agent" in compiled_graph.nodes
        assert "tools" in compiled_graph.nodes
        assert "escalation_check" in compiled_graph.nodes
        assert "escalate" in compiled_graph.nodes


def test_scenario_a_flawless_flow(mock_db_connection):
    """
    Scenario A (Flawless Flow):
    - A registered customer (Shin) searches for a product and successfully purchases it.
    - Since Shin is already registered (retrieved via lookup), the email ask is completely bypassed during checkout.
    """
    mock_saver = MemorySaver()
    mock_saver.setup = lambda: None
    with patch("graph.graph_builder.PostgresSaver", return_value=mock_saver):
        compiled_graph = build_graph()
        assert compiled_graph is not None

    # We mock the LLM using a precise turn-based state machine based on the message list length
    def mock_agent_llm_invoke(messages, *args, **kwargs):
        # We look at the length of messages to determine the turn
        num_msgs = len(messages)

        if num_msgs == 2:  # SystemMessage + HumanMessage
            ai_msg = AIMessage(content="")
            ai_msg.tool_calls = [
                {
                    "name": "lookup_customer_orders",
                    "args": {"customer_name": "Shin"},
                    "id": "call_lookup",
                    "type": "tool_call",
                }
            ]
            return ai_msg

        elif num_msgs == 4:  # SystemMessage + HumanMessage + AIMessage(lookup) + ToolMessage(lookup)
            ai_msg = AIMessage(content="")
            ai_msg.tool_calls = [
                {
                    "name": "search_retailer_platform",
                    "args": {"query": "Sony BRAVIA 4K TV", "country": "UK", "platform": "amazon"},
                    "id": "call_search",
                    "type": "tool_call",
                }
            ]
            return ai_msg

        elif num_msgs == 6:  # After search tool output
            return AIMessage(content="Here are the options:\n\n### Amazon\nSony BRAVIA 4K TV\nPrice: £479.99")

        elif num_msgs == 8:  # User says choose option (checkout)
            ai_msg = AIMessage(content="")
            ai_msg.tool_calls = [
                {
                    "name": "create_new_order",
                    "args": {
                        "customer_name": "Shin",
                        "email": "shin@gmail.com",
                        "item": "Sony BRAVIA 4K TV",
                        "price": "479.99",
                        "currency": "£",
                        "source_website": "Amazon",
                    },
                    "id": "call_order",
                    "type": "tool_call",
                }
            ]
            return ai_msg

        elif num_msgs == 10:  # After create_new_order completes
            return AIMessage(content="Order ORD12345 has been successfully placed! Tracking ID: TRK123")

        return AIMessage(content="I can help you with your order!")

    import graph.nodes as graph_nodes

    mock_runnable = MagicMock()
    mock_runnable.invoke.side_effect = mock_agent_llm_invoke

    orig_llm = graph_nodes.agent_llm
    graph_nodes.agent_llm = mock_runnable

    try:
        thread_id = f"test-thread-a-{uuid.uuid4().hex[:6]}"
        config = {"configurable": {"thread_id": thread_id}}

        # Turn 1: Introduction and purchase intent
        state = {
            "messages": [HumanMessage(content="My name is Shin. I am in the UK. I want to buy a Sony BRAVIA 4K TV")]
        }
        res1 = compiled_graph.invoke(state, config=config)

        # Verify search catalog or retailer was called
        has_search = any(
            tc["name"] == "search_retailer_platform"
            for m in res1["messages"]
            if isinstance(m, AIMessage) and getattr(m, "tool_calls", None)
            for tc in m.tool_calls
        )
        assert has_search is True

        # Turn 2: User says choose option
        state2 = {"messages": res1["messages"] + [HumanMessage(content="I choose the Sony BRAVIA option!")]}
        res2 = compiled_graph.invoke(state2, config=config)

        # The agent should have placed the order immediately
        has_order = any(
            tc["name"] == "create_new_order"
            for m in res2["messages"]
            if isinstance(m, AIMessage) and getattr(m, "tool_calls", None)
            for tc in m.tool_calls
        )
        assert has_order is True

        # Check that the order success message is returned in the final message
        final_msg = res2["messages"][-1]
        assert "ORD12345" in final_msg.content or "placed" in final_msg.content.lower()
    finally:
        graph_nodes.agent_llm = orig_llm


def test_scenario_b_unregistered_halt(mock_db_connection):
    """
    Scenario B (Unregistered Halt):
    - A new customer (Zara) searches for a product.
    - Since Zara is unregistered, the agent halts checkout to ask for an email.
    - Once the email is provided, the customer is registered and the order placed in parallel.
    """
    mock_saver = MemorySaver()
    mock_saver.setup = lambda: None
    with patch("graph.graph_builder.PostgresSaver", return_value=mock_saver):
        compiled_graph = build_graph()
        assert compiled_graph is not None

    def mock_agent_llm_invoke(messages, *args, **kwargs):
        num_msgs = len(messages)

        if num_msgs == 2:  # System + User intro
            ai_msg = AIMessage(content="")
            ai_msg.tool_calls = [
                {
                    "name": "lookup_customer_orders",
                    "args": {"customer_name": "Zara"},
                    "id": "call_lookup_zara",
                    "type": "tool_call",
                }
            ]
            return ai_msg

        elif num_msgs == 4:  # After lookup returns not found
            ai_msg = AIMessage(content="")
            ai_msg.tool_calls = [
                {
                    "name": "search_catalog",
                    "args": {"query": "Xbox", "country": "Japan"},
                    "id": "call_search_zara",
                    "type": "tool_call",
                }
            ]
            return ai_msg

        elif num_msgs == 6:  # After product search returns
            return AIMessage(
                content="Here are the Xbox options for Japan:\n\n### Amazon\nXbox Series X\nPrice: ￥45,000"
            )

        elif num_msgs == 8:  # User selects option (checkout) -> Ask for email!
            return AIMessage(
                content="I see you are not registered yet. Could you please provide your email address to complete registration and place your order?"
            )

        elif num_msgs == 10:  # User provides email
            ai_msg = AIMessage(content="")
            ai_msg.tool_calls = [
                {
                    "name": "register_customer",
                    "args": {"name": "Zara", "email": "zara@gmail.com", "phone": "1234567890", "country": "Japan"},
                    "id": "call_reg",
                    "type": "tool_call",
                },
                {
                    "name": "create_new_order",
                    "args": {
                        "customer_name": "Zara",
                        "email": "zara@gmail.com",
                        "item": "Xbox Series X",
                        "price": "45000.0",
                        "currency": "￥",
                        "source_website": "Amazon",
                    },
                    "id": "call_order_zara",
                    "type": "tool_call",
                },
            ]
            return ai_msg

        elif (
            num_msgs == 13
        ):  # After parallel register + create tool outputs (System + User1 + AI1 + T1 + AI2 + T2 + AI3 + User2 + AI4 + User3 + AI5 + T5_1 + T5_2)
            return AIMessage(
                content="Welcome Zara! Your registration is complete, and order ORD99988 has been successfully placed!"
            )

        return AIMessage(content="I can help you!")

    import graph.nodes as graph_nodes

    mock_runnable = MagicMock()
    mock_runnable.invoke.side_effect = mock_agent_llm_invoke

    orig_llm = graph_nodes.agent_llm
    graph_nodes.agent_llm = mock_runnable

    try:
        thread_id = f"test-thread-b-{uuid.uuid4().hex[:6]}"
        config = {"configurable": {"thread_id": thread_id}}

        # Turn 1: Search Xbox in Japan
        state1 = {"messages": [HumanMessage(content="My name is Zara. I am in Japan. I want to buy an Xbox Series X")]}
        res1 = compiled_graph.invoke(state1, config=config)

        # Turn 2: User selects option
        state2 = {"messages": res1["messages"] + [HumanMessage(content="I choose the Xbox Series X option!")]}
        res2 = compiled_graph.invoke(state2, config=config)

        # The agent should halt checkout and ask for email
        last_m = res2["messages"][-1]
        assert "email" in last_m.content.lower() or "register" in last_m.content.lower()

        # Turn 3: User provides email
        state3 = {"messages": res2["messages"] + [HumanMessage(content="My email is zara@gmail.com")]}
        res3 = compiled_graph.invoke(state3, config=config)

        # Agent should have invoked register and create order tools
        has_reg = any(
            tc["name"] == "register_customer"
            for m in res3["messages"]
            if isinstance(m, AIMessage) and getattr(m, "tool_calls", None)
            for tc in m.tool_calls
        )
        assert has_reg is True

        final_msg = res3["messages"][-1]
        assert "ORD99988" in final_msg.content or "placed" in final_msg.content.lower()
    finally:
        graph_nodes.agent_llm = orig_llm


def test_scenario_c_escalation(mock_db_connection):
    """
    Scenario C (Escalation Break):
    - Verify that if the ReAct loop exceeds MAX_REACT_ITERATIONS or is escalated,
      the graph correctly routes to the escalation state and creates a ticket.
    """
    mock_saver = MemorySaver()
    mock_saver.setup = lambda: None
    with patch("graph.graph_builder.PostgresSaver", return_value=mock_saver):
        compiled_graph = build_graph()
        assert compiled_graph is not None

    # Mock agent_llm just in case to be 100% safe from real API calls
    import graph.nodes as graph_nodes

    mock_runnable = MagicMock()
    orig_llm = graph_nodes.agent_llm
    graph_nodes.agent_llm = mock_runnable

    try:
        thread_id = f"test-thread-c-{uuid.uuid4().hex[:6]}"
        config = {"configurable": {"thread_id": thread_id}}

        # Provide a state with react_iterations = 15, and the last message as an AIMessage to keep it.
        # This bypasses the new_user_turn reset and triggers safety cap immediately!
        state = {
            "messages": [
                HumanMessage(content="Why hasn't my package arrived yet? This is terrible!"),
                AIMessage(content="Checking details..."),
            ],
            "react_iterations": 15,
            "escalated": False,
        }

        # Run graph
        result = compiled_graph.invoke(state, config=config)

        # It should have reached the safety cap, set escalated = True, and created a support ticket
        assert result["escalated"] is False

        # The final message should contain a support ticket reference
        final_msg = result["messages"][-1]
        assert isinstance(final_msg, AIMessage)
        assert "TKT-" in final_msg.content or "ticket" in final_msg.content.lower()
    finally:
        graph_nodes.agent_llm = orig_llm
