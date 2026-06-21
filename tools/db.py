import os

from psycopg_pool import ConnectionPool

from logger import get_logger

logger = get_logger("db-pool")

_pool = None


def get_db_config():
    """
    Returns the connection string or parameters based on the environment.
    Supports both standard DATABASE_URL (GCP e2-micro Postgres / local) and Cloud SQL Unix Sockets (GCP Cloud SQL).
    """
    # 1. Check for standard DATABASE_URL (GCP e2-micro Postgres / Local)
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

        logger.info(
            f"Connecting to Cloud SQL via Unix Socket: {socket_path}", extra={"event": "db_config", "mode": "cloud_sql"}
        )

        # Format for psycopg connection string with unix socket
        return f"host={socket_path} user={db_user} password={db_pass} dbname={db_name}"

    if db_url:
        logger.info("Connecting to DB via DATABASE_URL (GCP Postgres)", extra={"event": "db_config", "mode": "url"})
        return db_url

    raise ValueError("No database configuration found (DATABASE_URL or CLOUD_SQL_CONNECTION_NAME)")


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        conn_info = get_db_config()
        _pool = ConnectionPool(
            conn_info,
            min_size=1,  # Keep 1 warm connection on the persistent min-instance (eliminates cold-start DB latency)
            max_size=3,  # 3 connections per instance: 1 for checkpointer, 1 for tools, 1 buffer
            open=True,
            max_idle=30,  # Keep idle connections alive for 30s on the warm instance
            reconnect_timeout=10,  # Fail fast on connection loss
            check=ConnectionPool.check_connection,  # validates connection is alive before returning
            kwargs={"autocommit": True, "connect_timeout": 5},  # Short timeout for faster failures
        )
    return _pool


def get_connection():
    return get_pool().connection()
