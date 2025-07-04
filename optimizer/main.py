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

    fig, ax1 = plt.subplots(figsize=(12, 8))

    # Define colors for different activities
    activity_colors = {
        "charge": "#40EE60",  # Green
        "charge_solar_surplus": "#FFFF00",  # Yellow
        "charge_limit": "#00FFFF",  # Light blue
        "discharge": "#FF2621",  # Red
        "discharge_for_home": "#AAA500",  # Orange
        "discharge_limit": "#FF8681",  # Light pink
        "self_consumption": "#A6A6AA",  # Gray
        "idle": "#000000",  # Black
    }

    # Create background bands for activities
    timestamps = list(schedule.keys())
    activities = [item.activity.value for item in schedule.values()]

    # Group consecutive activities
    current_activity = activities[0]
    start_idx = 0

    for i, activity in enumerate(activities):
        if activity != current_activity:
            # Color the background for the previous activity
            color = activity_colors.get(current_activity, "#FFFFFF")
            ax1.axvspan(
                timestamps[start_idx], timestamps[i - 1], alpha=0.3, color=color
            )
            current_activity = activity
            start_idx = i

    # Color the last activity group
    color = activity_colors.get(current_activity, "#FFFFFF")
    ax1.axvspan(timestamps[start_idx], timestamps[-1], alpha=0.3, color=color)

    # Plot battery_flow and house_consumption on the left y-axis
    ax1.plot(
        list(schedule.keys()),
        [
            -item.battery_flow * 12 for item in schedule.values()
        ],  # Convert Wh to W (5-min timeslots)
        label="Battery Flow",
        linewidth=2,
    )
    ax1.plot(
        list(schedule.keys()),
        [item.house_consumption * 12 for item in schedule.values()],  # Convert Wh to W
        label="House Consumption",
        linewidth=2,
    )
    ax1.plot(
        list(schedule.keys()),
        [item.grid_flow * 12 for item in schedule.values()],  # Convert Wh to W
        label="Grid Flow",
        color="tab:purple",
        linewidth=2,
    )
    ax1.set_ylabel("Power (W)")
    ax1.set_xlabel("Time")
    ax1.legend(loc="upper left")

    # Create a second y-axis for prices
    ax2 = ax1.twinx()
    ax2.plot(
        list(schedule.keys()),
        [item.prices for item in schedule.values()],
        color="tab:red",
        label="Prices",
        linewidth=2,
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
        linewidth=2,
    )
    ax3.set_ylabel("Battery SOC (Wh)", color="tab:green")
    ax3.tick_params(axis="y", labelcolor="tab:green")
    ax3.legend(loc="upper right", bbox_to_anchor=(1.15, 1))

    # Add activity legend at the bottom
    activity_legend_elements = []
    for activity, color in activity_colors.items():
        activity_legend_elements.append(
            plt.Rectangle(
                (0, 0),
                1,
                1,
                facecolor=color,
                alpha=0.3,
                label=activity.replace("_", " ").title(),
            )
        )

    # Create a separate legend for activities at the bottom
    fig.legend(
        activity_legend_elements,
        [elem.get_label() for elem in activity_legend_elements],
        loc="lower center",
        ncol=4,
        title="Activities",
        bbox_to_anchor=(0.5, 0.02),
    )

    plt.tight_layout()
    plt.subplots_adjust(bottom=0.15)  # Make room for the activity legend
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
