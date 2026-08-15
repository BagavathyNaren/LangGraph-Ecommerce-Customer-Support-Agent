import random
import uuid
from datetime import datetime, timedelta
from domain.analytics import log_event
from domain.products.pricing import is_country_supported
from domain.products.search import search_products
from domain.rules import USER_FRIENDLY_DB_ERROR
from infra.db import get_connection
from infra.logger import get_logger
from infra.notifications import send_email, send_telegram

logger = get_logger("orders")

def get_order_status(order_id: str) -> dict:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT order_id, status, item, expected_delivery
                    FROM orders
                    WHERE order_id = %s
                """,
                    (order_id,),
                )
                row = cur.fetchone()
                if not row:
                    return {"status": "not_found", "order_id": order_id}
                result = {"order_id": row[0], "status": row[1], "item": row[2]}
                if row[1] not in ["cancelled", "returned", "delivered"]:
                    result["expected_delivery"] = str(row[3])
                return result
    except Exception as e:
        logger.error("DB error in get_order_status", extra={"event": "db_error", "error": str(e), "order_id": order_id})
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
                            subject=f"Order Cancelled: {order_id}",
                            body=f"Hi {name},\n\nYour order {order_id} has been successfully cancelled.",
                        )

                    if telegram_id:
                        send_telegram(chat_id=telegram_id, message=f"❌ Order Cancelled!\nOrder ID: {order_id}")

                conn.commit()
                return {"success": True, "message": f"Order {order_id} cancelled successfully."}
    except Exception as e:
        logger.error("DB error in cancel_order", extra={"event": "db_error", "error": str(e), "order_id": order_id})
        return {"error": USER_FRIENDLY_DB_ERROR}


def update_order_from_webhook(order_id: str, new_status: str, carrier: str = None) -> dict:
    """Updates order status via external webhook and sends proactive notifications."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status, item FROM orders WHERE order_id = %s", (order_id,))
                row = cur.fetchone()
                if not row:
                    return {"success": False, "message": f"Order {order_id} not found."}

                old_status = row[0]
                item_name = row[1]

                if old_status in ("cancelled", "returned"):
                    return {"success": False, "message": f"Order {order_id} is in terminal state ({old_status})."}

                cur.execute("UPDATE orders SET status = %s WHERE order_id = %s", (new_status, order_id))

                # Proactive Notification
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

                    carrier_text = f" via {carrier}" if carrier else ""

                    if new_status == "delivered":
                        subj = f"📦 Your order has been delivered! ({order_id})"
                        body = f"Hi {name},\n\nGreat news! Your {item_name} has been delivered{carrier_text}.\nEnjoy your purchase!"
                        tele_msg = f"📦 Delivered!\nYour {item_name} (Order {order_id}) has arrived."
                    else:
                        subj = f"🚚 Shipping Update: {order_id}"
                        body = f"Hi {name},\n\nYour {item_name} is now: {new_status.replace('_', ' ').title()}{carrier_text}."
                        tele_msg = f"🚚 Shipping Update!\nOrder {order_id} is now: {new_status}"

                    if email:
                        send_email(to_email=email, subject=subj, body=body)
                    if telegram_id:
                        send_telegram(chat_id=telegram_id, message=tele_msg)

                conn.commit()
                return {"success": True, "message": f"Order {order_id} updated to {new_status}."}
    except Exception as e:
        logger.error(
            "DB error in update_order_from_webhook", extra={"event": "db_error", "error": str(e), "order_id": order_id}
        )
        return {"error": USER_FRIENDLY_DB_ERROR}



