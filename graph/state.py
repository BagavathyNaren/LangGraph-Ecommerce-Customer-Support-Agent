from typing import Optional
from langgraph.graph import MessagesState

class AgentState(MessagesState):
    order_id: Optional[str] = None
    intent: Optional[str] = None
    tool_result: Optional[str] = None
    anger_count: int = 0
    retry_count: int = 0
    refund_amount: float = 0.0
    escalated: bool = False