from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

import matplotlib.pyplot as plt

from optimizer.models import TimeslotItem


def show_schedule_plot(schedule: Dict[datetime, TimeslotItem]) -> None:
    fig, ax1 = plt.subplots(figsize=(12, 8))
    activity_colors = {
        "charge": "#40EE60",
        "charge_solar_surplus": "#FFFF00",
        "charge_limit": "#00FFFF",
        "discharge": "#FF2621",
        "discharge_for_home": "#AAA500",
        "discharge_limit": "#FF8681",
        "self_consumption": "#A6A6AA",
        "idle": "#000000",
    }
    timestamps = list(schedule.keys())
    activities = [item.activity.value for item in schedule.values()]
    current_activity = activities[0]
    start_idx = 0
    for i, activity in enumerate(activities):
        if activity != current_activity:
            color = activity_colors.get(current_activity, "#FFFFFF")
            ax1.axvspan(
                timestamps[start_idx], timestamps[i - 1], alpha=0.3, color=color
            )
            current_activity = activity
            start_idx = i
    color = activity_colors.get(current_activity, "#FFFFFF")
    ax1.axvspan(timestamps[start_idx], timestamps[-1], alpha=0.3, color=color)
    ax1.plot(
        list(schedule.keys()),
        [-item.battery_flow_wh * 12 for item in schedule.values()],
        label="Battery Flow",
        linewidth=2,
    )
    ax1.plot(
        list(schedule.keys()),
        [item.house_consumption_wh * 12 for item in schedule.values()],
        label="House Consumption",
        linewidth=2,
    )
    ax1.plot(
        list(schedule.keys()),
        [item.grid_flow_wh * 12 for item in schedule.values()],
        label="Grid Flow",
        color="tab:purple",
        linewidth=2,
    )
    ax1.set_ylabel("Power (W)")
    ax1.set_xlabel("Time")
    ax2 = ax1.twinx()
    ax2.plot(
        list(schedule.keys()),
        [item.prices for item in schedule.values()],
        color="tab:red",
        label="Prices",
        linewidth=2,
    )
    ax2.set_ylabel("Price", color="tab:red")
    ax2.tick_params(axis="y", labelcolor="tab:red")
    ax3 = ax1.twinx()
    ax3.spines["right"].set_position(("outward", 60))
    ax3.plot(
        list(schedule.keys()),
        [(item.battery_expected_soc_wh / 440) for item in schedule.values()],
        color="tab:green",
        label="Battery SOC %",
        linewidth=2,
    )
    ax3.set_ylabel("Battery SOC (Wh)", color="tab:green")
    ax3.tick_params(axis="y", labelcolor="tab:green")
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
    fig.legend(
        activity_legend_elements,
        [elem.get_label() for elem in activity_legend_elements],
        loc="lower center",
        ncol=4,
        title="Activities",
        bbox_to_anchor=(0.5, 0.02),
    )
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.15)
    plt.show()
    plt.close(fig)


def save_schedule_plot(
    schedule: Dict[datetime, TimeslotItem], save_path: str = "schedule.png"
) -> None:
    fig, ax1 = plt.subplots(figsize=(12, 8))
    activity_colors = {
        "charge": "#43A047",  # Prominent green
        "charge_solar_surplus": "#A5D6A7",  # Light green
        "charge_limit": "#FFF59D",  # Pale yellow-green
        "discharge": "#C62828",  # Prominent red
        "discharge_for_home": "#FF8A65",  # Light red/orange
        "discharge_limit": "#FFCDD2",  # Pale red
        # self_consumption and idle removed
    }
    timestamps = list(schedule.keys())
    activities = [item.activity.value for item in schedule.values()]
    current_activity = activities[0]
    start_idx = 0
    for i, activity in enumerate(activities):
        if activity != current_activity:
            color = activity_colors.get(current_activity, "#FFFFFF")
            ax1.axvspan(
                timestamps[start_idx], timestamps[i - 1], alpha=0.3, color=color
            )
            current_activity = activity
            start_idx = i
    color = activity_colors.get(current_activity, "#FFFFFF")
    ax1.axvspan(timestamps[start_idx], timestamps[-1], alpha=0.3, color=color)

    ax1.plot(
        list(schedule.keys()),
        [(item.battery_expected_soc_wh / 440) for item in schedule.values()],
        color="tab:green",
        label="Battery SOC %",
        linewidth=2,
    )
    ax1.set_ylabel("Battery %")
    ax1.set_xlabel("Time")
    ax2 = ax1.twinx()
    ax2.plot(
        list(schedule.keys()),
        [item.prices for item in schedule.values()],
        color="tab:red",
        label="Prices",
        linewidth=2,
    )
    ax2.set_ylabel("Price", color="tab:red")
    ax2.tick_params(axis="y", labelcolor="tab:red")
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
    fig.legend(
        activity_legend_elements,
        [elem.get_label() for elem in activity_legend_elements],
        loc="lower center",
        ncol=4,
        title="Activities",
        bbox_to_anchor=(0.5, 0.02),
    )
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.15)
    plt.savefig(save_path)
    plt.close(fig)
