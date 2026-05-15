import json
from tools.db import get_connection
from logger import get_logger
import threading

logger = get_logger("analytics")

def init_analytics_db():
    """Ensure the analytics table exists."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS analytics_events (
                        id SERIAL PRIMARY KEY,
                        event_type VARCHAR(50) NOT NULL,
                        thread_id VARCHAR(100),
                        intent VARCHAR(50),
                        metadata JSONB,
                        duration_ms INTEGER,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX IF NOT EXISTS idx_analytics_event_type ON analytics_events(event_type);
                    CREATE INDEX IF NOT EXISTS idx_analytics_thread_id ON analytics_events(thread_id);
                """)
                logger.info("Analytics database initialized", extra={"event": "analytics_init"})
    except Exception as e:
        logger.error("Failed to initialize analytics DB", extra={"event": "analytics_init_error", "error": str(e)})

def log_event(event_type: str, thread_id: str = None, intent: str = None, metadata: dict = None, duration_ms: int = None):
    """Log an analytics event asynchronously."""
    def _log():
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO analytics_events (event_type, thread_id, intent, metadata, duration_ms)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (event_type, thread_id, intent, json.dumps(metadata or {}), duration_ms))
        except Exception as e:
            logger.error(f"Failed to log event {event_type}", extra={"event": "log_error", "error": str(e)})

    # Run in a separate thread to avoid blocking the main chat flow
    threading.Thread(target=_log, daemon=True).start()
