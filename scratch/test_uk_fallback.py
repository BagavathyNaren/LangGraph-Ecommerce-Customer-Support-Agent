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

from tools.real_tools import clean_title_for_search, extract_price_from_text


def get_shopping_price_fallback_debug(title: str, currency: str = "USD", gl: str = "us", hl: str = "en") -> str:
    serper_key = os.getenv("SERPER_API_KEY")
    try:
        cleaned_title = clean_title_for_search(title)
        print("Cleaned title:", cleaned_title)

        url = "https://google.serper.dev/shopping"
        headers = {"X-API-KEY": serper_key, "Content-Type": "application/json"}
        words = [w for w in re.findall(r"\w+", cleaned_title) if len(w) > 1]
        search_q = " ".join(words[:6])
        print("Search query:", search_q)

        payload = {"q": search_q, "num": 5, "gl": gl, "hl": hl}
        r = requests.post(url, json=payload, headers=headers, timeout=5)
        if r.status_code == 200:
            res_json = r.json()
            shopping_results = res_json.get("shopping", [])
            print("Shopping results found:", len(shopping_results))
            for item in shopping_results:
                raw_price = item.get("price", "")
                print(f"Match item: '{item.get('title')}' - raw_price: '{raw_price}'")
                price = extract_price_from_text(raw_price, default_currency=currency)
                print(f"  Parsed price: '{price}'")
                if price != "Unknown":
                    return price
    except Exception as e:
        print("Error:", e)
    return "Unknown"


def main():
    print("Testing UK fallback with gl='gb':")
    price = get_shopping_price_fallback_debug("PlayStation Sony 5 Digital Edition - Amazon UK", "GBP", "gb", "en")
    print("Resolved Price:", price)


if __name__ == "__main__":
    main()
