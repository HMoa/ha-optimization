from __future__ import annotations

import sys
from datetime import datetime, timedelta
from typing import Any, Dict

import pandas as pd

sys.path.append("..")  # Ensure parent directory is in path for imports
from optimizer.elpris_api import fetch_electricity_prices
from optimizer.influxdb_client import InfluxDBClientWrapper, InfluxDBConfig
from optimizer.models import Elpris


def fetch_hourly_diffs(
    measurement: str,
    field: str,
    start: datetime,
    end: datetime,
    config_path: str = "config/influxdb_config.json",
) -> pd.DataFrame:
    """
    Fetches the hourly difference for a given measurement/field from InfluxDB between start and end datetimes.
    Returns a DataFrame with columns: 'timestamp', 'diff'.
    """
    config = InfluxDBConfig(config_path)
    # Override measurement and field
    config.config["measurement"] = measurement
    config.config["field"] = field
    with InfluxDBClientWrapper(config) as client:
        # Query for the full day, group by 1h
        influxql_query = f"""
        SELECT DIFFERENCE(MEAN({field})) as diff
        FROM "{measurement}"
        WHERE time >= '{start.isoformat()}Z' and time < '{end.isoformat()}Z'
        GROUP BY time(1h)
        ORDER BY time ASC
        """
        result = client.client.query(influxql_query)
        data = []
        for point in result.get_points():
            if point["diff"] is not None:
                data.append({"timestamp": point["time"], "diff": float(point["diff"])})
        return pd.DataFrame(data)


def fetch_minutely_power(
    measurement: str,
    field: str,
    start: datetime,
    end: datetime,
    config_path: str = "config/influxdb_config.json",
) -> pd.DataFrame:
    """
    Fetches minutely power data (in Watts) for a given measurement/field from InfluxDB between start and end datetimes.
    Returns a DataFrame with columns: 'timestamp', 'value'.
    """
    config = InfluxDBConfig(config_path)
    config.config["measurement"] = measurement
    config.config["field"] = field
    with InfluxDBClientWrapper(config) as client:
        influxql_query = f"""
        SELECT MEAN({field}) as value
        FROM "{measurement}"
        WHERE time >= '{start.isoformat()}Z' and time < '{end.isoformat()}Z'
        GROUP BY time(1m)
        ORDER BY time ASC
        """
        result = client.client.query(influxql_query)
        data = []
        for point in result.get_points():
            if point["value"] is not None:
                data.append(
                    {"timestamp": point["time"], "value": float(point["value"])}
                )
        return pd.DataFrame(data)


def main() -> None:
    # Get yesterday's date range
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    start = yesterday
    end = today

    # Fetch hourly prices for yesterday
    prices: Dict[datetime, Elpris] = fetch_electricity_prices(yesterday)
    # Map prices to hour (truncate to hour)
    price_per_hour = {
        dt.replace(minute=0, second=0, microsecond=0): price
        for dt, price in prices.items()
    }

    # Fetch hourly consumption and production diffs
    consumed_df = fetch_hourly_diffs("energy.consumed", "value", start, end)
    produced_df = fetch_hourly_diffs("energy.produced", "value", start, end)

    # Convert timestamps to datetime and align to hour
    consumed_df["hour"] = pd.to_datetime(consumed_df["timestamp"]).dt.floor("h")
    produced_df["hour"] = pd.to_datetime(produced_df["timestamp"]).dt.floor("h")

    # Merge with prices and calculate cost/revenue
    consumed_df["price"] = consumed_df["hour"].map(
        lambda h: price_per_hour[h].get_buy_price() if h in price_per_hour else None
    )
    produced_df["price"] = produced_df["hour"].map(
        lambda h: price_per_hour[h].get_sell_price() if h in price_per_hour else None
    )

    # Calculate cost and revenue (convert Wh to kWh by dividing price by 1000)
    consumed_df["cost"] = consumed_df["diff"] * (consumed_df["price"] / 1000)
    produced_df["revenue"] = produced_df["diff"] * (produced_df["price"] / 1000)

    actual_total_cost = consumed_df["cost"].sum() - produced_df["revenue"].sum()

    # --- Calculate cost without batteries (using power.pv and power.consumed in W) ---
    consumed_power_df = fetch_minutely_power("power.consumed", "value", start, end)
    pv_power_df = fetch_minutely_power("power.pv", "value", start, end)

    # Convert timestamps to datetime and align to hour
    consumed_power_df["hour"] = pd.to_datetime(consumed_power_df["timestamp"]).dt.floor(
        "h"
    )
    pv_power_df["hour"] = pd.to_datetime(pv_power_df["timestamp"]).dt.floor("h")

    # Convert W to Wh per minute, then sum by hour
    consumed_power_df["wh"] = consumed_power_df["value"] / 60.0
    pv_power_df["wh"] = pv_power_df["value"] / 60.0
    consumed_hourly = consumed_power_df.groupby("hour")["wh"].sum().reset_index()
    pv_hourly = pv_power_df.groupby("hour")["wh"].sum().reset_index()

    # Map prices to hour
    consumed_hourly["price"] = consumed_hourly["hour"].map(
        lambda h: price_per_hour[h].get_buy_price() if h in price_per_hour else None
    )
    pv_hourly["price"] = pv_hourly["hour"].map(
        lambda h: price_per_hour[h].get_sell_price() if h in price_per_hour else None
    )

    # Calculate cost and revenue (convert Wh to kWh by dividing price by 1000)
    consumed_hourly["cost"] = consumed_hourly["wh"] * (consumed_hourly["price"] / 1000)
    pv_hourly["revenue"] = pv_hourly["wh"] * (pv_hourly["price"] / 1000)

    total_no_battery_cost = consumed_hourly["cost"].sum() - pv_hourly["revenue"].sum()

    print(
        f"\nUsage cost (no batteries) for {yesterday.date()}: {total_no_battery_cost:.2f} SEK"
    )
    print(
        f"Actual cost (with batteries) for {yesterday.date()}: {actual_total_cost:.2f} SEK"
    )
    print(
        f"Savings for {yesterday.date()}: {total_no_battery_cost - actual_total_cost:.2f} SEK\n"
    )

    # Save results to InfluxDB
    config = InfluxDBConfig()
    with InfluxDBClientWrapper(config) as client:
        # Use midnight UTC for the calculated day as timestamp
        result_timestamp = yesterday.replace(tzinfo=None).isoformat() + "Z"
        client.write_point(
            measurement="evaluation",
            fields={
                "usage_cost": float(total_no_battery_cost),
                "actual_cost": float(actual_total_cost),
                "savings": float(total_no_battery_cost - actual_total_cost),
            },
            tags=None,
            timestamp=result_timestamp,
        )


if __name__ == "__main__":
    main()
