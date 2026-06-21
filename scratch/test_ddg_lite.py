import re
import urllib.parse

import requests


def search_ddg_lite(query):
    print(f"\n--- DDG LITE SEARCH FOR: {query} ---")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    # DDG Lite search requires a POST request to https://lite.duckduckgo.com/lite/
    # with payload: q=query
    url = "https://lite.duckduckgo.com/lite/"
    data = {"q": query}

    try:
        r = requests.post(url, headers=headers, data=data, timeout=10)
        print(f"Status Code: {r.status_code}")
        html = r.text

        # In DDG Lite, results are listed in table rows.
        # Links are in: <a href="https://..." class="result-link">Title</a>
        # Let's find all links and their text using regex!
        # Pattern: <a href="([^"]+)"[^>]*class="result-link"[^>]*>(.*?)</a>
        pattern = r'<a href="([^"]+)"[^>]*class="result-link"[^>]*>(.*?)</a>'
        matches = re.findall(pattern, html, re.DOTALL)

        # If that doesn't match, let's extract all external links with their titles!
        if not matches:
            # Table rows have standard links like <td class="result-title"><a href="https://...">Title</a></td>
            pattern_alt = r'<a href="(https?://[^"]+)"[^>]*>(.*?)</a>'
            matches = re.findall(pattern_alt, html)

        results = []
        for href, title in matches:
            # Clean title
            title_clean = re.sub(r"<[^>]+>", "", title).strip()
            # Clean redirect URL if present
            if "//duckduckgo.com/l/?uddg=" in href:
                actual_url_encoded = href.split("//duckduckgo.com/l/?uddg=")[1].split("&")[0]
                href = urllib.parse.unquote(actual_url_encoded)
            elif href.startswith("//"):
                href = "https:" + href

            if "google" not in href and "duckduckgo" not in href:
                results.append({"title": title_clean, "link": href})

        print(f"Found {len(results)} results:")
        for idx, r in enumerate(results[:5]):
            print(f"{idx + 1}. {r['title']}\n   Link: {r['link']}\n")

        return results
    except Exception as e:
        print(f"Error: {e}")
        return []


def main():
    search_ddg_lite("site:amazon.in Samsung S24 Ultra")
    search_ddg_lite("site:flipkart.com Samsung S24 Ultra")
    search_ddg_lite("site:croma.com Samsung S24 Ultra")


if __name__ == "__main__":
    main()
