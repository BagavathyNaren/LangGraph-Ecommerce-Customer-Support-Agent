from langchain_core.tools import tool
from tools.real_tools import (
    get_order_status, get_refund_status, initiate_return,
    cancel_order, get_customer_orders
)
import re

ORDER_ID_PATTERN = re.compile(r"^ORD\d{3,10}$")

@tool
def check_order_status(order_id: str) -> str:
    """Check the delivery status of a customer order. Use when a customer asks 'where is my order' or 'order status'. Requires order ID like ORD001."""
    if not ORDER_ID_PATTERN.match(order_id):
        return "Invalid order ID format. Please ask for the order ID in format ORD followed by digits (e.g., ORD001)."
    result = get_order_status(order_id)
    return str(result)

@tool
def check_refund_status(order_id: str) -> str:
    """Check refund status and amount for a customer order. Use when a customer asks about their refund. Requires order ID like ORD001."""
    if not ORDER_ID_PATTERN.match(order_id):
        return "Invalid order ID format. Please ask for the order ID in format ORD followed by digits (e.g., ORD001)."
    result = get_refund_status(order_id)
    return str(result)

@tool
def process_return(order_id: str) -> str:
    """Initiate a return for a delivered order. Use when a customer wants to return an item. Requires order ID like ORD001."""
    if not ORDER_ID_PATTERN.match(order_id):
        return "Invalid order ID format. Please ask for the order ID in format ORD followed by digits (e.g., ORD001)."
    result = initiate_return(order_id, "customer request")
    return str(result)

@tool
def process_cancellation(order_id: str) -> str:
    """Cancel a pending or processing order. Use when a customer wants to cancel. Requires order ID like ORD001."""
    if not ORDER_ID_PATTERN.match(order_id):
        return "Invalid order ID format. Please ask for the order ID in format ORD followed by digits (e.g., ORD001)."
    result = cancel_order(order_id)
    return str(result)

@tool
def lookup_customer_orders(customer_name: str) -> str:
    """Look up all orders for a customer by their name. Use when a customer says their name and asks about their orders. Do NOT use with email addresses — suggest searching by name instead."""
    result = get_customer_orders(customer_name)
    return str(result)

# All tools available to the agent
AGENT_TOOLS = [
    check_order_status,
    check_refund_status,
    process_return,
    process_cancellation,
    lookup_customer_orders
]
