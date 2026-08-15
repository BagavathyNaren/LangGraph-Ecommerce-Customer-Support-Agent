# Compatibility shim — real implementation has moved to infra/logging_tools.py
# Remove after Phase 5 test cleanup.
from infra.logging_tools import log_conversation

__all__ = ["log_conversation"]
