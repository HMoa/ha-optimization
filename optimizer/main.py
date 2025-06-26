#!/usr/bin/env python3
"""
Console Application start
"""
import sys

import matplotlib

# matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import pandas as pd
from battery_optimizer_workflow import BatteryOptimizerWorkflow


def main():
    """Main function of the application."""
    import argparse

    parser = argparse.ArgumentParser(description="Battery Optimizer Workflow")
    parser.add_argument(
        "--battery_percent",
        type=int,
        default=34,
        help="Initial battery percent (default: 34)",
    )
    args = parser.parse_args()

    workflow = BatteryOptimizerWorkflow(battery_percent=args.battery_percent)
    # workflow.run_workflow()
    schedule = workflow.generate_schedule_from_file()

    fig, ax1 = plt.subplots()

    # Plot battery_expected_soc and battery_flow on the left y-axis
    ax1.plot(
        schedule.keys(),
        [item.battery_expected_soc for item in schedule.values()],
        label="Battery SOC",
    )
    ax1.plot(
        schedule.keys(),
        [item.battery_flow for item in schedule.values()],
        label="Battery Flow",
    )
    ax1.set_ylabel("Battery SOC / Flow")
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

    plt.show()

    return 0


if __name__ == "__main__":
    # This ensures that the main() function is called only when this script is run directly
    # (not when imported as a module)
    sys.exit(main())
