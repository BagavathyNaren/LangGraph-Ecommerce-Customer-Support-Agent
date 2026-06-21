import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()
APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")
run_id = "oNwroGOnZqXaxaaxL"

url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_TOKEN}"
res = requests.get(url)
run_data = res.json().get("data", {})
print(f"Run ID: {run_id}")
print(f"Status: {run_data.get('status')}")
dataset_id = run_data.get("defaultDatasetId")
print(f"Dataset ID: {dataset_id}")

if dataset_id:
    items_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={APIFY_TOKEN}"
    items_res = requests.get(items_url)
    items = items_res.json()
    print(f"Total Items: {len(items)}")
    if items:
        print(f"First item: {json.dumps(items[0], indent=2)}")
