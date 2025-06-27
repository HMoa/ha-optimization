#!/usr/bin/env python3
"""
Console Application start
"""
import json
import sys

import matplotlib

# matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from battery_optimizer_workflow import BatteryOptimizerWorkflow


def main():
    """Main function of the application."""
    import argparse

    parser = argparse.ArgumentParser(description="Battery Optimizer Workflow")
    parser.add_argument(
        "--battery_percent",
        type=int,
        default=84,
        help="Initial battery percent",
    )
    args = parser.parse_args()

    print(f"Initial battery percent: {args.battery_percent}")
    workflow = BatteryOptimizerWorkflow(battery_percent=args.battery_percent)
    # workflow.run_workflow()
    schedule = workflow.generate_schedule_from_file()

    # Convert schedule to JSON-serializable format
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

    print("Schedule saved to schedule.json")

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


def plot_consumption():
    from datetime import datetime, timedelta

    from consumption_provider import get_consumption

    start_date = datetime(2025, 6, 28, 0, 0, 0)  # 1st of June 2025
    consumption = get_consumption(start_date, start_date + timedelta(days=1))

    fig, ax1 = plt.subplots()
    ax1.plot(consumption.keys(), consumption.values(), label="Consumption")
    ax1.set_ylabel("Consumption")
    ax1.set_xlabel("Time")
    ax1.legend(loc="upper left")
    plt.show()


if __name__ == "__main__":
    # This ensures that the main() function is called only when this script is run directly
    # (not when imported as a module)
    sys.exit(main())
    # sys.exit(plot_consumption())
