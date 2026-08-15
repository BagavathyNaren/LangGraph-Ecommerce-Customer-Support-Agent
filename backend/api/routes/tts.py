import os
import requests as req
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response as FastResponse
from infra.logger import get_logger

logger = get_logger("tts-route")
router = APIRouter()

TTS_MODEL = "tts-1"
HTTP_TIMEOUT = 60  # seconds


@router.get("/tts")
def generate_speech_audio(text: str):
    """Proxy TTS audio through the backend using OpenAI's TTS API.
    Uses the 'echo' voice (clear, warm male) and tts-1 for low-latency, loud and clear output.
    """
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")

        url = "https://api.openai.com/v1/audio/speech"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        data = {"model": TTS_MODEL, "input": text, "voice": "echo", "response_format": "mp3"}
        r = req.post(url, headers=headers, json=data, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return FastResponse(
            content=r.content,
            media_type="audio/mpeg",
            headers={
                "Cache-Control": "public, max-age=86400",
                "Access-Control-Allow-Origin": "*",
            },
        )
    except Exception as e:
        logger.warning(f"TTS proxy error: {e}")
        raise HTTPException(status_code=502, detail="TTS service unavailable")
