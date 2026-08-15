# Compatibility shim — domain logic has been split into backend/domain/ and backend/infra/
# All tools and tests importing from tools.real_tools will continue to work seamlessly.

from domain.analytics import get_analytics_summary
from domain.customers import get_customer_orders, register_new_customer
from domain.knowledge import search_knowledge_base
from domain.orders import cancel_order, get_order_status, place_new_order, update_order_from_webhook
from domain.products.pricing import (
    clean_title_for_search,
    extract_price_from_text,
    get_shopping_price_fallback,
    is_country_supported,
)
from domain.products.search import fetch_retailer_data, search_products
from domain.refunds import get_refund_status, initiate_return
from domain.rules import SUPPORTED_COUNTRIES, USER_FRIENDLY_DB_ERROR
from domain.tickets import create_support_ticket
from infra.http import _create_retry_session, _session

__all__ = [
    "_create_retry_session",
    "_session",
    "is_country_supported",
    "get_order_status",
    "get_refund_status",
    "initiate_return",
    "cancel_order",
    "update_order_from_webhook",
    "get_customer_orders",
    "register_new_customer",
    "search_products",
    "extract_price_from_text",
    "clean_title_for_search",
    "get_shopping_price_fallback",
    "fetch_retailer_data",
    "place_new_order",
    "search_knowledge_base",
    "create_support_ticket",
    "get_analytics_summary",
    "USER_FRIENDLY_DB_ERROR",
    "SUPPORTED_COUNTRIES",
]
