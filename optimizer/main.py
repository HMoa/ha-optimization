#!/usr/bin/env python
"""
Console Application start
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

from optimizer.battery_optimizer_workflow import BatteryOptimizerWorkflow
from optimizer.plotting import show_schedule_plot


def plot_outcome(battery_percent: float) -> int:
    from optimizer.battery_optimizer_workflow import BatteryOptimizerWorkflow

    workflow = BatteryOptimizerWorkflow(battery_percent=battery_percent)
    workflow.generate_schedule()
    schedule = workflow.schedule
    if schedule is None:
        print("No schedule available to plot")
        return 1
    show_schedule_plot(schedule, workflow.config)
    return 0


def generate_schedule(
    battery_percent: float,
    ev_soc_percent: float | None = None,
    ev_ready_time: str | None = None,
    save: bool = False,
    save_image: bool = False,
) -> None:

    workflow = BatteryOptimizerWorkflow(
        battery_percent=battery_percent,
        ev_soc_percent=ev_soc_percent,
        ev_ready_time=ev_ready_time,
    )
    workflow.generate_schedule()

    if workflow.schedule is None:
        print("No schedule generated")
        return

    schedule_json = {}
    for timestamp, item in workflow.schedule.items():
        schedule_json[timestamp.isoformat()] = {
            "start_time": item.start_time.isoformat(),
            "prices": item.prices,
            "battery_flow": item.battery_flow_wh,
            "battery_expected_soc": item.battery_expected_soc_percent,
            "house_consumption": item.house_consumption_wh,
            "activity": item.activity.value,
            "amount": item.amount,
            "amount_percent": item.amount_percent(),
        }

    # Save to file
    with open("schedule.json", "w") as f:
        json.dump(schedule_json, f, indent=2)

    if save_image:
        from optimizer.plotting import save_schedule_plot

        save_schedule_plot(
            workflow.schedule, save_path="schedule.png", battery_config=workflow.config
        )
        print("Schedule plot saved as schedule.png")


def main() -> None:
    """Main function of the application."""

    parser = argparse.ArgumentParser(description="Battery Optimizer Workflow")
    parser.add_argument(
        "--battery_percent",
        type=float,
        default=84,
        help="Initial battery percent",
    )
    parser.add_argument(
        "--ev_soc_percent",
        type=float,
        default=None,
        help="Current EV battery state of charge (percent)",
    )
    parser.add_argument(
        "--ev_ready_time",
        type=str,
        default=None,
        help="When the EV should be charged and ready (ISO format: YYYY-MM-DDTHH:MM:SS)",
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
    parser.add_argument(
        "--use_influxdb",
        action="store_true",
        default=False,
        help="Fetch initial consumption values from InfluxDB",
    )
    parser.add_argument(
        "--influxdb_config",
        type=str,
        default="config/influxdb_config.json",
        help="Path to InfluxDB configuration file",
    )
    parser.add_argument(
        "--current-schedule",
        action="store_true",
        default=False,
        help="Print the current item in schedule.json (closest to now, not after)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        default=False,
        help="Save optimizer parameters to sample_data/optimizer_params.pkl",
    )
    parser.add_argument(
        "--save_image",
        action="store_true",
        default=False,
        help="Save schedule plot as an image (schedule.png)",
    )
    args = parser.parse_args()

    if args.current_schedule:
        try:
            with open("schedule.json", "r") as f:
                schedule = json.load(f)
            now = datetime.now().astimezone()
            # Sort the keys and loop through, taking the last one not after now
            last_key = None
            for k in sorted(schedule.keys()):
                dt = datetime.fromisoformat(k)
                if dt <= now:
                    last_key = k
                else:
                    break
            if last_key is not None:
                print(json.dumps(schedule[last_key], indent=2))
            else:
                print("No schedule item found for the current time or earlier.")
        except Exception as e:
            print(f"Error reading schedule.json: {e}")
        sys.exit(0)

    if args.plot_only:
        print("Plotting schedule")
        sys.exit(plot_outcome(args.battery_percent))
    else:
        print("Generating schedule")

        generate_schedule(
            args.battery_percent,
            ev_soc_percent=args.ev_soc_percent,
            ev_ready_time=args.ev_ready_time,
            save=args.save,
            save_image=args.save_image,
        )


if __name__ == "__main__":
    main()
