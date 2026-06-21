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


def list_orders():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT o.order_id, o.customer_id, c.name, o.item, o.status
                FROM orders o
                JOIN customers c ON o.customer_id = c.customer_id
                ORDER BY o.order_id DESC LIMIT 20
            """)
            rows = cur.fetchall()
            print(f"Total orders fetched: {len(rows)}")
            for r in rows:
                s = repr(r).encode("ascii", "backslashreplace").decode("ascii")
                print(s)


if __name__ == "__main__":
    list_orders()
