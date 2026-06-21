import os
import sys

from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))
load_dotenv()

from tools.db import get_connection


def cleanup_alextest():
    print("=== Cleaning up AlexTest customers and their orders/tickets from DB ===")
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Find all customer IDs whose name starts with Alex or AlexTest
                cur.execute("SELECT customer_id, name FROM customers WHERE name ILIKE 'Alex%'")
                rows = cur.fetchall()
                if rows:
                    print(f"Found {len(rows)} AlexTest customers.")
                    for cust_id, name in rows:
                        print(f"Deleting customer {name} (ID: {cust_id})...")
                        cur.execute("DELETE FROM support_tickets WHERE customer_id = %s", (cust_id,))
                        cur.execute(
                            "DELETE FROM refunds WHERE order_id IN (SELECT order_id FROM orders WHERE customer_id = %s)",
                            (cust_id,),
                        )
                        cur.execute("DELETE FROM orders WHERE customer_id = %s", (cust_id,))
                        cur.execute("DELETE FROM customers WHERE customer_id = %s", (cust_id,))
                    conn.commit()
                    print("Cleanup finished successfully.")
                else:
                    print("No AlexTest customers found.")
    except Exception as e:
        print(f"Database cleanup failed: {e}")


if __name__ == "__main__":
    cleanup_alextest()
