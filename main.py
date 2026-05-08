from contextlib import asynccontextmanager
from cache.redis_cache import get_cached_response, set_cached_response
from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, field_validator, Field
from langchain_core.messages import HumanMessage
from graph.graph_builder import build_graph
from security.guards import validate_input, validate_output
from logger import get_logger
from evaluation.evaluator import run_evaluation
import re
import os
import time
import uuid
import asyncio
import json
import psycopg

os.environ["LANGCHAIN_TRACING_V2"] = os.environ.get("LANGCHAIN_TRACING_V2", "false")
os.environ["LANGCHAIN_API_KEY"] = os.environ.get("LANGCHAIN_API_KEY", "")
os.environ["LANGCHAIN_PROJECT"] = os.environ.get("LANGCHAIN_PROJECT", "ecommerce-support-agent")

logger = get_logger("ecommerce-agent")

BANNED_PATTERNS = [
    r"<script.*?>", r"javascript:", r"\.\./",
    r"lc_kwargs", r"lc_serializable",
    r"(?i)(drop|delete|truncate)\s+table",
    r"(?i)ignore\s+previous\s+instructions",
    r"(?i)you\s+are\s+now\s+a",
]

graph = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph
    logger.info("Starting up agent", extra={"event": "startup"})
    graph = build_graph()
    logger.info("Graph built successfully", extra={"event": "graph_ready"})
    yield
    logger.info("Shutting down", extra={"event": "shutdown"})

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    thread_id: str = Field(default="default", min_length=1, max_length=100)

    @field_validator("message")
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        for pattern in BANNED_PATTERNS:
            if re.search(pattern, v):
                raise ValueError("Message contains disallowed content.")
        return v.strip()

    @field_validator("thread_id")
    @classmethod
    def sanitize_thread_id(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_\-]+$", v):
            raise ValueError("thread_id must be alphanumeric.")
        return v

@app.get("/")
def root():
    return FileResponse("static/index.html")

@app.get("/health")
def health():
    from cache.redis_cache import r

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
    graph_status = "ready" if graph is not None else "not initialized"

    overall = "healthy" if all([
        db_status == "healthy",
        redis_status == "healthy",
        graph_status == "ready"
    ]) else "degraded"

    return {
        "status": overall,
        "components": {
            "database": db_status,
            "redis": redis_status,
            "langsmith": langsmith_status,
            "graph": graph_status
        },
        "version": "1.0.0"
    }

