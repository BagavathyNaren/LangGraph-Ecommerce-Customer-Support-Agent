from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


def setup_middleware(app: FastAPI, is_configured: bool = True):
    @app.middleware("http")
    async def config_middleware(request: Request, call_next):
        if not is_configured and request.url.path not in ["/health", "/", "/assets"]:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service is currently unconfigured. Please configure environment variables in Cloud Run."
                },
            )
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://my-agentic-lab.web.app",
            "https://my-agentic-lab.firebaseapp.com",
            "http://localhost:5173",
            "*",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )
