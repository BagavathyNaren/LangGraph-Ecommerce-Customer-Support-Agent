import asyncio
import json
import re
import time
import uuid
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage

from agent.graph_builder import get_graph
from api.schemas import ChatRequest
from domain.analytics import log_event
from infra.cache.redis_cache import get_cached_response, set_cached_response
from infra.logger import get_logger
from infra.logging_tools import log_conversation
from infra.security.guards import validate_input, validate_output

logger = get_logger("chat-route")
router = APIRouter()


def get_final_response(result):
    """Extract the final AI response from the ReAct message list."""
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            return msg.content
    return result["messages"][-1].content


@router.post("/chat")
def create_chat_response(request: ChatRequest, background_tasks: BackgroundTasks):
    start = time.time()
    request_id = str(uuid.uuid4())[:8]
    graph = get_graph()

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

        if graph is None:
            raise RuntimeError("Agent graph is not initialized yet.")

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


@router.post("/chat/stream")
async def stream_chat_response(request: ChatRequest, background_tasks: BackgroundTasks):
    message = request.message
    thread_id = request.thread_id
    try:
        if len(message) > 500:
            raise ValueError("Message exceeds maximum length of 500 characters.")
        loop = asyncio.get_running_loop()
        validated_message, pii_detected = await loop.run_in_executor(None, validate_input, message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    async def generate():
        start = time.time()
        request_id = str(uuid.uuid4())[:8]
        graph = get_graph()
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
                    background_tasks.add_task(
                        log_conversation,
                        thread_id,
                        validated_message,
                        cached["response"],
                        cached.get("intent"),
                        cached.get("order_id"),
                    )
                    return

            if graph is None:
                raise RuntimeError("Agent graph is not initialized yet.")

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

            background_tasks.add_task(
                log_conversation, thread_id, validated_message, response, result.get("intent"), result.get("order_id")
            )

            background_tasks.add_task(
                log_event, "stream_response", thread_id, result.get("intent"), {"pii": pii_detected}, duration_ms
            )

            yield f"data: {json.dumps({'done': True, 'intent': result.get('intent'), 'escalated': result.get('escalated', False), 'order_id': result.get('order_id'), 'cache_hit': False})}\n\n"

        except Exception as e:
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
