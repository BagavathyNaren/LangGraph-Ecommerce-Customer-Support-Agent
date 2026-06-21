import os

from pydantic import BaseModel, Field, model_validator

from logger import get_logger

logger = get_logger("env-validator")


class EnvSettings(BaseModel):
    OPENAI_API_KEY: str = Field(default="")
    DATABASE_URL: str = Field(default="")
    CLOUD_SQL_CONNECTION_NAME: str = Field(default="")
    EMAIL_PROVIDER: str = Field(default="resend")
    RESEND_API_KEY: str = Field(default="")
    GMAIL_SENDER_EMAIL: str = Field(default="")
    GMAIL_APP_PASSWORD: str = Field(default="")
    TAVILY_API_KEY: str = Field(default="")
    SERPER_API_KEY: str = Field(default="")

    @model_validator(mode="after")
    def validate_dependencies(self) -> "EnvSettings":
        # 1. OpenAI Key validation
        if not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY must be provided and cannot be empty.")

        # 2. Database validation
        if not self.DATABASE_URL and not self.CLOUD_SQL_CONNECTION_NAME:
            raise ValueError(
                "Either DATABASE_URL or CLOUD_SQL_CONNECTION_NAME must be provided in the environment variables."
            )

        # 3. Email provider validation
        provider = self.EMAIL_PROVIDER.lower().strip()
        if provider == "gmail":
            if not self.GMAIL_SENDER_EMAIL or not self.GMAIL_APP_PASSWORD:
                raise ValueError(
                    "When EMAIL_PROVIDER is 'gmail', both GMAIL_SENDER_EMAIL and GMAIL_APP_PASSWORD must be provided."
                )
        elif provider == "resend":
            if not self.RESEND_API_KEY:
                raise ValueError("When EMAIL_PROVIDER is 'resend', RESEND_API_KEY must be provided.")
        else:
            raise ValueError(
                f"Unsupported EMAIL_PROVIDER '{self.EMAIL_PROVIDER}'. Supported providers are 'gmail' or 'resend'."
            )

        # 4. Search API warning
        if not self.TAVILY_API_KEY and not self.SERPER_API_KEY:
            logger.warning(
                "Neither TAVILY_API_KEY nor SERPER_API_KEY is configured. Product search operations will fail.",
                extra={"event": "env_warning", "reason": "no_search_api_configured"},
            )

        return self


def validate_env():
    """Validate environment variables. Raises ValueError on failure."""
    logger.info("Initializing environment variable validation checks...", extra={"event": "env_validation_start"})
    try:
        # Load from os.environ
        data = {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
            "DATABASE_URL": os.environ.get("DATABASE_URL", ""),
            "CLOUD_SQL_CONNECTION_NAME": os.environ.get("CLOUD_SQL_CONNECTION_NAME", ""),
            "EMAIL_PROVIDER": os.environ.get("EMAIL_PROVIDER", "resend"),
            "RESEND_API_KEY": os.environ.get("RESEND_API_KEY", ""),
            "GMAIL_SENDER_EMAIL": os.environ.get("GMAIL_SENDER_EMAIL", ""),
            "GMAIL_APP_PASSWORD": os.environ.get("GMAIL_APP_PASSWORD", ""),
            "TAVILY_API_KEY": os.environ.get("TAVILY_API_KEY", ""),
            "SERPER_API_KEY": os.environ.get("SERPER_API_KEY", ""),
        }

        settings = EnvSettings(**data)
        logger.info("Environment variable validation succeeded.", extra={"event": "env_validation_success"})
        return settings
    except Exception as e:
        logger.error(
            f"Environment variable validation FAILED: {str(e)}",
            extra={"event": "env_validation_failed", "error": str(e)},
        )
        raise ValueError(f"Strict environment variable validation failed: {str(e)}") from e
