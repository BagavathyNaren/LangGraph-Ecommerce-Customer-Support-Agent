# Compatibility shim — logger moved to infra/logger.py
from infra.logger import StructuredLogger, get_logger

__all__ = ["StructuredLogger", "get_logger"]
