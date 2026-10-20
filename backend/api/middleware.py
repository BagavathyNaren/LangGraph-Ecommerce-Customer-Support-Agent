from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from infra.logger import get_logger
from infra.security.rate_limiter import check_rate_limit

logger = get_logger("middleware")

ALLOWED_ORIGINS = [
    "https://my-agentic-lab.web.app",
    "https://my-agentic-lab.firebaseapp.com",
    "http://localhost:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://127.0.0.1:5173",
]

# Trusted app client token passed by our frontend
VALID_APP_CLIENT_TOKENS = {"my-agentic-lab-v1", "agent-lab-web"}


def setup_middleware(app: FastAPI, is_configured: bool = True):
    @app.middleware("http")
    async def security_and_rate_limit_middleware(request: Request, call_next):
        # 1. Allow OPTIONS preflight requests immediately
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        # 2. Public / Internal Webhook & Health bypass
        public_paths = ["/health", "/", "/assets", "/docs", "/openapi.json"]
        is_public = path in public_paths or path.startswith("/webhooks/") or path.startswith("/cron/") or path.startswith("/evaluate")

        # 3. Anti-bot and Origin validation for protected credit-consuming endpoints (/chat, /chat/stream, /tts)
        if not is_public:
            origin = request.headers.get("origin")
            referer = request.headers.get("referer")
            app_client = request.headers.get("x-app-client")

            # Validate Origin if provided
            if origin:
                if not any(origin.rstrip("/") == allowed.rstrip("/") for allowed in ALLOWED_ORIGINS):
                    logger.warning(
                        "Blocked request from unauthorized origin",
                        extra={"event": "origin_blocked", "origin": origin, "path": path},
                    )
                    return JSONResponse(
                        status_code=403,
                        content={"error": "Access forbidden: Unauthorized origin."},
                    )
            elif referer:
                if not any(referer.startswith(allowed) for allowed in ALLOWED_ORIGINS):
                    logger.warning(
                        "Blocked request from unauthorized referer",
                        extra={"event": "referer_blocked", "referer": referer, "path": path},
                    )
                    return JSONResponse(
                        status_code=403,
                        content={"error": "Access forbidden: Unauthorized referer."},
                    )
            else:
                # Direct script/curl call without Origin or Referer: require X-App-Client
                if not app_client or app_client not in VALID_APP_CLIENT_TOKENS:
                    logger.warning(
                        "Blocked direct API call without client authorization",
                        extra={"event": "direct_call_blocked", "path": path},
                    )
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": "Access forbidden: Direct automated API access is restricted. Please use the application interface."
                        },
                    )

            # 4. Distributed Rate Limiting to prevent API credit exhaustion
            endpoint_tag = "tts" if path.startswith("/tts") else "chat"
            allowed, reason, retry_after = check_rate_limit(request, endpoint_tag=endpoint_tag)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": reason,
                        "retry_after": retry_after,
                        "detail": "Rate limit exceeded to protect API resources. Please try again shortly.",
                    },
                    headers={"Retry-After": str(retry_after)},
                )

        # 5. Unconfigured service check (evaluated only for legitimate requests)
        if not is_configured and not is_public:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service is currently unconfigured. Please configure environment variables in Cloud Run."
                },
            )

        response = await call_next(request)

        # 6. Add security headers to response
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # Strict CORS configuration: No wildcards
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
