import os
import sys

import yaml

from tools.db import get_connection

# Force stdout to be utf-8 just in case
sys.stdout.reconfigure(encoding="utf-8")


def check_orders():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT o.order_id, o.customer_id, c.name, c.email, o.item, o.price, o.source_website
                    FROM orders o
                    JOIN customers c ON o.customer_id = c.customer_id
                    ORDER BY o.order_id DESC
                    LIMIT 5
                """)
                rows = cur.fetchall()
                print("Recent Orders (joined with customers):")
                for r in rows:
                    print(r)
    except Exception as e:
        print("Error checking orders:", e)


if __name__ == "__main__":
    try:
        with open("env.yaml") as f:
            env_vars = yaml.safe_load(f)
            for k, v in env_vars.items():
                os.environ[k] = str(v)
    except Exception:
        pass
    check_orders()
