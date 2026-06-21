import os

import yaml

from tools.db import get_connection


def check_customers():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT customer_id, name, email, country FROM customers")
                rows = cur.fetchall()
                print("Registered Customers:")
                for r in rows:
                    print(r)

                cur.execute("SELECT order_id, customer_id, item, price, source_website FROM orders")
                orows = cur.fetchall()
                print("\nPlaced Orders:")
                for o in orows:
                    print(o)
    except Exception as e:
        print("Error checking customers:", e)


if __name__ == "__main__":
    try:
        with open("env.yaml") as f:
            env_vars = yaml.safe_load(f)
            for k, v in env_vars.items():
                os.environ[k] = str(v)
    except Exception:
        pass
    check_customers()
