import psycopg2

conn = psycopg2.connect("postgresql://postgres:my-agentic-lab@35.209.170.21:5432/postgres")
conn.autocommit = True
with conn.cursor() as cur:
    # Get all matching customer IDs
    cur.execute("SELECT customer_id FROM customers WHERE name ILIKE '%info naren%' OR email ILIKE '%naren@info.com%'")
    cust_ids = [row[0] for row in cur.fetchall()]

    if cust_ids:
        print(f"Found matching customer IDs: {cust_ids}")
        for cust_id in cust_ids:
            cur.execute("DELETE FROM support_tickets WHERE customer_id = %s", (cust_id,))
            cur.execute(
                "DELETE FROM refunds WHERE order_id IN (SELECT order_id FROM orders WHERE customer_id = %s)", (cust_id,)
            )
            cur.execute("DELETE FROM orders WHERE customer_id = %s", (cust_id,))
            cur.execute("DELETE FROM customers WHERE customer_id = %s", (cust_id,))
        print("Cleaned up matching customers, refunds, orders, and tickets.")
    else:
        print("No matching customers found.")
conn.close()
