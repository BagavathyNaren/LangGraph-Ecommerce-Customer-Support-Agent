import json
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")


def test_scraper_with_memory(platform, actor_id, run_input, memory_val):
    if memory_val:
        mem_str = f"&memory={memory_val}"
        desc = f"memory={memory_val}"
    else:
        mem_str = ""
        desc = "default memory"

    print(f"\n--- Testing {platform} Scraper ({actor_id}) with {desc} ---")
    url = f"https://api.apify.com/v2/acts/{actor_id}/runs?token={APIFY_TOKEN}&waitForFinish=60{mem_str}"
    try:
        res = requests.post(url, json=run_input)
        print(f"Status Code: {res.status_code}")
        run_data = res.json().get("data", {})
        run_status = run_data.get("status")
        run_id = run_data.get("id")
        print(f"Run ID: {run_id}, Status: {run_status}")

        # If still running, poll for up to 30 seconds
        start_time = time.time()
        while run_status not in ["SUCCEEDED", "FAILED", "ABORTED"] and (time.time() - start_time) < 30:
            print("Still running, polling status...")
            time.sleep(5)
            status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_TOKEN}"
            status_res = requests.get(status_url)
            run_data = status_res.json().get("data", {})
            run_status = run_data.get("status")
            print(f"Polled Status: {run_status}")

        print(f"Final Status: {run_status}")
        if run_status == "FAILED":
            # Get the error message
            log_url = f"https://api.apify.com/v2/actor-runs/{run_id}/log?token={APIFY_TOKEN}"
            log_res = requests.get(log_url)
            print("Logs snippet:")
            print("\n".join(log_res.text.split("\n")[-10:]))
        else:
            dataset_id = run_data.get("defaultDatasetId")
            print(f"Dataset ID: {dataset_id}")
            if dataset_id:
                items_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={APIFY_TOKEN}"
                items_res = requests.get(items_url)
                items = items_res.json()
                print(f"Total Items retrieved: {len(items)}")
                if items:
                    print(f"First item snippet: {json.dumps(items[0], indent=2)[:500]}")
    except Exception as e:
        print(f"Error: {e}")


# Flipkart test
test_scraper_with_memory(
    "Flipkart",
    "easyapi~flipkart-product-scraper",
    {
        "searchUrls": ["https://www.flipkart.com/search?q=iPhone+16+Pro"],
        "maxItems": 3,
        "proxyConfiguration": {"useApifyProxy": True},
    },
    1024,
)
