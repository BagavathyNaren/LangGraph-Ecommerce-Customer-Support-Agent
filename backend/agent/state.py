from langgraph.graph import MessagesState


class AgentState(MessagesState):
    order_id: str | None = None
    intent: str | None = None
    tool_result: str | None = None
    anger_count: int = 0
    retry_count: int = 0
    refund_amount: float = 0.0
    escalated: bool = False
    react_iterations: int = 0
