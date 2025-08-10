#!/usr/bin/env python
"""
Battery Calibration Analysis

Analyzes the relationship between charge settings and actual battery charge/discharge
to determine proper calibration factors.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats


def parse_battery_data(raw_data: str) -> List[Dict]:
    """Parse the mixed JSON and text data from Node-RED logs."""
    # Extract JSON objects using regex
    json_pattern = r'\{ charge: (\d+), battery_cha: "([^"]*)", battery_discha: "([^"]*)", count: \d+ \}'
    matches = re.findall(json_pattern, raw_data)

    data = []
    for match in matches:
        charge_setting = int(match[0])
        battery_cha = float(match[1]) if match[1] != "0" and match[1] != "" else 0.0
        battery_discha = float(match[2]) if match[2] != "0" and match[2] != "" else 0.0

        data.append(
            {
                "charge_setting": charge_setting,
                "battery_cha": battery_cha,
                "battery_discha": battery_discha,
                "is_charging": battery_cha > 0,
                "is_discharging": battery_discha > 0,
            }
        )

    return data


def analyze_relationship(data: List[Dict]) -> Dict:
    """Analyze the relationship between settings and actual performance."""
    df = pd.DataFrame(data)

    # Separate charging and discharging data
    charging_data = df[df["is_charging"]].copy()
    discharging_data = df[df["is_discharging"]].copy()

    results = {}

    # Analyze charging relationship
    if len(charging_data) > 0:
        charging_data["ratio"] = (
            charging_data["battery_cha"] / charging_data["charge_setting"]
        )

        # Linear regression
        slope_c, intercept_c, r_value_c, p_value_c, std_err_c = stats.linregress(
            charging_data["charge_setting"], charging_data["battery_cha"]
        )

        results["charging"] = {
            "slope": slope_c,
            "intercept": intercept_c,
            "r_squared": r_value_c**2,
            "p_value": p_value_c,
            "std_error": std_err_c,
            "mean_ratio": charging_data["ratio"].mean(),
            "std_ratio": charging_data["ratio"].std(),
            "data_points": len(charging_data),
        }

    # Analyze discharging relationship
    if len(discharging_data) > 0:
        discharging_data["ratio"] = (
            discharging_data["battery_discha"] / discharging_data["charge_setting"]
        )

        # Linear regression
        slope_d, intercept_d, r_value_d, p_value_d, std_err_d = stats.linregress(
            discharging_data["charge_setting"], discharging_data["battery_discha"]
        )

        results["discharging"] = {
            "slope": slope_d,
            "intercept": intercept_d,
            "r_squared": r_value_d**2,
            "p_value": p_value_d,
            "std_error": std_err_d,
            "mean_ratio": discharging_data["ratio"].mean(),
            "std_ratio": discharging_data["ratio"].std(),
            "data_points": len(discharging_data),
        }

    return results, df


def plot_analysis(df: pd.DataFrame, results: Dict) -> None:
    """Create visualization plots of the analysis."""
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))

    # Charging data
    charging_data = df[df["is_charging"]]
    if len(charging_data) > 0:
        ax1.scatter(
            charging_data["charge_setting"],
            charging_data["battery_cha"],
            alpha=0.7,
            color="green",
        )

        # Fit line
        x_range = np.linspace(
            charging_data["charge_setting"].min(),
            charging_data["charge_setting"].max(),
            100,
        )
        y_fit = (
            results["charging"]["slope"] * x_range + results["charging"]["intercept"]
        )
        ax1.plot(
            x_range,
            y_fit,
            "r--",
            label=f'Fit: y = {results["charging"]["slope"]:.3f}x + {results["charging"]["intercept"]:.1f}',
        )

        ax1.set_xlabel("Charge Setting")
        ax1.set_ylabel("Actual Charging (Wh)")
        ax1.set_title(
            f'Charging Relationship (R² = {results["charging"]["r_squared"]:.3f})'
        )
        ax1.legend()
        ax1.grid(True)

    # Discharging data
    discharging_data = df[df["is_discharging"]]
    if len(discharging_data) > 0:
        ax2.scatter(
            discharging_data["charge_setting"],
            discharging_data["battery_discha"],
            alpha=0.7,
            color="red",
        )

        # Fit line
        x_range = np.linspace(
            discharging_data["charge_setting"].min(),
            discharging_data["charge_setting"].max(),
            100,
        )
        y_fit = (
            results["discharging"]["slope"] * x_range
            + results["discharging"]["intercept"]
        )
        ax2.plot(
            x_range,
            y_fit,
            "b--",
            label=f'Fit: y = {results["discharging"]["slope"]:.3f}x + {results["discharging"]["intercept"]:.1f}',
        )

        ax2.set_xlabel("Charge Setting")
        ax2.set_ylabel("Actual Discharging (Wh)")
        ax2.set_title(
            f'Discharging Relationship (R² = {results["discharging"]["r_squared"]:.3f})'
        )
        ax2.legend()
        ax2.grid(True)

    # Ratio analysis for charging
    if len(charging_data) > 0:
        charging_data_copy = charging_data.copy()
        charging_data_copy["ratio"] = (
            charging_data_copy["battery_cha"] / charging_data_copy["charge_setting"]
        )
        ax3.scatter(
            charging_data_copy["charge_setting"],
            charging_data_copy["ratio"],
            alpha=0.7,
            color="green",
        )
        ax3.axhline(
            y=charging_data_copy["ratio"].mean(),
            color="r",
            linestyle="--",
            label=f'Mean: {charging_data_copy["ratio"].mean():.3f}',
        )
        ax3.set_xlabel("Charge Setting")
        ax3.set_ylabel("Ratio (Actual/Setting)")
        ax3.set_title("Charging Ratio vs Setting")
        ax3.legend()
        ax3.grid(True)

    # Ratio analysis for discharging
    if len(discharging_data) > 0:
        discharging_data_copy = discharging_data.copy()
        discharging_data_copy["ratio"] = (
            discharging_data_copy["battery_discha"]
            / discharging_data_copy["charge_setting"]
        )
        ax4.scatter(
            discharging_data_copy["charge_setting"],
            discharging_data_copy["ratio"],
            alpha=0.7,
            color="red",
        )
        ax4.axhline(
            y=discharging_data_copy["ratio"].mean(),
            color="b",
            linestyle="--",
            label=f'Mean: {discharging_data_copy["ratio"].mean():.3f}',
        )
        ax4.set_xlabel("Charge Setting")
        ax4.set_ylabel("Ratio (Actual/Setting)")
        ax4.set_title("Discharging Ratio vs Setting")
        ax4.legend()
        ax4.grid(True)

    plt.tight_layout()
    plt.show()


def calculate_calibration_factors(results: Dict) -> Dict:
    """Calculate calibration factors for the optimizer."""
    calibration = {}

    if "charging" in results:
        # Use slope as the primary calibration factor
        calibration["charge_factor"] = results["charging"]["slope"]
        calibration["charge_offset"] = results["charging"]["intercept"]

        # Alternative: use mean ratio
        calibration["charge_ratio"] = results["charging"]["mean_ratio"]

    if "discharging" in results:
        calibration["discharge_factor"] = results["discharging"]["slope"]
        calibration["discharge_offset"] = results["discharging"]["intercept"]
        calibration["discharge_ratio"] = results["discharging"]["mean_ratio"]

    return calibration


def recommend_settings(target_wh: float, calibration: Dict) -> Dict:
    """Recommend settings to achieve target charge/discharge."""
    recommendations = {}

    if "charge_factor" in calibration:
        # Using linear model: actual = factor * setting + offset
        recommended_charge = (target_wh - calibration["charge_offset"]) / calibration[
            "charge_factor"
        ]
        recommendations["charge_setting"] = max(0, recommended_charge)

        # Alternative using ratio
        recommendations["charge_setting_ratio"] = (
            target_wh / calibration["charge_ratio"]
        )

    if "discharge_factor" in calibration:
        recommended_discharge = (
            target_wh - calibration["discharge_offset"]
        ) / calibration["discharge_factor"]
        recommendations["discharge_setting"] = max(0, recommended_discharge)
        recommendations["discharge_setting_ratio"] = (
            target_wh / calibration["discharge_ratio"]
        )

    return recommendations


def main():
    """Main analysis function."""
    # Your raw data (discharge data)
    discharge_raw_data = """
{ charge: 50, battery_cha: "0", battery_discha: "206.014", count: 0 }
{ charge: 100, battery_cha: "0", battery_discha: "408.9867", count: 0 }
{ charge: 150, battery_cha: "0", battery_discha: "619.0522", count: 0 }
{ charge: 200, battery_cha: "0", battery_discha: "826.477", count: 0 }
{ charge: 250, battery_cha: "0", battery_discha: "1022.4064", count: 0 }
{ charge: 300, battery_cha: "0", battery_discha: "1225.1315", count: 0 }
{ charge: 350, battery_cha: "0", battery_discha: "1434.0835", count: 0 }
{ charge: 400, battery_cha: "0", battery_discha: "1637.7449", count: 0 }
{ charge: 450, battery_cha: "0", battery_discha: "1849.0747", count: 0 }
{ charge: 500, battery_cha: "0", battery_discha: "2049.3931", count: 0 }
{ charge: 550, battery_cha: "0", battery_discha: "2254.4563", count: 0 }
{ charge: 600, battery_cha: "0", battery_discha: "2457.9707", count: 0 }
{ charge: 650, battery_cha: "0", battery_discha: "2658.4995", count: 0 }
{ charge: 700, battery_cha: "0", battery_discha: "2865.1196", count: 0 }
{ charge: 750, battery_cha: "0", battery_discha: "3083.7993", count: 0 }
{ charge: 800, battery_cha: "0", battery_discha: "3267.333", count: 0 }
{ charge: 850, battery_cha: "0", battery_discha: "3468.1558", count: 0 }
{ charge: 900, battery_cha: "0", battery_discha: "3691.7173", count: 0 }
{ charge: 950, battery_cha: "0", battery_discha: "3888.2988", count: 0 }
{ charge: 1000, battery_cha: "0", battery_discha: "4092.8738", count: 0 }
{ charge: 1050, battery_cha: "0", battery_discha: "4312.2227", count: 0 }
{ charge: 1100, battery_cha: "0", battery_discha: "4504.2817", count: 0 }
{ charge: 1150, battery_cha: "0", battery_discha: "4691.4116", count: 0 }
{ charge: 1200, battery_cha: "0", battery_discha: "4923.0078", count: 0 }
{ charge: 1250, battery_cha: "0", battery_discha: "5101.0825", count: 0 }
{ charge: 1300, battery_cha: "0", battery_discha: "5320.1758", count: 0 }
{ charge: 1350, battery_cha: "0", battery_discha: "5548.7344", count: 0 }
{ charge: 1400, battery_cha: "0", battery_discha: "5726.1309", count: 0 }
{ charge: 1450, battery_cha: "0", battery_discha: "5933.4551", count: 0 }
{ charge: 1550, battery_cha: "0", battery_discha: "6330.7729", count: 0 }
{ charge: 1600, battery_cha: "0", battery_discha: "6591.457", count: 0 }
{ charge: 1650, battery_cha: "0", battery_discha: "6751.4341", count: 0 }
{ charge: 1700, battery_cha: "0", battery_discha: "6929.874", count: 0 }
{ charge: 1750, battery_cha: "0", battery_discha: "7166.2393", count: 0 }
{ charge: 1800, battery_cha: "0", battery_discha: "7376.2256", count: 0 }
{ charge: 1850, battery_cha: "0", battery_discha: "7570.7236", count: 0 }
{ charge: 1900, battery_cha: "0", battery_discha: "7748.7192", count: 0 }
{ charge: 1950, battery_cha: "0", battery_discha: "7937.8755", count: 0 }
{ charge: 2000, battery_cha: "0", battery_discha: "8153.2578", count: 0 }
{ charge: 2050, battery_cha: "0", battery_discha: "8389.208", count: 0 }
{ charge: 2100, battery_cha: "0", battery_discha: "8607.6357", count: 0 }
{ charge: 2150, battery_cha: "0", battery_discha: "8781.4316", count: 0 }
{ charge: 2200, battery_cha: "0", battery_discha: "8889.5039", count: 0 }
{ charge: 2250, battery_cha: "0", battery_discha: "8916.6201", count: 0 }
{ charge: 2300, battery_cha: "0", battery_discha: "9044.0957", count: 0 }
"""

    # Your raw charging data
    charge_raw_data = """
{ charge: 50, battery_cha: "198.6885", battery_discha: "0", count: 0 }
{ charge: 100, battery_cha: "403.2705", battery_discha: "0", count: 0 }
{ charge: 150, battery_cha: "614.5859", battery_discha: "0", count: 0 }
{ charge: 200, battery_cha: "821.072", battery_discha: "0", count: 0 }
{ charge: 250, battery_cha: "1028.0161", battery_discha: "0", count: 0 }
{ charge: 300, battery_cha: "1230.6202", battery_discha: "0", count: 0 }
{ charge: 350, battery_cha: "1434.6354", battery_discha: "0", count: 0 }
{ charge: 400, battery_cha: "1632.9612", battery_discha: "0", count: 0 }
{ charge: 450, battery_cha: "1848.1122", battery_discha: "0", count: 0 }
{ charge: 500, battery_cha: "2049.8108", battery_discha: "0", count: 0 }
{ charge: 550, battery_cha: "2259.3655", battery_discha: "0", count: 0 }
{ charge: 600, battery_cha: "2453.4724", battery_discha: "0", count: 0 }
{ charge: 650, battery_cha: "2660.8691", battery_discha: "0", count: 0 }
{ charge: 700, battery_cha: "2870.7578", battery_discha: "0", count: 0 }
{ charge: 750, battery_cha: "3075.2283", battery_discha: "0", count: 0 }
{ charge: 800, battery_cha: "3271.6445", battery_discha: "0", count: 0 }
{ charge: 850, battery_cha: "3479.4143", battery_discha: "0", count: 0 }
{ charge: 900, battery_cha: "3711.9924", battery_discha: "0", count: 0 }
{ charge: 950, battery_cha: "3892.5042", battery_discha: "0", count: 0 }
{ charge: 1000, battery_cha: "4101.2764", battery_discha: "0", count: 0 }
{ charge: 1050, battery_cha: "4293.3682", battery_discha: "0", count: 0 }
{ charge: 1100, battery_cha: "4483.9473", battery_discha: "0", count: 0 }
{ charge: 1150, battery_cha: "4693.0601", battery_discha: "0", count: 0 }
{ charge: 1200, battery_cha: "4901.8438", battery_discha: "0", count: 0 }
{ charge: 1250, battery_cha: "5111.2021", battery_discha: "0", count: 0 }
{ charge: 1300, battery_cha: "5326.936", battery_discha: "0", count: 0 }
{ charge: 1350, battery_cha: "5529.0776", battery_discha: "0", count: 0 }
{ charge: 1400, battery_cha: "5757.6626", battery_discha: "0", count: 0 }
{ charge: 1450, battery_cha: "5925.585", battery_discha: "0", count: 0 }
{ charge: 1550, battery_cha: "6314.356", battery_discha: "0", count: 0 }
{ charge: 1600, battery_cha: "6538.3804", battery_discha: "0", count: 0 }
{ charge: 1650, battery_cha: "6726.2295", battery_discha: "0", count: 0 }
{ charge: 1700, battery_cha: "6941.7207", battery_discha: "0", count: 0 }
{ charge: 1750, battery_cha: "7189.6289", battery_discha: "0", count: 0 }
{ charge: 1800, battery_cha: "7388.2197", battery_discha: "0", count: 0 }
{ charge: 1850, battery_cha: "7556.5229", battery_discha: "0", count: 0 }
{ charge: 1900, battery_cha: "7767.8066", battery_discha: "0", count: 0 }
{ charge: 1950, battery_cha: "8002.3145", battery_discha: "0", count: 0 }
{ charge: 2000, battery_cha: "8233.8457", battery_discha: "0", count: 0 }
{ charge: 2050, battery_cha: "8423.8145", battery_discha: "0", count: 0 }
{ charge: 2100, battery_cha: "8582.8457", battery_discha: "0", count: 0 }
{ charge: 2150, battery_cha: "8772.8975", battery_discha: "0", count: 0 }
{ charge: 2200, battery_cha: "9035.0605", battery_discha: "0", count: 0 }
{ charge: 2250, battery_cha: "9241.1582", battery_discha: "0", count: 0 }
{ charge: 2300, battery_cha: "9419.1523", battery_discha: "0", count: 0 }

