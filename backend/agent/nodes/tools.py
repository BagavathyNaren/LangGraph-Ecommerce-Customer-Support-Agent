import time
from concurrent.futures import ThreadPoolExecutor

from langchain_core.messages import ToolMessage

from agent.nodes.guardrails.prompts import TOOL_INTENT_MAP
from agent.state import AgentState
from infra.cache.redis_cache import get_cached_tool_result, set_cached_tool_result
from infra.logger import get_logger
from tools.agent_tools import AGENT_TOOLS

logger = get_logger("ecommerce-agent")


def tool_node(state: AgentState) -> AgentState:
    """Execute tool calls from the agent's last response, with Redis caching and parallel execution."""


    last_message = state["messages"][-1]
    tool_map = {t.name: t for t in AGENT_TOOLS}
    tool_calls = last_message.tool_calls

    if not tool_calls:
        return state

    def execute_single_tool(tool_call):
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        start = time.time()

        try:
            # Check tool cache first
            cached = get_cached_tool_result(tool_name, tool_args)
            if cached:
                result = cached
                duration_ms = round((time.time() - start) * 1000)
                logger.info(
                    "Tool executed (cached)",
                    extra={
                        "event": "tool_cached",
                        "tool": tool_name,
                        "tool_args": tool_args,
                        "duration_ms": duration_ms,
                    },
                )
            else:
                tool_fn = tool_map.get(tool_name)
                if tool_fn:
                    result = tool_fn.invoke(tool_args)
                    # Cache the result (skip if it contains an error)
                    if "error" not in str(result).lower() or "not_found" in str(result).lower():
                        set_cached_tool_result(tool_name, tool_args, str(result))
                else:
                    result = f"Tool {tool_name} not found."
                duration_ms = round((time.time() - start) * 1000)
                logger.info(
                    "Tool executed (live)",
                    extra={"event": "tool_live", "tool": tool_name, "tool_args": tool_args, "duration_ms": duration_ms},
                )
        except Exception as e:
            result = f"Error executing tool '{tool_name}': {str(e)}"
            duration_ms = round((time.time() - start) * 1000)
            logger.error(
                "Tool execution failed",
                extra={
                    "event": "tool_error",
                    "tool": tool_name,
                    "tool_args": tool_args,
                    "error": str(e),
                    "duration_ms": duration_ms,
                },
            )

        return ToolMessage(content=str(result), tool_call_id=tool_call["id"], name=tool_name), tool_name, tool_args

    # Execute all tool calls concurrently
    with ThreadPoolExecutor(max_workers=min(len(tool_calls), 5)) as executor:
        futures = [executor.submit(execute_single_tool, tc) for tc in tool_calls]
        for future in futures:
            tool_msg, tool_name, tool_args = future.result()
            state["messages"].append(tool_msg)

            # Extract metadata for frontend badges
            if "order_id" in tool_args:
                state["order_id"] = tool_args["order_id"]
            if tool_name in TOOL_INTENT_MAP:
                if state.get("intent") != "new_order":
                    state["intent"] = TOOL_INTENT_MAP[tool_name]

    return state


