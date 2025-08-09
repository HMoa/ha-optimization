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


def analyze_savings_patterns(
    evaluation_date: Optional[datetime] = None,
) -> pd.DataFrame:
    """
    Analyzes savings patterns by creating a comprehensive hourly breakdown of energy flows and costs.
    Returns a DataFrame with hourly data including purchased/sold energy, costs, and hypothetical scenarios.
    """
    # Get the date to evaluate (default to yesterday if not specified)
    if evaluation_date is None:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        evaluation_date = today - timedelta(days=1)

    # Convert local date range to UTC for InfluxDB queries
    local_start = evaluation_date
    local_end = evaluation_date + timedelta(days=1)

    # Convert to UTC (local time - 2 hours for CEST)
    utc_start = local_start - timedelta(hours=2)
    utc_end = local_end - timedelta(hours=2)

    print(f"Analyzing data for {evaluation_date.date()}")
    print(f"Local time range: {local_start} to {local_end}")
    print(f"UTC time range for InfluxDB: {utc_start} to {utc_end} (local time - 2h)")

    # Fetch hourly prices for the evaluation date
    prices: Dict[datetime, Elpris] = fetch_electricity_prices(evaluation_date, "SE3")
    print(f"Fetched {len(prices)} price points")
    # Map prices to hour (truncate to hour and convert to timezone-naive)
    price_per_hour = {
        dt.replace(minute=0, second=0, microsecond=0).replace(tzinfo=None): price
        for dt, price in prices.items()
    }

    # Fetch actual energy flows (with battery optimization) - using UTC range
    consumed_df = fetch_hourly_diffs("energy.consumed", "value", utc_start, utc_end)
    produced_df = fetch_hourly_diffs("energy.produced", "value", utc_start, utc_end)

    # Fetch battery SoC data
    battery_soc_df = fetch_minutely_power("energy.SoC", "value", utc_start, utc_end)

    print(f"Fetched {len(consumed_df)} consumed data points")
    print(f"Fetched {len(produced_df)} produced data points")
    print(f"Fetched {len(battery_soc_df)} battery SoC data points")

    # Convert timestamps to datetime and align to hour (convert UTC to local time)
    if len(consumed_df) > 0:
        consumed_df["hour"] = (
            pd.to_datetime(consumed_df["timestamp"])
            .dt.tz_convert("Europe/Stockholm")
            .dt.tz_localize(None)
            .dt.floor("h")
        )
    if len(produced_df) > 0:
        produced_df["hour"] = (
            pd.to_datetime(produced_df["timestamp"])
            .dt.tz_convert("Europe/Stockholm")
            .dt.tz_localize(None)
            .dt.floor("h")
        )

    # Fetch raw power data (without battery optimization)
    consumed_power_df = fetch_minutely_power(
        "power.consumed", "value", utc_start, utc_end
    )
    pv_power_df = fetch_minutely_power("power.pv", "value", utc_start, utc_end)

    print(f"Fetched {len(consumed_power_df)} consumed power data points")
    print(f"Fetched {len(pv_power_df)} PV power data points")

    # Convert timestamps to datetime and align to hour (convert UTC to local time)
    if len(consumed_power_df) > 0:
        consumed_power_df["hour"] = (
            pd.to_datetime(consumed_power_df["timestamp"])
            .dt.tz_convert("Europe/Stockholm")
            .dt.tz_localize(None)
            .dt.floor("h")
        )
    if len(pv_power_df) > 0:
        pv_power_df["hour"] = (
            pd.to_datetime(pv_power_df["timestamp"])
            .dt.tz_convert("Europe/Stockholm")
            .dt.tz_localize(None)
            .dt.floor("h")
        )

    # Convert W to Wh per minute, then sum by hour
    if len(consumed_power_df) > 0:
        consumed_power_df["wh"] = consumed_power_df["value"] / 60.0
        consumed_hourly = consumed_power_df.groupby("hour")["wh"].sum().reset_index()
    else:
        consumed_hourly = pd.DataFrame(columns=["hour", "wh"])

    if len(pv_power_df) > 0:
        pv_power_df["wh"] = pv_power_df["value"] / 60.0
        pv_hourly = pv_power_df.groupby("hour")["wh"].sum().reset_index()
    else:
        pv_hourly = pd.DataFrame(columns=["hour", "wh"])

    # Process battery SoC data (convert UTC to local time)
    if len(battery_soc_df) > 0:
        battery_soc_df["hour"] = (
            pd.to_datetime(battery_soc_df["timestamp"])
            .dt.tz_convert("Europe/Stockholm")
            .dt.tz_localize(None)
            .dt.floor("h")
        )
        battery_soc_hourly = (
            battery_soc_df.groupby("hour")["value"].mean().reset_index()
        )
    else:
        battery_soc_hourly = pd.DataFrame(columns=["hour", "value"])

    # Create comprehensive analysis DataFrame
    analysis_data = []

    for hour in pd.date_range(local_start, local_end - timedelta(hours=1), freq="h"):
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
            }
        )

    return pd.DataFrame(analysis_data)


