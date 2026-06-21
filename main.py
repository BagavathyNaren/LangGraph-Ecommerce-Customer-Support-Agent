import os

from dotenv import load_dotenv

load_dotenv()

from security.env_validator import validate_env

validate_env()

import asyncio
import json
import re
import time
import uuid
from contextlib import asynccontextmanager

import psycopg
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field, field_validator

from cache.redis_cache import get_cached_response, set_cached_response
from evaluation.evaluator import run_evaluation
from graph.graph_builder import build_graph
from logger import get_logger
from security.guards import validate_input, validate_output
from tools.analytics import init_analytics_db, log_event

os.environ["LANGCHAIN_TRACING_V2"] = os.environ.get("LANGCHAIN_TRACING_V2", "false")
os.environ["LANGCHAIN_API_KEY"] = os.environ.get("LANGCHAIN_API_KEY", "")
os.environ["LANGCHAIN_PROJECT"] = os.environ.get("LANGCHAIN_PROJECT", "ecommerce-support-agent")

logger = get_logger("ecommerce-agent")

BANNED_PATTERNS = [
    r"<script.*?>",
    r"javascript:",
    r"\.\./",
    r"lc_kwargs",
    r"lc_serializable",
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
    # Self-healing DB migration: ensure phone_number column exists (safe for GCP migration)
    try:
        from tools.db import get_connection

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    ALTER TABLE customers
                    ADD COLUMN IF NOT EXISTS phone_number VARCHAR(20) DEFAULT NULL;
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_customers_phone
                    ON customers(phone_number);
                """)
                # DB-level duplicate ticket guard: ONE open ticket per (order_id, customer_id)
                # Drop old narrow index (by issue_type) if it exists, then create the broad one
                cur.execute("DROP INDEX IF EXISTS uq_open_ticket_per_order_issue")
                cur.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_one_open_ticket_per_order
                    ON support_tickets (order_id, customer_id)
                    WHERE status = 'open' AND customer_id IS NOT NULL;
                """)

                # Phase 3B DB Schema Updates
                cur.execute("""
                    ALTER TABLE customers
                    ADD COLUMN IF NOT EXISTS country VARCHAR(50) DEFAULT NULL;
                """)
                cur.execute("""
                    ALTER TABLE orders
                    ADD COLUMN IF NOT EXISTS product_id VARCHAR(20) DEFAULT NULL,
                    ADD COLUMN IF NOT EXISTS price DECIMAL(10,2) DEFAULT NULL,
                    ADD COLUMN IF NOT EXISTS source_website VARCHAR(100) DEFAULT NULL;
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS products (
                        product_id VARCHAR(20) PRIMARY KEY,
                        name VARCHAR(200) NOT NULL,
                        category VARCHAR(100),
                        price DECIMAL(10,2) NOT NULL,
                        currency VARCHAR(3) DEFAULT 'INR',
                        country VARCHAR(50) NOT NULL,
                        source_website VARCHAR(100),
                        in_stock BOOLEAN DEFAULT true,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                # Seed initial products if table is empty
                cur.execute("SELECT COUNT(*) FROM products")
                if cur.fetchone()[0] == 0:
                    seed_products = [
                        (
                            "PRD-TV-001",
                            'Sony Bravia 55" 4K Smart TV',
                            "Electronics",
                            54990.00,
                            "INR",
                            "India",
                            "Amazon India",
                            True,
                        ),
                        (
                            "PRD-TV-002",
                            'Sony Bravia 50" 4K Smart TV',
                            "Electronics",
                            49990.00,
                            "INR",
                            "India",
                            "Flipkart",
                            True,
                        ),
                        (
                            "PRD-TV-003",
                            'Sony Bravia 43" 4K Smart TV',
                            "Electronics",
                            39990.00,
                            "INR",
                            "India",
                            "Croma",
                            True,
                        ),
                        (
                            "PRD-SH-001",
                            "Nike Air Max Running Shoes",
                            "Fashion",
                            8995.00,
                            "INR",
                            "India",
                            "Myntra",
                            True,
                        ),
                        (
                            "PRD-SH-002",
                            "Nike Air Force 1 Sneakers",
                            "Fashion",
                            7495.00,
                            "INR",
                            "India",
                            "Amazon India",
                            True,
                        ),
                        (
                            "PRD-SB-001",
                            "Adidas FIFA Pro Soccer Ball",
                            "Sports",
                            2999.00,
                            "INR",
                            "India",
                            "Amazon India",
                            True,
                        ),
                        (
                            "PRD-SB-002",
                            "Puma La Liga Trainer Ball",
                            "Sports",
                            1999.00,
                            "INR",
                            "India",
                            "Flipkart",
                            True,
                        ),
                    ]
                    cur.executemany(
                        """
                        INSERT INTO products (product_id, name, category, price, currency, country, source_website, in_stock)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        seed_products,
                    )
                    logger.info("Seeded products table", extra={"event": "db_seed"})
        logger.info(
            "DB migration: schema verified (phone_number + unique ticket index)", extra={"event": "db_migration"}
        )
    except Exception as e:
        logger.warning(f"DB migration warning: {e}", extra={"event": "db_migration_warning"})
    # Build the graph asynchronously so the ASGI server can start
    # quickly and bind to the port; heavy initialisation can run in
    # the background and will set `graph` when ready.
    loop = asyncio.get_event_loop()

    async def _build_graph_bg():
        global graph
        try:
            g = await loop.run_in_executor(None, build_graph)
            graph = g
            logger.info("Graph built successfully", extra={"event": "graph_ready"})
        except Exception as e:
            logger.error(f"Graph build failed: {e}", extra={"event": "graph_failed"})

    # schedule background graph build
    asyncio.create_task(_build_graph_bg())
    yield
    logger.info("Shutting down", extra={"event": "shutdown"})


