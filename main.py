#!/usr/bin/env python3
"""
Console Application start
"""
import sys

from battery_optimizer_workflow import BatteryOptimizerWorkflow


def main():
    """Main function of the application."""

    workflow = BatteryOptimizerWorkflow()
    workflow.run_workflow()

    return 0


if __name__ == "__main__":
    # This ensures that the main() function is called only when this script is run directly
    # (not when imported as a module)
    sys.exit(main())
