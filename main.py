from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator, Field
from langchain_core.messages import HumanMessage
from graph.graph_builder import build_graph
import re
import os

app = FastAPI()
graph = build_graph()

app.mount("/static", StaticFiles(directory="static"), name="static")

BANNED_PATTERNS = [
    r"<script.*?>", r"javascript:", r"\.\./",   # XSS + path traversal
    r"lc_kwargs", r"lc_serializable",           # CVE-2025-68664 deserialization
    r"(?i)(drop|delete|truncate)\s+table",      # SQL injection
    r"(?i)ignore\s+previous\s+instructions",    # prompt injection
    r"(?i)you\s+are\s+now\s+a",                # role hijacking
]

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
        config = {"configurable": {"thread_id": request.thread_id}}
        result = graph.invoke(
            {"messages": [HumanMessage(content=request.message)]},
            config=config
        )
        last_message = result["messages"][-1].content
        return {
            "response": last_message,
            "intent": result.get("intent"),
            "escalated": result.get("escalated", False),
            "order_id": result.get("order_id")
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal agent error.")