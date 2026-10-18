from domain.products.pricing import is_country_supported
from domain.rules import USER_FRIENDLY_DB_ERROR
from infra.db import get_connection
from infra.logger import get_logger

logger = get_logger("customers")

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
                        from infra.notifications import send_email

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