app = FastAPI(lifespan=lifespan)

from fastapi.middleware.cors import CORSMiddleware

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

app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    thread_id: str = Field(default="default", min_length=1, max_length=100)
    email: str = Field(default=None)  # Explicit email from frontend for customer registration

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

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if v is not None:
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
                raise ValueError("Invalid email address format.")
        return v


class WebhookPayload(BaseModel):
    order_id: str = Field(..., description="The ID of the order")
    status: str = Field(..., description="The new status of the order (e.g. delivered)")
    carrier: str = Field(default=None, description="The shipping carrier")
    timestamp: str = Field(default=None, description="Event timestamp")
    secret: str = Field(..., description="Webhook authentication secret")


# Update TTS model and timeout
TTS_MODEL = "tts-1"
HTTP_TIMEOUT = 60  # seconds


@app.get("/tts")
def tts_proxy(text: str):
    """
    Proxy TTS audio through the backend using OpenAI's TTS API.
    Uses the 'echo' voice (clear, warm male) and tts-1 for low-latency, loud and clear output.
    """
    import requests as req
    from fastapi.responses import Response as FastResponse

    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")

        url = "https://api.openai.com/v1/audio/speech"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        data = {"model": TTS_MODEL, "input": text, "voice": "echo", "response_format": "mp3"}
        r = req.post(url, headers=headers, json=data, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return FastResponse(
            content=r.content,
            media_type="audio/mpeg",
            headers={
                "Cache-Control": "public, max-age=86400",
                "Access-Control-Allow-Origin": "*",
            },
        )
    except Exception as e:
        logger.warning(f"TTS proxy error: {e}")
        raise HTTPException(status_code=502, detail="TTS service unavailable")


@app.get("/cron/process-etas")
def process_etas(secret: str = None):
    """
    Cron job endpoint to auto-complete old refunds and deliver old orders.
    Called by GCP Cloud Scheduler.
    """
    expected_secret = os.environ.get("CRON_SECRET", "default-cron-secret")
    if secret != expected_secret:
        raise HTTPException(status_code=403, detail="Unauthorized")

    try:
        from tools.db import get_connection

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


@app.get("/")
def root():
    return FileResponse("frontend/dist/index.html")


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


@app.post("/chat")
def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    start = time.time()
    request_id = str(uuid.uuid4())[:8]

    logger.info(
        "Chat request received",
        extra={
            "event": "chat_request",
            "request_id": request_id,
            "thread_id": request.thread_id,
            "message_length": len(request.message),
        },
    )

    try:
        if len(request.message) > 500:
            raise ValueError("Message exceeds maximum length of 500 characters.")

        validated_message, pii_detected = validate_input(request.message)

        # Use explicit frontend email first; fall back to scanning message text
        raw_email = request.email or None
        if not raw_email:
            email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", request.message)
            raw_email = email_match.group(0) if email_match else None

        if pii_detected:
            logger.warning(
                "PII detected and redacted in input",
                extra={"event": "pii_redacted", "request_id": request_id, "thread_id": request.thread_id},
            )

        # CACHE BYPASS: Never cache analytics or status requests
        is_analytics_query = any(
            word in validated_message.lower() for word in ["analytics", "stats", "summary", "dashboard"]
        )

        if not pii_detected and not is_analytics_query:
            cached = get_cached_response(validated_message, request.thread_id)
            if cached:
                duration_ms = round((time.time() - start) * 1000)
                logger.info(
                    "Cache hit — returning cached response",
                    extra={
                        "event": "cache_hit",
                        "request_id": request_id,
                        "thread_id": request.thread_id,
                        "duration_ms": duration_ms,
                    },
                )
                return {**cached, "request_id": request_id, "cache_hit": True}

        config = {"configurable": {"thread_id": request.thread_id, "raw_email": raw_email}}
        result = graph.invoke({"messages": [HumanMessage(content=validated_message)]}, config=config)
        raw_response = get_final_response(result)
        safe_response = validate_output(raw_response)

        response_data = {
            "response": safe_response,
            "intent": result.get("intent"),
            "escalated": result.get("escalated", False),
            "order_id": result.get("order_id"),
            "pii_detected": pii_detected,
        }

        # Avoid caching incomplete introductions or extremely short cut-off statements
        is_cutoff_intro = False
        msg_clean = validated_message.lower().strip().replace(".", "").replace(",", "").strip()
        if msg_clean in ["my name is", "i am", "i'm", "this is", "my full name is"]:
            is_cutoff_intro = True

        if not pii_detected and not result.get("escalated", False) and not is_analytics_query and not is_cutoff_intro:
            set_cached_response(validated_message, response_data, request.thread_id)

        from tools.logging_tools import log_conversation

        background_tasks.add_task(
            log_conversation,
            request.thread_id,
            validated_message,
            safe_response,
            result.get("intent"),
            result.get("order_id"),
        )

        duration_ms = round((time.time() - start) * 1000)
        logger.info(
            "Chat request completed",
            extra={
                "event": "chat_response",
                "request_id": request_id,
                "thread_id": request.thread_id,
                "intent": result.get("intent"),
                "escalated": result.get("escalated", False),
                "pii_detected": pii_detected,
                "duration_ms": duration_ms,
                "cache_hit": False,
            },
        )

        duration_ms = round((time.time() - start) * 1000)
        background_tasks.add_task(
            log_event, "chat_response", request.thread_id, result.get("intent"), {"pii": pii_detected}, duration_ms
        )

        return {**response_data, "request_id": request_id, "cache_hit": False}

    except ValueError as e:
        logger.warning(
            "Request blocked",
            extra={
                "event": "request_blocked",
                "request_id": request_id,
                "thread_id": request.thread_id,
                "reason": str(e),
            },
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # DEBUG: Print the actual error to logs
        print(f"CHAT ERROR DEBUG: {e}")
        import traceback

        traceback.print_exc()

        logger.error(
            "Internal agent error",
            extra={"event": "agent_error", "request_id": request_id, "thread_id": request.thread_id, "error": str(e)},
        )
        fallback_msg = "We are experiencing high traffic, please try again in a few minutes."
        return {
            "response": fallback_msg,
            "intent": None,
            "escalated": False,
            "order_id": None,
            "pii_detected": False,
            "request_id": request_id,
            "cache_hit": False,
        }


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, background_tasks: BackgroundTasks):
    message = request.message
    thread_id = request.thread_id
    try:
        if len(message) > 500:
            raise ValueError("Message exceeds maximum length of 500 characters.")
        loop = asyncio.get_event_loop()
        validated_message, pii_detected = await loop.run_in_executor(None, validate_input, message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    async def generate():
        start = time.time()
        request_id = str(uuid.uuid4())[:8]
        logger.info(
            "Stream request received",
            extra={
                "event": "stream_request",
                "request_id": request_id,
                "thread_id": thread_id,
                "pii_detected": pii_detected,
            },
        )
        try:
            # Use explicit frontend email first; fall back to scanning message text
            raw_email = request.email or None
            if not raw_email:
                email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", message)
                raw_email = email_match.group(0) if email_match else None

            # CACHE BYPASS: Never serve analytics from cache — data must be real-time
            is_analytics_query = any(
                word in validated_message.lower() for word in ["analytics", "stats", "summary", "dashboard"]
            )

            if not pii_detected and not is_analytics_query:
                cached = get_cached_response(validated_message, thread_id)
                if cached:
                    duration_ms = round((time.time() - start) * 1000)
                    logger.info(
                        "Stream cache hit",
                        extra={
                            "event": "stream_cache_hit",
                            "request_id": request_id,
                            "thread_id": thread_id,
                            "duration_ms": duration_ms,
                        },
                    )
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
                        cached.get("order_id"),
                    )
                    return

            config = {"configurable": {"thread_id": thread_id, "raw_email": raw_email}}
            result = await loop.run_in_executor(
                None, lambda: graph.invoke({"messages": [HumanMessage(content=validated_message)]}, config=config)
            )
            response = validate_output(get_final_response(result))

            if not pii_detected and not result.get("escalated", False) and not is_analytics_query:
                set_cached_response(
                    validated_message,
                    {
                        "response": response,
                        "intent": result.get("intent"),
                        "escalated": result.get("escalated", False),
                        "order_id": result.get("order_id"),
                        "pii_detected": pii_detected,
                    },
                    thread_id,
                )

            words = response.split(" ")
            for i, word in enumerate(words):
                token = word if i == len(words) - 1 else word + " "
                yield f"data: {json.dumps({'token': token, 'done': False})}\n\n"
                await asyncio.sleep(0.04)

            duration_ms = round((time.time() - start) * 1000)
            logger.info(
                "Stream request completed",
                extra={
                    "event": "stream_response",
                    "request_id": request_id,
                    "thread_id": thread_id,
                    "intent": result.get("intent"),
                    "escalated": result.get("escalated", False),
                    "pii_detected": pii_detected,
                    "duration_ms": duration_ms,
                },
            )

            from tools.logging_tools import log_conversation

            background_tasks.add_task(
                log_conversation, thread_id, validated_message, response, result.get("intent"), result.get("order_id")
            )

            duration_ms = round((time.time() - start) * 1000)
            # Use BackgroundTasks for stream logging
            background_tasks.add_task(
                log_event, "stream_response", thread_id, result.get("intent"), {"pii": pii_detected}, duration_ms
            )

            yield f"data: {json.dumps({'done': True, 'intent': result.get('intent'), 'escalated': result.get('escalated', False), 'order_id': result.get('order_id'), 'cache_hit': False})}\n\n"

        except Exception as e:
            # DEBUG: Print the actual error to logs so we can fix it
            print(f"STREAM ERROR DEBUG: {e}")
            import traceback

            traceback.print_exc()

            logger.error(
                "Stream error",
                extra={"event": "stream_error", "request_id": request_id, "thread_id": thread_id, "error": str(e)},
            )
            fallback_msg = "We are experiencing high traffic, please try again in a few minutes."
            for word in fallback_msg.split(" "):
                yield f"data: {json.dumps({'token': word + ' ', 'done': False})}\n\n"
                await asyncio.sleep(0.04)
            yield f"data: {json.dumps({'done': True, 'intent': None, 'escalated': False, 'order_id': None, 'cache_hit': False})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", background=background_tasks)


@app.post("/webhooks/shipping-update")
def shipping_webhook(payload: WebhookPayload, background_tasks: BackgroundTasks):
    expected_secret = os.environ.get("WEBHOOK_SECRET", "dev-secret-123")
    if payload.secret != expected_secret:
        logger.warning("Webhook auth failed", extra={"event": "webhook_auth_failure"})
        raise HTTPException(status_code=403, detail="Forbidden: invalid secret")

    from tools.real_tools import update_order_from_webhook

    result = update_order_from_webhook(payload.order_id, payload.status, payload.carrier)

    if not result.get("success"):
        error_msg = result.get("message", "Unknown error")
        logger.warning(
            "Webhook logic failed",
            extra={"event": "webhook_logic_failure", "error": error_msg, "order_id": payload.order_id},
        )
        # Determine status code based on error
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg)
        elif "terminal state" in error_msg.lower():
            raise HTTPException(status_code=409, detail=error_msg)
        else:
            raise HTTPException(status_code=500, detail=error_msg)

    # Log to analytics
    from tools.analytics import log_event

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
