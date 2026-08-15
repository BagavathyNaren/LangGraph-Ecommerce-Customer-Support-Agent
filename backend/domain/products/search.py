import os
import re
import urllib.parse
from infra.db import get_connection
from infra.http import _session
from infra.logger import get_logger
from domain.products.pricing import (
    clean_title_for_search,
    extract_price_from_text,
    get_shopping_price_fallback,
    is_country_supported,
)

logger = get_logger("product-search")

def search_products(query: str, country: str = "India") -> dict:
    """Search the product catalog for available products. Use this BEFORE placing an order so the customer can choose an option."""
    if not is_country_supported(country):
        return {
            "success": False,
            "message": f"We only support ordering and product searches for UAE, Japan, US, UK, and India. Unfortunately, '{country}' is not supported.",
        }
    if not country or str(country).strip().lower() in ["unknown", "none", ""]:
        country = "India"
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Basic search by matching name or category
                search_term = "%" + "%".join(query.split()) + "%"
                cur.execute(
                    """
                    SELECT product_id, name, price, currency, source_website
                    FROM products
                    WHERE (name ILIKE %s OR category ILIKE %s)
                      AND country ILIKE %s AND in_stock = true
                    ORDER BY price ASC
                    LIMIT 5
                """,
                    (search_term, search_term, country),
                )

                rows = cur.fetchall()
                if not rows:
                    return {"success": False, "message": f"No products found matching '{query}' in {country}."}

                products = []
                for row in rows:
                    products.append(
                        {"product_id": row[0], "name": row[1], "price": f"{row[3]} {row[2]:.2f}", "source": row[4]}
                    )
                return {"success": True, "country": country, "products": products}
    except Exception as e:
        logger.error("DB error in search_products", extra={"event": "db_error", "error": str(e), "query": query})
        return {"error": USER_FRIENDLY_DB_ERROR}



