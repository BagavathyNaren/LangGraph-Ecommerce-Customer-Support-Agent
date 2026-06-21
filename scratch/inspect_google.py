import urllib.parse

import requests


def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    url = f"https://www.google.com/search?q={urllib.parse.quote('Samsung S24 Ultra')}"

    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {r.status_code}")
        print("First 1000 characters of HTML:")
        print(r.text[:1000])
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
