import pytest
from unittest.mock import patch, MagicMock
from tools.real_tools import (
    get_order_status,
    cancel_order,
    initiate_return,
    fetch_retailer_data,
    USER_FRIENDLY_DB_ERROR
)
import requests

def test_database_connection_dropout_chaos():
    """
    Chaos Test:
    - Simulate database connection dropout (e.g. get_connection raises OperationalError).
    - Verify that get_order_status, cancel_order, and initiate_return recover gracefully,
      returning user-friendly error messages rather than crashing the system.
    """
    with patch("tools.real_tools.get_connection") as mock_get_conn:
        # Simulate PostgreSQL connection timeout / OperationalError
        mock_get_conn.side_effect = Exception("OperationalError: connection to server at localhost:5432 failed: Connection refused")
        
        # 1. get_order_status
        result_status = get_order_status("ORD12345")
        assert "error" in result_status
        assert result_status["error"] == USER_FRIENDLY_DB_ERROR
        
        # 2. cancel_order
        result_cancel = cancel_order("ORD12345")
        assert "error" in result_cancel
        assert result_cancel["error"] == USER_FRIENDLY_DB_ERROR
        
        # 3. initiate_return
        result_return = initiate_return("ORD12345", "defective")
        assert "error" in result_return
        assert result_return["error"] == USER_FRIENDLY_DB_ERROR

def test_external_search_api_timeout_recovery():
    """
    Chaos Test:
    - Simulate Tavily / Serper external search APIs timing out (raising requests.Timeout).
    - Verify that fetch_retailer_data falls back gracefully and handles complete failure
      without crashing the application.
    """
    with patch("requests.Session.post") as mock_post, \
         patch("tools.real_tools.search_products") as mock_search_products:
        
        # Simulate network timeout
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out on api.tavily.com")
        # Simulate catalog fallback returning no products
        mock_search_products.return_value = {"success": False, "message": "No products found."}
        
        result = fetch_retailer_data("Amazon", "Xbox Series X", "UK")
        
        # Verify that it returns an error status rather than crashing
        assert "error" in result
        assert "Search limit exceeded" in result["error"]
