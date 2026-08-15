# Compatibility shim — real event logging moved to domain/analytics.py
# get_analytics_summary stays in tools/real_tools.py for now (moved in Phase 2.2)
# Remove after Phase 5 test cleanup.
from domain.analytics import init_analytics_db, log_event
from tools.real_tools import get_analytics_summary

__all__ = ["get_analytics_summary", "init_analytics_db", "log_event"]
