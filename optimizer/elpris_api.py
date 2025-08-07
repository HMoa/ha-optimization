from __future__ import annotations

from datetime import datetime, timedelta

import requests

from optimizer.models import Elpris


def fetch_electricity_prices(
    start_date: datetime, grid_area: str
) -> dict[datetime, Elpris]:
    base_url = "https://www.elprisetjustnu.se/api/v1/prices"
    today = start_date.date()

    tomorrow = today + timedelta(days=1)

    prices: dict[datetime, Elpris] = {}

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
                prices[time_start] = Elpris(entry["SEK_per_kWh"])
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
                prices[time_start] = Elpris(entry["SEK_per_kWh"])
    except Exception as e:
        print(f"Error fetching tomorrow's prices: {e}")

    return prices


if __name__ == "__main__":
    prices = fetch_electricity_prices(datetime.now(), "SE3")
    for time, price in sorted(prices.items()):
        print(f"{time}: {price} SEK/kWh")
