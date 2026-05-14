from tools.db import get_connection
from logger import get_logger

logger = get_logger("logging")

def log_conversation(thread_id: str, user_message: str, ai_response: str, intent: str, order_id: str):
    """Log the conversation turn to the database."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                customer_id = None
                if order_id:
                    # Attempt to resolve customer_id from order_id, fail silently if not found
                    cur.execute("SELECT customer_id FROM orders WHERE order_id = %s", (order_id,))
                    row = cur.fetchone()
                    if row:
                        customer_id = row[0]
                
                cur.execute("""
                    INSERT INTO conversation_logs (thread_id, customer_id, user_message, ai_response, intent, order_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (thread_id, customer_id, user_message, ai_response, intent, order_id))
                conn.commit()
    except Exception as e:
        logger.error("Failed to log conversation", extra={"event": "log_error", "error": str(e), "thread_id": thread_id})
