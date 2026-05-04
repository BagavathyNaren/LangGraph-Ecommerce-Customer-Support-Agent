from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator, Field
from langchain_core.messages import HumanMessage
from graph.graph_builder import build_graph
from security.guards import validate_input, validate_output
from logger import get_logger
import re
import os
import time

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
    return {"status": "ok"}

@app.post("/chat")
def chat(request: ChatRequest):
    start = time.time()
    logger.info("Chat request received", extra={
        "event": "chat_request",
        "thread_id": request.thread_id,
        "message_length": len(request.message)
    })

    try:
        validated_message, pii_detected = validate_input(request.message)

        if pii_detected:
            logger.warning("PII detected and redacted in input", extra={
                "event": "pii_redacted",
                "thread_id": request.thread_id
            })

        config = {"configurable": {"thread_id": request.thread_id}}
        result = graph.invoke(
            {"messages": [HumanMessage(content=validated_message)]},
            config=config
        )
        raw_response = result["messages"][-1].content
        safe_response = validate_output(raw_response)

        duration_ms = round((time.time() - start) * 1000)
        logger.info("Chat request completed", extra={
            "event": "chat_response",
            "thread_id": request.thread_id,
            "intent": result.get("intent"),
            "escalated": result.get("escalated", False),
            "pii_detected": pii_detected,
            "duration_ms": duration_ms
        })

        return {
            "response": safe_response,
            "intent": result.get("intent"),
            "escalated": result.get("escalated", False),
            "order_id": result.get("order_id"),
            "pii_detected": pii_detected
        }

    except ValueError as e:
        logger.warning("Request blocked", extra={
            "event": "request_blocked",
            "thread_id": request.thread_id,
            "reason": str(e)
        })
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Internal agent error", extra={
            "event": "agent_error",
            "thread_id": request.thread_id,
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail="Internal agent error.")