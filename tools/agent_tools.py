from langchain_core.tools import tool
from tools.real_tools import (
    get_order_status, get_refund_status, initiate_return,
    cancel_order, get_customer_orders, place_new_order,
    register_new_customer
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

from langchain_core.runnables import RunnableConfig

@tool
def register_customer(name: str, email: str, config: RunnableConfig) -> str:
    """Register a new customer account. Use when a customer wants to register, or when they want to place an order but don't have an account yet. Requires their full name and email address."""
    if email == "<EMAIL_ADDRESS>":
        real_email = config.get("configurable", {}).get("raw_email")
        if real_email:
            email = real_email
        else:
            return "Error: Secure email vault extraction failed. Please ensure your email is valid."
    result = register_new_customer(name, email)
    return str(result)

@tool
def create_new_order(customer_name: str, item: str) -> str:
    """Place a new order for a customer. Use ONLY when a customer explicitly wants to BUY or PURCHASE a new product. Do NOT use for complaints, stolen items, or support issues."""
    result = place_new_order(customer_name, item)
    return str(result)

@tool
def create_support_ticket(order_id: str, issue_type: str, message: str) -> str:
    """Create a support ticket for a human agent. Use for complex issues, complaints, stolen packages, damaged items, or when the user explicitly asks for a human. Requires order ID, issue type (e.g., 'stolen_package', 'damaged'), and a descriptive message."""
    from tools.real_tools import create_support_ticket as create_ticket_logic
    import uuid
    ticket_id = f"TKT-{uuid.uuid4().hex[:6].upper()}"
    result = create_ticket_logic(ticket_id, order_id, issue_type, message)
    return str(result)

# All tools available to the agent
AGENT_TOOLS = [
    check_order_status,
    check_refund_status,
    process_return,
    process_cancellation,
    lookup_customer_orders,
    register_customer,
    create_new_order,
    create_support_ticket
]
