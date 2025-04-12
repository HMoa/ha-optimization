#!/usr/bin/env python3
"""
Console Application start
"""
import sys

import matplotlib.pyplot as plt
import pandas as pd

from battery_optimizer_workflow import BatteryOptimizerWorkflow


def main():
    """Main function of the application."""
    df = pd.DataFrame({"x": range(1, 11), "y": [i**2 for i in range(1, 11)]})

    df.plot(x="x", y="y", kind="line")

    plt.show()
    # workflow = BatteryOptimizerWorkflow()
    # workflow.run_workflow()

    return 0


if __name__ == "__main__":
    # This ensures that the main() function is called only when this script is run directly
    # (not when imported as a module)
    sys.exit(main())
