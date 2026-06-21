import pytest
from tools.real_tools import (
    is_country_supported,
    get_order_status,
    get_refund_status,
    initiate_return,
    cancel_order,
    get_customer_orders,
    register_new_customer,
    clean_title_for_search,
    extract_price_from_text,
    search_products,
    fetch_retailer_data
)

def test_is_country_supported():
    assert is_country_supported("UK") is True
    assert is_country_supported("Japan") is True
    assert is_country_supported("UAE") is True
    assert is_country_supported("India") is True
    assert is_country_supported("USA") is True
    assert is_country_supported("US") is True
    assert is_country_supported("Germany") is False
    assert is_country_supported("China") is False
    assert is_country_supported(None) is False
    assert is_country_supported("") is False

def test_get_order_status(mock_db_connection):
    result = get_order_status("ORD12345")
    assert result["order_id"] == "ORD12345"
    assert result["status"] == "delivered"
    assert result["item"] == "Xbox Series X"

def test_get_refund_status(mock_db_connection):
    result = get_refund_status("ORD12345")
    assert result["refund_id"] == "RFD12345"
    assert result["refund_status"] == "approved"
    assert result["amount"] == 45000.0

def test_initiate_return(mock_db_connection):
    result = initiate_return("ORD12345", "Item defective")
    assert result["success"] is True
    assert "pickup" in result["message"].lower()

def test_cancel_order(mock_db_connection):
    result = cancel_order("ORD12345")
    assert result["success"] is True

def test_get_customer_orders(mock_db_connection):
    result = get_customer_orders("Shin")
    assert "customer" in result
    assert len(result["orders"]) > 0
    assert result["orders"][0]["order_id"] == "ORD12345"

def test_register_new_customer(mock_db_connection):
    result = register_new_customer("Shin", "shin@gmail.com", "1234567890", "UK")
    assert result["success"] is True
    assert "successfully registered" in result["message"]

def test_clean_title_for_search():
    assert clean_title_for_search("Amazon.com: Sony PlayStation 5 Console®") == "Sony PlayStation 5 Console"
    assert clean_title_for_search("Xbox One X 1TB : Video Games - Amazon") == "Xbox One X 1TB"

def test_extract_price_from_text():
    assert extract_price_from_text("It costs £450.00 today") == "£450.00"
    assert extract_price_from_text("Price is $299") == "$299"
    assert extract_price_from_text("Only ₹45,000 for this product") == "₹45,000"
    assert extract_price_from_text("No price information", default_currency="INR") == "Unknown"

def test_search_products(mock_http_requests):
    result = search_products("Xbox", "UK")
    assert result["success"] is True
    assert len(result["products"]) > 0
    for prod in result["products"]:
        assert prod["price"] != "Unknown"
        assert prod["price"] != "Not listed"

def test_fetch_retailer_data(mock_http_requests):
    result = fetch_retailer_data("Amazon", "Xbox", "UK")
    assert len(result["results"]) > 0
    for prod in result["results"]:
        assert prod["estimated_price"] is not None
        assert "not listed" not in prod["estimated_price"].lower()
