import os

import requests
from dotenv import load_dotenv

load_dotenv()
APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")

# Fetch recent runs
url = f"https://api.apify.com/v2/actor-runs?token={APIFY_TOKEN}&limit=3"
res = requests.get(url)
runs = res.json().get("data", {}).get("items", [])
for r in runs:
    print(f"Run ID: {r.get('id')}, Actor: {r.get('actId')}, Status: {r.get('status')}")
