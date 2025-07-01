from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Dict

import requests


def fetch_electricity_prices() -> Dict[datetime, float]:
    base_url = "https://www.elprisetjustnu.se/api/v1/prices"
    grid_area = "SE3"

    # Get today's date
    today = datetime.now()
    tomorrow = today + timedelta(days=1)

    prices: Dict[datetime, float] = {}

    # Format dates for URL
    today_str = today.strftime("%Y/%m-%d")
    tomorrow_str = tomorrow.strftime("%Y/%m-%d")

    # Fetch today's prices
    today_url = f"{base_url}/{today_str}_{grid_area}.json"
    try:
        response = requests.get(today_url)
        if response.status_code == 200:
            today_data = response.json()
            for entry in today_data:
                time_start = datetime.fromisoformat(entry["time_start"])
                prices[time_start] = entry["SEK_per_kWh"]
    except Exception as e:
        print(f"Error fetching today's prices: {e}")

    # Fetch tomorrow's prices if available
    tomorrow_url = f"{base_url}/{tomorrow_str}_{grid_area}.json"
    try:
        response = requests.get(tomorrow_url)
        if response.status_code == 200:
            tomorrow_data = response.json()
            for entry in tomorrow_data:
                time_start = datetime.fromisoformat(entry["time_start"])
                prices[time_start] = entry["SEK_per_kWh"]
    except Exception as e:
        print(f"Error fetching tomorrow's prices: {e}")

    return prices


if __name__ == "__main__":
    prices = fetch_electricity_prices()
    for time, price in sorted(prices.items()):
        print(f"{time}: {price} SEK/kWh")
