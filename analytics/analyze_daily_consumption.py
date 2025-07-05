#!/usr/bin/env python3
from __future__ import annotations

import pandas as pd


def analyze_daily_consumption(df: pd.DataFrame) -> pd.Series:
    """Analyze daily consumption patterns from 1-minute watt data"""

    print("Loading consumption data...")

    # Remove null values
    df = df.dropna(subset=["time", "value"])

    print(f"Loaded {len(df)} data points")
    print(f"Date range: {df['time'].min()} to {df['time'].max()}")

    # Convert watts to watt-hours (1 minute = 1/60 hour)
    # Power (W) × Time (h) = Energy (Wh)
    df["watt_hours"] = df["value"] * (1 / 60)  # Convert 1-minute watts to watt-hours

    # Group by date and sum to get daily consumption
    df["date"] = df["time"].dt.date
    daily_consumption = df.groupby("date")["watt_hours"].sum()

    print("=== DAILY CONSUMPTION ANALYSIS ===")
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

    # Additional analysis
    print("Additional insights:")
    print(
        f"Total consumption period: {daily_consumption.sum():.2f} Wh ({daily_consumption.sum()/1000:.2f} kWh)"
    )
    print(f"Average hourly consumption: {daily_consumption.mean()/24:.2f} Wh")

    # Day of week analysis
    df["day_of_week"] = df["time"].dt.day_name()
    daily_avg_by_weekday = (
        df.groupby("day_of_week")["watt_hours"].sum().groupby(level=0).mean()
    )
    print("Average consumption by day of week:")
    for day, consumption in daily_avg_by_weekday.items():
        print(f"{day}: {consumption:.2f} Wh ({consumption/1000:.2f} kWh)")

    return daily_consumption


if __name__ == "__main__":
    # Load the consumption data
    df = pd.read_csv("analytics/consumption250705-2.csv", parse_dates=["time"], sep=",")
    df = df.dropna(subset=["time", "value"])
    analyze_daily_consumption(df)
