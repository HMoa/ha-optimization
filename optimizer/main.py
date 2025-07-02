#!/usr/bin/env python3
"""
Console Application start
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta

import matplotlib
import matplotlib.pyplot as plt

from optimizer.battery_optimizer_workflow import BatteryOptimizerWorkflow
from optimizer.consumption_provider import get_consumption
from optimizer.production_provider import get_production


def plot_outcome(battery_percent: int) -> int:
    workflow = BatteryOptimizerWorkflow(battery_percent=battery_percent)
    schedule = workflow.generate_schedule_from_file()

    if schedule is None:
        print("No schedule available to plot")
        return 1

    fig, ax1 = plt.subplots()

    # Plot battery_flow and house_consumption on the left y-axis
    ax1.plot(
        list(schedule.keys()),
        [-item.battery_flow for item in schedule.values()],
        label="Battery Flow",
    )
    ax1.plot(
        list(schedule.keys()),
        [item.house_consumption for item in schedule.values()],
        label="House Consumption",
    )
    ax1.plot(
        list(schedule.keys()),
        [item.grid_flow for item in schedule.values()],
        label="Grid Flow",
        color="tab:purple",
    )
    ax1.set_ylabel("Battery Flow / House Consumption")
    ax1.set_xlabel("Time")
    ax1.legend(loc="upper left")

    # Create a second y-axis for prices
    ax2 = ax1.twinx()
    ax2.plot(
        list(schedule.keys()),
        [item.prices for item in schedule.values()],
        color="tab:red",
        label="Prices",
    )
    ax2.set_ylabel("Prices", color="tab:red")
    ax2.tick_params(axis="y", labelcolor="tab:red")
    ax2.legend(loc="upper right")

    # Create a third y-axis for battery SOC
    ax3 = ax1.twinx()
    # Offset the third axis to the right
    ax3.spines["right"].set_position(("outward", 60))
    ax3.plot(
        list(schedule.keys()),
        [(item.battery_expected_soc / 440) for item in schedule.values()],
        color="tab:green",
        label="Battery SOC %",
    )
    ax3.set_ylabel("Battery SOC (Wh)", color="tab:green")
    ax3.tick_params(axis="y", labelcolor="tab:green")
    ax3.legend(loc="upper right", bbox_to_anchor=(1.15, 1))

    plt.tight_layout()
    plt.show()

    return 0


def generate_schedule(battery_percent: int) -> None:
    workflow = BatteryOptimizerWorkflow(battery_percent=battery_percent)
    workflow.generate_schedule()

    if workflow.schedule is None:
        print("No schedule generated")
        return

    schedule_json = {}
    for timestamp, item in workflow.schedule.items():
        schedule_json[timestamp.isoformat()] = {
            "start_time": item.start_time.isoformat(),
            "prices": item.prices,
            "battery_flow": item.battery_flow,
            "battery_expected_soc": item.battery_expected_soc,
            "house_consumption": item.house_consumption,
            "activity": item.activity.value,
            "amount": item.amount,
        }

    # Save to file
    with open("schedule.json", "w") as f:
        json.dump(schedule_json, f, indent=2)


def plot_consumption() -> None:

    start_date = datetime(2025, 6, 18, 0, 0, 0)  # 1st of June 2025
    consumption = get_consumption(start_date, start_date + timedelta(days=1))

    fig, ax1 = plt.subplots()
    ax1.plot(list(consumption.keys()), list(consumption.values()), label="Consumption")
    ax1.set_ylabel("Consumption")
    ax1.set_xlabel("Time")
    ax1.legend(loc="upper left")
    plt.show()


def plot_production() -> None:

    start_date = datetime(2025, 6, 6, 0, 0, 0)  # 1st of June 2025
    production = get_production(start_date, start_date + timedelta(days=1))

    fig, ax1 = plt.subplots()
    ax1.plot(list(production.keys()), list(production.values()), label="Production")
    ax1.set_ylabel("Production")
    ax1.set_xlabel("Time")
    ax1.legend(loc="upper left")
    plt.show()


def main() -> None:
    """Main function of the application."""

    parser = argparse.ArgumentParser(description="Battery Optimizer Workflow")
    parser.add_argument(
        "--battery_percent",
        type=int,
        default=84,
        help="Initial battery percent",
    )
    parser.add_argument(
        "--generate_schedule",
        action="store_true",
        default=True,
        help="Generate schedule (default: True)",
    )
    parser.add_argument(
        "--plot_only",
        action="store_true",
        default=False,
        help="Plot schedule instead of generating (default: generate schedule)",
    )
    args = parser.parse_args()

    if args.plot_only:
        print("Plotting schedule")
        sys.exit(plot_outcome(args.battery_percent))
    else:
        print("Generating schedule")
        generate_schedule(args.battery_percent)


if __name__ == "__main__":
    main()
