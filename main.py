from contextlib import asynccontextmanager
from cache.redis_cache import get_cached_response, set_cached_response
from fastapi import FastAPI, HTTPException, Header, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, field_validator, Field
from langchain_core.messages import HumanMessage, AIMessage
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
from tools.analytics import init_analytics_db, log_event

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

def get_final_response(result):
    """Extract the final AI response from the ReAct message list."""
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            return msg.content
    return result["messages"][-1].content

@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph
    logger.info("Starting up agent", extra={"event": "startup"})
    init_analytics_db()
    graph = build_graph()
    logger.info("Graph built successfully", extra={"event": "graph_ready"})
    yield
    logger.info("Shutting down", extra={"event": "shutdown"})

app = FastAPI(lifespan=lifespan)

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
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
def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    start = time.time()
    request_id = str(uuid.uuid4())[:8]

    logger.info("Chat request received", extra={
        "event": "chat_request",
        "request_id": request_id,
        "thread_id": request.thread_id,
        "message_length": len(request.message)
    })

    try:
        if len(request.message) > 500:
            raise ValueError("Message exceeds maximum length of 500 characters.")
            
        validated_message, pii_detected = validate_input(request.message)

        # Securely extract raw email before redaction to act as a vault for tools
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", request.message)
        raw_email = email_match.group(0) if email_match else None

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

        config = {"configurable": {"thread_id": request.thread_id, "raw_email": raw_email}}
        result = graph.invoke(
            {"messages": [HumanMessage(content=validated_message)]},
            config=config
        )
        raw_response = get_final_response(result)
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

        from tools.logging_tools import log_conversation
        background_tasks.add_task(
            log_conversation,
            request.thread_id,
            validated_message,
            safe_response,
            result.get("intent"),
            result.get("order_id")
        )

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

        duration_ms = round((time.time() - start) * 1000)
        background_tasks.add_task(
            log_event,
            "chat_response", 
            request.thread_id, 
            result.get("intent"), 
            {"pii": pii_detected}, 
            duration_ms
        )

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
        fallback_msg = "We are experiencing high traffic, please try again in a few minutes."
        return {
            "response": fallback_msg,
            "intent": None,
            "escalated": False,
            "order_id": None,
            "pii_detected": False,
            "request_id": request_id,
            "cache_hit": False
        }

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, background_tasks: BackgroundTasks):
    message = request.message
    thread_id = request.thread_id
    try:
        if len(message) > 500:
            raise ValueError("Message exceeds maximum length of 500 characters.")
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
            email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", message)
            raw_email = email_match.group(0) if email_match else None
            
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
                    from tools.logging_tools import log_conversation
                    background_tasks.add_task(
                        log_conversation,
                        thread_id,
                        validated_message,
                        cached["response"],
                        cached.get("intent"),
                        cached.get("order_id")
                    )
                    return

            config = {"configurable": {"thread_id": thread_id, "raw_email": raw_email}}
            result = await loop.run_in_executor(
                None,
                lambda: graph.invoke(
                    {"messages": [HumanMessage(content=validated_message)]},
                    config=config
                )
            )
            response = validate_output(get_final_response(result))

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
            
            from tools.logging_tools import log_conversation
            background_tasks.add_task(
                log_conversation,
                thread_id,
                validated_message,
                response,
                result.get("intent"),
                result.get("order_id")
            )
            
            duration_ms = round((time.time() - start) * 1000)
            # Use BackgroundTasks for stream logging
            background_tasks.add_task(
                log_event,
                "stream_response", 
                thread_id, 
                result.get("intent"), 
                {"pii": pii_detected}, 
                duration_ms
            )
            
            yield f"data: {json.dumps({'done': True, 'intent': result.get('intent'), 'escalated': result.get('escalated', False), 'order_id': result.get('order_id'), 'cache_hit': False})}\n\n"

        except Exception as e:
            logger.error("Stream error", extra={
                "event": "stream_error",
                "request_id": request_id,
                "thread_id": thread_id,
                "error": str(e)
            })
            fallback_msg = "We are experiencing high traffic, please try again in a few minutes."
            for word in fallback_msg.split(" "):
                yield f"data: {json.dumps({'token': word + ' ', 'done': False})}\n\n"
                await asyncio.sleep(0.04)
            yield f"data: {json.dumps({'done': True, 'intent': None, 'escalated': False, 'order_id': None, 'cache_hit': False})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", background=background_tasks)

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