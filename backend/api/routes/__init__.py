from api.routes.chat import router as chat_router
from api.routes.cron import router as cron_router
from api.routes.evaluate import router as evaluate_router
from api.routes.health import router as health_router
from api.routes.tts import router as tts_router
from api.routes.webhooks import router as webhooks_router

__all__ = [
    "chat_router",
    "cron_router",
    "evaluate_router",
    "health_router",
    "tts_router",
    "webhooks_router",
]
