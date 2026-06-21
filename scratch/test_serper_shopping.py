import os
import sys

from dotenv import load_dotenv

# Add parent directory to path to load tools
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment keys
load_dotenv()

from tools.real_tools import fetch_retailer_data


def test_shopping_search():
    product_query = "Samsung S24 Ultra"
    platforms = ["amazon", "flipkart", "croma"]

    print(f"=== Testing Real-Time Serper Shopping Searches for '{product_query}' ===")
    for platform in platforms:
        print(f"\nSearching on platform: {platform.capitalize()}...")
        try:
            res = fetch_retailer_data(platform, product_query)
            if "success" in res and res["success"]:
                print(f"[SUCCESS] Results for {platform.capitalize()}:")
                for idx, item in enumerate(res["results"][:3], start=1):
                    print(f"  {idx}. {item['title']}")
                    print(f"     Price: {item['estimated_price']}")
                    print(f"     Source: {item['source']}")
            else:
                print(f"[FAILED] to fetch: {res.get('error', 'Unknown Error')}")
        except Exception as e:
            print(f"[EXCEPTION] raised: {e}")


if __name__ == "__main__":
    test_shopping_search()
