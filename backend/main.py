import asyncio
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from agent.graph_builder import build_graph, set_graph
from api.middleware import setup_middleware
from api.routes import (
    chat_router,
    cron_router,
    evaluate_router,
    health_router,
    tts_router,
    webhooks_router,
)
from domain.analytics import init_analytics_db
from infra.db import get_connection
from infra.logger import get_logger
from infra.security.env_validator import validate_env

os.environ["LANGCHAIN_TRACING_V2"] = os.environ.get("LANGCHAIN_TRACING_V2", "false")
os.environ["LANGCHAIN_API_KEY"] = os.environ.get("LANGCHAIN_API_KEY", "")
os.environ["LANGCHAIN_PROJECT"] = os.environ.get("LANGCHAIN_PROJECT", "ecommerce-support-agent")

logger = get_logger("ecommerce-agent")

is_configured = True
try:
    validate_env()
except ValueError as e:
    print(f"CRITICAL: Environment validation failed: {e}. Running in unconfigured mode.")
    is_configured = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up agent", extra={"event": "startup"})
    if not is_configured:
        logger.warning(
            "Application is running in unconfigured mode. Skipping DB and Graph initialization.",
            extra={"event": "startup_skip"},
        )
        yield
        return

    init_analytics_db()
    # Ensure database schema is up-to-date
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    ALTER TABLE customers
                    ADD COLUMN IF NOT EXISTS phone_number VARCHAR(20) DEFAULT NULL;
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_customers_phone
                    ON customers(phone_number);
                """)
                cur.execute("DROP INDEX IF EXISTS uq_open_ticket_per_order_issue")
                cur.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_one_open_ticket_per_order
                    ON support_tickets (order_id, customer_id)
                    WHERE status = 'open' AND customer_id IS NOT NULL;
                """)
                cur.execute("""
                    ALTER TABLE customers
                    ADD COLUMN IF NOT EXISTS country VARCHAR(50) DEFAULT NULL;
                """)
                cur.execute("""
                    ALTER TABLE orders
                    ADD COLUMN IF NOT EXISTS product_id VARCHAR(20) DEFAULT NULL,
                    ADD COLUMN IF NOT EXISTS price DECIMAL(10,2) DEFAULT NULL,
                    ADD COLUMN IF NOT EXISTS source_website VARCHAR(100) DEFAULT NULL;
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS products (
                        product_id VARCHAR(20) PRIMARY KEY,
                        name VARCHAR(200) NOT NULL,
                        category VARCHAR(100),
                        price DECIMAL(10,2) NOT NULL,
                        currency VARCHAR(3) DEFAULT 'INR',
                        country VARCHAR(50) NOT NULL,
                        source_website VARCHAR(100),
                        in_stock BOOLEAN DEFAULT true,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cur.execute("SELECT COUNT(*) FROM products")
                if cur.fetchone()[0] == 0:
                    seed_products = [
                        ("PRD-TV-001", 'Sony Bravia 55\" 4K Smart TV', "Electronics", 54990.00, "INR", "India", "Amazon India", True),
                        ("PRD-TV-002", 'Sony Bravia 50\" 4K Smart TV', "Electronics", 49990.00, "INR", "India", "Flipkart", True),
                        ("PRD-TV-003", 'Sony Bravia 43\" 4K Smart TV', "Electronics", 39990.00, "INR", "India", "Croma", True),
                        ("PRD-SH-001", "Nike Air Max Running Shoes", "Fashion", 8995.00, "INR", "India", "Myntra", True),
                        ("PRD-SH-002", "Nike Air Force 1 Sneakers", "Fashion", 7495.00, "INR", "India", "Amazon India", True),
                        ("PRD-SB-001", "Adidas FIFA Pro Soccer Ball", "Sports", 2999.00, "INR", "India", "Amazon India", True),
                        ("PRD-SB-002", "Puma La Liga Trainer Ball", "Sports", 1999.00, "INR", "India", "Flipkart", True),
                    ]
                    cur.executemany(
                        """
                        INSERT INTO products (product_id, name, category, price, currency, country, source_website, in_stock)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        seed_products,
                    )
                    logger.info("Seeded products table", extra={"event": "db_seed"})
        logger.info(
            "DB migration: schema verified (phone_number + unique ticket index)", extra={"event": "db_migration"}
        )
    except Exception as e:
        logger.warning(f"DB migration warning: {e}", extra={"event": "db_migration_warning"})

    # Asynchronously build graph in background
    loop = asyncio.get_event_loop()

    async def _build_graph_bg():
        try:
            g = await loop.run_in_executor(None, build_graph)
            set_graph(g)
            logger.info("Graph built successfully", extra={"event": "graph_ready"})
        except Exception as e:
            logger.error(f"Graph build failed: {e}", extra={"event": "graph_failed"})

    asyncio.create_task(_build_graph_bg())
    yield
    logger.info("Shutting down", extra={"event": "shutdown"})


app = FastAPI(lifespan=lifespan)

# Setup middleware (CORS & configuration gate)
setup_middleware(app, is_configured=is_configured)

# Register modular API routers
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(tts_router)
app.include_router(cron_router)
app.include_router(webhooks_router)
app.include_router(evaluate_router)
