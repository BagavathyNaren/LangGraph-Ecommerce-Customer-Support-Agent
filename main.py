from fastapi import FastAPI
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from graph.graph_builder import build_graph
import os

app = FastAPI()
graph = build_graph()

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"

@app.get("/")
def root():
    return {"status": "ecommerce-support-agent is running"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/chat")
def chat(request: ChatRequest):
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