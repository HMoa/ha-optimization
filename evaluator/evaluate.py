from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

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


def main(evaluation_date: Optional[datetime] = None) -> None:
    # Get the date to evaluate (default to yesterday if not specified)
    if evaluation_date is None:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        evaluation_date = today - timedelta(days=1)

    # Convert local date range to UTC for InfluxDB queries
    local_start = evaluation_date
    local_end = evaluation_date + timedelta(days=1)

    # Convert to UTC using proper timezone conversion
    # First, assume the local time is in Swedish timezone (Europe/Stockholm)
    utc_start = (
        pd.Timestamp(local_start)
        .tz_localize("Europe/Stockholm")
        .tz_convert("UTC")
        .tz_localize(None)
    )
    utc_end = (
        pd.Timestamp(local_end)
        .tz_localize("Europe/Stockholm")
        .tz_convert("UTC")
        .tz_localize(None)
    )

    # Fetch hourly prices for the evaluation date
    prices: Dict[datetime, Elpris] = fetch_electricity_prices(evaluation_date, "SE3")
    # Map prices to hour (truncate to hour and convert to timezone-naive)
    price_per_hour = {
        dt.replace(minute=0, second=0, microsecond=0).replace(tzinfo=None): price
        for dt, price in prices.items()
    }

    # Fetch hourly consumption and production diffs (using UTC range)
    consumed_df = fetch_hourly_diffs("energy.consumed", "value", utc_start, utc_end)
    produced_df = fetch_hourly_diffs("energy.produced", "value", utc_start, utc_end)

    # Convert timestamps to datetime and align to hour (convert UTC to local time)
    consumed_df["hour"] = (
        pd.to_datetime(consumed_df["timestamp"])
        .dt.tz_convert("Europe/Stockholm")
        .dt.tz_localize(None)
        .dt.floor("h")
    )
    produced_df["hour"] = (
        pd.to_datetime(produced_df["timestamp"])
        .dt.tz_convert("Europe/Stockholm")
        .dt.tz_localize(None)
        .dt.floor("h")
    )

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
    consumed_power_df = fetch_minutely_power(
        "power.consumed", "value", utc_start, utc_end
    )
    pv_power_df = fetch_minutely_power("power.pv", "value", utc_start, utc_end)

    # Convert timestamps to datetime and align to hour (convert UTC to local time)
    consumed_power_df["hour"] = (
        pd.to_datetime(consumed_power_df["timestamp"])
        .dt.tz_convert("Europe/Stockholm")
        .dt.tz_localize(None)
        .dt.floor("h")
    )
    pv_power_df["hour"] = (
        pd.to_datetime(pv_power_df["timestamp"])
        .dt.tz_convert("Europe/Stockholm")
        .dt.tz_localize(None)
        .dt.floor("h")
    )

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
        f"\nUsage cost (no batteries) for {evaluation_date.date()}: {total_no_battery_cost:.2f} SEK"
    )
    print(
        f"Actual cost (with batteries) for {evaluation_date.date()}: {actual_total_cost:.2f} SEK"
    )
    print(
        f"Savings for {evaluation_date.date()}: {total_no_battery_cost - actual_total_cost:.2f} SEK\n"
    )

    # Save results to InfluxDB
    config = InfluxDBConfig()
    with InfluxDBClientWrapper(config) as client:
        # Use midnight UTC for the calculated day as timestamp
        result_timestamp = evaluation_date.replace(tzinfo=None).isoformat() + "Z"
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
    parser = argparse.ArgumentParser(
        description="Evaluate energy consumption and production."
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Date to evaluate in YYYY-MM-DD format (default: yesterday).",
    )
    args = parser.parse_args()

    evaluation_date = None
    if args.date:
        try:
            evaluation_date = datetime.strptime(args.date, "%Y-%m-%d").replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        except ValueError:
            print(
                f"Error: Invalid date format. Please use YYYY-MM-DD. Example: --date 2023-10-27"
            )
            sys.exit(1)

    main(evaluation_date)