def place_new_order(
    customer_name: str,
    item: str,
    customer_email: str = None,
    product_id: str = None,
    price: str = None,
    currency: str = None,
    source_website: str = None,
    category: str = "General",
) -> dict:
    """Place a new order for a customer."""
    import random
    import uuid
    from datetime import datetime, timedelta

    # Truncate item name at the very beginning to prevent VARCHAR(100) errors
    if item:
        item = item[:95]

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                row = None
                # 1. Exact Email Match (most robust, exact, immune to name duplicates)
                if customer_email:
                    cur.execute(
                        "SELECT customer_id, name, email, telegram_chat_id FROM customers WHERE LOWER(email) = LOWER(%s) LIMIT 1",
                        (customer_email,),
                    )
                    row = cur.fetchone()
                    if row:
                        cust_id, db_name, db_email, db_tg = row
                        db_name_clean = db_name.lower().strip()
                        curr_name_clean = customer_name.lower().strip()
                        if db_name_clean not in curr_name_clean and curr_name_clean not in db_name_clean:
                            return {
                                "success": False,
                                "message": f"ERROR: The email '{customer_email}' is already registered to customer '{db_name}'. You cannot place an order for '{customer_name}' using this email. Please ask the customer to provide their own unique email address.",
                            }

                # 2. Exact Name Match (fallback)
                if not row:
                    cur.execute(
                        "SELECT customer_id, name, email, telegram_chat_id FROM customers WHERE LOWER(name) = LOWER(%s) LIMIT 1",
                        (customer_name,),
                    )
                    row = cur.fetchone()

                # 3. Partial Match (last resort fallback)
                if not row:
                    cur.execute(
                        "SELECT customer_id, name, email, telegram_chat_id FROM customers WHERE name ILIKE %s OR email ILIKE %s LIMIT 1",
                        (f"%{customer_name}%", f"%{customer_name}%"),
                    )
                    row = cur.fetchone()

                if not row:
                    return {
                        "success": False,
                        "message": f"Customer '{customer_name}' not found. Please register an account first.",
                    }

                customer_id, real_name, email, telegram_chat_id = row
                # Ensure unique order ID
                while True:
                    order_id = f"ORD{random.randint(100, 9999)}"
                    cur.execute("SELECT order_id FROM orders WHERE order_id = %s", (order_id,))
                    if not cur.fetchone():
                        break

                tracking = f"TRK-{order_id}-{datetime.now().year}"
                delivery_date = (datetime.now() + timedelta(days=5)).date()

                price_float = None
                if product_id:
                    cur.execute("SELECT name, price, source_website FROM products WHERE product_id = %s", (product_id,))
                    prod_row = cur.fetchone()
                    if prod_row:
                        item = prod_row[0][:95]  # Overwrite item name with official product name
                        price_float = prod_row[1]
                        source_website = prod_row[2]
                    elif price and currency:
                        # Dynamic Product Insertion with pre-provided product_id (Fallback if not in catalog)
                        country = "Unknown"
                        try:
                            price_float = float(str(price).replace(",", "").replace("$", "").replace("₹", "").strip())
                        except ValueError:
                            price_float = 0.0

                        cur.execute(
                            """
                            INSERT INTO products (product_id, name, category, price, currency, country, source_website, in_stock)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, true)
                            ON CONFLICT (product_id) DO NOTHING
                        """,
                            (product_id, item, category, price_float, currency, country, source_website),
                        )
                        conn.commit()
                    else:
                        return {"success": False, "message": f"Product ID '{product_id}' not found."}
                elif price and currency:
                    # Dynamic Product Insertion
                    product_id = f"PRD-DYN-{uuid.uuid4().hex[:6].upper()}"
                    country = "Unknown"  # Default if not explicitly tracked here, but usually inferred from search
                    try:
                        price_float = float(str(price).replace(",", "").replace("$", "").replace("₹", "").strip())
                    except ValueError:
                        price_float = 0.0

                    cur.execute(
                        """
                        INSERT INTO products (product_id, name, category, price, currency, country, source_website, in_stock)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, true)
                        ON CONFLICT (product_id) DO NOTHING
                    """,
                        (product_id, item, category, price_float, currency, country, source_website),
                    )
                    conn.commit()
                price_str = price if price else (f"₹{price_float:,.2f}" if price_float else "Unknown")

                # ── Strict Order Validation Schema (CRITICAL) ──
                try:
                    from pydantic import BaseModel, Field

                    class OrderConfirmation(BaseModel):
                        order_id: str = Field(..., pattern=r"^ORD\d{3,10}$")
                        item: str = Field(..., min_length=1)
                        price: str = Field(..., min_length=1)
                        expected_delivery_date: str = Field(..., min_length=1)
                        tracking_id: str = Field(..., pattern=r"^TRK-ORD\d{3,10}-\d{4}$")

                    OrderConfirmation(
                        order_id=order_id,
                        item=item,
                        price=price_str,
                        expected_delivery_date=str(delivery_date),
                        tracking_id=tracking,
                    )
                    logger.info(
                        "Order confirmation successfully validated against strict schema",
                        extra={"event": "order_validated", "order_id": order_id},
                    )
                except Exception as schema_err:
                    logger.error(
                        f"Order validation schema check failed: {schema_err}",
                        extra={
                            "event": "order_validation_failed",
                            "order_id": order_id,
                            "item": item,
                            "price": price_str,
                            "tracking": tracking,
                        },
                    )
                    return {
                        "success": False,
                        "message": f"Order finalization aborted: schema validation failed. Error: {str(schema_err)}",
                    }

                cur.execute(
                    """
                    INSERT INTO orders (order_id, customer_id, item, status, expected_delivery, tracking_number, product_id, price, source_website)
                    VALUES (%s, %s, %s, 'processing', %s, %s, %s, %s, %s)
                """,
                    (order_id, customer_id, item, delivery_date, tracking, product_id, price_float, source_website),
                )
                conn.commit()

                # Send email and Telegram notification after placing order successfully
                try:
                    from infra.notifications import send_email, send_telegram

                    price_str = price if price else (f"₹{price_float:,.2f}" if price_float else "Unknown")
                    if email:
                        send_email(
                            to_email=email,
                            subject=f"Order Confirmed: {order_id}",
                            body=f"Hi {real_name},\n\nThank you for your purchase! Your order {order_id} for '{item}' has been placed successfully.\nPrice: {price_str}\nExpected delivery date: {delivery_date}.\nTracking number: {tracking}.",
                        )
                    if telegram_chat_id:
                        send_telegram(
                            chat_id=telegram_chat_id,
                            message=f"🛍️ Order Placed successfully!\nOrder ID: {order_id}\nItem: {item}\nPrice: {price_str}\nExpected delivery: {delivery_date}",
                        )
                except Exception as notify_err:
                    logger.error(f"Failed to send order notifications for {order_id}: {notify_err}")

                return {
                    "success": True,
                    "order_id": order_id,
                    "message": f"Order {order_id} for '{item}' has been placed successfully! Expected delivery: {delivery_date}. Tracking: {tracking}",
                }
    except Exception as e:
        logger.error(
            "DB error in place_new_order", extra={"event": "db_error", "error": str(e), "customer": customer_name}
        )
        return {"error": USER_FRIENDLY_DB_ERROR}

