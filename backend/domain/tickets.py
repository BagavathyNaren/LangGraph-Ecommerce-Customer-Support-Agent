from domain.analytics import log_event
from infra.db import get_connection
from infra.logger import get_logger
from infra.notifications import send_email, send_telegram

logger = get_logger("tickets")

def create_support_ticket(
    ticket_id: str, order_id: str, issue_type: str, message: str, customer_name: str = None
) -> dict:
    # Keywords that indicate a physical delivery issue (requires delivered status)
    DELIVERY_REQUIRED_KEYWORDS = {"stolen", "damaged", "wrong_item", "missing", "not_received"}
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                customer_id = None

                # 1. Try to find customer via order_id
                if order_id:
                    cur.execute("SELECT customer_id, status FROM orders WHERE order_id = %s", (order_id,))
                    row = cur.fetchone()
                    if row:
                        customer_id = row[0]
                        order_status = row[1]

                        # Guard: check if ANY delivery keyword is contained in the issue_type
                        is_delivery_issue = any(kw in issue_type.lower() for kw in DELIVERY_REQUIRED_KEYWORDS)
                        if is_delivery_issue and order_status != "delivered":
                            return {
                                "success": False,
                                "message": f"Order {order_id} has status '{order_status}' and has not been delivered yet. "
                                f"Please wait for delivery before reporting a {issue_type.replace('_', ' ')} issue. "
                                f"If your order is significantly delayed, we can help with that instead.",
                            }

                        # Bug 1 Fix: Validate caller's name matches the order owner
                        if customer_name and customer_name.lower().strip() not in ("customer", ""):
                            cur.execute("SELECT name FROM customers WHERE customer_id = %s", (customer_id,))
                            owner_row = cur.fetchone()
                            if owner_row and owner_row[0]:
                                owner_words = set(owner_row[0].lower().split())
                                caller_words = set(customer_name.lower().split())
                                if not caller_words.intersection(owner_words):
                                    logger.warning(
                                        "Identity mismatch on ticket creation",
                                        extra={
                                            "event": "identity_mismatch",
                                            "caller": customer_name,
                                            "owner": owner_row[0],
                                            "order_id": order_id,
                                        },
                                    )
                                    return {
                                        "success": False,
                                        "identity_mismatch": True,
                                        "message": (
                                            f"I could not verify your identity for order {order_id}. "
                                            f"The name you provided does not match our records. "
                                            f"Please contact us using the email address registered with this order."
                                        ),
                                    }

                # 2. If no customer_id found via order, try by name
                if not customer_id and customer_name:
                    cur.execute(
                        "SELECT customer_id FROM customers WHERE name ILIKE %s LIMIT 1", (f"%{customer_name}%",)
                    )
                    name_row = cur.fetchone()
                    if name_row:
                        customer_id = name_row[0]

                # 3. Bug 3 Fix: Duplicate check — ONE open ticket per order per customer (any issue type)
                if order_id:
                    if customer_id:
                        cur.execute(
                            """
                            SELECT ticket_id, issue_type FROM support_tickets
                            WHERE order_id = %s
                              AND customer_id = %s
                              AND status = 'open'
                            LIMIT 1
                        """,
                            (order_id, customer_id),
                        )
                    else:
                        cur.execute(
                            """
                            SELECT ticket_id, issue_type FROM support_tickets
                            WHERE order_id = %s
                              AND customer_id IS NULL
                              AND status = 'open'
                            LIMIT 1
                        """,
                            (order_id,),
                        )
                    existing = cur.fetchone()
                    if existing:
                        logger.info(
                            "Duplicate ticket suppressed",
                            extra={
                                "event": "duplicate_ticket",
                                "existing_ticket": existing[0],
                                "order_id": order_id,
                                "existing_issue": existing[1],
                            },
                        )
                        return {
                            "success": True,
                            "message": f"An open support ticket already exists for order {order_id} (Ticket ID: {existing[0]}). "
                            "A human agent will review your case and contact you within 2 hours.",
                            "ticket_id": existing[0],
                            "duplicate": True,
                        }

                cur.execute(
                    """
                    INSERT INTO support_tickets (ticket_id, customer_id, order_id, issue_type, message)
                    VALUES (%s, %s, %s, %s, %s)
                """,
                    (ticket_id, customer_id, order_id, issue_type, message),
                )

                # Notification
                if customer_id:
                    cur.execute(
                        "SELECT email, name, telegram_chat_id FROM customers WHERE customer_id = %s", (customer_id,)
                    )
                    cust_row = cur.fetchone()
                    if cust_row:
                        email, name, telegram_id = cust_row
                        from infra.notifications import send_email, send_telegram

                        if email:
                            send_email(
                                to_email=email,
                                subject=f"Support Ticket Created: {ticket_id}",
                                body=f"Hi {name},\n\nWe received your support request regarding order {order_id}. Ticket ID: {ticket_id}.",
                            )

                        if telegram_id:
                            send_telegram(
                                chat_id=telegram_id,
                                message=f"🚨 Ticket Created!\nID: {ticket_id}\nOrder: {order_id}\nIssue: {issue_type}",
                            )

                conn.commit()

                # ANALYTICS: Log ticket conversion (Synchronous for 100% reliability)
                log_event("ticket_created", order_id, "support", {"ticket_id": ticket_id, "issue": issue_type})

                return {
                    "success": True,
                    "message": "A human agent will review your case and contact you within 2 hours.",
                    "ticket_id": ticket_id,
                }
    except Exception as e:
        logger.error(
            "DB error in create_support_ticket", extra={"event": "db_error", "error": str(e), "ticket_id": ticket_id}
        )
        return {
            "success": False,
            "message": "We experienced an issue creating your ticket, but an agent has been notified.",
        }

