import os

import requests
from dotenv import load_dotenv

load_dotenv()
APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")
run_id = "oNwroGOnZqXaxaaxL"

# Let's get the log of the run
log_url = f"https://api.apify.com/v2/actor-runs/{run_id}/log?token={APIFY_TOKEN}"
log_res = requests.get(log_url)
print("Flipkart Run Log:")
print(log_res.text[-2000:])
