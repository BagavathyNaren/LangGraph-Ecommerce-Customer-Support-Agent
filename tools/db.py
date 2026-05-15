import os
from psycopg_pool import ConnectionPool
from logger import get_logger

logger = get_logger("db-pool")

_pool = None

def get_db_config():
    """
    Returns the connection string or parameters based on the environment.
    Supports both standard URL (Neon/HF) and Cloud SQL Unix Sockets (GCP).
    """
    # 1. Check for standard DATABASE_URL (Hugging Face / Local)
    db_url = os.environ.get("DATABASE_URL")
    
    # 2. Check for GCP Cloud SQL specific variables
    # If CLOUD_SQL_CONNECTION_NAME is set, we use Unix Sockets
    conn_name = os.environ.get("CLOUD_SQL_CONNECTION_NAME")  # e.g. "project:region:instance"
    
    if conn_name:
        db_user = os.environ.get("DB_USER", "postgres")
        db_pass = os.environ.get("DB_PASS", "")
        db_name = os.environ.get("DB_NAME", "postgres")
        
        # GCP Cloud Run injects the socket at this specific path
        socket_path = f"/cloudsql/{conn_name}"
        
        logger.info(f"Connecting to Cloud SQL via Unix Socket: {socket_path}", 
                    extra={"event": "db_config", "mode": "cloud_sql"})
        
        # Format for psycopg connection string with unix socket
        return f"host={socket_path} user={db_user} password={db_pass} dbname={db_name}"
    
    if db_url:
        logger.info("Connecting to DB via DATABASE_URL (Standard/Neon)", 
                    extra={"event": "db_config", "mode": "url"})
        return db_url
    
    raise ValueError("No database configuration found (DATABASE_URL or CLOUD_SQL_CONNECTION_NAME)")

def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        conn_info = get_db_config()
        _pool = ConnectionPool(
            conn_info,
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
