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


def run_test_for_region(region_name: str, country_arg: str):
    query = "Sony PlayStation 5"
    print("\n==================================================")
    print(f" TESTING REGION: {region_name.upper()} (Country: {country_arg})")
    print("==================================================")

    try:
        res = fetch_retailer_data("amazon", query, country_arg)
        print("Success:", res.get("success"))
        if res.get("success"):
            results = res.get("results", [])
            print(f"Found {len(results)} items:")
            for idx, r in enumerate(results[:3]):  # Show top 3 for brevity
                title = r.get("title", "").encode("utf-8", errors="ignore").decode("utf-8")
                print(f"\n#{idx + 1}")
                print(f"Title: {title}")
                print(f"Price: {r.get('estimated_price')}")
                print(f"Source: {r.get('source')}")
        else:
            print("Error:", res.get("error") or res.get("message"))
    except Exception as e:
        print(f"Test failed with exception: {e}")


def main():
    regions = [
        ("Japan (JPY/¥)", "Japan"),
        ("China (CNY/¥)", "China"),
        ("United Arab Emirates (AED/د.إ)", "UAE"),
        ("United Kingdom (GBP/£)", "UK"),
    ]

    for name, country in regions:
        run_test_for_region(name, country)


if __name__ == "__main__":
    main()
