import os
import time
from collections import defaultdict, deque
from threading import Lock
from fastapi import Request

from infra.cache.redis_cache import get_redis_client
from infra.logger import get_logger

logger = get_logger("rate-limiter")

# In-memory fallback structures
_memory_lock = Lock()
_memory_minute_hits = defaultdict(deque)
_memory_hour_hits = defaultdict(deque)
_memory_day_hits = defaultdict(deque)

# Rate limit thresholds (requests allowed per window)
RATE_LIMITS = {
    "chat": {
        "minute": int(os.getenv("RATE_LIMIT_CHAT_PER_MINUTE", "15")),
        "hour": int(os.getenv("RATE_LIMIT_CHAT_PER_HOUR", "60")),
        "day": int(os.getenv("RATE_LIMIT_CHAT_PER_DAY", "200")),
    },
    "tts": {
        "minute": int(os.getenv("RATE_LIMIT_TTS_PER_MINUTE", "6")),
        "hour": int(os.getenv("RATE_LIMIT_TTS_PER_HOUR", "30")),
        "day": int(os.getenv("RATE_LIMIT_TTS_PER_DAY", "100")),
    },
}


def get_client_ip(request: Request) -> str:
    """Extract real client IP from Cloud Run reverse proxy headers."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # First entry is the client IP
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host.strip()
    return "127.0.0.1"


def _check_memory_rate_limit(key: str, limits: dict) -> tuple[bool, str, int]:
    """In-memory sliding window fallback when Redis is unavailable."""
    now = time.time()
    with _memory_lock:
        # 1. Minute window
        minute_q = _memory_minute_hits[key]
        while minute_q and minute_q[0] <= now - 60:
            minute_q.popleft()
        if len(minute_q) >= limits["minute"]:
            retry_after = int(60 - (now - minute_q[0])) + 1
            return False, "Per-minute limit exceeded. Please slow down.", max(1, retry_after)

        # 2. Hour window
        hour_q = _memory_hour_hits[key]
        while hour_q and hour_q[0] <= now - 3600:
            hour_q.popleft()
        if len(hour_q) >= limits["hour"]:
            retry_after = int(3600 - (now - hour_q[0])) + 1
            return False, "Hourly limit exceeded. Please try again later.", max(1, retry_after)

        # 3. Day window
        day_q = _memory_day_hits[key]
        while day_q and day_q[0] <= now - 86400:
            day_q.popleft()
        if len(day_q) >= limits["day"]:
            retry_after = int(86400 - (now - day_q[0])) + 1
            return False, "Daily credit protection limit reached. Please try again tomorrow.", max(1, retry_after)

        # Record this hit
        minute_q.append(now)
        hour_q.append(now)
        day_q.append(now)
        return True, "", 0


def check_rate_limit(request: Request, endpoint_tag: str = "chat") -> tuple[bool, str, int]:
    """Check if the requesting client is within allowed rate limits.

    Returns:
        (allowed: bool, reason: str, retry_after_seconds: int)
    """
    ip = get_client_ip(request)
    limits = RATE_LIMITS.get(endpoint_tag, RATE_LIMITS["chat"])

    redis_client = get_redis_client()
    if redis_client is None:
        # Fallback to local memory limiter
        allowed, reason, retry_after = _check_memory_rate_limit(f"{endpoint_tag}:{ip}", limits)
        if not allowed:
            logger.warning(
                "Memory rate limit exceeded",
                extra={"event": "rate_limit_exceeded", "ip": ip, "endpoint": endpoint_tag, "reason": reason},
            )
        return allowed, reason, retry_after

    try:
        current_time = int(time.time())
        current_minute = current_time // 60
        current_hour = current_time // 3600
        current_day = current_time // 86400

        minute_key = f"rl:{endpoint_tag}:m:{ip}:{current_minute}"
        hour_key = f"rl:{endpoint_tag}:h:{ip}:{current_hour}"
        day_key = f"rl:{endpoint_tag}:d:{ip}:{current_day}"

        # Pipeline atomic increment + expire
        pipe = redis_client.pipeline()
        pipe.incr(minute_key)
        pipe.expire(minute_key, 120)
        pipe.incr(hour_key)
        pipe.expire(hour_key, 7200)
        pipe.incr(day_key)
        pipe.expire(day_key, 90000)
        results = pipe.execute()

        minute_count = results[0]
        hour_count = results[2]
        day_count = results[4]

        if minute_count > limits["minute"]:
            retry_after = 60 - (current_time % 60) + 1
            logger.warning(
                "Rate limit exceeded (minute)",
                extra={"event": "rate_limit_exceeded", "ip": ip, "endpoint": endpoint_tag, "count": minute_count},
            )
            return False, "Rate limit exceeded (requests/min). Please slow down.", max(1, retry_after)

        if hour_count > limits["hour"]:
            retry_after = 3600 - (current_time % 3600) + 1
            logger.warning(
                "Rate limit exceeded (hour)",
                extra={"event": "rate_limit_exceeded", "ip": ip, "endpoint": endpoint_tag, "count": hour_count},
            )
            return False, "Hourly request quota exceeded. Please try again later.", max(1, retry_after)

        if day_count > limits["day"]:
            retry_after = 86400 - (current_time % 86400) + 1
            logger.warning(
                "Rate limit exceeded (day)",
                extra={"event": "rate_limit_exceeded", "ip": ip, "endpoint": endpoint_tag, "count": day_count},
            )
            return False, "Daily API credit protection limit reached. Please try again tomorrow.", max(1, retry_after)

        return True, "", 0

    except Exception as e:
        logger.warning(
            "Redis rate limiter failed, falling back to memory",
            extra={"event": "rate_limiter_redis_error", "error": str(e)},
        )
        return _check_memory_rate_limit(f"{endpoint_tag}:{ip}", limits)
