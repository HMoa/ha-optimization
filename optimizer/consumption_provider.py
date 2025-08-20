from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import joblib
import numpy as np
import pandas as pd


def add_features_for_prediction(df: pd.DataFrame) -> pd.DataFrame:
    """Add all the features used in our ultimate trained model"""
    df = df.copy()

    # Basic time features
    df["day_of_year"] = df["time"].dt.dayofyear
    df["minutes_of_day"] = df["time"].dt.hour * 60 + df["time"].dt.minute
    df["minutes_sin"] = np.sin(2 * np.pi * df["minutes_of_day"] / (24 * 60))
    df["minutes_cos"] = np.cos(2 * np.pi * df["minutes_of_day"] / (24 * 60))

    # Day of week features (cyclical encoding only)
    day_of_week = df["time"].dt.dayofweek
    df["day_of_week_sin"] = np.sin(2 * np.pi * day_of_week / 7)
    df["day_of_week_cos"] = np.cos(2 * np.pi * day_of_week / 7)

    # Hour features (cyclical encoding only)
    hour = df["time"].dt.hour
    df["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    df["hour_cos"] = np.cos(2 * np.pi * hour / 24)

    # Add optimized lagged features (5 lags for best performance)
    for lag in range(1, 6):  # 1 to 5 lags (5, 10, 15, 20, 25 minutes ago)
        df[f"consumption_lag_{lag}"] = df["value"].shift(lag)

    # Add rolling features (6 periods = 30 minutes)
    df["consumption_rolling_mean_6"] = df["value"].rolling(6).mean()
    df["consumption_rolling_std_6"] = df["value"].rolling(6).std()

    return df


def prepare_features_for_prediction(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare features for prediction (same columns as ultimate model training)"""
    # Get all feature columns (exclude 'time' and 'value')
    feature_columns = [col for col in df.columns if col not in ["time", "value"]]

    return df[feature_columns]


def get_consumption_with_initial_values(
    start_date: datetime, end_date: datetime, initial_consumption_values: List[float]
) -> Dict[datetime, float]:
    """
    Get predicted consumption using provided initial consumption values as history

    Args:
        start_date: Start time for predictions
        end_date: End time for predictions
        initial_consumption_values: List of consumption values to use as history
                                  (should be in 5-minute intervals, most recent last)
    """
    # Snap start_date to the closest 5-minute interval
    start_date = start_date - timedelta(
        minutes=start_date.minute % 5,
        seconds=start_date.second,
        microseconds=start_date.microsecond,
    )

    # Load the ultimate model
    model_path = os.path.join(
        os.path.dirname(__file__), "../models/power-consumption-ultimate.joblib"
    )

    if not os.path.exists(model_path):
        raise FileNotFoundError(
            f"Model not found at {model_path}. Please run analyze_consumption.py first to train the model."
        )

    model = joblib.load(model_path)

    # Generate time slots
    time_slots = []
    t = start_date
    while t <= end_date:
        time_slots.append(t)
        t += timedelta(minutes=5)

    if len(time_slots) == 0:
        return {}

    # Create history from provided values
    history_times = []
    history_values = []

    # Create history periods before our prediction start
    for i, value in enumerate(initial_consumption_values):
        history_time = start_date - timedelta(
            minutes=5 * (len(initial_consumption_values) - i)
        )
        history_times.append(history_time)
        history_values.append(value)

    # Predict iteratively
    consumption_data: Dict[datetime, float] = {}

    for current_time in time_slots:
        # Create DataFrame with current history + current time slot
        current_df = pd.DataFrame(
            {
                "time": history_times + [current_time],
                "value": history_values + [0.0],  # Placeholder for current prediction
            }
        )

        # Add features
        df_with_features = add_features_for_prediction(current_df)
        X = prepare_features_for_prediction(df_with_features)

        # Get features for the current time slot (last row)
        current_features = X.iloc[-1:].copy()

        # Check if we have valid features
        if current_features.isna().any().any():
            # Use time-based fallback
            hour = current_time.hour
            if 6 <= hour <= 8:
                prediction = 800.0
            elif 17 <= hour <= 21:
                prediction = 1200.0
            elif 22 <= hour or hour <= 5:
                prediction = 300.0
            else:
                prediction = 600.0
        else:
            # Make prediction
            prediction = model.predict(current_features)[0]
            prediction = max(0, float(prediction))

        # Store prediction
        consumption_data[current_time] = prediction

        # Update history for next iteration
        history_times.append(current_time)
        history_values.append(prediction)

        # Keep only the last 15 periods to support 5 lags + rolling features
        if len(history_times) > 15:
            history_times = history_times[-15:]
            history_values = history_values[-15:]

    return consumption_data


if __name__ == "__main__":
    # Test the different consumption prediction methods
    print("=== Testing Different Consumption Prediction Methods ===\n")

    start_time = datetime(2025, 6, 1, 11, 0, 0)
    end_time = datetime(2025, 6, 1, 11, 30, 0)

    try:
        print("\n1. Method with provided initial consumption values:")
        # Provide 10 periods of history (most recent last) to support 5 lags + rolling features
        initial_values = [
            600.0,  # 50 minutes ago
            650.0,  # 45 minutes ago
            700.0,  # 40 minutes ago
            750.0,  # 35 minutes ago
            800.0,  # 30 minutes ago
            750.0,  # 25 minutes ago
            700.0,  # 20 minutes ago
            650.0,  # 15 minutes ago
            600.0,  # 10 minutes ago
            550.0,  # 5 minutes ago
        ]  # 50 minutes of history
        initial_response = get_consumption_with_initial_values(
            start_time, end_time, initial_values
        )
        for dt, consumption in list(initial_response.items())[:5]:  # Show first 5
            print(f"  {dt.strftime('%H:%M')}: {consumption:.1f} W")
        print("  ...")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please run analyze_consumption.py first to train the model.")
