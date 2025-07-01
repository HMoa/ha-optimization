#!/usr/bin/env python3
"""
Console Application start
"""
import argparse
import json
import sys

import matplotlib
import matplotlib.pyplot as plt
from battery_optimizer_workflow import BatteryOptimizerWorkflow


def plot_outcome(battery_percent):
    workflow = BatteryOptimizerWorkflow(battery_percent=battery_percent)
    # workflow.run_workflow()
    schedule = workflow.generate_schedule_from_file()

    fig, ax1 = plt.subplots()

    # Plot battery_flow and house_consumption on the left y-axis
    ax1.plot(
        schedule.keys(),
        [-item.battery_flow for item in schedule.values()],
        label="Battery Flow",
    )
    ax1.plot(
        schedule.keys(),
        [item.house_consumption for item in schedule.values()],
        label="House Consumption",
    )
    ax1.plot(
        schedule.keys(),
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
        schedule.keys(),
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
        schedule.keys(),
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


def generate_schedule(battery_percent):
    workflow = BatteryOptimizerWorkflow(battery_percent=battery_percent)
    schedule = workflow.generate_schedule()

    schedule_json = {}
    for timestamp, item in schedule.items():
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


def plot_consumption():
    from datetime import datetime, timedelta

    from consumption_provider import get_consumption

    start_date = datetime(2025, 6, 18, 0, 0, 0)  # 1st of June 2025
    consumption = get_consumption(start_date, start_date + timedelta(days=1))

    fig, ax1 = plt.subplots()
    ax1.plot(consumption.keys(), consumption.values(), label="Consumption")
    ax1.set_ylabel("Consumption")
    ax1.set_xlabel("Time")
    ax1.legend(loc="upper left")
    plt.show()


def plot_production():
    from datetime import datetime, timedelta

    from production_provider import get_production

    start_date = datetime(2025, 6, 28, 0, 0, 0)  # 1st of June 2025
    production = get_production(start_date, start_date + timedelta(days=1))

    fig, ax1 = plt.subplots()
    ax1.plot(production.keys(), production.values(), label="Production")
    ax1.set_ylabel("Production")
    ax1.set_xlabel("Time")
    ax1.legend(loc="upper left")
    plt.show()


def main():
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
        type=bool,
        default=True,
        help="Generate schedule",
    )
    args = parser.parse_args()
    if args.generate_schedule:
        generate_schedule(args.battery_percent)
    else:
        sys.exit(plot_outcome(args.battery_percent))


if __name__ == "__main__":
    main()
