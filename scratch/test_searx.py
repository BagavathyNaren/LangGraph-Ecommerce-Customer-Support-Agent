import urllib.parse

import requests


def search_searx(query):
    print(f"\n--- SEARX SEARCH FOR: {query} ---")

    # List of public SearxNG instances to try in case of rate limits
    instances = [
        "https://searx.be",
        "https://searx.space",
        "https://searx.me",
        "https://searx.work",
        "https://northboot.xyz",
        "https://searx.priv.pw",
    ]

    for instance in instances:
        url = f"{instance}/search?q={urllib.parse.quote(query)}&format=json"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        try:
            print(f"Trying instance: {instance}...")
            r = requests.get(url, headers=headers, timeout=8)
            if r.status_code == 200:
                data = r.json()
                results = data.get("results", [])
                print(f"Success! Found {len(results)} results from {instance}:")
                for idx, item in enumerate(results[:3]):
                    print(
                        f"{idx + 1}. {item.get('title')}\n   Link: {item.get('url')}\n   Snippet: {item.get('content')}\n"
                    )
                return results
            else:
                print(f"Status Code {r.status_code} from {instance}")
        except Exception as e:
            print(f"Error from {instance}: {e}")

    print("All Searx instances failed.")
    return []


def main():
    search_searx("site:amazon.in Samsung S24 Ultra")


if __name__ == "__main__":
    main()
