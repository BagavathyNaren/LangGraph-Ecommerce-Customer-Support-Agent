import os
import sys

import yaml

from tools.db import get_connection

sys.stdout.reconfigure(encoding="utf-8")


def find_details():
    order_ids = ["ORD4904", "ORD7442"]
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                for oid in order_ids:
                    print(f"--- Searching details for {oid} ---")
                    cur.execute(
                        """
                        SELECT o.order_id, o.customer_id, o.item, o.status, o.expected_delivery, o.tracking_number, o.product_id, o.price, o.source_website
                        FROM orders o
                        WHERE o.order_id = %s
                    """,
                        (oid,),
                    )
                    row = cur.fetchone()
                    if row:
                        print("Order columns:")
                        print(row)
                        cust_id = row[1]
                        cur.execute(
                            "SELECT customer_id, name, email, phone_number, country FROM customers WHERE customer_id = %s",
                            (cust_id,),
                        )
                        crow = cur.fetchone()
                        print("Associated Customer:")
                        print(crow)
                    else:
                        print("Not found in orders table.")
    except Exception as e:
        print("Error:", e)


if __name__ == "__main__":
    try:
        with open("env.yaml") as f:
            env_vars = yaml.safe_load(f)
            for k, v in env_vars.items():
                os.environ[k] = str(v)
    except Exception:
        pass
    find_details()
