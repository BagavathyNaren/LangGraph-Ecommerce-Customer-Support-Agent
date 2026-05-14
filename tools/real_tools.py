import os
from tools.db import get_connection
from logger import get_logger

logger = get_logger("tools")

USER_FRIENDLY_DB_ERROR = "We're experiencing a temporary issue. Please try again in a moment."

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
        logger.error("DB error in get_order_status", extra={"event": "db_error", "error": str(e), "order_id": order_id})
        return {"error": USER_FRIENDLY_DB_ERROR}

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
        logger.error("DB error in get_refund_status", extra={"event": "db_error", "error": str(e), "order_id": order_id})
        return {"error": USER_FRIENDLY_DB_ERROR}

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
        logger.error("DB error in initiate_return", extra={"event": "db_error", "error": str(e), "order_id": order_id})
        return {"error": USER_FRIENDLY_DB_ERROR}

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
        logger.error("DB error in cancel_order", extra={"event": "db_error", "error": str(e), "order_id": order_id})
        return {"error": USER_FRIENDLY_DB_ERROR}

def get_customer_orders(customer_name: str) -> dict:
    """Look up a customer by name or email, return their profile and orders."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Search by name or email (case-insensitive partial match)
                cur.execute("""
                    SELECT c.customer_id, c.name, c.email,
                           o.order_id, o.status, o.item, o.expected_delivery, o.tracking_number
                    FROM customers c
                    LEFT JOIN orders o ON c.customer_id = o.customer_id
                    WHERE c.name ILIKE %s OR c.email ILIKE %s
                    ORDER BY o.expected_delivery DESC
                """, (f"%{customer_name}%", f"%{customer_name}%"))
                rows = cur.fetchall()
                if not rows:
                    return {"status": "not_found", "query": customer_name}
                customer = {"customer_id": rows[0][0], "name": rows[0][1], "email": rows[0][2]}
                orders = []
                for row in rows:
                    if row[3]:  # order_id exists
                        orders.append({
                            "order_id": row[3],
                            "status": row[4],
                            "item": row[5],
                            "expected_delivery": str(row[6]),
                            "tracking_number": row[7]
                        })
                return {"customer": customer, "orders": orders}
    except Exception as e:
        logger.error("DB error in get_customer_orders", extra={"event": "db_error", "error": str(e), "query": customer_name})
        return {"error": USER_FRIENDLY_DB_ERROR}

def search_knowledge_base(query: str) -> dict:
    return {"answer": f"Based on our policy regarding '{query}': please allow 5-7 business days for processing. Contact support for urgent cases."}

def create_support_ticket(issue_summary: str) -> dict:
    import uuid
    ticket_id = f"TKT-{uuid.uuid4().hex[:6].upper()}"
    return {"ticket_id": ticket_id, "message": "Ticket raised. Human agent will contact within 2 hours."}