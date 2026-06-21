import re
import urllib.parse

import requests


def google_search_regex(query):
    print(f"\n--- GOOGLE SEARCH FOR: {query} ---")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        html = r.text

        # Regex to find links and titles
        # Standard: <a href="https://..." ...><h3 ...>Title</h3>
        pattern = r'<a href="(https://[^"]+)"[^>]*>\s*<h3[^>]*>(.*?)</h3>'
        matches = re.findall(pattern, html)

        results = []
        for url_match, title in matches:
            # Clean up title tags like <span> or <em> or <b>
            title_clean = re.sub(r"<[^>]+>", "", title)
            url_clean = urllib.parse.unquote(url_match)
            if "google.com" not in url_clean:
                results.append({"title": title_clean.strip(), "link": url_clean})

        # Try a second pattern if Layout changed or redirects are used
        if not results:
            # Fallback for simple Google search responses
            pattern_simple = r'href="/url\?q=(https://[^&"]+)[^"]*"\s*[^>]*>.*?<span[^>]*>(.*?)</span>'
            matches_simple = re.findall(pattern_simple, html)
            for url_match, title in matches_simple:
                title_clean = re.sub(r"<[^>]+>", "", title)
                url_clean = urllib.parse.unquote(url_match)
                if "google.com" not in url_clean:
                    results.append({"title": title_clean.strip(), "link": url_clean})

        print(f"Found {len(results)} results:")
        for idx, r in enumerate(results[:5]):
            print(f"{idx + 1}. {r['title']}\n   Link: {r['link']}\n")

        return results
    except Exception as e:
        print(f"Error: {e}")
        return []


def main():
    google_search_regex("site:amazon.in Samsung S24 Ultra")
    google_search_regex("site:flipkart.com Samsung S24 Ultra")
    google_search_regex("site:croma.com Samsung S24 Ultra")


if __name__ == "__main__":
    main()
