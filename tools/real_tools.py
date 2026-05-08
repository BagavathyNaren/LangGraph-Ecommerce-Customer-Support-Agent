import os
from tools.db import get_connection

def get_order_status(order_id: str) -> dict:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT order_id, status, item, expected_delivery
                    FROM orders
                    WHERE order_id = %s
                """, (order_id,))
                row = cur.fetchone()
                if not row:
                    return {"status": "not_found", "order_id": order_id}
                return {
                    "order_id": row[0],
                    "status": row[1],
                    "item": row[2],
                    "expected_delivery": str(row[3])
                }
    except Exception as e:
        return {"error": str(e)}

def get_refund_status(order_id: str) -> dict:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT r.refund_id, r.status, r.amount, r.eta
                    FROM refunds r
                    JOIN orders o ON r.order_id = o.order_id
                    WHERE r.order_id = %s
                """, (order_id,))
                row = cur.fetchone()
                if not row:
                    return {"status": "no_refund_found", "order_id": order_id}
                return {
                    "refund_id": row[0],
                    "refund_status": row[1],
                    "amount": float(row[2]),
                    "eta": row[3]
                }
    except Exception as e:
        return {"error": str(e)}

def initiate_return(order_id: str, reason: str) -> dict:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM orders WHERE order_id = %s", (order_id,))
                row = cur.fetchone()
                if not row:
                    return {"success": False, "message": f"Order {order_id} not found."}
                if row[0] != "delivered":
                    return {"success": False, "message": f"Order {order_id} cannot be returned — status is {row[0]}."}
                return {
                    "success": True,
                    "return_id": f"RET-{order_id}",
                    "message": "Return initiated. Pickup scheduled within 2-3 days."
                }
    except Exception as e:
        return {"error": str(e)}

def cancel_order(order_id: str) -> dict:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM orders WHERE order_id = %s", (order_id,))
                row = cur.fetchone()
                if not row:
                    return {"success": False, "message": f"Order {order_id} not found."}
                if row[0] in ("delivered", "cancelled"):
                    return {"success": False, "message": f"Order {order_id} cannot be cancelled — status is {row[0]}."}
                cur.execute("UPDATE orders SET status = 'cancelled' WHERE order_id = %s", (order_id,))
                conn.commit()
                return {"success": True, "message": f"Order {order_id} cancelled successfully."}
    except Exception as e:
        return {"error": str(e)}

def search_knowledge_base(query: str) -> dict:
    return {"answer": f"Based on our policy regarding '{query}': please allow 5-7 business days for processing. Contact support for urgent cases."}

def create_support_ticket(issue_summary: str) -> dict:
    import uuid
    ticket_id = f"TKT-{uuid.uuid4().hex[:6].upper()}"
    return {"ticket_id": ticket_id, "message": "Ticket raised. Human agent will contact within 2 hours."}