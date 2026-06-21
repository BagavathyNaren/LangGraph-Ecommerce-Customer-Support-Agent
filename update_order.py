import os

import psycopg

# Uses GCP Postgres (e2-micro) connection string from environment variable
db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:my-agentic-lab@35.209.170.21:5432/postgres")
try:
    conn = psycopg.connect(db_url)
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status = 'delivered' WHERE order_id = 'ORD2984'")
    conn.commit()
    print("SUCCESS: Order ORD2984 is now DELIVERED.")
    cur.close()
    conn.close()
except Exception as e:
    print(f"FAILED: {e}")
