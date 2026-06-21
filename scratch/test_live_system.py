import os
import sys

from dotenv import load_dotenv

# Reconfigure stdout to support UTF-8 printing
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))
load_dotenv()

from tools.real_tools import fetch_retailer_data


def main():
    query = "Sony PlayStation 5"
    print(f"Searching Amazon USA for '{query}' using updated live tools...")
    res = fetch_retailer_data("amazon", query, "USA")
    print("Success:", res.get("success"))
    if res.get("success"):
        results = res.get("results", [])
        print(f"Found {len(results)} items:")
        for idx, r in enumerate(results):
            print(f"\n#{idx + 1}")
            print(f"Title: {r.get('title')}")
            print(f"Price: {r.get('estimated_price')}")
            print(f"Source: {r.get('source')}")
    else:
        print("Error:", res.get("error"))


if __name__ == "__main__":
    main()
