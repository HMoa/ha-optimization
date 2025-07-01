#!/usr/bin/env python3
from __future__ import annotations

import pandas as pd


def resample_to_5min(df: pd.DataFrame) -> pd.DataFrame:
    """Resample 1-minute data to 5-minute intervals"""
    df_resampled = df.set_index("time")["value"].resample("5min").mean().reset_index()
    return df_resampled


def analyze_daily_consumption(df: pd.DataFrame, resolution_name: str) -> pd.Series:
    """Analyze daily consumption patterns from watt data"""

    print(f"\n=== {resolution_name.upper()} RESOLUTION ANALYSIS ===")
    print(f"Data points: {len(df)}")
    print(f"Date range: {df['time'].min()} to {df['time'].max()}")

    # Convert watts to watt-hours
    if resolution_name == "1-minute":
        # 1 minute = 1/60 hour
        df["watt_hours"] = df["value"] * (1 / 60)
    else:  # 5-minute
        # 5 minutes = 5/60 = 1/12 hour
        df["watt_hours"] = df["value"] * (5 / 60)

    # Group by date and sum to get daily consumption
    df["date"] = df["time"].dt.date
    daily_consumption = df.groupby("date")["watt_hours"].sum()

    print(f"Number of days: {len(daily_consumption)}")
    print(
        f"Average daily consumption: {daily_consumption.mean():.2f} Wh ({daily_consumption.mean()/1000:.2f} kWh)"
    )
    print(
        f"Median daily consumption: {daily_consumption.median():.2f} Wh ({daily_consumption.median()/1000:.2f} kWh)"
    )
    print(
        f"Standard deviation: {daily_consumption.std():.2f} Wh ({daily_consumption.std()/1000:.2f} kWh)"
    )
    print(
        f"Min daily consumption: {daily_consumption.min():.2f} Wh ({daily_consumption.min()/1000:.2f} kWh)"
    )
    print(
        f"Max daily consumption: {daily_consumption.max():.2f} Wh ({daily_consumption.max()/1000:.2f} kWh)"
    )

    # Calculate coefficient of variation (CV = std/mean)
    cv = daily_consumption.std() / daily_consumption.mean()
    print(f"Coefficient of variation: {cv:.3f} ({cv*100:.1f}%)")

    # Show daily consumption values
    print("Daily consumption values (Wh):")
    for date, consumption in daily_consumption.items():
        print(f"{date}: {consumption:.2f} Wh ({consumption/1000:.2f} kWh)")

    return daily_consumption


def main() -> None:
    print("Loading consumption data...")

    # Load the consumption data
    df_1min = pd.read_csv("consumed-power.csv", parse_dates=["time"], sep=",")
    df_1min = df_1min.dropna(subset=["time", "value"])

    print(f"Original 1-minute data: {len(df_1min)} points")

    # Create 5-minute downsampled version
    df_5min = resample_to_5min(df_1min.copy())
    df_5min = df_5min.dropna(subset=["time", "value"])

    print(f"5-minute downsampled data: {len(df_5min)} points")

    # Analyze both versions
    daily_1min = analyze_daily_consumption(df_1min, "1-minute")
    daily_5min = analyze_daily_consumption(df_5min, "5-minute")

    # Compare results
    print("=== COMPARISON ===")
    print(f"1-minute average: {daily_1min.mean():.2f} Wh")
    print(f"5-minute average: {daily_5min.mean():.2f} Wh")
    print(
        f"Difference: {abs(daily_1min.mean() - daily_5min.mean()):.2f} Wh ({abs(daily_1min.mean() - daily_5min.mean())/daily_1min.mean()*100:.1f}%)"
    )

    print(f"\n1-minute std: {daily_1min.std():.2f} Wh")
    print(f"5-minute std: {daily_5min.std():.2f} Wh")
    print(
        f"Difference: {abs(daily_1min.std() - daily_5min.std()):.2f} Wh ({abs(daily_1min.std() - daily_5min.std())/daily_1min.std()*100:.1f}%)"
    )


if __name__ == "__main__":
    main()
