import redis
import hashlib
import json
import os
from logger import get_logger

logger = get_logger("cache")

def get_redis_client():
    url = os.environ.get("REDIS_URL")
    if not url:
        return None
    try:
        client = redis.from_url(url, decode_responses=True, socket_timeout=2)
        client.ping()
        return client
    except Exception as e:
        logger.warning("Redis unavailable", extra={"event": "cache_unavailable", "error": str(e)})
        return None

r = get_redis_client()
CACHE_TTL = 3600

def make_cache_key(message: str, thread_id: str = "global") -> str:
    normalized = message.lower().strip()
    return "agent:v1:" + hashlib.sha256(f"{thread_id}:{normalized}".encode()).hexdigest()

def get_cached_response(message: str, thread_id: str = "global") -> dict | None:
    if r is None:
        return None
    try:
        key = make_cache_key(message, thread_id)
        value = r.get(key)
        if value:
            logger.info("Cache hit", extra={"event": "cache_hit"})
            return json.loads(value)
        return None
    except Exception as e:
        logger.warning("Cache get failed", extra={"event": "cache_error", "error": str(e)})
        return None

def set_cached_response(message: str, response: dict, thread_id: str = "global") -> None:
    if r is None:
        return
    try:
        key = make_cache_key(message, thread_id)
        r.setex(key, CACHE_TTL, json.dumps(response))
        logger.info("Cache set", extra={"event": "cache_set"})
    except Exception as e:
        logger.warning("Cache set failed", extra={"event": "cache_error", "error": str(e)})

# --- Tool-level caching ---
TOOL_CACHE_TTL = 120  # 2 minutes — short TTL for data freshness

def make_tool_cache_key(tool_name: str, args: dict) -> str:
    """Create a cache key from tool name + sorted args."""
    args_str = json.dumps(args, sort_keys=True).lower().strip()
    return "tool:v1:" + hashlib.sha256(f"{tool_name}:{args_str}".encode()).hexdigest()

def get_cached_tool_result(tool_name: str, args: dict) -> str | None:
    if r is None:
        return None
    try:
        key = make_tool_cache_key(tool_name, args)
        value = r.get(key)
        if value:
            logger.info("Tool cache hit", extra={
                "event": "tool_cache_hit", "tool": tool_name
            })
            return value
        return None
    except Exception as e:
        logger.warning("Tool cache get failed", extra={"event": "tool_cache_error", "error": str(e)})
        return None

def set_cached_tool_result(tool_name: str, args: dict, result: str) -> None:
    if r is None:
        return
    try:
        key = make_tool_cache_key(tool_name, args)
        r.setex(key, TOOL_CACHE_TTL, result)
        logger.info("Tool cache set", extra={
            "event": "tool_cache_set", "tool": tool_name
        })
    except Exception as e:
        logger.warning("Tool cache set failed", extra={"event": "tool_cache_error", "error": str(e)})