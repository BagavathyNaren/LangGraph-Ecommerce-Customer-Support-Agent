from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator, Field
from langchain_core.messages import HumanMessage
from graph.graph_builder import build_graph
from security.guards import validate_input, validate_output
import re
import os

os.environ["LANGCHAIN_TRACING_V2"] = os.environ.get("LANGCHAIN_TRACING_V2", "false")
os.environ["LANGCHAIN_API_KEY"] = os.environ.get("LANGCHAIN_API_KEY", "")
os.environ["LANGCHAIN_PROJECT"] = os.environ.get("LANGCHAIN_PROJECT", "ecommerce-support-agent")

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
    graph = build_graph()
    yield

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
    try:
        validated_message = validate_input(request.message)
        config = {"configurable": {"thread_id": request.thread_id}}
        result = graph.invoke(
            {"messages": [HumanMessage(content=validated_message)]},
            config=config
        )
        raw_response = result["messages"][-1].content
        safe_response = validate_output(raw_response)
        return {
            "response": safe_response,
            "intent": result.get("intent"),
            "escalated": result.get("escalated", False),
            "order_id": result.get("order_id")
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal agent error.")