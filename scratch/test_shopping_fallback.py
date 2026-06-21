import os
import re
import sys

import requests
from dotenv import load_dotenv

# Reconfigure stdout to support UTF-8 printing
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))
load_dotenv()


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
            return f"INR {m.group(1)}"

    # 2. Try finding dollar sign
    for m in re.finditer(r"(?:\$|USD)\s*([\d,]+(?:\.\d{2})?)", cleaned, flags=re.IGNORECASE):
        if not is_subscription_or_protection(m.start(), m.end(), cleaned):
            return f"USD {m.group(1)}"

    # 3. Try finding Euro sign
    for m in re.finditer(r"(?:€|EUR)\s*([\d,]+(?:\.\d{2})?)", cleaned, flags=re.IGNORECASE):
        if not is_subscription_or_protection(m.start(), m.end(), cleaned):
            return f"EUR {m.group(1)}"

    # 4. Try finding GBP sign
    for m in re.finditer(r"(?:£|GBP)\s*([\d,]+(?:\.\d{2})?)", cleaned, flags=re.IGNORECASE):
        if not is_subscription_or_protection(m.start(), m.end(), cleaned):
            return f"GBP {m.group(1)}"

    # 5. Try finding JPY/CNY Yen/Yuan sign
    for m in re.finditer(r"(?:¥|JPY|CNY)\s*([\d,]+(?:\.\d{2})?)", cleaned, flags=re.IGNORECASE):
        if not is_subscription_or_protection(m.start(), m.end(), cleaned):
            curr = default_currency if default_currency in ["JPY", "CNY"] else "JPY"
            return f"{curr} {m.group(1)}"

    # 6. Generic number with price context (e.g. "price: 499", "cost 500")
    for m in re.finditer(
        r"\b(?:price|cost|rate|sale|buy|at)\s*[:=-]?\s*([1-9]\d{1,}(?:,\d{3})*(?:\.\d{2})?)\b",
        cleaned,
        flags=re.IGNORECASE,
    ):
        if not is_subscription_or_protection(m.start(), m.end(), cleaned):
            return f"{default_currency} {m.group(1)}"

    return "Unknown"


def get_shopping_price_fallback(title: str, currency: str = "USD", gl: str = "us", hl: str = "en") -> str:
    """Fallback helper to query Google Shopping broadly for a specific product title."""
    serper_key = os.getenv("SERPER_API_KEY")
    if not serper_key:
        return "Unknown"

    try:
        url = "https://google.serper.dev/shopping"
        headers = {"X-API-KEY": serper_key, "Content-Type": "application/json"}
        # Use first 6 words of title for broad match
        words = [w for w in re.findall(r"\w+", title) if len(w) > 1]
        search_q = " ".join(words[:6])
        print(f"Fallback search query: '{search_q}'")

        payload = {"q": search_q, "num": 3, "gl": gl, "hl": hl}
        r = requests.post(url, json=payload, headers=headers, timeout=5)
        if r.status_code == 200:
            res_json = r.json()
            shopping_results = res_json.get("shopping", [])
            if shopping_results:
                for item in shopping_results:
                    raw_price = item.get("price", "")
                    if raw_price:
                        price = extract_price_from_text(raw_price, default_currency=currency)
                        if price != "Unknown":
                            print(f"Match found in fallback: '{item.get('title')}' at price {price}")
                            return price
    except Exception as e:
        print(f"Fallback error: {e}")
    return "Unknown"


def main():
    # Test cases for extract_price_from_text
    print("--- TESTING extract_price_from_text ---")

    # 1. Protection plan price
    text1 = "Sony PlayStation 5 Console (Renewed) : Complete Protect: One plan covers all for $16.99/month."
    print("Test 1 (Protection Plan):", extract_price_from_text(text1, "USD"))

    # 2. Model number
    text2 = "PlayStation PS5 HW 1115 STANDARD_US - Amazon.com"
    print("Test 2 (Model Number):", extract_price_from_text(text2, "USD"))

    # 3. Valid price with context
    text3 = "Buy Sony PlayStation 5 at 499 on Amazon"
    print("Test 3 (Price with Context):", extract_price_from_text(text3, "USD"))

    # Test cases for get_shopping_price_fallback
    print("\n--- TESTING get_shopping_price_fallback ---")
    titles = [
        "Sony PlayStation 5 PS5 Disc Version Gaming Console",
        "Sony Playstation 5 Digital Edition PS5 Console",
        "PlayStation®5 console – 1TB",
    ]
    for t in titles:
        print(f"\nProduct: '{t}'")
        price = get_shopping_price_fallback(t, "USD", "us", "en")
        print(f"Resolved Price: {price}")


if __name__ == "__main__":
    main()
