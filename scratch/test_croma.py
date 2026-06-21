import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")
actor_id = "apify~website-content-crawler"
croma_search_url = "https://www.croma.com/searchB?q=iPhone+16+Pro%3Arelevance&text=iPhone+16+Pro"

run_input = {
    "startUrls": [{"url": croma_search_url}],
    "maxPages": 1,
    "maxCrawlPages": 1,
    "crawlerType": "playwright:adaptive",
    "proxyConfiguration": {"useApifyProxy": True},
}

print(f"--- Testing Croma Scraper ({actor_id}) ---")
url = f"https://api.apify.com/v2/acts/{actor_id}/runs?token={APIFY_TOKEN}&waitForFinish=60&memory=1024"
try:
    res = requests.post(url, json=run_input)
    print(f"Status Code: {res.status_code}")
    run_data = res.json().get("data", {})
    run_status = run_data.get("status")
    run_id = run_data.get("id")
    print(f"Run ID: {run_id}, Status: {run_status}")

    # Poll for 30s
    start_time = time.time()
    while run_status not in ["SUCCEEDED", "FAILED", "ABORTED"] and (time.time() - start_time) < 30:
        print("Polling status...")
        time.sleep(5)
        status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_TOKEN}"
        status_res = requests.get(status_url)
        run_data = status_res.json().get("data", {})
        run_status = run_data.get("status")
        print(f"Polled Status: {run_status}")

    print(f"Final Status: {run_status}")
    if run_status == "SUCCEEDED":
        dataset_id = run_data.get("defaultDatasetId")
        print(f"Dataset ID: {dataset_id}")
        items_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={APIFY_TOKEN}"
        items_res = requests.get(items_url)
        items = items_res.json()
        print(f"Total Items: {len(items)}")
        if items:
            print("First item markdown (first 500 chars):")
            print(items[0].get("markdown", items[0].get("text", ""))[:500])
except Exception as e:
    print(f"Error: {e}")
