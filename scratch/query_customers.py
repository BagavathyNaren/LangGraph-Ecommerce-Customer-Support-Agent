import os
import sys

import yaml

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.db import get_connection


def query():
    try:
        with open("env.yaml") as f:
            env_vars = yaml.safe_load(f)
            for k, v in env_vars.items():
                os.environ[k] = str(v)
    except Exception:
        print("Could not load env.yaml")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT customer_id, name, email, country FROM customers")
            rows = cur.fetchall()
            print("CUSTOMERS:")
            for r in rows:
                print(r)


if __name__ == "__main__":
    query()
