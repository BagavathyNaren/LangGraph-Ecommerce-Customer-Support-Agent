import os
import sys

import yaml

# Add parent directory to path to load tools
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load from env.yaml for local script execution
try:
    with open("env.yaml") as f:
        env_vars = yaml.safe_load(f)
        for k, v in env_vars.items():
            os.environ[k] = str(v)
except Exception:
    print("Could not load env.yaml")

from tools.db import get_connection


def cleanup_test_customers():
    test_names = [
        "Ken",
        "Fatima",
        "George",
        "moorthy",
        "Moorthy",
        "Shiro",
        "Aafrin",
        "Michael",
        "Chan",
        "Juhi",
        "Mumtaj",
        "Joseph Vijay",
        "Joseph",
    ]
    with get_connection() as conn:
        with conn.cursor() as cur:
            for name in test_names:
                print(f"=== Cleaning up '{name}' ===")
                cur.execute("SELECT customer_id FROM customers WHERE LOWER(name) = LOWER(%s)", (name,))
                rows = cur.fetchall()
                cust_ids = [r[0] for r in rows]
                if cust_ids:
                    print(f"Found customer IDs for {name}: {cust_ids}")
                    for cust_id in cust_ids:
                        cur.execute("DELETE FROM support_tickets WHERE customer_id = %s", (cust_id,))
                        cur.execute(
                            "DELETE FROM refunds WHERE order_id IN (SELECT order_id FROM orders WHERE customer_id = %s)",
                            (cust_id,),
                        )
                        cur.execute("DELETE FROM orders WHERE customer_id = %s", (cust_id,))
                        cur.execute("DELETE FROM customers WHERE customer_id = %s", (cust_id,))
                    print(f"Cleaned up '{name}' successfully.")
                else:
                    print(f"No customer found with name '{name}'.")
            conn.commit()


if __name__ == "__main__":
    cleanup_test_customers()
