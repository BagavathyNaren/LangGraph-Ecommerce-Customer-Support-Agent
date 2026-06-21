import os
import sys
from unittest.mock import MagicMock, patch


# 1. Globally mock psycopg and psycopg_pool before any other project imports
class ConnectionPool:
    def __class_getitem__(cls, item):
        return cls


class Connection:
    def __class_getitem__(cls, item):
        return cls


class Pipeline:
    def __class_getitem__(cls, item):
        return cls


class DictRow:
    pass


mock_psycopg_pool = MagicMock()
mock_psycopg_pool.ConnectionPool = ConnectionPool
mock_psycopg_pool.Pipeline = Pipeline
sys.modules["psycopg_pool"] = mock_psycopg_pool

mock_psycopg = MagicMock()
mock_psycopg.Connection = Connection
mock_psycopg.rows.DictRow = DictRow
sys.modules["psycopg"] = mock_psycopg
sys.modules["psycopg.rows"] = MagicMock()
sys.modules["psycopg.types"] = MagicMock()
sys.modules["psycopg.types.json"] = MagicMock()

# Now import tools.db and override its functions at module load time!
import tools.db

# Global connection mocks
mock_conn = MagicMock()
mock_cursor = MagicMock()

# Setup cursors and connection context managers
mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
mock_conn.__enter__.return_value = mock_conn

mock_connection_ctx = MagicMock()
mock_connection_ctx.__enter__.return_value = mock_conn

# Assign the module overrides
tools.db.get_connection = lambda: mock_connection_ctx
tools.db.get_pool = lambda: MagicMock()

import pytest

# Set dummy environment variables for tests
os.environ["DATABASE_URL"] = "postgresql://dummy:dummy@localhost:5432/dummy"
os.environ["OPENAI_API_KEY"] = "sk-dummy-key-for-testing"
os.environ["TAVILY_API_KEY"] = "tvly-dummy-key"
os.environ["SERPER_API_KEY"] = "serper-dummy-key"


@pytest.fixture(autouse=True)
def mock_db_connection():
    """
    Globally mocks psycopg connection pool and database access context managers.
    Prevents tests from attempting to connect to a real PostgreSQL instance.
    """

    # Pre-populate cursor fetch results for common SQL queries
    def execute_side_effect(query, params=None):
        query_str = query.strip().lower() if isinstance(query, str) else ""

        # 1. get_refund_status (6 columns)
        if "refunds" in query_str and "status" in query_str:
            mock_cursor.fetchone.return_value = ("RFD12345", "approved", 45000.0, "2026-06-01", "damaged", "2026-05-30")

        # 2. Existing refund check in initiate_return (return None so no duplicate refund)
        elif "refunds" in query_str and "refund_id" in query_str:
            mock_cursor.fetchone.return_value = None

        # 3. get_customer_orders (left join - 9 columns)
        elif "left join" in query_str:
            mock_cursor.fetchall.return_value = [
                (
                    "cust_1",
                    "Shin",
                    "shin@gmail.com",
                    "UK",
                    "ORD12345",
                    "delivered",
                    "Xbox Series X",
                    "2026-06-01",
                    "TRK123",
                )
            ]

        # 4. User registration check in register_new_customer (return None so user doesn't exist yet)
        elif "customer_id" in query_str and "email" in query_str:
            mock_cursor.fetchone.return_value = None

        # 5. cancel_order customer info (3 columns)
        elif "email" in query_str and "telegram_chat_id" in query_str:
            mock_cursor.fetchone.return_value = ("shin@gmail.com", "Shin", "telegram_123")

        # 5.5 Support ticket creation customer/status fetch
        elif "customer_id" in query_str and "status" in query_str and "orders" in query_str:
            mock_cursor.fetchone.return_value = ("cust_1", "delivered")

        # 6. get_order_status / cancel_order status check (4 columns for select, or single status)
        elif "status" in query_str and "orders" in query_str and "item" not in query_str:
            # Inspect call stack to see if cancel is being executed
            frame = sys._getframe()
            is_cancel = False
            while frame:
                if "cancel" in frame.f_code.co_name.lower():
                    is_cancel = True
                    break
                frame = frame.f_back

            if is_cancel:
                mock_cursor.fetchone.return_value = ("placed",)
            else:
                mock_cursor.fetchone.return_value = ("delivered",)
        elif "order_id" in query_str and "orders" in query_str and "item" in query_str:
            mock_cursor.fetchone.return_value = ("ORD12345", "delivered", "Xbox Series X", "2026-06-01")

        # 7. products catalog search
        elif "products" in query_str:
            mock_cursor.fetchall.return_value = [("PROD123", "Xbox Series X Console", 479.99, "£", "Amazon")]
        elif "orders" in query_str and "customer_id" in query_str:
            mock_cursor.fetchall.return_value = [("ORD12345", "delivered", "Xbox Series X", 45000.0, "2026-06-01")]
            mock_cursor.fetchone.return_value = ("ORD12345", "delivered", "Xbox Series X", 45000.0, "2026-06-01")

        # 7.5 Customer name query for support ticket identity verification
        elif "name" in query_str and "customers" in query_str and "customer_id" in query_str:
            mock_cursor.fetchone.return_value = ("Shin Chan",)

        # 7.8 Support ticket duplicate check (return None to indicate no duplicate)
        elif "support_tickets" in query_str:
            mock_cursor.fetchone.return_value = None

        # 8. default cases
        else:
            mock_cursor.fetchone.return_value = ("cust_1", "Shin", "shin@gmail.com", "UK")
            mock_cursor.fetchall.return_value = []

    mock_cursor.execute.side_effect = execute_side_effect
    yield mock_conn


