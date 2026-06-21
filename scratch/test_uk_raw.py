import os
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


def main():
    serper_key = os.getenv("SERPER_API_KEY")
    url = "https://google.serper.dev/shopping"
    headers = {"X-API-KEY": serper_key, "Content-Type": "application/json"}

    q = "PlayStation Sony 5 Digital Edition"
    print(f"Searching Shopping in UK for: {q}")
    payload = {"q": q, "num": 3, "gl": "uk", "hl": "en"}
    r = requests.post(url, json=payload, headers=headers)
    try:
        res = r.json()
        items = res.get("shopping", [])
        print("Raw items returned:", len(items))
        for i, item in enumerate(items):
            print(f"\nItem #{i + 1}:")
            print("Title:", item.get("title"))
            print("Price:", item.get("price"))
            print("Source:", item.get("source"))
            print("Link:", item.get("link"))
    except Exception as e:
        print("Error:", e)


if __name__ == "__main__":
    main()
