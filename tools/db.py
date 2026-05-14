import os
from psycopg_pool import ConnectionPool

_pool = None

def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            os.environ["DATABASE_URL"],
            min_size=1,
            max_size=5,
            open=True,
            max_idle=60,
            reconnect_timeout=30,
            check=ConnectionPool.check_connection,  # validates connection is alive before returning
            kwargs={"autocommit": True, "connect_timeout": 10}
        )
    return _pool

def get_connection():
    return get_pool().connection()
