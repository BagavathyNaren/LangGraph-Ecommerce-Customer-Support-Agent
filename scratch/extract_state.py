import os

import psycopg
from dotenv import load_dotenv

load_dotenv()
conn = psycopg.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()
cur.execute("SELECT checkpoint FROM checkpoints WHERE thread_id = 'thread-mi06ct6ar' ORDER BY thread_ts DESC LIMIT 1")
row = cur.fetchone()
if row:
    print(row[0])
else:
    print("No checkpoint found.")
