def get_order_status(order_id: str) -> dict:
    mock_orders = {
        "ORD001": {"status": "delivered", "item": "Nike Shoes", "date": "2026-04-28"},
        "ORD002": {"status": "in_transit", "item": "Samsung Charger", "date": "2026-05-01"},
        "ORD003": {"status": "processing", "item": "Laptop Stand", "date": "2026-05-03"},
    }
    return mock_orders.get(order_id, {"status": "not_found"})

def initiate_return(order_id: str, reason: str) -> dict:
    return {"success": True, "return_id": f"RET-{order_id}", "message": "Return initiated. Pickup in 2-3 days."}

def get_refund_status(order_id: str) -> dict:
    return {"order_id": order_id, "refund_status": "pending", "amount": 1200.0, "eta": "3-5 business days"}

def cancel_order(order_id: str) -> dict:
    return {"success": True, "message": f"Order {order_id} cancelled successfully."}

def search_knowledge_base(query: str) -> dict:
    return {"answer": f"Based on our policy: '{query}' — please allow 5-7 days for processing."}

def create_support_ticket(issue_summary: str) -> dict:
    return {"ticket_id": "TKT-9901", "message": "Ticket raised. Human agent will contact within 2 hours."}