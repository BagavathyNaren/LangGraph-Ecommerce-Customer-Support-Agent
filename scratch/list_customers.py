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


def list_customers():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT customer_id, name, email, country FROM customers")
            rows = cur.fetchall()
            print(f"Total customers: {len(rows)}")
            for r in rows:
                print(r)


if __name__ == "__main__":
    list_customers()
