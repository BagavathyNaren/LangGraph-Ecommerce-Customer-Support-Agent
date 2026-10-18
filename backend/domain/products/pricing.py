import os
import re
from infra.http import _session
from infra.logger import get_logger

logger = get_logger("pricing")

def is_country_supported(country: str) -> bool:
    if not country:
        return False
    c = str(country).strip().lower()
    supported = {
        "uae",
        "united arab emirates",
        "emirates",
        "ae",
        "japan",
        "jp",
        "usa",
        "united states",
        "us",
        "uk",
        "united kingdom",
        "britain",
        "gb",
        "india",
        "in",
    }
    return c in supported



def extract_price_from_text(text: str, default_currency: str = "INR") -> str:
    """Helper to extract estimated price in various currencies from title or snippet."""

    # Clean text to remove common numeric specs to avoid false matches (e.g. 200 MP, 512 GB)
    cleaned = re.sub(
        r"\b\d+\s*(?:MP|GB|RAM|Hz|W|mAh|cm|inch|inches|fps|GB|TB|Gen\s*\d|Core\s*i\d|Ryzen\s*\d)\b",
        "",
        text,
        flags=re.IGNORECASE,
    )

    def is_subscription_or_protection(match_start, match_end, full_text):
        # Look at the context after the match
        after = full_text[match_end:].strip().lower()
        if re.match(r"^(?:\/|per\s+|a\s+)?(?:month|mo|year|yr|week|wk|day|annum)\b", after):
            return True
        # Also check if it's part of a protection plan phrase
        before = full_text[:match_start].lower()
        if any(keyword in before for keyword in ["protect", "protection", "warranty", "insurance"]):
            return True
        return False

    # 1. Try finding INR rupee sign and digit
    for m in re.finditer(r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d{2})?)", cleaned, flags=re.IGNORECASE):
        if not is_subscription_or_protection(m.start(), m.end(), cleaned):
            return f"₹{m.group(1)}"

    # 2. Try finding dollar sign
    for m in re.finditer(r"(?:\$|USD)\s*([\d,]+(?:\.\d{2})?)", cleaned, flags=re.IGNORECASE):
        if not is_subscription_or_protection(m.start(), m.end(), cleaned):
            return f"${m.group(1)}"

    # 3. Try finding Euro sign
    for m in re.finditer(r"(?:€|EUR)\s*([\d,]+(?:\.\d{2})?)", cleaned, flags=re.IGNORECASE):
        if not is_subscription_or_protection(m.start(), m.end(), cleaned):
            return f"€{m.group(1)}"

    # 4. Try finding GBP sign
    for m in re.finditer(r"(?:£|GBP)\s*([\d,]+(?:\.\d{2})?)", cleaned, flags=re.IGNORECASE):
        if not is_subscription_or_protection(m.start(), m.end(), cleaned):
            return f"£{m.group(1)}"

    # 5. Try finding JPY/CNY Yen/Yuan sign — return proper currency symbols, not ISO codes
    for m in re.finditer(r"(?:¥|￥|JPY|CNY)\s*([\d,]+(?:\.\d{2})?)", cleaned, flags=re.IGNORECASE):
        if not is_subscription_or_protection(m.start(), m.end(), cleaned):
            curr = default_currency if default_currency in ["JPY", "CNY"] else "JPY"
            symbol = "￥" if curr == "JPY" else "¥"  # Full-width ￥ for JPY, half-width ¥ for CNY
            return f"{symbol}{m.group(1)}"

    # 5b. Try finding AED/Dirham sign
    for m in re.finditer(r"(?:AED|د\.إ)\s*([\d,]+(?:\.\d{2})?)", cleaned, flags=re.IGNORECASE):
        if not is_subscription_or_protection(m.start(), m.end(), cleaned):
            return f"AED {m.group(1)}"

    # 6. Generic number with price context (e.g. "price: 499", "cost 500")
    # Map ISO codes to symbols for the generic fallback
    _CURRENCY_SYMBOL_MAP = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "￥", "CNY": "¥", "AED": "AED "}
    for m in re.finditer(
        r"\b(?:price|cost|rate|sale|buy|at)\s*[:=-]?\s*([1-9]\d{1,}(?:,\d{3})*(?:\.\d{2})?)\b",
        cleaned,
        flags=re.IGNORECASE,
    ):
        if not is_subscription_or_protection(m.start(), m.end(), cleaned):
            sym = _CURRENCY_SYMBOL_MAP.get(default_currency.upper(), default_currency + " ")
            return f"{sym}{m.group(1)}"

    return "Unknown"


def clean_title_for_search(title: str) -> str:
    """Helper to strip site prefix and suffix metadata for highly accurate search queries."""

    cleaned = title
    # Remove common prefix patterns (e.g. "Amazon.com: ", "亚马逊海外购：")
    cleaned = re.sub(
        r"^(?:Amazon\.(?:com|in|co\.jp|cn)|Amazon|Flipkart|Croma|亚马逊海外购|亚马逊)\s*[:|：|-]\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Remove common suffix patterns (e.g. " : Everything Else - Amazon.com", " - Croma")
    cleaned = re.sub(
        r"\s*[:|：|-]\s*(?:Amazon\.(?:com|in|co\.jp|cn)|Amazon|Flipkart|Croma|亚马逊海外购|亚马逊|Video Games|Electronics|Everything Else|Home Audio|Mobile Phones|Smartphones).*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Clean non-alphanumeric chars (like ®, ™) to keep search simple
    cleaned = re.sub(r"[®™]", "", cleaned)
    return cleaned.strip()


def get_shopping_price_fallback(title: str, currency: str = "USD", gl: str = "us", hl: str = "en") -> str:
    """Fallback helper to query Google Shopping broadly for a specific product title
    to retrieve a realistic price if organic search returned 'Unknown'."""

    serper_key = os.getenv("SERPER_API_KEY")
    if not serper_key:
        return "Unknown"

    try:
        # Clean title to remove SEO prefixes/suffixes
        cleaned_title = clean_title_for_search(title)

        url = "https://google.serper.dev/shopping"
        headers = {"X-API-KEY": serper_key, "Content-Type": "application/json"}
        # Use first 6 words of the cleaned title for broad matching
        words = [w for w in re.findall(r"\w+", cleaned_title) if len(w) > 1]
        search_q = " ".join(words[:6])

        payload = {"q": search_q, "num": 3, "gl": gl, "hl": hl}
        r = _session.post(url, json=payload, headers=headers, timeout=5)
        if r.status_code == 200:
            res_json = r.json()
            shopping_results = res_json.get("shopping", [])
            if shopping_results:
                for item in shopping_results:
                    raw_price = item.get("price", "")
                    if raw_price:
                        price = extract_price_from_text(raw_price, default_currency=currency)
                        if price != "Unknown":
                            return price
    except Exception as e:
        logger.error(f"Shopping price fallback failed for title '{title}': {e}")
    return "Unknown"

