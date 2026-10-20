import base64
import hashlib
import os
import requests as req
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response as FastResponse

from infra.cache.redis_cache import get_redis_client
from infra.logger import get_logger

logger = get_logger("tts-route")
router = APIRouter()

TTS_MODEL = "tts-1"
HTTP_TIMEOUT = 30  # seconds
MAX_TTS_TEXT_LENGTH = 300  # Cap characters to prevent credit exhaustion
TTS_CACHE_TTL = 86400 * 3  # 3 days cache for repeated phrases


@router.get("/tts")
def generate_speech_audio(text: str):
    """Proxy TTS audio through the backend using OpenAI's TTS API.

    Protected with:
    - Max length enforcement (300 chars max)
    - Redis audio caching (eliminates repetitive OpenAI TTS billing)
    """
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    cleaned_text = text.strip()
    if len(cleaned_text) > MAX_TTS_TEXT_LENGTH:
        cleaned_text = cleaned_text[:MAX_TTS_TEXT_LENGTH]

    # 1. Check Redis Cache for pre-generated audio
    cache_key = "tts:v1:" + hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()
    redis_client = get_redis_client()
    if redis_client:
        try:
            cached_b64 = redis_client.get(cache_key)
            if cached_b64:
                logger.info("TTS cache hit", extra={"event": "tts_cache_hit", "text_len": len(cleaned_text)})
                audio_bytes = base64.b64decode(cached_b64)
                return FastResponse(
                    content=audio_bytes,
                    media_type="audio/mpeg",
                    headers={"Cache-Control": "public, max-age=86400"},
                )
        except Exception as e:
            logger.warning("TTS cache lookup error", extra={"event": "tts_cache_error", "error": str(e)})

    # 2. Call OpenAI TTS API
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

        url = "https://api.openai.com/v1/audio/speech"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        data = {"model": TTS_MODEL, "input": cleaned_text, "voice": "echo", "response_format": "mp3"}

        r = req.post(url, headers=headers, json=data, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        audio_content = r.content

        # 3. Store in Redis Cache
        if redis_client:
            try:
                b64_content = base64.b64encode(audio_content).decode("ascii")
                redis_client.setex(cache_key, TTS_CACHE_TTL, b64_content)
                logger.info("TTS audio cached", extra={"event": "tts_cache_stored"})
            except Exception as e:
                logger.warning("TTS cache store error", extra={"event": "tts_cache_store_error", "error": str(e)})

        return FastResponse(
            content=audio_content,
            media_type="audio/mpeg",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except req.RequestException as e:
        logger.warning(f"OpenAI TTS API error: {e}")
        raise HTTPException(status_code=502, detail="TTS service unavailable")
    except Exception as e:
        logger.error(f"TTS internal error: {e}")
        raise HTTPException(status_code=500, detail="TTS generation failed")
