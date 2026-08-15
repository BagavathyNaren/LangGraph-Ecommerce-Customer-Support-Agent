import os
import psycopg
from fastapi import APIRouter
from agent.graph_builder import get_graph
from infra.cache.redis_cache import r

router = APIRouter()


@router.get("/")
def get_service_overview():
    return {"status": "ok", "message": "Backend API is running. Frontend is served via Firebase Hosting."}


@router.get("/health")
def get_service_health():
    try:
        db_url = os.environ.get("DATABASE_URL", "")
        conn = psycopg.connect(db_url, connect_timeout=3)
        conn.close()
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)[:60]}"

    try:
        if r is not None:
            r.ping()
            redis_status = "healthy"
        else:
            redis_status = "unavailable"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)[:60]}"

    langsmith_status = "enabled" if os.environ.get("LANGCHAIN_TRACING_V2", "false").lower() == "true" else "disabled"
    graph_status = "ready" if get_graph() is not None else "not initialized"

    overall = (
        "healthy" if all([db_status == "healthy", redis_status == "healthy", graph_status == "ready"]) else "degraded"
    )

    return {
        "status": overall,
        "components": {
            "database": db_status,
            "redis": redis_status,
            "langsmith": langsmith_status,
            "graph": graph_status,
        },
        "version": "1.0.0",
    }
