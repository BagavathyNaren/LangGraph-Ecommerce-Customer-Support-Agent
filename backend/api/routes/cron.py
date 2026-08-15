import os
from fastapi import APIRouter, HTTPException
from infra.db import get_connection
from infra.logger import get_logger

logger = get_logger("cron-route")
router = APIRouter()


@router.get("/cron/process-etas")
def process_due_order_updates(secret: str = None):
    """Cron job endpoint to auto-complete old refunds and deliver old orders.
    Called by GCP Cloud Scheduler.
    """
    expected_secret = os.environ.get("CRON_SECRET", "default-cron-secret")
    if secret != expected_secret:
        raise HTTPException(status_code=403, detail="Unauthorized")

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Complete pending refunds older than 2 days
                cur.execute("""
                    UPDATE refunds
                    SET status = 'completed'
                    WHERE status = 'pending' AND updated_at <= NOW() - INTERVAL '2 days'
                """)
                refunds_updated = cur.rowcount

                # 2. Mark processing/in_transit orders as delivered if expected_delivery has passed
                cur.execute("""
                    UPDATE orders
                    SET status = 'delivered'
                    WHERE status IN ('processing', 'in_transit') AND expected_delivery < CURRENT_DATE
                """)
                orders_updated = cur.rowcount

                conn.commit()
                logger.info(
                    f"Cron execution successful. Refunds completed: {refunds_updated}, Orders delivered: {orders_updated}"
                )
                return {"status": "success", "refunds_updated": refunds_updated, "orders_updated": orders_updated}
    except Exception as e:
        logger.error(f"Cron execution failed: {e}")
        raise HTTPException(status_code=500, detail="Database error during cron execution")
