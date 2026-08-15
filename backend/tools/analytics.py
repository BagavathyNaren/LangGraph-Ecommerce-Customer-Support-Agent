# Compatibility shim — real analytics functions moved to domain/analytics.py
# Remove after Phase 5 test cleanup.
from domain.analytics import get_analytics_summary, init_analytics_db, log_event

__all__ = ["get_analytics_summary", "init_analytics_db", "log_event"]
