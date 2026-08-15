import json

from infra.logger import get_logger
from infra.db import get_connection

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


def log_event(
    event_type: str, thread_id: str = None, intent: str = None, metadata: dict = None, duration_ms: int = None
):
    """Log an analytics event synchronously (intended to be called via BackgroundTasks)."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO analytics_events (event_type, thread_id, intent, metadata, duration_ms)
                    VALUES (%s, %s, %s, %s, %s)
                """,
                    (event_type, thread_id, intent, json.dumps(metadata or {}), duration_ms),
                )
            conn.commit()
            logger.info(f"Logged event: {event_type}")
    except Exception as e:
        logger.error(f"Failed to log event {event_type}: {e}")


def get_analytics_summary() -> dict:
    """Fetch a summary of business analytics from the database."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Count directly from support_tickets table (source of truth)
                cur.execute("SELECT COUNT(*) FROM support_tickets")
                total_tickets = int(cur.fetchone()[0] or 0)

                # 2. Count directly from refunds table (source of truth)
                cur.execute("SELECT COUNT(*) FROM refunds")
                total_returns = int(cur.fetchone()[0] or 0)

                # 3. Average Latency from analytics_events
                cur.execute("SELECT AVG(duration_ms) FROM analytics_events WHERE duration_ms IS NOT NULL")
                avg_latency_raw = cur.fetchone()[0]
                avg_latency = round(float(avg_latency_raw)) if avg_latency_raw is not None else 0

                # 4. Most Common Intent from analytics_events
                cur.execute("""
                    SELECT intent, COUNT(*) as count
                    FROM analytics_events
                    WHERE intent IS NOT NULL
                    GROUP BY intent
                    ORDER BY count DESC
                    LIMIT 1
                """)
                top_intent_row = cur.fetchone()
                top_intent = str(top_intent_row[0]) if top_intent_row else "N/A"

                return {
                    "total_tickets": total_tickets,
                    "total_returns": total_returns,
                    "avg_response_time_ms": avg_latency,
                    "most_common_intent": top_intent,
                }
    except Exception as e:
        logger.error(f"Analytics query failed: {e}")
        return {"error": "Could not retrieve analytics data."}
