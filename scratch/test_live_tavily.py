import os
import sys

from dotenv import load_dotenv

# Ensure local path is in import path
sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))

load_dotenv()

from tools.real_tools import fetch_retailer_data


def main():
    query = "Samsung S24 Ultra"
    print(f"Testing live Tavily search with refined price extraction for '{query}'...")

    # Check if TAVILY_API_KEY is loaded
    tavily_key = os.getenv("TAVILY_API_KEY")
    print(f"TAVILY_API_KEY present in environment: {tavily_key is not None}")
    if tavily_key:
        print(f"Tavily Key starts with: {tavily_key[:8]}...")

    for platform in ["amazon", "flipkart", "croma"]:
        print(f"\n--- Searching {platform.upper()} ---")
        res = fetch_retailer_data(platform, query)
        print("Success:", res.get("success"))
        if res.get("success"):
            results = res.get("results", [])
            print(f"Found {len(results)} items:")
            for idx, r in enumerate(results[:3]):
                print(
                    f"{idx + 1}. Title: {r.get('title')}\n   Price: {r.get('estimated_price')}\n   Source: {r.get('source')}\n"
                )
        else:
            print("Error/No Results:", res.get("error"))


if __name__ == "__main__":
    main()
