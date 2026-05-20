from langchain_core.tools import tool
from tools.real_tools import (
    get_order_status, get_refund_status, initiate_return,
    cancel_order, get_customer_orders, place_new_order,
    register_new_customer, get_analytics_summary
)
import re

ORDER_ID_PATTERN = re.compile(r"^ORD\d{3,10}$")

# Phonetic aliases the speech-recognition API commonly transcribes instead of "ORD"
_PHONETIC_ORD_PREFIX = re.compile(
    r'^(?:odd|or\s*d|o\.?r\.?d\.?|0rd|ord)\s*[-\s]*',
    re.IGNORECASE
)

def normalize_order_id(order_id: str) -> str:
    """Normalize an order ID string, correcting common speech-recognition mishearings.

    Examples that all resolve to ORD001:
        'ORD 001', 'ord001', 'ODD001', 'ODD 001', 'Odd 001',
        'OR D 001', 'O.R.D 001', '0rd001'
    """
    if not order_id:
        return ""
    # Step 1: strip leading/trailing whitespace
    normalized = order_id.strip()
    # Step 2: fix phonetic prefix mishearings (ODD -> ORD, OR D -> ORD, etc.)
    normalized = _PHONETIC_ORD_PREFIX.sub('ORD', normalized)
    # Step 3: strip all remaining separators (spaces, dashes, dots, underscores, colons)
    normalized = re.sub(r'[\s\-_\.:\(\)]+', '', normalized)
    # Step 4: uppercase everything
    return normalized.upper()

@tool
def check_order_status(order_id: str) -> str:
    """Check the delivery status of a customer order. Use when a customer asks 'where is my order' or 'order status'. Requires order ID like ORD001."""
    order_id = normalize_order_id(order_id)
    if not ORDER_ID_PATTERN.match(order_id):
        return f"I couldn't find an order with ID '{order_id}'. Order IDs start with ORD followed by digits (e.g., ORD001). Could you please confirm your order ID?"
    result = get_order_status(order_id)
    return str(result)

@tool
def check_refund_status(order_id: str) -> str:
    """Check refund status and amount for a customer order. Use when a customer asks about their refund. Requires order ID like ORD001."""
    order_id = normalize_order_id(order_id)
    if not ORDER_ID_PATTERN.match(order_id):
        return f"I couldn't find an order with ID '{order_id}'. Order IDs start with ORD followed by digits (e.g., ORD001). Could you please confirm your order ID?"
    result = get_refund_status(order_id)
    return str(result)

@tool
def process_return(order_id: str, reason: str = "customer request") -> str:
    """Initiate a return for a delivered order. Use when a customer wants to return an item. Requires order ID like ORD001 and the reason for the return (e.g., 'defective', 'wrong size', 'no longer needed')."""
    order_id = normalize_order_id(order_id)
    if not ORDER_ID_PATTERN.match(order_id):
        return f"I couldn't find an order with ID '{order_id}'. Order IDs start with ORD followed by digits (e.g., ORD001). Could you please confirm your order ID?"
    result = initiate_return(order_id, reason)
    return str(result)

@tool
def process_cancellation(order_id: str) -> str:
    """Cancel a pending or processing order. Use when a customer wants to cancel. Requires order ID like ORD001."""
    order_id = normalize_order_id(order_id)
    if not ORDER_ID_PATTERN.match(order_id):
        return f"I couldn't find an order with ID '{order_id}'. Order IDs start with ORD followed by digits (e.g., ORD001). Could you please confirm your order ID?"
    result = cancel_order(order_id)
    return str(result)

@tool
def lookup_customer_orders(customer_name: str) -> str:
    """Look up all orders for a customer by their name. Use when a customer says their name and asks about their orders. Do NOT use with email addresses — suggest searching by name instead."""
    result = get_customer_orders(customer_name)
    return str(result)

from langchain_core.runnables import RunnableConfig

@tool
def register_customer(name: str, email: str, config: RunnableConfig, phone_number: str = None) -> str:
    """Register a new customer account. Use when a customer wants to register or place an order. Requires their full name and a valid email address provided by the customer in the chat."""
    # Use the verified email extracted from the customer's message (not LLM-hallucinated)
    real_email = config.get("configurable", {}).get("raw_email")
    if not real_email:
        return (
            "ERROR: No valid email address found in the customer's message. "
            "Do NOT call this tool again — instead ask the customer to provide their email address in the chat."
        )
    result = register_new_customer(name, real_email, phone_number)
    return str(result)

@tool
def create_new_order(customer_name: str, item: str, config: RunnableConfig) -> str:
    """Place a new order for a customer. Use ONLY when a customer explicitly wants to BUY or PURCHASE a new product. Do NOT use for complaints, stolen items, or support issues."""
    email = config.get("configurable", {}).get("raw_email")
    result = place_new_order(customer_name, item, email)
    return str(result)

@tool
def create_support_ticket(order_id: str, issue_type: str, message: str, customer_name: str = "") -> str:
    """Create a support ticket for a human agent. Use for complex issues, complaints, stolen packages, damaged items, or when the user explicitly asks for a human. Requires order ID, issue type (e.g., 'stolen_package', 'damaged'), a descriptive message, and the customer_name as stated in the conversation."""
    from tools.real_tools import create_support_ticket as create_ticket_logic
    import uuid
    order_id = normalize_order_id(order_id)
    ticket_id = f"TKT-{uuid.uuid4().hex[:6].upper()}"
    result = create_ticket_logic(ticket_id, order_id, issue_type, message, customer_name or None)

    if result.get("identity_mismatch"):
        return result.get("message", "Identity could not be verified for this order.")
    elif result.get("duplicate"):
        existing_id = result.get("ticket_id", "existing")
        return (
            f"IMPORTANT: Tell the customer exactly this — "
            f"'A support ticket is already open for order {order_id}. "
            f"Your Ticket ID is {existing_id}. "
            f"A human agent is already reviewing your case and will contact you within 2 hours.'"
        )
    elif result.get("success"):
        return (
            f"Support ticket created successfully. "
            f"Ticket ID: {ticket_id}. "
            f"A human agent will review your case and contact you within 2 hours."
        )
    else:
        return result.get("message", "We experienced an issue creating your ticket, but an agent has been notified.")

@tool
def view_business_analytics() -> str:
    """Show high-level business analytics summary. Use ONLY when the user asks for 'analytics', 'dashboard', 'stats', or 'business performance'."""
    result = get_analytics_summary()
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
    create_support_ticket,
    view_business_analytics
]
