import re
from pydantic import BaseModel, Field, field_validator

BANNED_PATTERNS = [
    r"<script.*?>",
    r"javascript:",
    r"\.\./",
    r"lc_kwargs",
    r"lc_serializable",
    r"(?i)(drop|delete|truncate)\s+table",
    r"(?i)ignore\s+previous\s+instructions",
    r"(?i)you\s+are\s+now\s+a",
]


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    thread_id: str = Field(default="default", min_length=1, max_length=100)
    email: str = Field(default=None)  # Explicit email from frontend for customer registration

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

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if v is not None:
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
                raise ValueError("Invalid email address format.")
        return v


class WebhookPayload(BaseModel):
    order_id: str = Field(..., description="The ID of the order")
    status: str = Field(..., description="The new status of the order (e.g. delivered)")
    carrier: str = Field(default=None, description="The shipping carrier")
    timestamp: str = Field(default=None, description="Event timestamp")
    secret: str = Field(..., description="Webhook authentication secret")