def create_savings_plots(df: pd.DataFrame, save_path: Optional[str] = None) -> None:
    """
    Creates comprehensive plots showing energy flows, costs, and savings patterns.
    """
    # Set up the plotting style
    plt.style.use("default")
    sns.set_palette("husl")

    # Create a figure with multiple subplots
    fig, axes = plt.subplots(2, 3, figsize=(20, 12))
    fig.suptitle(
        f'Savings Analysis - {df["hour"].iloc[0].date()}',
        fontsize=16,
        fontweight="bold",
    )

    # 1. Cost/Revenue breakdown
    ax1 = axes[0, 0]
    ax1.plot(
        df["hour"],
        df["actual_cost_sek"],
        label="Actual cost",
        marker="o",
        linewidth=2,
        color="red",
    )
    ax1.plot(
        df["hour"],
        df["actual_revenue_sek"],
        label="Actual revenue",
        marker="s",
        linewidth=2,
        color="green",
    )
    ax1.plot(
        df["hour"],
        df["hypothetical_cost_sek"],
        label="Hypothetical cost",
        marker="^",
        linestyle="--",
        alpha=0.7,
        color="darkred",
    )
    ax1.plot(
        df["hour"],
        df["hypothetical_revenue_sek"],
        label="Hypothetical revenue",
        marker="v",
        linestyle="--",
        alpha=0.7,
        color="darkgreen",
    )
    ax1.set_title("Cost/Revenue Breakdown")
    ax1.set_ylabel("SEK")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 2. Cost comparison
    ax2 = axes[0, 1]
    ax2.plot(
        df["hour"],
        df["actual_cost_sek"],
        label="Actual cost",
        marker="o",
        linewidth=2,
        color="red",
    )
    ax2.plot(
        df["hour"],
        df["actual_revenue_sek"],
        label="Actual revenue",
        marker="s",
        linewidth=2,
        color="green",
    )
    ax2.plot(
        df["hour"],
        df["hypothetical_cost_sek"],
        label="Hypothetical cost",
        marker="^",
        linestyle="--",
        alpha=0.7,
        color="darkred",
    )
    ax2.plot(
        df["hour"],
        df["hypothetical_revenue_sek"],
        label="Hypothetical revenue",
        marker="v",
        linestyle="--",
        alpha=0.7,
        color="darkgreen",
    )
    ax2.set_title("Cost/Revenue Comparison")
    ax2.set_ylabel("SEK")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # 2. Net cost comparison (clearer than savings)
    ax2 = axes[0, 1]
    ax2.plot(
        df["hour"],
        df["actual_net_cost_sek"],
        label="With battery",
        marker="o",
        linewidth=2,
        color="blue",
    )
    ax2.plot(
        df["hour"],
        df["hypothetical_net_cost_sek"],
        label="Without battery",
        marker="s",
        linewidth=2,
        color="orange",
    )
    ax2.fill_between(
        df["hour"],
        df["actual_net_cost_sek"],
        df["hypothetical_net_cost_sek"],
        alpha=0.3,
        color="green",
        label="Savings area",
    )
    ax2.set_title("Net Cost Comparison (Lower is Better)")
    ax2.set_ylabel("SEK")
    ax2.axhline(y=0, color="black", linestyle="-", alpha=0.3)
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # 3. Battery State of Charge
    ax3 = axes[0, 2]
    ax3.plot(
        df["hour"],
        df["battery_soc_percent"],
        label="Battery SoC",
        marker="o",
        linewidth=2,
        color="purple",
    )
    ax3.set_title("Battery State of Charge")
    ax3.set_ylabel("SoC (%)")
    ax3.set_ylim(0, 100)
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # 4. Buy/Sell Prices
    ax4 = axes[1, 0]
    ax4.plot(
        df["hour"],
        df["buy_price"],
        label="Buy price",
        marker="o",
        linewidth=2,
        color="red",
    )
    ax4.plot(
        df["hour"],
        df["sell_price"],
        label="Sell price",
        marker="s",
        linewidth=2,
        color="green",
    )
    ax4.set_title("Buy/Sell Prices")
    ax4.set_ylabel("SEK/kWh")
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    # 5. Battery activity
    ax5 = axes[1, 1]
    ax5.plot(
        df["hour"],
        df["battery_charge_wh"],
        label="Battery charging",
        marker="o",
        linewidth=2,
        color="green",
    )
    ax5.plot(
        df["hour"],
        df["battery_discharge_wh"],
        label="Battery discharging",
        marker="s",
        linewidth=2,
        color="red",
    )
    ax5.set_title("Battery Activity")
    ax5.set_ylabel("Energy (Wh)")
    ax5.legend()
    ax5.grid(True, alpha=0.3)

    # 6. Energy flows comparison
    ax6 = axes[1, 2]
    ax6.plot(
        df["hour"],
        df["actual_purchased_wh"],
        label="Purchased (with battery)",
        marker="o",
        linewidth=2,
        color="red",
    )
    ax6.plot(
        df["hour"],
        df["actual_sold_wh"],
        label="Sold (with battery)",
        marker="s",
        linewidth=2,
        color="green",
    )
    ax6.plot(
        df["hour"],
        df["hypothetical_purchased_wh"],
        label="Would purchase (no battery)",
        marker="^",
        linestyle="--",
        alpha=0.7,
        color="darkred",
    )
    ax6.plot(
        df["hour"],
        df["hypothetical_sold_wh"],
        label="Would sell (no battery)",
        marker="v",
        linestyle="--",
        alpha=0.7,
        color="darkgreen",
    )
    ax6.set_title("Energy Flows Comparison")
    ax6.set_ylabel("Energy (Wh)")
    ax6.legend()
    ax6.grid(True, alpha=0.3)

    # Format x-axis for all subplots
    for ax in axes.flat:
        ax.tick_params(axis="x", rotation=45)
        ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%H:%M"))

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Plots saved to {save_path}")
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


def main(evaluation_date: Optional[datetime] = None, save_plots: bool = False) -> None:
    """
    Main function to run the savings analysis.
    """
    print(f"Analyzing savings patterns...")

    # Run the analysis
    df = analyze_savings_patterns(evaluation_date)

    # Print summary statistics
    print_summary_statistics(df)

    # Create and save plots
    if save_plots:
        plot_filename = f"savings_analysis_{df['hour'].iloc[0].date()}.png"
        create_savings_plots(df, save_path=plot_filename)
    else:
        create_savings_plots(df)

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
