import pytest
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from graph.nodes import escalation_check, escalate

def test_escalation_check_no_escalate():
    state = {
        "messages": [HumanMessage(content="Hello! I have a question about my PlayStation delivery.")],
        "anger_count": 0,
        "retry_count": 0,
        "refund_amount": 0.0,
        "escalated": False
    }
    result = escalation_check(state)
    assert result["escalated"] is False
    assert result["anger_count"] == 0

def test_escalation_check_anger_triggers():
    state = {
        "messages": [HumanMessage(content="This is useless! I want a refund now!")],
        "anger_count": 0,
        "retry_count": 0,
        "refund_amount": 0.0,
        "escalated": False
    }
    result = escalation_check(state)
    # First anger word matches, anger_count becomes 1
    assert result["anger_count"] == 1
    assert result["escalated"] is False

    # Second anger word triggers escalation
    result["messages"].append(HumanMessage(content="I am furious! Escalate this!"))
    result = escalation_check(result)
    assert result["anger_count"] == 2
    assert result["escalated"] is True

def test_escalation_check_retry_cap():
    state = {
        "messages": [HumanMessage(content="Still doesn't work.")],
        "anger_count": 0,
        "retry_count": 3,
        "refund_amount": 0.0,
        "escalated": False
    }
    result = escalation_check(state)
    assert result["escalated"] is True

def test_escalation_check_high_value_refund():
    state = {
        "messages": [HumanMessage(content="Cancel this massive order.")],
        "anger_count": 0,
        "retry_count": 0,
        "refund_amount": 6000.0,
        "escalated": False
    }
    result = escalation_check(state)
    assert result["escalated"] is True

def test_escalate_generates_ticket(mock_db_connection):
    state = {
        "messages": [
            HumanMessage(content="My name is Shin. I want to cancel ORD12345"),
            HumanMessage(content="Angry")
        ],
        "order_id": "ORD12345",
        "escalated": True
    }
    result = escalate(state)
    last_msg = result["messages"][-1]
    assert isinstance(last_msg, AIMessage)
    assert "TKT-" in last_msg.content or "support ticket" in last_msg.content.lower()

def test_escalate_scans_history_reverse(mock_db_connection):
    # Tests that escalate resolves order_id and customer name from human message patterns if state is empty
    state = {
        "messages": [
            HumanMessage(content="Hi, this is Chan. My order is ORD998877"),
            HumanMessage(content="Escalate this immediately!")
        ],
        "escalated": True
    }
    result = escalate(state)
    last_msg = result["messages"][-1]
    assert isinstance(last_msg, AIMessage)
    assert "TKT-" in last_msg.content
