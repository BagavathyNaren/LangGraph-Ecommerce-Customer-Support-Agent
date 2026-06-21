import os

import requests
from dotenv import load_dotenv

load_dotenv()


def print_raw_shopping():
    serper_key = os.getenv("SERPER_API_KEY")
    url = "https://google.serper.dev/shopping"
    headers = {"X-API-KEY": serper_key, "Content-Type": "application/json"}
    payload = {"q": "Amazon Samsung S24 Ultra", "num": 5}
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        r.raise_for_status()
        res_json = r.json()
        print("=== Raw Serper Shopping Response ===")
        shopping_results = res_json.get("shopping", [])
        print(f"Found {len(shopping_results)} shopping results.")
        for idx, item in enumerate(shopping_results, start=1):
            print(f"\nItem {idx}:")
            for key, val in item.items():
                print(f"  {key}: {val}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    print_raw_shopping()
