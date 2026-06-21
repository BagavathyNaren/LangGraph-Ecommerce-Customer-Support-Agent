import re
import urllib.parse

import requests


def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    url = f"https://www.google.com/search?q={urllib.parse.quote('site:amazon.in Samsung S24 Ultra')}"

    try:
        r = requests.get(url, headers=headers, timeout=10)
        html = r.text

        # Find all URLs starting with https://
        urls = re.findall(r'href="(https://[^"]+)"', html)
        print(f"Found {len(urls)} links starting with https:")
        amazon_links = [u for u in urls if "amazon.in" in u and "google" not in u]
        print(f"Found {len(amazon_links)} Amazon links:")
        for idx, link in enumerate(amazon_links[:10]):
            print(f"{idx + 1}. {urllib.parse.unquote(link)}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