@pytest.fixture(autouse=True)
def mock_http_requests():
    """
    Mocks standard requests.Session and raw request methods globally.
    Redirects search engine calls to deterministic, valid mock results.
    """

    def get_side_effect(url, *args, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        url_lower = url.lower()

        # StreamElements TTS Brian Voice Mock response
        if "tts" in url_lower or "api.streamelements.com" in url_lower:
            resp.content = b"fake-mp3-audio-content"
        else:
            resp.json.return_value = {}
        return resp

    def post_side_effect(url, *args, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        url_lower = url.lower()

        # Tavily Search API Mock response
        if "tavily" in url_lower:
            resp.json.return_value = {
                "results": [
                    {
                        "title": "Microsoft Xbox Series X Console",
                        "url": "https://www.amazon.co.uk/xbox-series-x",
                        "content": "Buy Xbox Series X Console at Amazon UK for £479.99 today.",
                    }
                ]
            }
        # Serper Shopping Search Mock response
        elif "google.serper.dev/shopping" in url_lower or "serper" in url_lower:
            resp.json.return_value = {
                "shopping": [
                    {
                        "title": "Microsoft Xbox Series X 1TB Digital Console",
                        "price": "£436.00",
                        "link": "https://www.amazon.co.uk/xbox-1tb-digital",
                        "source": "Amazon.co.uk",
                    }
                ]
            }
        else:
            resp.json.return_value = {}
        return resp

    with (
        patch("requests.Session.get") as mock_session_get,
        patch("requests.Session.post") as mock_session_post,
        patch("requests.get") as mock_get,
        patch("requests.post") as mock_post,
    ):
        mock_session_get.side_effect = get_side_effect
        mock_session_post.side_effect = post_side_effect
        mock_get.side_effect = get_side_effect
        mock_post.side_effect = post_side_effect
        yield


@pytest.fixture
def mock_llm_response():
    """
    Helper fixture to patch LangChain ChatOpenAI responses for integration tests.
    Allows simulating specific multi-turn dialogues deterministically.
    """
    mock_chat = MagicMock()
    mock_ai_message = MagicMock()
    mock_ai_message.content = "Certainly! I will find an Xbox for you in the UK."
    mock_chat.invoke.return_value = mock_ai_message

    with patch("langchain_openai.ChatOpenAI") as mock_chat_cls:
        mock_chat_cls.return_value = mock_chat
        yield mock_chat
