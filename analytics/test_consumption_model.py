#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd


def load_test_data(file_path: str = "consumed-power.csv") -> pd.DataFrame:
    """Load actual data for testing the model"""
    print(f"Loading test data from {file_path}")

    # Load data
    df = pd.read_csv(file_path, parse_dates=["time"])

    # Basic cleaning
    df = df.dropna(subset=["time", "value"])
    df = df.sort_values("time")

    # Remove outliers
    mean_val = df["value"].mean()
    std_val = df["value"].std()
    df = df[
        (df["value"] >= mean_val - 3 * std_val)
        & (df["value"] <= mean_val + 3 * std_val)
    ]

    print(f"Loaded {len(df)} test records")
    return df


def add_basic_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add basic time-based features (same as training)"""
    df = df.copy()

    # Basic time features (same as original working script)
    df["day_of_year"] = df["time"].dt.dayofyear
    df["minutes_of_day"] = df["time"].dt.hour * 60 + df["time"].dt.minute
    df["minutes_sin"] = np.sin(2 * np.pi * df["minutes_of_day"] / (24 * 60))
    df["minutes_cos"] = np.cos(2 * np.pi * df["minutes_of_day"] / (24 * 60))

    # Add lagged features (5-minute intervals)
    df["consumption_lag_1"] = df["value"].shift(1)  # 5 minutes ago
    df["consumption_lag_2"] = df["value"].shift(2)  # 10 minutes ago

    # Add rolling mean (6 periods = 30 minutes)
    df["consumption_rolling_mean_6"] = df["value"].rolling(6).mean()

    # Add rolling standard deviation (6 periods = 30 minutes)
    df["consumption_rolling_std_6"] = df["value"].rolling(6).std()

    return df


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare features for prediction (same columns as training)"""
    feature_columns = [
        "day_of_year",
        "minutes_of_day",
        "minutes_sin",
        "minutes_cos",
        "consumption_lag_1",
        "consumption_lag_2",
        "consumption_rolling_mean_6",
        "consumption_rolling_std_6",
    ]

    return df[feature_columns]


def predict_consumption(model_path: str, input_data: pd.DataFrame) -> pd.DataFrame:
    """Predict consumption using the trained model"""
    # Load the model
    model = joblib.load(model_path)

    # Prepare features
    df_with_features = add_basic_time_features(input_data)

    # Get features for prediction
    X = prepare_features(df_with_features)

    # Remove rows with NaN values
    valid_mask = ~X.isna().any(axis=1)
    X_valid = X[valid_mask]

    if len(X_valid) == 0:
        print("Warning: No valid data for prediction")
        return pd.DataFrame()

    # Make predictions
    predictions = model.predict(X_valid)

    # Create result DataFrame
    result_df = input_data[valid_mask].copy()
    result_df["predicted_consumption"] = predictions
    result_df["actual_consumption"] = result_df["value"]

    return result_df


def main() -> None:
    """Test the baseline consumption model with actual data"""
    print("=== Testing Baseline Power Consumption Model ===")

    # Model path
    model_path = "../models/power-consumption-baseline.joblib"

    if not Path(model_path).exists():
        print(f"Error: Model file not found at {model_path}")
        print("Please run analyze_consumption.py first to train the baseline model.")
        return

    # Load actual test data
    test_data = load_test_data()

    # Use the last 500 records for testing (should work fine with basic features)
    test_subset = test_data.tail(500).copy()
    print(f"Using last {len(test_subset)} records for testing")

    # Make predictions
    print("Making predictions...")
    results = predict_consumption(model_path, test_subset)

    if len(results) == 0:
        print("No predictions made.")
        return

    # Display results
    print("\nPrediction Results (showing first 10 records):")
    print("=" * 80)
    print(
        f"{'Time':<20} {'Actual (W)':<12} {'Predicted (W)':<15} {'Difference (W)':<15}"
    )
    print("-" * 80)

    for _, row in results.head(10).iterrows():
        actual = row["actual_consumption"]
        predicted = row["predicted_consumption"]
        diff = predicted - actual
        print(
            f"{row['time'].strftime('%Y-%m-%d %H:%M'):<20} "
            f"{actual:<12.1f} {predicted:<15.1f} {diff:<15.1f}"
        )

    # Calculate overall metrics
    if len(results) > 0:
        actual_values = results["actual_consumption"]
        predicted_values = results["predicted_consumption"]

        mse = np.mean((actual_values - predicted_values) ** 2)
        rmse = np.sqrt(mse)
        mae = np.mean(np.abs(actual_values - predicted_values))
        r2 = 1 - np.sum((actual_values - predicted_values) ** 2) / np.sum(
            (actual_values - actual_values.mean()) ** 2
        )

        print("\nOverall Performance:")
        print(f"  RMSE: {rmse:.2f} W")
        print(f"  MAE:  {mae:.2f} W")
        print(f"  R²:   {r2:.4f}")
        print(f"  Predictions made: {len(results)} out of {len(test_subset)} records")

        # Show some statistics
        print("\nData Statistics:")
        print(
            f"  Actual consumption range: {actual_values.min():.1f} - {actual_values.max():.1f} W"
        )
        print(
            f"  Predicted consumption range: {predicted_values.min():.1f} - {predicted_values.max():.1f} W"
        )
        print(f"  Mean actual consumption: {actual_values.mean():.1f} W")
        print(f"  Mean predicted consumption: {predicted_values.mean():.1f} W")

    print(f"\nBaseline model successfully loaded from {model_path}")


if __name__ == "__main__":
    main()
