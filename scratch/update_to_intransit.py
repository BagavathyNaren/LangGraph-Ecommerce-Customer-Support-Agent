import os
import sys

import yaml

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.db import get_connection


def update():
    try:
        with open("env.yaml") as f:
            env_vars = yaml.safe_load(f)
            for k, v in env_vars.items():
                os.environ[k] = str(v)
    except Exception:
        print("Could not load env.yaml")

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Update ORD1061 and ORD3216 to in_transit
                cur.execute("UPDATE orders SET status = 'in_transit' WHERE order_id IN ('ORD1061', 'ORD3216')")
                conn.commit()
                print("SUCCESS: Updated ORD1061 and ORD3216 to 'in_transit' status in the database!")
    except Exception as e:
        print(f"FAILED: {e}")


if __name__ == "__main__":
    update()