"""

    # Combine the data
    combined_data = discharge_raw_data + "\n" + charge_raw_data

    # Parse the data
    print("Parsing battery calibration data...")
    data = parse_battery_data(combined_data)
    print(f"Parsed {len(data)} data points")

    # Analyze relationships
    print("\nAnalyzing charge/discharge relationships...")
    results, df = analyze_relationship(data)

    # Print results
    print("\n" + "=" * 60)
    print("BATTERY CALIBRATION ANALYSIS RESULTS")
    print("=" * 60)

    if "charging" in results:
        r = results["charging"]
        print(f"\nCHARGING ANALYSIS ({r['data_points']} data points):")
        print(
            f"  Linear model: Actual = {r['slope']:.3f} × Setting + {r['intercept']:.1f}"
        )
        print(f"  R² = {r['r_squared']:.4f} (correlation strength)")
        print(f"  Mean ratio = {r['mean_ratio']:.3f} ± {r['std_ratio']:.3f}")
        print(
            f"  Your ~4x estimate was close! Actual average is {r['mean_ratio']:.1f}x"
        )

    if "discharging" in results:
        r = results["discharging"]
        print(f"\nDISCHARGING ANALYSIS ({r['data_points']} data points):")
        print(
            f"  Linear model: Actual = {r['slope']:.3f} × Setting + {r['intercept']:.1f}"
        )
        print(f"  R² = {r['r_squared']:.4f} (correlation strength)")
        print(f"  Mean ratio = {r['mean_ratio']:.3f} ± {r['std_ratio']:.3f}")
        print(
            f"  Your ~4x estimate was close! Actual average is {r['mean_ratio']:.1f}x"
        )

    # Compare charging vs discharging
    if "charging" in results and "discharging" in results:
        charge_ratio = results["charging"]["mean_ratio"]
        discharge_ratio = results["discharging"]["mean_ratio"]
        diff_percent = (
            abs(charge_ratio - discharge_ratio)
            / ((charge_ratio + discharge_ratio) / 2)
            * 100
        )

        print(f"\nCOMPARISON:")
        print(f"  Charging ratio:    {charge_ratio:.3f}")
        print(f"  Discharging ratio: {discharge_ratio:.3f}")
        print(f"  Difference:        {diff_percent:.1f}%")

        if diff_percent < 5:
            print(
                "  ✅ Charge and discharge are very similar - you can use the same factor!"
            )
        elif diff_percent < 10:
            print(
                "  ⚠️  Charge and discharge differ slightly - consider separate factors"
            )
        else:
            print(
                "  ❌ Charge and discharge differ significantly - use separate factors"
            )

    # Calculate calibration factors
    calibration = calculate_calibration_factors(results)

    print(f"\nCALIBRATION FACTORS FOR YOUR OPTIMIZER:")
    print("-" * 40)
    for key, value in calibration.items():
        print(f"  {key}: {value:.3f}")

    # Examples
    print(f"\nEXAMPLE RECOMMENDATIONS:")
    print("-" * 25)
    for target in [1000, 2000, 3000, 5000]:
        recommendations = recommend_settings(target, calibration)
        print(f"For {target}Wh target:")
        if "charge_setting" in recommendations:
            print(f"  Charge setting: {recommendations['charge_setting']:.0f}")
        if "discharge_setting" in recommendations:
            print(f"  Discharge setting: {recommendations['discharge_setting']:.0f}")

    # Create plots
    print(f"\nGenerating analysis plots...")
    plot_analysis(df, results)
    print("Analysis plots displayed")

    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
