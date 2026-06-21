import os

import yaml

from tools.db import get_connection


def clean_test_users():
    names = ["Chan", "Mumtaj", "Joseph Vijay"]
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Find customer IDs for these names
                for name in names:
                    cur.execute("SELECT customer_id FROM customers WHERE name ILIKE %s", (f"%{name}%",))
                    cust_ids = [row[0] for row in cur.fetchall()]
                    if cust_ids:
                        print(f"Found customer IDs for {name}: {cust_ids}")
                        for cust_id in cust_ids:
                            # Delete support tickets
                            cur.execute("DELETE FROM support_tickets WHERE customer_id = %s", (cust_id,))
                            # Delete refunds
                            cur.execute(
                                "DELETE FROM refunds WHERE order_id IN (SELECT order_id FROM orders WHERE customer_id = %s)",
                                (cust_id,),
                            )
                            # Delete orders
                            cur.execute("DELETE FROM orders WHERE customer_id = %s", (cust_id,))
                            # Delete customers
                            cur.execute("DELETE FROM customers WHERE customer_id = %s", (cust_id,))
                        print(f"Cleaned up records for {name}.")
                    else:
                        print(f"No records found for {name}.")
                conn.commit()
                print("All requested test users cleaned up successfully.")
    except Exception as e:
        print(f"Error cleaning database: {e}")


if __name__ == "__main__":
    # Load env from env.yaml
    try:
        with open("env.yaml") as f:
            env_vars = yaml.safe_load(f)
            for k, v in env_vars.items():
                os.environ[k] = str(v)
    except Exception:
        print("Could not load env.yaml")

    clean_test_users()
