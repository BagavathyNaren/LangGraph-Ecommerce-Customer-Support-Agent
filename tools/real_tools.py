import os
from tools.db import get_connection
from logger import get_logger
from tools.analytics import log_event

logger = get_logger("tools")

USER_FRIENDLY_DB_ERROR = "We are experiencing high traffic, please try again in a few minutes."

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
    import uuid
    import random
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
                    return {"success": False, "message": f"A return/refund is already being processed for order {order_id}."}

                # Update order status
                cur.execute("UPDATE orders SET status = 'returned' WHERE order_id = %s", (order_id,))
                
                # Generate new refund record
                refund_id = f"REF-{uuid.uuid4().hex[:6].upper()}"
                amount = round(random.uniform(50.0, 500.0), 2)  # Demo dynamic pricing
                eta = "3-5 business days"
                
                cur.execute("""
                    INSERT INTO refunds (refund_id, order_id, amount, status, eta)
                    VALUES (%s, %s, %s, 'pending', %s)
                """, (refund_id, order_id, amount, eta))
                
                # Notification
                cur.execute("""
                    SELECT c.email, c.name, c.telegram_chat_id FROM customers c 
                    JOIN orders o ON c.customer_id = o.customer_id 
                    WHERE o.order_id = %s
                """, (order_id,))
                cust_row = cur.fetchone()
                if cust_row:
                    email, name, telegram_id = cust_row
                    from tools.notifications import send_email, send_telegram
                    
                    if email:
                        send_email(
                            to_email=email, 
                            subject=f"Return Initiated: {order_id}", 
                            body=f"Hi {name},\n\nWe have initiated a return for order {order_id}. Your refund ID is {refund_id} for the amount of ${amount:.2f}."
                        )
                    
                    if telegram_id:
                        send_telegram(
                            chat_id=telegram_id,
                            message=f"📦 Return Initiated!\nOrder: {order_id}\nRefund ID: {refund_id}\nAmount: ${amount:.2f}"
                        )
                    
                conn.commit()

                # ANALYTICS: Log return conversion (Synchronous for 100% reliability)
                log_event("return_initiated", order_id, "return", {"refund_id": refund_id, "amount": amount})

                return {
                    "success": True,
                    "return_id": f"RET-{order_id}",
                    "message": f"Return initiated successfully. Refund ID: {refund_id}. Pickup scheduled within 2-3 days."
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
                
                # Notification
                cur.execute("""
                    SELECT c.email, c.name, c.telegram_chat_id FROM customers c 
                    JOIN orders o ON c.customer_id = o.customer_id 
                    WHERE o.order_id = %s
                """, (order_id,))
                cust_row = cur.fetchone()
                if cust_row:
                    email, name, telegram_id = cust_row
                    from tools.notifications import send_email, send_telegram
                    
                    if email:
                        send_email(
                            to_email=email, 
                            subject=f"Order Cancelled: {order_id}", 
                            body=f"Hi {name},\n\nYour order {order_id} has been successfully cancelled."
                        )
                    
                    if telegram_id:
                        send_telegram(
                            chat_id=telegram_id,
                            message=f"❌ Order Cancelled!\nOrder ID: {order_id}"
                        )

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

def register_new_customer(name: str, email: str) -> dict:
    """Register a new customer in the database."""
    import uuid
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Check if email already exists
                cur.execute("SELECT customer_id FROM customers WHERE email = %s", (email,))
                if cur.fetchone():
                    return {"success": False, "message": f"An account with email {email} already exists."}
                
                customer_id = f"CUST-{uuid.uuid4().hex[:6].upper()}"
                
                cur.execute("""
                    INSERT INTO customers (customer_id, name, email)
                    VALUES (%s, %s, %s)
                """, (customer_id, name, email))
                conn.commit()
                
                return {
                    "success": True,
                    "customer_id": customer_id,
                    "message": f"Customer '{name}' successfully registered with email '{email}'."
                }
    except Exception as e:
        logger.error("DB error in register_new_customer", extra={"event": "db_error", "error": str(e), "email": email})
        return {"error": USER_FRIENDLY_DB_ERROR}

def place_new_order(customer_name: str, item: str) -> dict:
    """Place a new order for a customer."""
    import random
    from datetime import datetime, timedelta
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Find customer
                cur.execute("SELECT customer_id FROM customers WHERE name ILIKE %s OR email ILIKE %s", (f"%{customer_name}%", f"%{customer_name}%"))
                row = cur.fetchone()
                if not row:
                    return {"success": False, "message": f"Customer '{customer_name}' not found. Please register an account first."}
                
                customer_id = row[0]
                # Ensure unique order ID
                while True:
                    order_id = f"ORD{random.randint(100, 9999)}"
                    cur.execute("SELECT order_id FROM orders WHERE order_id = %s", (order_id,))
                    if not cur.fetchone():
                        break

                tracking = f"TRK-{order_id}-{datetime.now().year}"
                delivery_date = (datetime.now() + timedelta(days=5)).date()
                
                cur.execute("""
                    INSERT INTO orders (order_id, customer_id, item, status, expected_delivery, tracking_number)
                    VALUES (%s, %s, %s, 'processing', %s, %s)
                """, (order_id, customer_id, item, delivery_date, tracking))
                conn.commit()
                
                return {
                    "success": True,
                    "order_id": order_id,
                    "message": f"Order {order_id} for '{item}' has been placed successfully! Expected delivery: {delivery_date}. Tracking: {tracking}"
                }
    except Exception as e:
        logger.error("DB error in place_new_order", extra={"event": "db_error", "error": str(e), "customer": customer_name})
        return {"error": USER_FRIENDLY_DB_ERROR}

def search_knowledge_base(query: str) -> dict:
    return {"answer": f"Based on our policy regarding '{query}': please allow 5-7 business days for processing. Contact support for urgent cases."}

def create_support_ticket(ticket_id: str, order_id: str, issue_type: str, message: str) -> dict:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                customer_id = None
                if order_id:
                    cur.execute("SELECT customer_id FROM orders WHERE order_id = %s", (order_id,))
                    row = cur.fetchone()
                    if row:
                        customer_id = row[0]
                
                cur.execute("""
                    INSERT INTO support_tickets (ticket_id, customer_id, order_id, issue_type, message)
                    VALUES (%s, %s, %s, %s, %s)
                """, (ticket_id, customer_id, order_id, issue_type, message))
                
                # Notification
                if customer_id:
                    cur.execute("SELECT email, name, telegram_chat_id FROM customers WHERE customer_id = %s", (customer_id,))
                    cust_row = cur.fetchone()
                    if cust_row:
                        email, name, telegram_id = cust_row
                        from tools.notifications import send_email, send_telegram
                        
                        if email:
                            send_email(
                                to_email=email, 
                                subject=f"Support Ticket Created: {ticket_id}", 
                                body=f"Hi {name},\n\nWe received your support request regarding order {order_id}. Ticket ID: {ticket_id}."
                            )
                        
                        if telegram_id:
                            send_telegram(
                                chat_id=telegram_id,
                                message=f"🚨 Ticket Created!\nID: {ticket_id}\nOrder: {order_id}\nIssue: {issue_type}"
                            )

                conn.commit()

                # ANALYTICS: Log ticket conversion (Synchronous for 100% reliability)
                log_event("ticket_created", order_id, "support", {"ticket_id": ticket_id, "issue": issue_type})

                return {"success": True, "message": "A human agent will review your case and contact you within 2 hours."}
    except Exception as e:
        logger.error("DB error in create_support_ticket", extra={"event": "db_error", "error": str(e), "ticket_id": ticket_id})
        return {"success": False, "message": "We experienced an issue creating your ticket, but an agent has been notified."}

def get_analytics_summary() -> dict:
    """Fetch a summary of business analytics from the database."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Total Tickets Created
                cur.execute("SELECT COUNT(*) FROM analytics_events WHERE event_type = 'ticket_created'")
                total_tickets = cur.fetchone()[0]

                # 2. Total Returns Initiated
                cur.execute("SELECT COUNT(*) FROM analytics_events WHERE event_type = 'return_initiated'")
                total_returns = cur.fetchone()[0]

                # 3. Average Latency
                cur.execute("SELECT AVG(duration_ms) FROM analytics_events WHERE duration_ms IS NOT NULL")
                avg_latency = round(cur.fetchone()[0] or 0)

                # 4. Most Common Intent
                cur.execute("""
                    SELECT intent, COUNT(*) as count 
                    FROM analytics_events 
                    WHERE intent IS NOT NULL 
                    GROUP BY intent 
                    ORDER BY count DESC 
                    LIMIT 1
                """)
                top_intent_row = cur.fetchone()
                top_intent = top_intent_row[0] if top_intent_row else "N/A"

                return {
                    "total_tickets": total_tickets,
                    "total_returns": total_returns,
                    "avg_response_time_ms": avg_latency,
                    "most_common_intent": top_intent
                }
    except Exception as e:
        return {"error": "Could not retrieve analytics data."}