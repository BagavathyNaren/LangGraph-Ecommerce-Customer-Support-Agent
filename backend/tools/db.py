# Compatibility shim — real implementation has moved to infra/db.py
# This file exists so that legacy imports (from tools.db import ...) continue to work
# during the transition period. Remove after Phase 5 test cleanup.
from infra.db import get_connection, get_db_config, get_pool

__all__ = ["get_connection", "get_db_config", "get_pool"]
