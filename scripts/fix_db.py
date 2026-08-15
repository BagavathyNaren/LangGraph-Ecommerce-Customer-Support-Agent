import os
from datetime import datetime, timedelta

from tools.db import get_connection


def fix_database():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Shift all dates forward to today + 5 days
                # This fixes Bug #1 (Dates in the past)
                new_date = (datetime.now() + timedelta(days=5)).date()
                cur.execute("UPDATE orders SET expected_delivery = %s", (new_date,))

                # 2. Sync order status with refunds table
                # If a refund exists for an order, that order should have status 'returned'
                # This fixes Bug #2 (Order ORD001 still showing as delivered)
                cur.execute("""
                    UPDATE orders
                    SET status = 'returned'
                    WHERE order_id IN (SELECT order_id FROM refunds)
                    AND status = 'delivered'
                """)

                conn.commit()
                print("Successfully updated database dates and synchronized order statuses.")
    except Exception as e:
        print(f"Error fixing database: {e}")


if __name__ == "__main__":
    import yaml

    # Load from env.yaml for local script execution
    try:
        with open("env.yaml") as f:
            env_vars = yaml.safe_load(f)
            for k, v in env_vars.items():
                os.environ[k] = str(v)
    except Exception:
        print("Could not load env.yaml")

    fix_database()