@app.post("/chat")
def chat(request: ChatRequest):
    start = time.time()
    request_id = str(uuid.uuid4())[:8]

    logger.info("Chat request received", extra={
        "event": "chat_request",
        "request_id": request_id,
        "thread_id": request.thread_id,
        "message_length": len(request.message)
    })

    try:
        validated_message, pii_detected = validate_input(request.message)

        if pii_detected:
            logger.warning("PII detected and redacted in input", extra={
                "event": "pii_redacted",
                "request_id": request_id,
                "thread_id": request.thread_id
            })

        if not pii_detected:
            cached = get_cached_response(validated_message, request.thread_id)
            if cached:
                duration_ms = round((time.time() - start) * 1000)
                logger.info("Cache hit — returning cached response", extra={
                    "event": "cache_hit",
                    "request_id": request_id,
                    "thread_id": request.thread_id,
                    "duration_ms": duration_ms
                })
                return {**cached, "request_id": request_id, "cache_hit": True}

        config = {"configurable": {"thread_id": request.thread_id}}
        result = graph.invoke(
            {"messages": [HumanMessage(content=validated_message)]},
            config=config
        )
        raw_response = result["messages"][-1].content
        safe_response = validate_output(raw_response)

        response_data = {
            "response": safe_response,
            "intent": result.get("intent"),
            "escalated": result.get("escalated", False),
            "order_id": result.get("order_id"),
            "pii_detected": pii_detected
        }

        if not pii_detected and not result.get("escalated", False):
            set_cached_response(validated_message, response_data, request.thread_id)

        duration_ms = round((time.time() - start) * 1000)
        logger.info("Chat request completed", extra={
            "event": "chat_response",
            "request_id": request_id,
            "thread_id": request.thread_id,
            "intent": result.get("intent"),
            "escalated": result.get("escalated", False),
            "pii_detected": pii_detected,
            "duration_ms": duration_ms,
            "cache_hit": False
        })

        return {**response_data, "request_id": request_id, "cache_hit": False}

    except ValueError as e:
        logger.warning("Request blocked", extra={
            "event": "request_blocked",
            "request_id": request_id,
            "thread_id": request.thread_id,
            "reason": str(e)
        })
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Internal agent error", extra={
            "event": "agent_error",
            "request_id": request_id,
            "thread_id": request.thread_id,
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail="Internal agent error.")

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    message = request.message
    thread_id = request.thread_id
    try:
        loop = asyncio.get_event_loop()
        validated_message, pii_detected = await loop.run_in_executor(
            None, validate_input, message
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    async def generate():
        start = time.time()
        request_id = str(uuid.uuid4())[:8]
        logger.info("Stream request received", extra={
            "event": "stream_request",
            "request_id": request_id,
            "thread_id": thread_id,
            "pii_detected": pii_detected
        })
        try:
            if not pii_detected:
                cached = get_cached_response(validated_message, thread_id)
                if cached:
                    duration_ms = round((time.time() - start) * 1000)
                    logger.info("Stream cache hit", extra={
                        "event": "stream_cache_hit",
                        "request_id": request_id,
                        "thread_id": thread_id,
                        "duration_ms": duration_ms
                    })
                    words = cached["response"].split(" ")
                    for i, word in enumerate(words):
                        token = word if i == len(words) - 1 else word + " "
                        yield f"data: {json.dumps({'token': token, 'done': False})}\n\n"
                        await asyncio.sleep(0.04)
                    yield f"data: {json.dumps({'done': True, 'intent': cached.get('intent'), 'escalated': cached.get('escalated', False), 'order_id': cached.get('order_id'), 'cache_hit': True})}\n\n"
                    return

            config = {"configurable": {"thread_id": thread_id}}
            result = await loop.run_in_executor(
                None,
                lambda: graph.invoke(
                    {"messages": [HumanMessage(content=validated_message)]},
                    config=config
                )
            )
            response = validate_output(result["messages"][-1].content)

            if not pii_detected and not result.get("escalated", False):
                set_cached_response(validated_message, {
                    "response": response,
                    "intent": result.get("intent"),
                    "escalated": result.get("escalated", False),
                    "order_id": result.get("order_id"),
                    "pii_detected": pii_detected
                }, thread_id)

            words = response.split(" ")
            for i, word in enumerate(words):
                token = word if i == len(words) - 1 else word + " "
                yield f"data: {json.dumps({'token': token, 'done': False})}\n\n"
                await asyncio.sleep(0.04)

            duration_ms = round((time.time() - start) * 1000)
            logger.info("Stream request completed", extra={
                "event": "stream_response",
                "request_id": request_id,
                "thread_id": thread_id,
                "intent": result.get("intent"),
                "escalated": result.get("escalated", False),
                "pii_detected": pii_detected,
                "duration_ms": duration_ms
            })
            yield f"data: {json.dumps({'done': True, 'intent': result.get('intent'), 'escalated': result.get('escalated', False), 'order_id': result.get('order_id'), 'cache_hit': False})}\n\n"

        except Exception as e:
            logger.error("Stream error", extra={
                "event": "stream_error",
                "request_id": request_id,
                "thread_id": thread_id,
                "error": str(e)
            })
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/evaluate")
def evaluate(x_api_key: str = Header(None)):
    expected_key = os.environ.get("EVAL_API_KEY", "")
    if not expected_key or x_api_key != expected_key:
        raise HTTPException(status_code=403, detail="Forbidden: invalid or missing API key.")
    if graph is None:
        raise HTTPException(status_code=503, detail="Agent not ready.")
    try:
        logger.info("Evaluation started", extra={"event": "eval_start"})
        results = run_evaluation(graph)
        return results
    except Exception as e:
        logger.error("Evaluation failed", extra={"event": "eval_error", "error": str(e)})
        raise HTTPException(status_code=500, detail="Evaluation failed.")