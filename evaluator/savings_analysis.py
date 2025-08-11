from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

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


def _add_5min_column_to_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Add 5-minute interval column to DataFrame, converting UTC timestamps to local time."""
    if len(df) > 0:
        df["interval_5min"] = (
            pd.to_datetime(df["timestamp"])
            .dt.tz_convert("Europe/Stockholm")
            .dt.tz_localize(None)
            .dt.floor("5min")
        )
    else:
        df["interval_5min"] = pd.Series([], dtype="datetime64[ns]")
    return df


def _fetch_energy_data(
    utc_start: datetime, utc_end: datetime
) -> tuple[
    pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame
]:
    """Fetch all energy data from InfluxDB."""
    # Fetch hourly consumption and production diffs (using UTC range)
    consumed_df = fetch_hourly_diffs("energy.consumed", "value", utc_start, utc_end)
    produced_df = fetch_hourly_diffs("energy.produced", "value", utc_start, utc_end)

    # Fetch minutely power data (for no-battery scenario)
    consumed_power_df = fetch_minutely_power(
        "power.consumed", "value", utc_start, utc_end
    )
    pv_power_df = fetch_minutely_power("power.pv", "value", utc_start, utc_end)

    # Fetch battery SoC data
    battery_soc_df = fetch_minutely_power("energy.SoC", "value", utc_start, utc_end)

    # Fetch inverter mode data
    inverter_mode_df = fetch_minutely_power(
        "schedule.mode", "value", utc_start, utc_end
    )

    return (
        consumed_df,
        produced_df,
        consumed_power_df,
        pv_power_df,
        battery_soc_df,
        inverter_mode_df,
    )


def _process_battery_scenario_data(
    consumed_df: pd.DataFrame,
    produced_df: pd.DataFrame,
    price_per_hour: dict[datetime, object],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Process data for battery-optimized scenario."""
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

    return consumed_df, produced_df


