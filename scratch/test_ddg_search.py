from duckduckgo_search import DDGS


def main():
    print("Testing DuckDuckGo search with raw keyword queries...")
    try:
        with DDGS() as ddgs:
            # Test 1: Simple keyword query
            print("\n--- QUERY: Samsung S24 Ultra ---")
            results = list(ddgs.text("Samsung S24 Ultra", max_results=3))
            print(f"Found {len(results)} results:")
            for idx, r in enumerate(results):
                print(idx + 1, r.get("title"), r.get("href"))

            # Test 2: Platform query
            print("\n--- QUERY: amazon.in Samsung S24 Ultra ---")
            results2 = list(ddgs.text("amazon.in Samsung S24 Ultra", max_results=3))
            print(f"Found {len(results2)} results:")
            for idx, r in enumerate(results2):
                print(idx + 1, r.get("title"), r.get("href"))

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
