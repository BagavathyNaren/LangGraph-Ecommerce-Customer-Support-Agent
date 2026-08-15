import os
from fastapi import APIRouter, BackgroundTasks, HTTPException
from api.schemas import WebhookPayload
from domain.analytics import log_event
from domain.orders import update_order_from_webhook
from infra.logger import get_logger

logger = get_logger("webhook-route")
router = APIRouter()


@router.post("/webhooks/shipping-update")
def handle_shipping_update_webhook(payload: WebhookPayload, background_tasks: BackgroundTasks):
    expected_secret = os.environ.get("WEBHOOK_SECRET", "dev-secret-123")
    if payload.secret != expected_secret:
        logger.warning("Webhook auth failed", extra={"event": "webhook_auth_failure"})
        raise HTTPException(status_code=403, detail="Forbidden: invalid secret")

    result = update_order_from_webhook(payload.order_id, payload.status, payload.carrier)

    if not result.get("success"):
        error_msg = result.get("message", "Unknown error")
        logger.warning(
            "Webhook logic failed",
            extra={"event": "webhook_logic_failure", "error": error_msg, "order_id": payload.order_id},
        )
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg)
        elif "terminal state" in error_msg.lower():
            raise HTTPException(status_code=409, detail=error_msg)
        else:
            raise HTTPException(status_code=500, detail=error_msg)

    # Log to analytics
    background_tasks.add_task(
        log_event,
        event_type="webhook_received",
        thread_id=f"webhook-{payload.order_id}",
        intent="shipping_update",
        metadata={"order_id": payload.order_id, "status": payload.status, "carrier": payload.carrier},
    )

    logger.info(
        "Webhook processed successfully",
        extra={"event": "webhook_success", "order_id": payload.order_id, "status": payload.status},
    )
    return {"success": True, "message": "Order updated and notifications sent"}
