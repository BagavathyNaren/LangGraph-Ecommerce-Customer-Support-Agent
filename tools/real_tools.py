import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from logger import get_logger
from tools.analytics import log_event
from tools.db import get_connection


def _create_retry_session(retries=3, backoff_factor=0.3, status_forcelist=(500, 502, 503, 504)):
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# Shared global HTTP session with connection pooling and automated backoff retry
_session = _create_retry_session()

logger = get_logger("tools")

USER_FRIENDLY_DB_ERROR = "We are experiencing high traffic, please try again in a few minutes."


def is_country_supported(country: str) -> bool:
    if not country:
        return False
    c = str(country).strip().lower()
    supported = {
        "uae",
        "united arab emirates",
        "emirates",
        "ae",
        "japan",
        "jp",
        "usa",
        "united states",
        "us",
        "uk",
        "united kingdom",
        "britain",
        "gb",
        "india",
        "in",
    }
    return c in supported


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
    import random
    import uuid

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
                    from tools.notifications import send_email, send_telegram

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
                    from tools.notifications import send_email, send_telegram

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
                    from tools.notifications import send_email, send_telegram

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


def get_customer_orders(customer_name: str) -> dict:
    """Look up a customer by name or email, return their profile and orders."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Search by name or email (case-insensitive partial match)
                # To prevent false positives where a name lookup (e.g. "Naren") matches an email substring
                # (e.g. "narencr0@gmail.com"), only query the email column if the search term looks like an email.
                if "@" in customer_name:
                    cur.execute(
                        """
                        SELECT c.customer_id, c.name, c.email, c.country,
                               o.order_id, o.status, o.item, o.expected_delivery, o.tracking_number
                        FROM customers c
                        LEFT JOIN orders o ON c.customer_id = o.customer_id
                        WHERE LOWER(c.email) = LOWER(%s)
                        ORDER BY o.expected_delivery DESC
                    """,
                        (customer_name.strip(),),
                    )
                else:
                    name_clean = customer_name.strip()
                    name_no_spaces = name_clean.replace(" ", "")
                    # First try exact match (case-insensitive) to avoid matching 'AlexTestXXXXX' when searching for 'Alex'
                    cur.execute(
                        """
                        SELECT c.customer_id, c.name, c.email, c.country,
                               o.order_id, o.status, o.item, o.expected_delivery, o.tracking_number
                        FROM customers c
                        LEFT JOIN orders o ON c.customer_id = o.customer_id
                        WHERE LOWER(c.name) = LOWER(%s) OR LOWER(c.name) = LOWER(%s)
                        ORDER BY o.expected_delivery DESC
                    """,
                        (name_clean, name_no_spaces),
                    )
                    rows = cur.fetchall()

                    if not rows:
                        # Fall back to case-insensitive partial match
                        cur.execute(
                            """
                            SELECT c.customer_id, c.name, c.email, c.country,
                                   o.order_id, o.status, o.item, o.expected_delivery, o.tracking_number
                            FROM customers c
                            LEFT JOIN orders o ON c.customer_id = o.customer_id
                            WHERE c.name ILIKE %s OR c.name ILIKE %s
                            ORDER BY o.expected_delivery DESC
                        """,
                            (f"%{name_clean}%", f"%{name_no_spaces}%"),
                        )
                        rows = cur.fetchall()
                if not rows:
                    return {"status": "not_found", "query": customer_name}

                # Rows mapping: 0=customer_id, 1=name, 2=email, 3=country, 4=order_id, 5=status, 6=item, 7=expected_delivery, 8=tracking_number
                customer = {"customer_id": rows[0][0], "name": rows[0][1], "email": rows[0][2], "country": rows[0][3]}
                orders = []
                for row in rows:
                    if row[4]:  # order_id exists
                        orders.append(
                            {
                                "order_id": row[4],
                                "status": row[5],
                                "item": row[6],
                                "expected_delivery": str(row[7]),
                                "tracking_number": row[8],
                            }
                        )
                return {"customer": customer, "orders": orders}
    except Exception as e:
        logger.error(
            "DB error in get_customer_orders", extra={"event": "db_error", "error": str(e), "query": customer_name}
        )
        return {"error": USER_FRIENDLY_DB_ERROR}


def register_new_customer(name: str, email: str, phone_number: str = None, country: str = "India") -> dict:
    """Register a new customer in the database."""
    if not is_country_supported(country):
        return {
            "success": False,
            "message": f"We only support registration, ordering, and product searches for UAE, Japan, US, UK, and India. Unfortunately, '{country}' is not supported.",
        }
    import uuid

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Validate email format strictly
                import re

                if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email) or len(email) < 6:
                    return {
                        "success": False,
                        "message": "Invalid email address format. Please provide a fully valid email address.",
                    }

                # Check if email already exists
                cur.execute("SELECT customer_id FROM customers WHERE email = %s", (email,))
                if cur.fetchone():
                    return {"success": False, "message": f"An account with email {email} already exists."}

                customer_id = f"CUST-{uuid.uuid4().hex[:6].upper()}"

                cur.execute(
                    """
                    INSERT INTO customers (customer_id, name, email, phone_number, country)
                    VALUES (%s, %s, %s, %s, %s)
                """,
                    (customer_id, name, email, phone_number, country),
                )
                conn.commit()

                # Send email notification after successful registration
                if email:
                    try:
                        from tools.notifications import send_email

                        send_email(
                            to_email=email,
                            subject="Welcome to Our Store!",
                            body=f"Hi {name},\n\nWelcome! Your customer account has been created successfully.\nYour Customer ID is {customer_id}.\n\nThank you for choosing us!",
                        )
                    except Exception as email_err:
                        logger.error(f"Failed to send welcome email to {email}: {email_err}")

                contact = f"email '{email}'"
                if phone_number:
                    contact += f" and phone '{phone_number}'"

                return {
                    "success": True,
                    "customer_id": customer_id,
                    "phone_number": phone_number,
                    "message": f"Customer '{name}' successfully registered with {contact}.",
                }
    except Exception as e:
        logger.error("DB error in register_new_customer", extra={"event": "db_error", "error": str(e), "email": email})
        return {"error": USER_FRIENDLY_DB_ERROR}


def search_products(query: str, country: str = "India") -> dict:
    """Search the product catalog for available products. Use this BEFORE placing an order so the customer can choose an option."""
    if not is_country_supported(country):
        return {
            "success": False,
            "message": f"We only support ordering and product searches for UAE, Japan, US, UK, and India. Unfortunately, '{country}' is not supported.",
        }
    if not country or str(country).strip().lower() in ["unknown", "none", ""]:
        country = "India"
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Basic search by matching name or category
                search_term = "%" + "%".join(query.split()) + "%"
                cur.execute(
                    """
                    SELECT product_id, name, price, currency, source_website
                    FROM products
                    WHERE (name ILIKE %s OR category ILIKE %s)
                      AND country ILIKE %s AND in_stock = true
                    ORDER BY price ASC
                    LIMIT 5
                """,
                    (search_term, search_term, country),
                )

                rows = cur.fetchall()
                if not rows:
                    return {"success": False, "message": f"No products found matching '{query}' in {country}."}

                products = []
                for row in rows:
                    products.append(
                        {"product_id": row[0], "name": row[1], "price": f"{row[3]} {row[2]:.2f}", "source": row[4]}
                    )
                return {"success": True, "country": country, "products": products}
    except Exception as e:
        logger.error("DB error in search_products", extra={"event": "db_error", "error": str(e), "query": query})
        return {"error": USER_FRIENDLY_DB_ERROR}


def extract_price_from_text(text: str, default_currency: str = "INR") -> str:
    """Helper to extract estimated price in various currencies from title or snippet."""
    import re

    # Clean text to remove common numeric specs to avoid false matches (e.g. 200 MP, 512 GB)
    cleaned = re.sub(
        r"\b\d+\s*(?:MP|GB|RAM|Hz|W|mAh|cm|inch|inches|fps|GB|TB|Gen\s*\d|Core\s*i\d|Ryzen\s*\d)\b",
        "",
        text,
        flags=re.IGNORECASE,
    )

    def is_subscription_or_protection(match_start, match_end, full_text):
        # Look at the context after the match
        after = full_text[match_end:].strip().lower()
        if re.match(r"^(?:\/|per\s+|a\s+)?(?:month|mo|year|yr|week|wk|day|annum)\b", after):
            return True
        # Also check if it's part of a protection plan phrase
        before = full_text[:match_start].lower()
        if any(keyword in before for keyword in ["protect", "protection", "warranty", "insurance"]):
            return True
        return False

    # 1. Try finding INR rupee sign and digit
    for m in re.finditer(r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d{2})?)", cleaned, flags=re.IGNORECASE):
        if not is_subscription_or_protection(m.start(), m.end(), cleaned):
            return f"₹{m.group(1)}"

    # 2. Try finding dollar sign
    for m in re.finditer(r"(?:\$|USD)\s*([\d,]+(?:\.\d{2})?)", cleaned, flags=re.IGNORECASE):
        if not is_subscription_or_protection(m.start(), m.end(), cleaned):
            return f"${m.group(1)}"

    # 3. Try finding Euro sign
    for m in re.finditer(r"(?:€|EUR)\s*([\d,]+(?:\.\d{2})?)", cleaned, flags=re.IGNORECASE):
        if not is_subscription_or_protection(m.start(), m.end(), cleaned):
            return f"€{m.group(1)}"

    # 4. Try finding GBP sign
    for m in re.finditer(r"(?:£|GBP)\s*([\d,]+(?:\.\d{2})?)", cleaned, flags=re.IGNORECASE):
        if not is_subscription_or_protection(m.start(), m.end(), cleaned):
            return f"£{m.group(1)}"

    # 5. Try finding JPY/CNY Yen/Yuan sign — return proper currency symbols, not ISO codes
    for m in re.finditer(r"(?:¥|￥|JPY|CNY)\s*([\d,]+(?:\.\d{2})?)", cleaned, flags=re.IGNORECASE):
        if not is_subscription_or_protection(m.start(), m.end(), cleaned):
            curr = default_currency if default_currency in ["JPY", "CNY"] else "JPY"
            symbol = "￥" if curr == "JPY" else "¥"  # Full-width ￥ for JPY, half-width ¥ for CNY
            return f"{symbol}{m.group(1)}"

    # 5b. Try finding AED/Dirham sign
    for m in re.finditer(r"(?:AED|د\.إ)\s*([\d,]+(?:\.\d{2})?)", cleaned, flags=re.IGNORECASE):
        if not is_subscription_or_protection(m.start(), m.end(), cleaned):
            return f"AED {m.group(1)}"

    # 6. Generic number with price context (e.g. "price: 499", "cost 500")
    # Map ISO codes to symbols for the generic fallback
    _CURRENCY_SYMBOL_MAP = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "￥", "CNY": "¥", "AED": "AED "}
    for m in re.finditer(
        r"\b(?:price|cost|rate|sale|buy|at)\s*[:=-]?\s*([1-9]\d{1,}(?:,\d{3})*(?:\.\d{2})?)\b",
        cleaned,
        flags=re.IGNORECASE,
    ):
        if not is_subscription_or_protection(m.start(), m.end(), cleaned):
            sym = _CURRENCY_SYMBOL_MAP.get(default_currency.upper(), default_currency + " ")
            return f"{sym}{m.group(1)}"

    return "Unknown"


def clean_title_for_search(title: str) -> str:
    """Helper to strip site prefix and suffix metadata for highly accurate search queries."""
    import re

    cleaned = title
    # Remove common prefix patterns (e.g. "Amazon.com: ", "亚马逊海外购：")
    cleaned = re.sub(
        r"^(?:Amazon\.(?:com|in|co\.jp|cn)|Amazon|Flipkart|Croma|亚马逊海外购|亚马逊)\s*[:|：|-]\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Remove common suffix patterns (e.g. " : Everything Else - Amazon.com", " - Croma")
    cleaned = re.sub(
        r"\s*[:|：|-]\s*(?:Amazon\.(?:com|in|co\.jp|cn)|Amazon|Flipkart|Croma|亚马逊海外购|亚马逊|Video Games|Electronics|Everything Else|Home Audio|Mobile Phones|Smartphones).*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Clean non-alphanumeric chars (like ®, ™) to keep search simple
    cleaned = re.sub(r"[®™]", "", cleaned)
    return cleaned.strip()


def get_shopping_price_fallback(title: str, currency: str = "USD", gl: str = "us", hl: str = "en") -> str:
    """Fallback helper to query Google Shopping broadly for a specific product title
    to retrieve a realistic price if organic search returned 'Unknown'."""
    import re

    serper_key = os.getenv("SERPER_API_KEY")
    if not serper_key:
        return "Unknown"

    try:
        # Clean title to remove SEO prefixes/suffixes
        cleaned_title = clean_title_for_search(title)

        url = "https://google.serper.dev/shopping"
        headers = {"X-API-KEY": serper_key, "Content-Type": "application/json"}
        # Use first 6 words of the cleaned title for broad matching
        words = [w for w in re.findall(r"\w+", cleaned_title) if len(w) > 1]
        search_q = " ".join(words[:6])

        payload = {"q": search_q, "num": 3, "gl": gl, "hl": hl}
        r = _session.post(url, json=payload, headers=headers, timeout=5)
        if r.status_code == 200:
            res_json = r.json()
            shopping_results = res_json.get("shopping", [])
            if shopping_results:
                for item in shopping_results:
                    raw_price = item.get("price", "")
                    if raw_price:
                        price = extract_price_from_text(raw_price, default_currency=currency)
                        if price != "Unknown":
                            return price
    except Exception as e:
        logger.error(f"Shopping price fallback failed for title '{title}': {e}")
    return "Unknown"


def fetch_retailer_data(platform: str, query: str, country: str = "India") -> dict:
    """Unified search routing logic using premium Web Search APIs (Tavily, Serper, or Google CSE)
    instead of Apify, as a robust and high-speed alternative."""
    if not is_country_supported(country):
        return {
            "success": False,
            "message": f"We only support ordering and product searches for UAE, Japan, US, UK, and India. Unfortunately, '{country}' is not supported.",
        }
    import re
    import urllib.parse

    platform = platform.lower().strip()
    country_clean = str(country).strip().lower() if country else "india"

    # Dynamic region maps for multi-country support
    amazon_domain = "amazon.in"
    gl = "in"
    hl = "en"

    if "usa" in country_clean or "united states" in country_clean or country_clean == "us":
        amazon_domain = "amazon.com"
        gl = "us"
        hl = "en"
        currency = "USD"
    elif "japan" in country_clean or country_clean == "jp":
        amazon_domain = "amazon.co.jp"
        gl = "jp"
        hl = "ja"
        currency = "JPY"
    elif (
        "uk" in country_clean
        or "united kingdom" in country_clean
        or "britain" in country_clean
        or country_clean == "gb"
    ):
        amazon_domain = "amazon.co.uk"
        gl = "gb"
        hl = "en"
        currency = "GBP"
    elif (
        "uae" in country_clean
        or "united arab emirates" in country_clean
        or "emirates" in country_clean
        or country_clean == "ae"
    ):
        amazon_domain = "amazon.ae"
        gl = "ae"
        hl = "en"
        currency = "AED"
    elif "india" in country_clean or country_clean == "in":
        amazon_domain = "amazon.in"
        gl = "in"
        hl = "en"
        currency = "INR"
    else:
        currency = "USD"  # default for unknown non-India regions

    # Map platform names to their primary domains
    domain_map = {"amazon": amazon_domain, "flipkart": "flipkart.com", "croma": "croma.com"}
    domain = domain_map.get(platform, amazon_domain)
    platform_name = platform.capitalize()

    # Block Indian-only platforms for non-India countries
    is_india = "india" in country_clean or country_clean == "in" or country_clean == "unknown" or country_clean == ""
    if platform in ["flipkart", "croma"] and not is_india:
        return {
            "success": False,
            "message": f"{platform_name} is only available in India. Please use Amazon for {country}.",
        }

    # Generic storefront titles that indicate a useless result (not a real product listing)
    GENERIC_TITLES = {
        "amazon",
        "amazon.co.jp",
        "amazon.in",
        "amazon.com",
        "amazon.co.uk",
        "amazon.ae",
        "amazon global store",
        "amazon international",
        "flipkart",
        "croma",
        "flipkart.com",
        "croma.com",
    }

    def is_generic_result(title: str) -> bool:
        """Return True if the title is a generic storefront name rather than a real product."""
        if not title:
            return True
        t = title.strip().lower()
        return t in GENERIC_TITLES or t in {g.lower() for g in GENERIC_TITLES}

    def is_valid_price(price: str) -> bool:
        """Return False for prices that are Unknown, Not listed, or ¥0 / $0 (garbage data)."""
        if not price:
            return False
        p_clean = price.strip().lower()
        if p_clean in [
            "unknown",
            "not listed",
            "not_listed",
            "n/a",
            "tbd",
            "none",
            "null",
            "not available",
            "not_available",
        ]:
            return False
        if "not listed" in p_clean or "unknown" in p_clean or "not available" in p_clean or "n/a" in p_clean:
            return False
        # Remove currency symbols and check if numeric value is > 0
        import re as _re_inner

        digits = _re_inner.sub(r"[^\d.]", "", price)
        if not digits:
            return False
        try:
            return float(digits) > 0
        except (ValueError, TypeError):
            # If there are digits but we can't parse a float (e.g. range like "40-50"), keep it
            return True

    # 0. Try SERPER GOOGLE SHOPPING SEARCH (Alternative 1 - Premium Live Prices)
    serper_key = os.getenv("SERPER_API_KEY")
    if serper_key:
        try:
            url = "https://google.serper.dev/shopping"
            headers = {"X-API-KEY": serper_key, "Content-Type": "application/json"}
            # Search strictly for this retailer domain in Google Shopping
            search_query = f"site:{domain} {query}"
            payload = {"q": search_query, "num": 5, "gl": gl, "hl": hl}
            r = _session.post(url, json=payload, headers=headers, timeout=10)
            r.raise_for_status()
            res_json = r.json()
            shopping_results = res_json.get("shopping", [])

            # Fallback: if querying with "site:domain" returns nothing, try querying the retailer name directly
            if not shopping_results:
                search_query_alt = f"{platform_name} {query}"
                payload = {"q": search_query_alt, "num": 5, "gl": gl, "hl": hl}
                r = _session.post(url, json=payload, headers=headers, timeout=10)
                r.raise_for_status()
                res_json = r.json()
                shopping_results = [
                    item
                    for item in res_json.get("shopping", [])
                    if platform.lower() in item.get("source", "").lower() or domain in item.get("link", "").lower()
                ]

            results = []
            for item in shopping_results:
                title = item.get("title", "")
                url_link = item.get("link", "")
                raw_price = item.get("price", "")

                # Skip generic storefront titles (not real products)
                if is_generic_result(title):
                    continue

                # Standarize price format via extraction helper
                price = extract_price_from_text(raw_price, default_currency=currency) if raw_price else "Unknown"
                if price == "Unknown" and raw_price:
                    price = raw_price

                # Skip zero-price garbage results
                if not is_valid_price(price):
                    continue

                results.append(
                    {"title": title, "estimated_price": price, "source": url_link, "platform": platform_name}
                )

            if results:
                logger.info(f"Successfully retrieved structured live shopping prices from Serper for {platform_name}")
                return {"success": True, "platform": platform_name, "results": results}
        except Exception as e:
            logger.error(f"Serper Shopping API failed for {platform}: {e}", exc_info=True)

    # 1. Try TAVILY SEARCH (Recommended)
    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key:
        try:
            url = "https://api.tavily.com/search"
            search_query = f"site:{domain} {query}"
            payload = {"api_key": tavily_key, "query": search_query, "max_results": 5, "include_domains": [domain]}
            r = _session.post(url, json=payload, timeout=10)
            r.raise_for_status()
            tavily_results = r.json().get("results", [])

            results = []
            for item in tavily_results:
                title = item.get("title", "")
                url_link = item.get("url", "")
                snippet = item.get("content", "")

                # Skip generic storefront titles (not real products)
                if is_generic_result(title):
                    continue

                # Extract price if present in title or snippet
                price = extract_price_from_text(title + " " + snippet, default_currency=currency)
                if price == "Unknown":
                    price = get_shopping_price_fallback(title, currency=currency, gl=gl, hl=hl)

                # Filter out unknown or zero prices
                if not is_valid_price(price):
                    continue

                results.append(
                    {"title": title, "estimated_price": price, "source": url_link, "platform": platform_name}
                )
            if results:
                return {"success": True, "platform": platform_name, "results": results}
        except Exception as e:
            logger.error(f"Tavily search failed for {platform}: {e}")

    # 2. Try SERPER GOOGLE SEARCH
    serper_key = os.getenv("SERPER_API_KEY")
    if serper_key:
        try:
            url = "https://google.serper.dev/search"
            headers = {"X-API-KEY": serper_key, "Content-Type": "application/json"}
            search_query = f"site:{domain} {query}"
            payload = {"q": search_query, "num": 5}
            r = _session.post(url, json=payload, headers=headers, timeout=10)
            r.raise_for_status()
            serper_results = r.json().get("organic", [])

            results = []
            for item in serper_results:
                title = item.get("title", "")
                url_link = item.get("link", "")
                snippet = item.get("snippet", "")

                # Skip generic storefront titles (not real products)
                if is_generic_result(title):
                    continue

                # Extract price if present in title or snippet
                price = extract_price_from_text(title + " " + snippet, default_currency=currency)
                if price == "Unknown":
                    price = get_shopping_price_fallback(title, currency=currency, gl=gl, hl=hl)

                # Filter out unknown or zero prices
                if not is_valid_price(price):
                    continue

                results.append(
                    {"title": title, "estimated_price": price, "source": url_link, "platform": platform_name}
                )
            if results:
                return {"success": True, "platform": platform_name, "results": results}
        except Exception as e:
            logger.error(f"Serper search failed for {platform}: {e}")

    # 3. Try GOOGLE CUSTOM SEARCH ENGINE (CSE)
    google_key = os.getenv("GOOGLE_API_KEY")
    google_cx = os.getenv("GOOGLE_CSE_ID")
    if google_key and google_cx:
        try:
            search_query = f"site:{domain} {query}"
            url = f"https://www.googleapis.com/customsearch/v1?key={google_key}&cx={google_cx}&q={urllib.parse.quote(search_query)}"
            r = _session.get(url, timeout=10)
            r.raise_for_status()
            google_results = r.json().get("items", [])

            results = []
            for item in google_results:
                title = item.get("title", "")
                url_link = item.get("link", "")
                snippet = item.get("snippet", "")

                # Extract price if present in title or snippet
                price = extract_price_from_text(title + " " + snippet, default_currency=currency)
                if price == "Unknown":
                    price = get_shopping_price_fallback(title, currency=currency, gl=gl, hl=hl)

                # Filter out unknown or zero prices
                if not is_valid_price(price):
                    continue

                results.append(
                    {"title": title, "estimated_price": price, "source": url_link, "platform": platform_name}
                )
            if results:
                return {"success": True, "platform": platform_name, "results": results}
        except Exception as e:
            logger.error(f"Google CSE failed for {platform}: {e}")

    # 4. KEYLESS DUCKDUCKGO WEB SCRAPER FALLBACK
    try:
        # DDG Lite search fallback
        url = "https://lite.duckduckgo.com/lite/"
        search_query = f"site:{domain} {query}"
        r = _session.post(url, headers={"User-Agent": "Mozilla/5.0"}, data={"q": search_query}, timeout=10)

        # If DDG lite returns 200/202, parse links using regex
        html = r.text
        pattern = r'<a href="([^"]+)"[^>]*class="result-link"[^>]*>(.*?)</a>'
        matches = re.findall(pattern, html, re.DOTALL)

        if not matches:
            pattern_alt = r'<a href="(https?://[^"]+)"[^>]*>(.*?)</a>'
            matches = re.findall(pattern_alt, html)

        results = []
        for href, title in matches:
            title_clean = re.sub(r"<[^>]+>", "", title).strip()
            if "//duckduckgo.com/l/?uddg=" in href:
                actual_url_encoded = href.split("//duckduckgo.com/l/?uddg=")[1].split("&")[0]
                href = urllib.parse.unquote(actual_url_encoded)
            elif href.startswith("//"):
                href = "https:" + href

            if domain in href and "google" not in href and "duckduckgo" not in href:
                price = extract_price_from_text(title_clean, default_currency=currency)
                if price == "Unknown":
                    price = get_shopping_price_fallback(title_clean, currency=currency, gl=gl, hl=hl)

                # Filter out unknown or zero prices
                if not is_valid_price(price):
                    continue

                results.append(
                    {"title": title_clean, "estimated_price": price, "source": href, "platform": platform_name}
                )

        if results:
            return {"success": True, "platform": platform_name, "results": results[:5]}

    except Exception as e:
        logger.error(f"DDG fallback failed for {platform}: {e}")

    # 5. NO-KEY STATIC DB CATALOG MATCH FALLBACK
    # If all online search fails or keys are missing, search local DB products
    try:
        from tools.real_tools import search_products

        db_res = search_products(query, country)
        if db_res.get("success"):
            results = []
            for p in db_res.get("products", []):
                prod_title = p.get("title", "")
                prod_price = p.get("price", "Unknown")
                prod_source = p.get("source", "https://amazon.in")
                results.append(
                    {
                        "title": prod_title,
                        "estimated_price": prod_price,
                        "source": prod_source,
                        "platform": platform_name,
                    }
                )
            if results:
                return {"success": True, "platform": platform_name, "results": results[:3]}
    except Exception as e:
        logger.error(f"Catalog fallback failed for {platform}: {e}")

    return {"error": f"Search limit exceeded or key not found for {platform_name}."}


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
                    from tools.notifications import send_email, send_telegram

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


def search_knowledge_base(query: str) -> dict:
    return {
        "answer": f"Based on our policy regarding '{query}': please allow 5-7 business days for processing. Contact support for urgent cases."
    }


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
                        if customer_name:
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
                        from tools.notifications import send_email, send_telegram

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
                }
    except Exception as e:
        logger.error(
            "DB error in create_support_ticket", extra={"event": "db_error", "error": str(e), "ticket_id": ticket_id}
        )
        return {
            "success": False,
            "message": "We experienced an issue creating your ticket, but an agent has been notified.",
        }


def get_analytics_summary() -> dict:
    """Fetch a summary of business analytics from the database."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Count directly from support_tickets table (source of truth)
                cur.execute("SELECT COUNT(*) FROM support_tickets")
                total_tickets = int(cur.fetchone()[0] or 0)

                # 2. Count directly from refunds table (source of truth)
                cur.execute("SELECT COUNT(*) FROM refunds")
                total_returns = int(cur.fetchone()[0] or 0)

                # 3. Average Latency from analytics_events
                cur.execute("SELECT AVG(duration_ms) FROM analytics_events WHERE duration_ms IS NOT NULL")
                avg_latency_raw = cur.fetchone()[0]
                avg_latency = round(float(avg_latency_raw)) if avg_latency_raw is not None else 0

                # 4. Most Common Intent from analytics_events
                cur.execute("""
                    SELECT intent, COUNT(*) as count
                    FROM analytics_events
                    WHERE intent IS NOT NULL
                    GROUP BY intent
                    ORDER BY count DESC
                    LIMIT 1
                """)
                top_intent_row = cur.fetchone()
                top_intent = str(top_intent_row[0]) if top_intent_row else "N/A"

                return {
                    "total_tickets": total_tickets,
                    "total_returns": total_returns,
                    "avg_response_time_ms": avg_latency,
                    "most_common_intent": top_intent,
                }
    except Exception as e:
        logger.error(f"Analytics query failed: {e}")
        return {"error": "Could not retrieve analytics data."}
