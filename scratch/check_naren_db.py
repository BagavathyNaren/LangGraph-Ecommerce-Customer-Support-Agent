import os
import sys

from dotenv import load_dotenv

# Add parent directory to path to load tools
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load env
load_dotenv()

from tools.real_tools import get_connection


def check_db():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                print("=== Checking Customer 'Info Naren' ===")
                cur.execute(
                    "SELECT customer_id, name, email, country FROM customers WHERE name ILIKE %s", ("%info naren%",)
                )
                rows = cur.fetchall()
                for r in rows:
                    print(f"ID: {r[0]}, Name: {r[1]}, Email: {r[2]}, Country: {r[3]}")

                print("\n=== Checking Customer 'Naren' ===")
                cur.execute("SELECT customer_id, name, email, country FROM customers WHERE name ILIKE %s", ("%naren%",))
                rows = cur.fetchall()
                for r in rows:
                    print(f"ID: {r[0]}, Name: {r[1]}, Email: {r[2]}, Country: {r[3]}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    check_db()
