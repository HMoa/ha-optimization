#!/usr/bin/env python
"""
Console Application start
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from typing import Optional

from optimizer.battery_optimizer_workflow import BatteryOptimizerWorkflow
from optimizer.consumption_provider import get_consumption
from optimizer.influxdb_client import get_initial_consumption_values
from optimizer.plotting import save_schedule_plot, show_schedule_plot
from optimizer.production_provider import get_production


def plot_outcome(battery_percent: float) -> int:
    from optimizer.battery_optimizer_workflow import BatteryOptimizerWorkflow

    workflow = BatteryOptimizerWorkflow(battery_percent=battery_percent)
    schedule = workflow.generate_schedule_from_file()
    if schedule is None:
        print("No schedule available to plot")
        return 1
    show_schedule_plot(schedule)
    return 0


def generate_schedule(
    battery_percent: float,
    save: bool = False,
    save_image: bool = False,
) -> None:

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

    if save:
        import os
        import pickle

        # Save params for later use
        params = [
            workflow.production,
            workflow.consumption,
            workflow.prices,
            workflow.config,
        ]
        sample_data_dir = os.path.join(os.path.dirname(__file__), "../sample_data")
        os.makedirs(sample_data_dir, exist_ok=True)
        sample_data_path = os.path.join(sample_data_dir, "optimizer_params.pkl")
        with open(sample_data_path, "wb") as f:
            pickle.dump(params, f)

    if save_image:
        from optimizer.plotting import save_schedule_plot

        save_schedule_plot(workflow.schedule, save_path="schedule.png")
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

        # Handle InfluxDB integration
        if args.use_influxdb:
            print("Fetching initial consumption values from InfluxDB...")
            try:
                influx_values = get_initial_consumption_values(args.influxdb_config)
                if influx_values:
                    print(f"Using {len(influx_values)} values from InfluxDB")
                else:
                    print(
                        "Warning: No data from InfluxDB, falling back to other methods"
                    )
            except Exception as e:
                print(f"Error fetching from InfluxDB: {e}")
                print("Falling back to other methods")

        generate_schedule(
            args.battery_percent,
            save=args.save,
            save_image=args.save_image,
        )


if __name__ == "__main__":
    main()