def _process_no_battery_scenario_data(
    consumed_power_df: pd.DataFrame,
    pv_power_df: pd.DataFrame,
    price_per_hour: dict[datetime, object],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Process data for no-battery scenario."""
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

    return consumed_hourly, pv_hourly


def _process_battery_soc_data(battery_soc_df: pd.DataFrame) -> pd.DataFrame:
    """Process battery State of Charge data."""
    if len(battery_soc_df) > 0:
        battery_soc_df = _add_hour_column_to_dataframe(battery_soc_df)
        # Calculate average SoC per hour
        battery_soc_hourly = (
            battery_soc_df.groupby("hour")["value"].mean().reset_index()
        )
        battery_soc_hourly["soc_percent"] = battery_soc_hourly["value"]
    else:
        battery_soc_hourly = pd.DataFrame(columns=["hour", "value", "soc_percent"])

    return battery_soc_hourly


def _process_inverter_mode_data(inverter_mode_df: pd.DataFrame) -> pd.DataFrame:
    """Process inverter mode data and map to activity names at 5-minute resolution."""
    if len(inverter_mode_df) > 0:
        inverter_mode_df = _add_5min_column_to_dataframe(inverter_mode_df)
        # Calculate mode per 5-minute interval (use most frequent mode in the interval)
        inverter_mode_5min = (
            inverter_mode_df.groupby("interval_5min")["value"]
            .agg(lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0])
            .reset_index()
        )
        # Map mode numbers to activity names
        mode_to_activity = {
            1: "charge",
            2: "charge_solar_surplus",
            3: "charge_limit",
            4: "discharge_limit",
            5: "discharge_for_home",
            6: "discharge",
        }
        inverter_mode_5min["activity"] = inverter_mode_5min["value"].map(
            mode_to_activity
        )
        # Rename column for consistency
        inverter_mode_5min = inverter_mode_5min.rename(
            columns={"interval_5min": "hour"}
        )
    else:
        inverter_mode_5min = pd.DataFrame(columns=["hour", "value", "activity"])

    return inverter_mode_5min


def analyze_savings_patterns(
    evaluation_date: Optional[datetime] = None,
) -> pd.DataFrame:
    """
    Analyzes savings patterns by creating a comprehensive hourly breakdown of energy flows and costs.
    Returns a DataFrame with hourly data including purchased/sold energy, costs, and hypothetical scenarios.
    """
    # Get the evaluation date
    evaluation_date = _get_evaluation_date(evaluation_date)

    # Convert local date range to UTC for InfluxDB queries
    utc_start, utc_end = _convert_local_to_utc_range(evaluation_date)

    # Fetch and map electricity prices
    original_prices, price_per_hour = _fetch_and_map_prices(evaluation_date)

    # Fetch all energy data
    (
        consumed_df,
        produced_df,
        consumed_power_df,
        pv_power_df,
        battery_soc_df,
        inverter_mode_df,
    ) = _fetch_energy_data(utc_start, utc_end)

    # Process battery scenario data
    consumed_df, produced_df = _process_battery_scenario_data(
        consumed_df, produced_df, price_per_hour
    )

    # Process no-battery scenario data
    consumed_hourly, pv_hourly = _process_no_battery_scenario_data(
        consumed_power_df, pv_power_df, price_per_hour
    )

    # Process battery SoC data
    battery_soc_hourly = _process_battery_soc_data(battery_soc_df)

    # Process inverter mode data
    inverter_mode_5min = _process_inverter_mode_data(inverter_mode_df)

    # Create comprehensive analysis DataFrame
    analysis_data = []

    for hour in pd.date_range(
        evaluation_date,
        evaluation_date + timedelta(days=1) - timedelta(hours=1),
        freq="h",
    ):
        hour_dt = hour.replace(tzinfo=None)
        # All data is now in local time, so we can use hour_dt directly

        # Get actual flows (with battery)
        actual_consumed = 0
        if len(consumed_df) > 0 and "hour" in consumed_df.columns:
            matching_consumed = consumed_df[consumed_df["hour"] == hour_dt]
            if len(matching_consumed) > 0:
                actual_consumed = matching_consumed["diff"].iloc[0]

        actual_produced = 0
        if len(produced_df) > 0 and "hour" in produced_df.columns:
            matching_produced = produced_df[produced_df["hour"] == hour_dt]
            if len(matching_produced) > 0:
                actual_produced = matching_produced["diff"].iloc[0]

        # Get raw consumption/production (without battery)
        raw_consumed = 0
        if len(consumed_hourly) > 0 and "hour" in consumed_hourly.columns:
            matching_consumed_hourly = consumed_hourly[
                consumed_hourly["hour"] == hour_dt
            ]
            if len(matching_consumed_hourly) > 0:
                raw_consumed = matching_consumed_hourly["wh"].iloc[0]

        raw_produced = 0
        if len(pv_hourly) > 0 and "hour" in pv_hourly.columns:
            matching_pv_hourly = pv_hourly[pv_hourly["hour"] == hour_dt]
            if len(matching_pv_hourly) > 0:
                raw_produced = matching_pv_hourly["wh"].iloc[0]

        # Get battery SoC
        battery_soc = 0
        if len(battery_soc_hourly) > 0 and "hour" in battery_soc_hourly.columns:
            matching_soc = battery_soc_hourly[battery_soc_hourly["hour"] == hour_dt]
            if len(matching_soc) > 0:
                battery_soc = matching_soc["value"].iloc[0]

        # Get inverter mode
        inverter_mode = "idle"
        if len(inverter_mode_5min) > 0 and "hour" in inverter_mode_5min.columns:
            matching_mode = inverter_mode_5min[inverter_mode_5min["hour"] == hour_dt]
            if len(matching_mode) > 0:
                inverter_mode = matching_mode["activity"].iloc[0]

        # Get prices (prices are already in local time)
        price = price_per_hour.get(hour_dt)
        buy_price = price.get_buy_price() if price else 0
        sell_price = price.get_sell_price() if price else 0

        # Calculate actual costs/revenue (with battery)
        actual_purchased = max(0, actual_consumed)  # Energy purchased from grid
        actual_sold = max(0, actual_produced)  # Energy sold to grid
        actual_cost = actual_purchased * (buy_price / 1000)  # Convert Wh to kWh
        actual_revenue = actual_sold * (sell_price / 1000)
        actual_net_cost = actual_cost - actual_revenue

        # Calculate hypothetical costs/revenue (without battery)
        hypothetical_purchased = max(
            0, raw_consumed - raw_produced
        )  # Net energy needed from grid
        hypothetical_sold = max(
            0, raw_produced - raw_consumed
        )  # Net energy sold to grid
        hypothetical_cost = hypothetical_purchased * (buy_price / 1000)
        hypothetical_revenue = hypothetical_sold * (sell_price / 1000)
        hypothetical_net_cost = hypothetical_cost - hypothetical_revenue

        # Calculate savings
        savings = hypothetical_net_cost - actual_net_cost

        analysis_data.append(
            {
                "hour": hour_dt,
                "buy_price": buy_price,
                "sell_price": sell_price,
                "spot_price": price.get_spot_price() if price else 0,
                # Actual flows (with battery)
                "actual_purchased_wh": actual_purchased,
                "actual_sold_wh": actual_sold,
                "actual_cost_sek": actual_cost,
                "actual_revenue_sek": actual_revenue,
                "actual_net_cost_sek": actual_net_cost,
                # Raw flows (without battery)
                "raw_consumed_wh": raw_consumed,
                "raw_produced_wh": raw_produced,
                "hypothetical_purchased_wh": hypothetical_purchased,
                "hypothetical_sold_wh": hypothetical_sold,
                "hypothetical_cost_sek": hypothetical_cost,
                "hypothetical_revenue_sek": hypothetical_revenue,
                "hypothetical_net_cost_sek": hypothetical_net_cost,
                # Savings
                "savings_sek": savings,
                # Battery impact
                "battery_charge_wh": max(
                    0, actual_produced - actual_consumed
                ),  # Positive when charging
                "battery_discharge_wh": max(
                    0, actual_consumed - actual_produced
                ),  # Positive when discharging
                "battery_soc_percent": battery_soc,  # Battery state of charge
                "inverter_mode": inverter_mode,  # Inverter working mode
            }
        )

    return pd.DataFrame(analysis_data)


def _setup_plot_style() -> None:
    """Set up the plotting style and configuration."""
    plt.style.use("default")
    sns.set_palette("husl")


def _create_figure_with_subplots(df: pd.DataFrame) -> tuple[plt.Figure, plt.Axes]:
    """Create the main figure with subplots."""
    fig, axes = plt.subplots(2, 3, figsize=(20, 12))
    fig.suptitle(
        f'Savings Analysis - {df["hour"].iloc[0].date()}',
        fontsize=16,
        fontweight="bold",
    )
    return fig, axes


def _plot_cost_revenue_breakdown(ax: plt.Axes, df: pd.DataFrame) -> None:
    """Plot cost/revenue breakdown graph."""
    ax.plot(
        df["hour"],
        df["actual_cost_sek"],
        label="Actual cost",
        marker="o",
        linewidth=2,
        color="red",
    )
    ax.plot(
        df["hour"],
        df["actual_revenue_sek"],
        label="Actual revenue",
        marker="s",
        linewidth=2,
        color="green",
    )
    ax.plot(
        df["hour"],
        df["hypothetical_cost_sek"],
        label="Hypothetical cost",
        marker="^",
        linestyle="--",
        alpha=0.7,
        color="darkred",
    )
    ax.plot(
        df["hour"],
        df["hypothetical_revenue_sek"],
        label="Hypothetical revenue",
        marker="v",
        linestyle="--",
        alpha=0.7,
        color="darkgreen",
    )
    ax.set_title("Cost/Revenue Breakdown")
    ax.set_ylabel("SEK")
    ax.legend()
    ax.grid(True, alpha=0.3)


def _plot_net_cost_comparison(ax: plt.Axes, df: pd.DataFrame) -> None:
    """Plot net cost comparison graph with conditional colored areas."""
    ax.plot(
        df["hour"],
        df["actual_net_cost_sek"],
        label="With battery",
        marker="o",
        linewidth=2,
        color="blue",
    )
    ax.plot(
        df["hour"],
        df["hypothetical_net_cost_sek"],
        label="Without battery",
        marker="s",
        linewidth=2,
        color="orange",
    )

    # Create conditional colored areas based on which scenario is better
    # Green when battery performs better (with_battery < without_battery)
    # Red when battery performs worse (without_battery < with_battery)

    # Find where battery performs better (green areas)
    battery_better = df["actual_net_cost_sek"] < df["hypothetical_net_cost_sek"]
    if battery_better.any():
        ax.fill_between(
            df["hour"],
            df["actual_net_cost_sek"],
            df["hypothetical_net_cost_sek"],
            where=battery_better,
            alpha=0.3,
            color="green",
            label="Battery savings",
        )

    # Find where battery performs worse (red areas)
    battery_worse = df["actual_net_cost_sek"] > df["hypothetical_net_cost_sek"]
    if battery_worse.any():
        ax.fill_between(
            df["hour"],
            df["actual_net_cost_sek"],
            df["hypothetical_net_cost_sek"],
            where=battery_worse,
            alpha=0.3,
            color="red",
            label="Battery cost",
        )

    ax.set_title("Net Cost Comparison (Lower is Better)")
    ax.set_ylabel("SEK")
    ax.axhline(y=0, color="black", linestyle="-", alpha=0.3)
    ax.legend()
    ax.grid(True, alpha=0.3)


def _plot_battery_soc(
    ax: plt.Axes, df: pd.DataFrame, inverter_mode_5min: pd.DataFrame
) -> None:
    """Plot battery State of Charge graph with inverter mode background at 5-minute resolution."""
    # Define activity colors (matching plotting.py)
    activity_colors = {
        "charge": "#40EE60",
        "charge_solar_surplus": "#c6ff63",
        "charge_limit": "#00FFFF",
        "discharge": "#FF2621",
        "discharge_for_home": "#fca649",
        "discharge_limit": "#a18102",
        "self_consumption": "#A6A6AA",
        "idle": "#000000",
    }

    # Add background colored spans for inverter modes at 5-minute resolution
    if len(inverter_mode_5min) > 0 and "hour" in inverter_mode_5min.columns:
        timestamps = list(inverter_mode_5min["hour"])
        activities = list(inverter_mode_5min["activity"])
        current_activity = activities[0] if activities else "idle"
        start_idx = 0

        for i, activity in enumerate(activities):
            if activity != current_activity:
                color = activity_colors.get(current_activity, "#FFFFFF")
                ax.axvspan(
                    timestamps[start_idx], timestamps[i - 1], alpha=0.3, color=color
                )
                current_activity = activity
                start_idx = i

        # Handle the last segment
        if len(activities) > 0:
            color = activity_colors.get(current_activity, "#FFFFFF")
            ax.axvspan(timestamps[start_idx], timestamps[-1], alpha=0.3, color=color)

    # Plot battery SoC line
    ax.plot(
        df["hour"],
        df["battery_soc_percent"],
        label="Battery SoC",
        marker="o",
        linewidth=2,
        color="purple",
        zorder=10,  # Ensure line appears above background
    )
    ax.set_title("Battery State of Charge")
    ax.set_ylabel("SoC (%)")
    ax.set_ylim(0, 100)
    ax.legend()
    ax.grid(True, alpha=0.3)


def _plot_buy_sell_prices(ax: plt.Axes, df: pd.DataFrame) -> None:
    """Plot buy/sell prices graph."""
    ax.plot(
        df["hour"],
        df["buy_price"],
        label="Buy price",
        marker="o",
        linewidth=2,
        color="red",
    )
    ax.plot(
        df["hour"],
        df["sell_price"],
        label="Sell price",
        marker="s",
        linewidth=2,
        color="green",
    )
    ax.set_title("Buy/Sell Prices")
    ax.set_ylabel("SEK/kWh")
    ax.legend()
    ax.grid(True, alpha=0.3)


def _plot_battery_activity(ax: plt.Axes, df: pd.DataFrame) -> None:
    """Plot battery activity graph."""
    ax.plot(
        df["hour"],
        df["battery_charge_wh"],
        label="Battery charging",
        marker="o",
        linewidth=2,
        color="green",
    )
    ax.plot(
        df["hour"],
        df["battery_discharge_wh"],
        label="Battery discharging",
        marker="s",
        linewidth=2,
        color="red",
    )
    ax.set_title("Battery Activity")
    ax.set_ylabel("Energy (Wh)")
    ax.legend()
    ax.grid(True, alpha=0.3)


def _plot_energy_flows_comparison(ax: plt.Axes, df: pd.DataFrame) -> None:
    """Plot energy flows comparison graph."""
    ax.plot(
        df["hour"],
        df["actual_purchased_wh"],
        label="Purchased (with battery)",
        marker="o",
        linewidth=2,
        color="red",
    )
    ax.plot(
        df["hour"],
        df["actual_sold_wh"],
        label="Sold (with battery)",
        marker="s",
        linewidth=2,
        color="green",
    )
    ax.plot(
        df["hour"],
        df["hypothetical_purchased_wh"],
        label="Would purchase (no battery)",
        marker="^",
        linestyle="--",
        alpha=0.7,
        color="darkred",
    )
    ax.plot(
        df["hour"],
        df["hypothetical_sold_wh"],
        label="Would sell (no battery)",
        marker="v",
        linestyle="--",
        alpha=0.7,
        color="darkgreen",
    )
    ax.set_title("Energy Flows Comparison")
    ax.set_ylabel("Energy (Wh)")
    ax.legend()
    ax.grid(True, alpha=0.3)


def _format_axes(axes: plt.Axes) -> None:
    """Format all subplot axes with consistent styling."""
    for ax in axes.flat:
        ax.tick_params(axis="x", rotation=45)
        ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%H:%M"))


def create_savings_plots(
    df: pd.DataFrame, inverter_mode_5min: pd.DataFrame, save_path: Optional[str] = None
) -> None:
    """
    Creates comprehensive plots showing energy flows, costs, and savings patterns.
    """
    # Set up the plotting style
    _setup_plot_style()

    # Create a figure with multiple subplots
    fig, axes = _create_figure_with_subplots(df)

    # Create individual plots
    _plot_cost_revenue_breakdown(axes[0, 0], df)
    _plot_net_cost_comparison(axes[0, 1], df)
    _plot_battery_soc(axes[0, 2], df, inverter_mode_5min)
    _plot_buy_sell_prices(axes[1, 0], df)
    _plot_battery_activity(axes[1, 1], df)
    _plot_energy_flows_comparison(axes[1, 2], df)

    # Format all axes
    _format_axes(axes)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
    else:
        plt.show()


def print_summary_statistics(df: pd.DataFrame) -> None:
    """
    Prints a comprehensive summary of the savings analysis.
    """
    print(f"\n{'='*60}")
    print(f"SAVINGS ANALYSIS SUMMARY - {df['hour'].iloc[0].date()}")
    print(f"{'='*60}")

    # Overall statistics
    total_actual_cost = df["actual_cost_sek"].sum()
    total_actual_revenue = df["actual_revenue_sek"].sum()
    total_actual_net = df["actual_net_cost_sek"].sum()

    total_hypothetical_cost = df["hypothetical_cost_sek"].sum()
    total_hypothetical_revenue = df["hypothetical_revenue_sek"].sum()
    total_hypothetical_net = df["hypothetical_net_cost_sek"].sum()

    total_savings = df["savings_sek"].sum()

    print(f"\nOVERALL COSTS:")
    print(f"  Actual (with battery):     {total_actual_net:.2f} SEK")
    print(f"  Hypothetical (no battery): {total_hypothetical_net:.2f} SEK")
    print(f"  Total savings:             {total_savings:.2f} SEK")

    # Explain the savings calculation
    if total_hypothetical_net < 0 and total_actual_net < 0:
        print(f"  Note: Both scenarios are profitable (negative = profit)")
        print(f"  Battery optimization improved profit by {abs(total_savings):.2f} SEK")
    elif total_hypothetical_net > 0 and total_actual_net < 0:
        print(f"  Note: Battery turned a loss into a profit!")
    elif total_hypothetical_net > 0 and total_actual_net > 0:
        print(
            f"  Note: Both scenarios had costs, battery reduced them by {total_savings:.2f} SEK"
        )
    else:
        print(f"  Note: Battery reduced profit by {abs(total_savings):.2f} SEK")

    print(f"\nENERGY FLOWS:")
    print(
        f"  Total purchased (with battery):     {df['actual_purchased_wh'].sum():.0f} Wh"
    )
    print(f"  Total sold (with battery):          {df['actual_sold_wh'].sum():.0f} Wh")
    print(
        f"  Would purchase (no battery):        {df['hypothetical_purchased_wh'].sum():.0f} Wh"
    )
    print(
        f"  Would sell (no battery):            {df['hypothetical_sold_wh'].sum():.0f} Wh"
    )

    print(f"\nBATTERY ACTIVITY:")
    print(f"  Total battery charging:    {df['battery_charge_wh'].sum():.0f} Wh")
    print(f"  Total battery discharging: {df['battery_discharge_wh'].sum():.0f} Wh")

    # Hourly breakdown
    print(f"\nHOURLY BREAKDOWN:")
    print(
        f"{'Hour':<6} {'Purchased':<10} {'Sold':<10} {'Cost':<8} {'Revenue':<10} {'Net':<8} {'Savings':<10}"
    )
    print(f"{'-'*70}")
    for _, row in df.iterrows():
        hour_str = row["hour"].strftime("%H:%M")
        print(
            f"{hour_str:<6} {row['actual_purchased_wh']:<10.0f} {row['actual_sold_wh']:<10.0f} "
            f"{row['actual_cost_sek']:<8.2f} {row['actual_revenue_sek']:<10.2f} "
            f"{row['actual_net_cost_sek']:<8.2f} {row['savings_sek']:<10.2f}"
        )

    # Best and worst hours
    best_hour = df.loc[df["savings_sek"].idxmax()]
    worst_hour = df.loc[df["savings_sek"].idxmin()]

    print(
        f"\nBEST SAVINGS HOUR: {best_hour['hour'].strftime('%H:%M')} ({best_hour['savings_sek']:.2f} SEK)"
    )
    print(
        f"WORST SAVINGS HOUR: {worst_hour['hour'].strftime('%H:%M')} ({worst_hour['savings_sek']:.2f} SEK)"
    )


def main(
    evaluation_date: Optional[datetime] = None, save_plots: bool = False
) -> pd.DataFrame:
    """
    Main function to run the savings analysis.
    """
    # Run the analysis
    df = analyze_savings_patterns(evaluation_date)

    # Get the 5-minute inverter mode data for plotting
    utc_start, utc_end = _convert_local_to_utc_range(evaluation_date)
    _, _, _, _, _, inverter_mode_df = _fetch_energy_data(utc_start, utc_end)
    inverter_mode_5min = _process_inverter_mode_data(inverter_mode_df)

    # Create and save plots
    if save_plots:
        plot_filename = f"savings_analysis_{df['hour'].iloc[0].date()}.png"
        create_savings_plots(df, inverter_mode_5min, save_path=plot_filename)
    else:
        create_savings_plots(df, inverter_mode_5min)

    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze energy savings patterns with detailed hourly breakdown."
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Date to analyze in YYYY-MM-DD format (default: yesterday).",
    )
    parser.add_argument(
        "--save-plots",
        action="store_true",
        help="Save plots to file instead of displaying them.",
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

    main(evaluation_date, args.save_plots)