def fetch_retailer_data(platform: str, query: str, country: str = "India") -> dict:
    """Unified search routing logic using premium Web Search APIs (Tavily, Serper, or Google CSE)
    instead of Apify, as a robust and high-speed alternative."""
    if not is_country_supported(country):
        return {
            "success": False,
            "message": f"We only support ordering and product searches for UAE, Japan, US, UK, and India. Unfortunately, '{country}' is not supported.",
        }
    import re
    import urllib.parse

    platform = platform.lower().strip()
    country_clean = str(country).strip().lower() if country else "india"

    # Dynamic region maps for multi-country support
    amazon_domain = "amazon.in"
    gl = "in"
    hl = "en"

    if "usa" in country_clean or "united states" in country_clean or country_clean == "us":
        amazon_domain = "amazon.com"
        gl = "us"
        hl = "en"
        currency = "USD"
    elif "japan" in country_clean or country_clean == "jp":
        amazon_domain = "amazon.co.jp"
        gl = "jp"
        hl = "ja"
        currency = "JPY"
    elif (
        "uk" in country_clean
        or "united kingdom" in country_clean
        or "britain" in country_clean
        or country_clean == "gb"
    ):
        amazon_domain = "amazon.co.uk"
        gl = "gb"
        hl = "en"
        currency = "GBP"
    elif (
        "uae" in country_clean
        or "united arab emirates" in country_clean
        or "emirates" in country_clean
        or country_clean == "ae"
    ):
        amazon_domain = "amazon.ae"
        gl = "ae"
        hl = "en"
        currency = "AED"
    elif "india" in country_clean or country_clean == "in":
        amazon_domain = "amazon.in"
        gl = "in"
        hl = "en"
        currency = "INR"
    else:
        currency = "USD"  # default for unknown non-India regions

    # Map platform names to their primary domains
    domain_map = {"amazon": amazon_domain, "flipkart": "flipkart.com", "croma": "croma.com"}
    domain = domain_map.get(platform, amazon_domain)
    platform_name = platform.capitalize()

    # Block Indian-only platforms for non-India countries
    is_india = "india" in country_clean or country_clean == "in" or country_clean == "unknown" or country_clean == ""
    if platform in ["flipkart", "croma"] and not is_india:
        return {
            "success": False,
            "message": f"{platform_name} is only available in India. Please use Amazon for {country}.",
        }

    # Generic storefront titles that indicate a useless result (not a real product listing)
    GENERIC_TITLES = {
        "amazon",
        "amazon.co.jp",
        "amazon.in",
        "amazon.com",
        "amazon.co.uk",
        "amazon.ae",
        "amazon global store",
        "amazon international",
        "flipkart",
        "croma",
        "flipkart.com",
        "croma.com",
    }

    def is_generic_result(title: str) -> bool:
        """Return True if the title is a generic storefront name rather than a real product."""
        if not title:
            return True
        t = title.strip().lower()
        return t in GENERIC_TITLES or t in {g.lower() for g in GENERIC_TITLES}

    def is_valid_price(price: str) -> bool:
        """Return False for prices that are Unknown, Not listed, or ¥0 / $0 (garbage data)."""
        if not price:
            return False
        p_clean = price.strip().lower()
        if p_clean in [
            "unknown",
            "not listed",
            "not_listed",
            "n/a",
            "tbd",
            "none",
            "null",
            "not available",
            "not_available",
        ]:
            return False
        if "not listed" in p_clean or "unknown" in p_clean or "not available" in p_clean or "n/a" in p_clean:
            return False
        # Remove currency symbols and check if numeric value is > 0
        import re as _re_inner

        digits = _re_inner.sub(r"[^\d.]", "", price)
        if not digits:
            return False
        try:
            return float(digits) > 0
        except (ValueError, TypeError):
            # If there are digits but we can't parse a float (e.g. range like "40-50"), keep it
            return True

    # 0. Try SERPER GOOGLE SHOPPING SEARCH (Alternative 1 - Premium Live Prices)
    serper_key = os.getenv("SERPER_API_KEY")
    if serper_key:
        try:
            url = "https://google.serper.dev/shopping"
            headers = {"X-API-KEY": serper_key, "Content-Type": "application/json"}
            # Search strictly for this retailer domain in Google Shopping
            search_query = f"site:{domain} {query}"
            payload = {"q": search_query, "num": 5, "gl": gl, "hl": hl}
            r = _session.post(url, json=payload, headers=headers, timeout=10)
            r.raise_for_status()
            res_json = r.json()
            shopping_results = res_json.get("shopping", [])

            # Fallback: if querying with "site:domain" returns nothing, try querying the retailer name directly
            if not shopping_results:
                search_query_alt = f"{platform_name} {query}"
                payload = {"q": search_query_alt, "num": 5, "gl": gl, "hl": hl}
                r = _session.post(url, json=payload, headers=headers, timeout=10)
                r.raise_for_status()
                res_json = r.json()
                shopping_results = [
                    item
                    for item in res_json.get("shopping", [])
                    if platform.lower() in item.get("source", "").lower() or domain in item.get("link", "").lower()
                ]

            results = []
            for item in shopping_results:
                title = item.get("title", "")
                url_link = item.get("link", "")
                raw_price = item.get("price", "")

                # Skip generic storefront titles (not real products)
                if is_generic_result(title):
                    continue

                # Standarize price format via extraction helper
                price = extract_price_from_text(raw_price, default_currency=currency) if raw_price else "Unknown"
                if price == "Unknown" and raw_price:
                    price = raw_price

                # Skip zero-price garbage results
                if not is_valid_price(price):
                    continue

                results.append(
                    {"title": title, "estimated_price": price, "source": url_link, "platform": platform_name}
                )

            if results:
                logger.info(f"Successfully retrieved structured live shopping prices from Serper for {platform_name}")
                return {"success": True, "platform": platform_name, "results": results}
        except Exception as e:
            logger.error(f"Serper Shopping API failed for {platform}: {e}", exc_info=True)

    # 1. Try TAVILY SEARCH (Recommended)
    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key:
        try:
            url = "https://api.tavily.com/search"
            search_query = f"site:{domain} {query}"
            payload = {"api_key": tavily_key, "query": search_query, "max_results": 5, "include_domains": [domain]}
            r = _session.post(url, json=payload, timeout=10)
            r.raise_for_status()
            tavily_results = r.json().get("results", [])

            results = []
            for item in tavily_results:
                title = item.get("title", "")
                url_link = item.get("url", "")
                snippet = item.get("content", "")

                # Skip generic storefront titles (not real products)
                if is_generic_result(title):
                    continue

                # Extract price if present in title or snippet
                price = extract_price_from_text(title + " " + snippet, default_currency=currency)
                if price == "Unknown":
                    price = get_shopping_price_fallback(title, currency=currency, gl=gl, hl=hl)

                # Filter out unknown or zero prices
                if not is_valid_price(price):
                    continue

                results.append(
                    {"title": title, "estimated_price": price, "source": url_link, "platform": platform_name}
                )
            if results:
                return {"success": True, "platform": platform_name, "results": results}
        except Exception as e:
            logger.error(f"Tavily search failed for {platform}: {e}")

    # 2. Try SERPER GOOGLE SEARCH
    serper_key = os.getenv("SERPER_API_KEY")
    if serper_key:
        try:
            url = "https://google.serper.dev/search"
            headers = {"X-API-KEY": serper_key, "Content-Type": "application/json"}
            search_query = f"site:{domain} {query}"
            payload = {"q": search_query, "num": 5}
            r = _session.post(url, json=payload, headers=headers, timeout=10)
            r.raise_for_status()
            serper_results = r.json().get("organic", [])

            results = []
            for item in serper_results:
                title = item.get("title", "")
                url_link = item.get("link", "")
                snippet = item.get("snippet", "")

                # Skip generic storefront titles (not real products)
                if is_generic_result(title):
                    continue

                # Extract price if present in title or snippet
                price = extract_price_from_text(title + " " + snippet, default_currency=currency)
                if price == "Unknown":
                    price = get_shopping_price_fallback(title, currency=currency, gl=gl, hl=hl)

                # Filter out unknown or zero prices
                if not is_valid_price(price):
                    continue

                results.append(
                    {"title": title, "estimated_price": price, "source": url_link, "platform": platform_name}
                )
            if results:
                return {"success": True, "platform": platform_name, "results": results}
        except Exception as e:
            logger.error(f"Serper search failed for {platform}: {e}")

    # 3. Try GOOGLE CUSTOM SEARCH ENGINE (CSE)
    google_key = os.getenv("GOOGLE_API_KEY")
    google_cx = os.getenv("GOOGLE_CSE_ID")
    if google_key and google_cx:
        try:
            search_query = f"site:{domain} {query}"
            url = f"https://www.googleapis.com/customsearch/v1?key={google_key}&cx={google_cx}&q={urllib.parse.quote(search_query)}"
            r = _session.get(url, timeout=10)
            r.raise_for_status()
            google_results = r.json().get("items", [])

            results = []
            for item in google_results:
                title = item.get("title", "")
                url_link = item.get("link", "")
                snippet = item.get("snippet", "")

                # Extract price if present in title or snippet
                price = extract_price_from_text(title + " " + snippet, default_currency=currency)
                if price == "Unknown":
                    price = get_shopping_price_fallback(title, currency=currency, gl=gl, hl=hl)

                # Filter out unknown or zero prices
                if not is_valid_price(price):
                    continue

                results.append(
                    {"title": title, "estimated_price": price, "source": url_link, "platform": platform_name}
                )
            if results:
                return {"success": True, "platform": platform_name, "results": results}
        except Exception as e:
            logger.error(f"Google CSE failed for {platform}: {e}")

    # 4. KEYLESS DUCKDUCKGO WEB SCRAPER FALLBACK
    try:
        # DDG Lite search fallback
        url = "https://lite.duckduckgo.com/lite/"
        search_query = f"site:{domain} {query}"
        r = _session.post(url, headers={"User-Agent": "Mozilla/5.0"}, data={"q": search_query}, timeout=10)

        # If DDG lite returns 200/202, parse links using regex
        html = r.text
        pattern = r'<a href="([^"]+)"[^>]*class="result-link"[^>]*>(.*?)</a>'
        matches = re.findall(pattern, html, re.DOTALL)

        if not matches:
            pattern_alt = r'<a href="(https?://[^"]+)"[^>]*>(.*?)</a>'
            matches = re.findall(pattern_alt, html)

        results = []
        for href, title in matches:
            title_clean = re.sub(r"<[^>]+>", "", title).strip()
            if "//duckduckgo.com/l/?uddg=" in href:
                actual_url_encoded = href.split("//duckduckgo.com/l/?uddg=")[1].split("&")[0]
                href = urllib.parse.unquote(actual_url_encoded)
            elif href.startswith("//"):
                href = "https:" + href

            if domain in href and "google" not in href and "duckduckgo" not in href:
                price = extract_price_from_text(title_clean, default_currency=currency)
                if price == "Unknown":
                    price = get_shopping_price_fallback(title_clean, currency=currency, gl=gl, hl=hl)

                # Filter out unknown or zero prices
                if not is_valid_price(price):
                    continue

                results.append(
                    {"title": title_clean, "estimated_price": price, "source": href, "platform": platform_name}
                )

        if results:
            return {"success": True, "platform": platform_name, "results": results[:5]}

    except Exception as e:
        logger.error(f"DDG fallback failed for {platform}: {e}")

    # 5. NO-KEY STATIC DB CATALOG MATCH FALLBACK
    # If all online search fails or keys are missing, search local DB products
    try:
        db_res = search_products(query, country)
        if db_res.get("success"):
            results = []
            for p in db_res.get("products", []):
                prod_title = p.get("title", "")
                prod_price = p.get("price", "Unknown")
                prod_source = p.get("source", "https://amazon.in")
                results.append(
                    {
                        "title": prod_title,
                        "estimated_price": prod_price,
                        "source": prod_source,
                        "platform": platform_name,
                    }
                )
            if results:
                return {"success": True, "platform": platform_name, "results": results[:3]}
    except Exception as e:
        logger.error(f"Catalog fallback failed for {platform}: {e}")

    return {"error": f"Search limit exceeded or key not found for {platform_name}."}

