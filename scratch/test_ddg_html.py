import re
import urllib.parse

import requests


def search_ddg_html(query):
    print(f"\n--- DDG HTML SEARCH FOR: {query} ---")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"

    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {r.status_code}")
        html = r.text

        # Parse the HTML results
        # DDG HTML search results have class "result__snippet", "result__url", "result__title"
        # Links are usually in: <a class="result__url" href="...">
        # Title is in: <a class="result__snippet" ...> or <a class="result__a" href="...">Title</a>

        # Regex to find result blocks
        # <a class="result__a" href="[^"]+">Title</a>
        pattern = r'<a class="result__a" href="([^"]+)">([^<]+)</a>'
        matches = re.findall(pattern, html)

        results = []
        for href, title in matches:
            # Clean redirect URL if present
            # href can be like: //duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.amazon.in%2F...
            if "//duckduckgo.com/l/?uddg=" in href:
                actual_url_encoded = href.split("//duckduckgo.com/l/?uddg=")[1].split("&")[0]
                href = urllib.parse.unquote(actual_url_encoded)
            elif href.startswith("//"):
                href = "https:" + href

            results.append({"title": title.strip(), "link": href})

        print(f"Found {len(results)} results:")
        for idx, r in enumerate(results[:5]):
            print(f"{idx + 1}. {r['title']}\n   Link: {r['link']}\n")

        return results
    except Exception as e:
        print(f"Error: {e}")
        return []


def main():
    search_ddg_html("site:amazon.in Samsung S24 Ultra")
    search_ddg_html("site:flipkart.com Samsung S24 Ultra")
    search_ddg_html("site:croma.com Samsung S24 Ultra")


if __name__ == "__main__":
    main()
