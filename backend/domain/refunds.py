import random
import uuid
from domain.analytics import log_event
from domain.rules import USER_FRIENDLY_DB_ERROR
from infra.db import get_connection
from infra.logger import get_logger

logger = get_logger("refunds")

def get_refund_status(order_id: str) -> dict:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT r.refund_id, r.status, r.amount, r.eta, r.refund_reason, r.updated_at
                    FROM refunds r
                    JOIN orders o ON r.order_id = o.order_id
                    WHERE r.order_id = %s
                """,
                    (order_id,),
                )
                row = cur.fetchone()
                if not row:
                    return {"status": "no_refund_found", "order_id": order_id}
                return {
                    "refund_id": row[0],
                    "refund_status": row[1],
                    "amount": float(row[2]),
                    "eta": row[3],
                    "refund_reason": row[4] or "Not specified",
                    "last_updated": str(row[5]) if row[5] else "N/A",
                }
    except Exception as e:
        logger.error(
            "DB error in get_refund_status", extra={"event": "db_error", "error": str(e), "order_id": order_id}
        )
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

                # Check if refund already exists
                cur.execute("SELECT refund_id FROM refunds WHERE order_id = %s", (order_id,))
                if cur.fetchone():
                    return {
                        "success": False,
                        "message": f"A return/refund is already being processed for order {order_id}.",
                    }

                # Update order status
                cur.execute("UPDATE orders SET status = 'returned' WHERE order_id = %s", (order_id,))

                # Generate new refund record
                refund_id = f"REF-{uuid.uuid4().hex[:6].upper()}"
                amount = round(random.uniform(50.0, 500.0), 2)  # Demo dynamic pricing
                eta = "3-5 business days"

                cur.execute(
                    """
                    INSERT INTO refunds (refund_id, order_id, amount, status, eta, refund_reason)
                    VALUES (%s, %s, %s, 'pending', %s, %s)
                """,
                    (refund_id, order_id, amount, eta, reason),
                )

                # Notification
                cur.execute(
                    """
                    SELECT c.email, c.name, c.telegram_chat_id FROM customers c
                    JOIN orders o ON c.customer_id = o.customer_id
                    WHERE o.order_id = %s
                """,
                    (order_id,),
                )
                cust_row = cur.fetchone()
                if cust_row:
                    email, name, telegram_id = cust_row
                    from infra.notifications import send_email, send_telegram

                    if email:
                        send_email(
                            to_email=email,
                            subject=f"Return Initiated: {order_id}",
                            body=f"Hi {name},\n\nWe have initiated a return for order {order_id}. Your refund ID is {refund_id} for the amount of ${amount:.2f}.",
                        )

                    if telegram_id:
                        send_telegram(
                            chat_id=telegram_id,
                            message=f"📦 Return Initiated!\nOrder: {order_id}\nRefund ID: {refund_id}\nAmount: ${amount:.2f}",
                        )

                conn.commit()

                # ANALYTICS: Log return conversion (Synchronous for 100% reliability)
                log_event("return_initiated", order_id, "return", {"refund_id": refund_id, "amount": amount})

                return {
                    "success": True,
                    "return_id": f"RET-{order_id}",
                    "message": f"Return initiated successfully. Refund ID: {refund_id}. Pickup scheduled within 2-3 days.",
                }
    except Exception as e:
        logger.error("DB error in initiate_return", extra={"event": "db_error", "error": str(e), "order_id": order_id})
        return {"error": USER_FRIENDLY_DB_ERROR}

