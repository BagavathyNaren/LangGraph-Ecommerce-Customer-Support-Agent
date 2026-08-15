# Compatibility shim — logger moved to infra/logger.py
from infra.logger import JSONFormatter, get_logger

__all__ = ["JSONFormatter", "get_logger"]
