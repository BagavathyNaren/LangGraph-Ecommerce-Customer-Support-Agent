import os
import sys

from dotenv import load_dotenv

# Reconfigure stdout to support UTF-8 printing of Indian Rupee symbol
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# Ensure local path is in import path
sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))

load_dotenv()

from tools.real_tools import fetch_retailer_data


def main():
    query = "Samsung S24 Ultra"
    print(f"Searching for '{query}'...")

    # 1. Amazon
    print("\n--- AMAZON SEARCH ---")
    res_amzn = fetch_retailer_data("amazon", query)
    print("Success:", res_amzn.get("success"))
    if res_amzn.get("success"):
        results = res_amzn.get("results", [])
        print(f"Found {len(results)} items:")
        for r in results[:3]:
            title = r.get("title", "").encode("utf-8", errors="ignore").decode("utf-8")
            print(f"- {title} ({r.get('estimated_price')}) via {r.get('source')}")
    else:
        print("Error:", res_amzn.get("error"))

    # 2. Flipkart
    print("\n--- FLIPKART SEARCH ---")
    res_fk = fetch_retailer_data("flipkart", query)
    print("Success:", res_fk.get("success"))
    if res_fk.get("success"):
        results = res_fk.get("results", [])
        print(f"Found {len(results)} items:")
        for r in results[:3]:
            title = r.get("title", "").encode("utf-8", errors="ignore").decode("utf-8")
            print(f"- {title} ({r.get('estimated_price')}) via {r.get('source')}")
    else:
        print("Error:", res_fk.get("error"))

    # 3. Croma
    print("\n--- CROMA SEARCH ---")
    res_croma = fetch_retailer_data("croma", query)
    print("Success:", res_croma.get("success"))
    if res_croma.get("success"):
        results = res_croma.get("results", [])
        print(f"Found {len(results)} items:")
        for r in results[:3]:
            print(f"- Snippet length: {len(r.get('content_snippet', ''))} characters")
    else:
        print("Error:", res_croma.get("error"))


if __name__ == "__main__":
    main()
