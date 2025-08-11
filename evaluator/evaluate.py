from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

sys.path.append("..")  # Ensure parent directory is in path for imports
from optimizer.elpris_api import fetch_electricity_prices
from optimizer.influxdb_client import InfluxDBClientWrapper, InfluxDBConfig


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


def _get_evaluation_date(evaluation_date: Optional[datetime]) -> datetime:
    """Get the evaluation date, defaulting to yesterday if not specified."""
    if evaluation_date is None:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return today - timedelta(days=1)
    return evaluation_date


def _convert_local_to_utc_range(local_date: datetime) -> tuple[datetime, datetime]:
    """Convert local date range to UTC for InfluxDB queries."""
    local_start = local_date
    local_end = local_date + timedelta(days=1)

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

    return utc_start.to_pydatetime(), utc_end.to_pydatetime()


def _fetch_and_map_prices(
    evaluation_date: datetime,
) -> tuple[dict[datetime, object], dict[datetime, object]]:
    """Fetch electricity prices and map them to timezone-naive hours.

    Returns:
        tuple: (original_prices, price_per_hour_mapped)
            - original_prices: timezone-aware prices as fetched from API
            - price_per_hour_mapped: timezone-naive prices mapped to hour keys
    """
    prices = fetch_electricity_prices(evaluation_date, "SE3")
    # Map prices to hour (truncate to hour and convert to timezone-naive)
    price_per_hour = {
        dt.replace(minute=0, second=0, microsecond=0).replace(tzinfo=None): price
        for dt, price in prices.items()
    }
    return prices, price_per_hour


def _add_hour_column_to_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Add hour column to DataFrame, converting UTC timestamps to local time."""
    if len(df) > 0:
        df["hour"] = (
            pd.to_datetime(df["timestamp"])
            .dt.tz_convert("Europe/Stockholm")
            .dt.tz_localize(None)
            .dt.floor("h")
        )
    else:
        df["hour"] = pd.Series([], dtype="datetime64[ns]")
    return df


def _calculate_battery_scenario_costs(
    utc_start: datetime, utc_end: datetime, price_per_hour: dict[datetime, object]
) -> tuple[float, pd.DataFrame, pd.DataFrame]:
    """Calculate costs for the battery-optimized scenario (actual costs)."""
    # Fetch hourly consumption and production diffs (using UTC range)
    consumed_df = fetch_hourly_diffs("energy.consumed", "value", utc_start, utc_end)
    produced_df = fetch_hourly_diffs("energy.produced", "value", utc_start, utc_end)

    # Convert timestamps to datetime and align to hour
    consumed_df = _add_hour_column_to_dataframe(consumed_df)
    produced_df = _add_hour_column_to_dataframe(produced_df)

    # Merge with prices and calculate cost/revenue
    if len(consumed_df) > 0:
        consumed_df["price"] = consumed_df["hour"].map(
            lambda h: price_per_hour[h].get_buy_price() if h in price_per_hour else None
        )
        consumed_df["cost"] = consumed_df["diff"] * (consumed_df["price"] / 1000)
    else:
        consumed_df["price"] = pd.Series([], dtype="float64")
        consumed_df["cost"] = pd.Series([], dtype="float64")

    if len(produced_df) > 0:
        produced_df["price"] = produced_df["hour"].map(
            lambda h: (
                price_per_hour[h].get_sell_price() if h in price_per_hour else None
            )
        )
        produced_df["revenue"] = produced_df["diff"] * (produced_df["price"] / 1000)
    else:
        produced_df["price"] = pd.Series([], dtype="float64")
        produced_df["revenue"] = pd.Series([], dtype="float64")

    actual_total_cost = consumed_df["cost"].sum() - produced_df["revenue"].sum()
    return actual_total_cost, consumed_df, produced_df


def _calculate_no_battery_scenario_costs(
    utc_start: datetime, utc_end: datetime, price_per_hour: dict[datetime, object]
) -> tuple[float, pd.DataFrame, pd.DataFrame]:
    """Calculate costs for the no-battery scenario (hypothetical costs)."""
    # Fetch minutely power data
    consumed_power_df = fetch_minutely_power(
        "power.consumed", "value", utc_start, utc_end
    )
    pv_power_df = fetch_minutely_power("power.pv", "value", utc_start, utc_end)

    # Convert timestamps to datetime and align to hour
    consumed_power_df = _add_hour_column_to_dataframe(consumed_power_df)
    pv_power_df = _add_hour_column_to_dataframe(pv_power_df)

    # Convert W to Wh per minute, then sum by hour
    if len(consumed_power_df) > 0:
        consumed_power_df["wh"] = consumed_power_df["value"] / 60.0
        consumed_hourly = consumed_power_df.groupby("hour")["wh"].sum().reset_index()
        # Map prices to hour
        consumed_hourly["price"] = consumed_hourly["hour"].map(
            lambda h: price_per_hour[h].get_buy_price() if h in price_per_hour else None
        )
        # Calculate cost (convert Wh to kWh by dividing price by 1000)
        consumed_hourly["cost"] = consumed_hourly["wh"] * (
            consumed_hourly["price"] / 1000
        )
    else:
        consumed_hourly = pd.DataFrame(columns=["hour", "wh", "price", "cost"])

    if len(pv_power_df) > 0:
        pv_power_df["wh"] = pv_power_df["value"] / 60.0
        pv_hourly = pv_power_df.groupby("hour")["wh"].sum().reset_index()
        # Map prices to hour
        pv_hourly["price"] = pv_hourly["hour"].map(
            lambda h: (
                price_per_hour[h].get_sell_price() if h in price_per_hour else None
            )
        )
        # Calculate revenue (convert Wh to kWh by dividing price by 1000)
        pv_hourly["revenue"] = pv_hourly["wh"] * (pv_hourly["price"] / 1000)
    else:
        pv_hourly = pd.DataFrame(columns=["hour", "wh", "price", "revenue"])

    total_no_battery_cost = consumed_hourly["cost"].sum() - pv_hourly["revenue"].sum()
    return total_no_battery_cost, consumed_hourly, pv_hourly


def _print_results(
    evaluation_date: datetime, total_no_battery_cost: float, actual_total_cost: float
) -> None:
    """Print the evaluation results."""
    print(
        f"\nUsage cost (no batteries) for {evaluation_date.date()}: {total_no_battery_cost:.2f} SEK"
    )
    print(
        f"Actual cost (with batteries) for {evaluation_date.date()}: {actual_total_cost:.2f} SEK"
    )
    print(
        f"Savings for {evaluation_date.date()}: {total_no_battery_cost - actual_total_cost:.2f} SEK\n"
    )


def _calculate_energy_storage_value(
    evaluation_date: datetime, price_per_hour: dict[datetime, object]
) -> tuple[float, float, float]:
    """
    Calculate the monetary value of energy stored in the battery at midnight.

    Args:
        evaluation_date: The date to evaluate
        price_per_hour: Dictionary mapping hours to price objects

    Returns:
        tuple: (energy_stored_wh, storage_value_sek, midnight_sell_price)
    """
    # Get midnight timestamp in local time
    midnight_local = evaluation_date.replace(hour=0, minute=0, second=0, microsecond=0)

    # Convert to UTC for InfluxDB query
    midnight_utc = (
        pd.Timestamp(midnight_local)
        .tz_localize("Europe/Stockholm")
        .tz_convert("UTC")
        .tz_localize(None)
    )

    # Query for SoC data around midnight (2-hour window to ensure we get data)
    query_start = midnight_utc - timedelta(minutes=5)
    query_end = midnight_utc + timedelta(minutes=5)

    # Fetch SoC data from InfluxDB at 5-minute resolution
    soc_df = fetch_minutely_power("energy.SoC", "value", query_start, query_end)

    # Find the SoC reading closest to midnight
    energy_stored_wh = 0.0
    if len(soc_df) > 0:
        battery_soc_percent = soc_df.iloc[0]["value"]

        # Calculate energy stored (SoC percentage * battery capacity)
        battery_capacity_wh = (
            44000  # Adjust this if your battery has different capacity
        )
        energy_stored_wh = (battery_soc_percent / 100) * battery_capacity_wh

    # Get the sell price at midnight
    midnight_hour = midnight_local
    midnight_price = price_per_hour.get(midnight_hour)
    midnight_sell_price = midnight_price.get_sell_price() if midnight_price else 0

    # Calculate storage value (convert Wh to kWh by dividing by 1000)
    storage_value_sek = energy_stored_wh * (midnight_sell_price / 1000)

    return energy_stored_wh, storage_value_sek, midnight_sell_price


def _calculate_energy_storage_value_diff(
    evaluation_date: datetime, price_per_hour: dict[datetime, object]
) -> tuple[float, float, float, float]:
    """
    Calculate the monetary value of the change in energy stored between midnight today and midnight yesterday.

    Args:
        evaluation_date: The date to evaluate
        price_per_hour: Dictionary mapping hours to price objects

    Returns:
        tuple: (energy_stored_today_wh, energy_stored_yesterday_wh, energy_diff_wh, diff_value_sek)
    """
    # Get midnight timestamps in local time
    midnight_today = evaluation_date.replace(hour=0, minute=0, second=0, microsecond=0)
    midnight_yesterday = midnight_today - timedelta(days=1)

    # Convert to UTC for InfluxDB queries
    midnight_today_utc = (
        pd.Timestamp(midnight_today)
        .tz_localize("Europe/Stockholm")
        .tz_convert("UTC")
        .tz_localize(None)
    )
    midnight_yesterday_utc = (
        pd.Timestamp(midnight_yesterday)
        .tz_localize("Europe/Stockholm")
        .tz_convert("UTC")
        .tz_localize(None)
    )

    # Query for SoC data around both midnights
    query_start_today = midnight_today_utc - timedelta(minutes=5)
    query_end_today = midnight_today_utc + timedelta(minutes=5)
    query_start_yesterday = midnight_yesterday_utc - timedelta(minutes=5)
    query_end_yesterday = midnight_yesterday_utc + timedelta(minutes=5)

    # Fetch SoC data from InfluxDB
    soc_today_df = fetch_minutely_power(
        "energy.SoC", "value", query_start_today, query_end_today
    )
    soc_yesterday_df = fetch_minutely_power(
        "energy.SoC", "value", query_start_yesterday, query_end_yesterday
    )

    # Calculate energy stored for both days
    battery_capacity_wh = 44000  # Adjust this if your battery has different capacity

    energy_stored_today_wh = 0.0
    if len(soc_today_df) > 0:
        battery_soc_percent_today = soc_today_df.iloc[0]["value"]
        energy_stored_today_wh = (battery_soc_percent_today / 100) * battery_capacity_wh

    energy_stored_yesterday_wh = 0.0
    if len(soc_yesterday_df) > 0:
        battery_soc_percent_yesterday = soc_yesterday_df.iloc[0]["value"]
        energy_stored_yesterday_wh = (
            battery_soc_percent_yesterday / 100
        ) * battery_capacity_wh

    # Calculate energy difference
    energy_diff_wh = energy_stored_today_wh - energy_stored_yesterday_wh

    # Get the sell price at midnight today
    midnight_hour = midnight_today
    midnight_price = price_per_hour.get(midnight_hour)
    midnight_sell_price = midnight_price.get_sell_price() if midnight_price else 0

    # Calculate difference value (convert Wh to kWh by dividing by 1000)
    diff_value_sek = energy_diff_wh * (midnight_sell_price / 1000)

    return (
        energy_stored_today_wh,
        energy_stored_yesterday_wh,
        energy_diff_wh,
        diff_value_sek,
    )


def _save_prices_to_influxdb(prices: dict[datetime, object]) -> None:
    """Save spot prices to InfluxDB with correct timezone handling."""
    config = InfluxDBConfig()
    with InfluxDBClientWrapper(config) as client:
        for price_datetime, elpris_obj in prices.items():
            # Convert timezone-aware datetime to UTC for InfluxDB storage
            if price_datetime.tzinfo is not None:
                utc_timestamp = price_datetime.astimezone().utctimetuple()
                timestamp_str = f"{utc_timestamp.tm_year:04d}-{utc_timestamp.tm_mon:02d}-{utc_timestamp.tm_mday:02d}T{utc_timestamp.tm_hour:02d}:{utc_timestamp.tm_min:02d}:{utc_timestamp.tm_sec:02d}Z"
            else:
                # If timezone-naive, assume it's already in local time and convert to UTC
                utc_datetime = (
                    pd.Timestamp(price_datetime)
                    .tz_localize("Europe/Stockholm")
                    .tz_convert("UTC")
                    .tz_localize(None)
                )
                timestamp_str = utc_datetime.isoformat() + "Z"

            client.write_point(
                measurement="SpotPrices",
                fields={
                    "spot_price": float(elpris_obj.get_spot_price()),
                    "buy_price": float(elpris_obj.get_buy_price()),
                    "sell_price": float(elpris_obj.get_sell_price()),
                },
                tags={"grid_area": "SE3"},
                timestamp=timestamp_str,
            )


def _save_results_to_influxdb(
    evaluation_date: datetime,
    total_no_battery_cost: float,
    actual_total_cost: float,
    energy_value_sek: float = 0.0,
    energy_value_diff_sek: float = 0.0,
) -> None:
    """Save evaluation results to InfluxDB."""
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
                "energy_value": float(energy_value_sek),
                "energy_value_diff": float(energy_value_diff_sek),
            },
            tags=None,
            timestamp=result_timestamp,
        )


def main(evaluation_date: Optional[datetime] = None) -> None:
    """Evaluate energy consumption and production costs with and without battery optimization."""
    # Get the evaluation date
    evaluation_date = _get_evaluation_date(evaluation_date)

    # Convert local date range to UTC for InfluxDB queries
    utc_start, utc_end = _convert_local_to_utc_range(evaluation_date)

    # Fetch and map electricity prices
    original_prices, price_per_hour = _fetch_and_map_prices(evaluation_date)

    # Calculate costs for battery-optimized scenario (actual costs)
    actual_total_cost, _, _ = _calculate_battery_scenario_costs(
        utc_start, utc_end, price_per_hour
    )

    # Calculate costs for no-battery scenario (hypothetical costs)
    total_no_battery_cost, _, _ = _calculate_no_battery_scenario_costs(
        utc_start, utc_end, price_per_hour
    )

    # Calculate energy storage value at midnight
    energy_stored_wh, storage_value_sek, midnight_sell_price = (
        _calculate_energy_storage_value(evaluation_date, price_per_hour)
    )

    # Calculate energy storage value difference
    (
        energy_stored_today_wh,
        energy_stored_yesterday_wh,
        energy_diff_wh,
        diff_value_sek,
    ) = _calculate_energy_storage_value_diff(evaluation_date, price_per_hour)

    # Print results
    _print_results(evaluation_date, total_no_battery_cost, actual_total_cost)

    # Print energy storage information
    print(f"Energy storage analysis:")
    print(f"  Battery SoC at midnight: {energy_stored_wh:.0f} Wh")
    print(f"  Midnight sell price: {midnight_sell_price:.2f} SEK/kWh")
    print(f"  Energy storage value: {storage_value_sek:.2f} SEK")
    print(
        f"  Adjusted savings: {(total_no_battery_cost - actual_total_cost + storage_value_sek):.2f} SEK\n"
    )

    # Print energy storage difference information
    print(f"Energy storage difference analysis:")
    print(f"  Battery SoC yesterday midnight: {energy_stored_yesterday_wh:.0f} Wh")
    print(f"  Battery SoC today midnight: {energy_stored_today_wh:.0f} Wh")
    print(f"  Energy difference: {energy_diff_wh:+.0f} Wh")
    print(f"  Difference value (at today's price): {diff_value_sek:.2f} SEK")
    print(
        f"  Adjusted savings with diff: {(total_no_battery_cost - actual_total_cost + diff_value_sek):.2f} SEK\n"
    )

    # Save spot prices to InfluxDB
    _save_prices_to_influxdb(original_prices)

    # Save results to InfluxDB
    _save_results_to_influxdb(
        evaluation_date,
        total_no_battery_cost,
        actual_total_cost,
        storage_value_sek,
        diff_value_sek,
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
                "Error: Invalid date format. Please use YYYY-MM-DD. Example: --date 2023-10-27"
            )
            sys.exit(1)

    main(evaluation_date)
