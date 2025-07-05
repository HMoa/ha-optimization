from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import joblib
import numpy as np
import pandas as pd


def add_features_for_prediction(df: pd.DataFrame) -> pd.DataFrame:
    """Add all the features used in our trained model"""
    df = df.copy()

    # Basic time features
    df["day_of_year"] = df["time"].dt.dayofyear
    df["minutes_of_day"] = df["time"].dt.hour * 60 + df["time"].dt.minute
    df["minutes_sin"] = np.sin(2 * np.pi * df["minutes_of_day"] / (24 * 60))
    df["minutes_cos"] = np.cos(2 * np.pi * df["minutes_of_day"] / (24 * 60))

    # Add lagged features (5-minute intervals)
    df["consumption_lag_1"] = df["value"].shift(1)  # 5 minutes ago
    df["consumption_lag_2"] = df["value"].shift(2)  # 10 minutes ago

    # Add rolling features (6 periods = 30 minutes)
    df["consumption_rolling_mean_6"] = df["value"].rolling(6).mean()
    df["consumption_rolling_std_6"] = df["value"].rolling(6).std()

    return df


def prepare_features_for_prediction(df: pd.DataFrame) -> pd.DataFrame:
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


def get_consumption(start_date: datetime, end_date: datetime) -> Dict[datetime, float]:
    """Get predicted consumption for the specified time range"""
    # Snap start_date to the closest 5-minute interval
    start_date = start_date - timedelta(
        minutes=start_date.minute % 5,
        seconds=start_date.second,
        microseconds=start_date.microsecond,
    )

    # Load the improved model
    model_path = os.path.join(
        os.path.dirname(__file__), "../models/power-consumption-baseline.joblib"
    )

    if not os.path.exists(model_path):
        raise FileNotFoundError(
            f"Model not found at {model_path}. Please run analyze_consumption.py first to train the model."
        )

    model = joblib.load(model_path)

    # Generate time slots between start_date and end_date (inclusive) at 5-minute intervals
    time_slots = []
    t = start_date
    while t <= end_date:
        time_slots.append(t)
        t += timedelta(minutes=5)

    # Create a more sophisticated approach for predictions without historical data
    # We'll use typical consumption patterns and iterate to improve predictions

    # Start with reasonable initial values based on time of day
    initial_consumption = []
    for dt in time_slots:
        hour = dt.hour
        # Typical household consumption patterns (higher in morning/evening, lower at night)
        if 6 <= hour <= 8:  # Morning
            base_consumption = 800
        elif 17 <= hour <= 21:  # Evening
            base_consumption = 1200
        elif 22 <= hour or hour <= 5:  # Night
            base_consumption = 300
        else:  # Day
            base_consumption = 600

        # Add some randomness
        consumption = base_consumption + np.random.normal(0, 100)
        initial_consumption.append(max(0, consumption))

    # Create DataFrame with initial consumption estimates
    df = pd.DataFrame({"time": time_slots, "value": initial_consumption})

    # Add all features
    df_with_features = add_features_for_prediction(df)

    # Get features for prediction
    X = prepare_features_for_prediction(df_with_features)

    # Remove rows with NaN values (first few rows will have NaN due to lags and rolling)
    valid_mask = ~X.isna().any(axis=1)
    X_valid = X[valid_mask]
    valid_times = df["time"][valid_mask]

    if len(X_valid) == 0:
        print("Warning: No valid predictions possible due to insufficient history")
        return {}

    # Make predictions
    predictions = model.predict(X_valid)

    # Create result dictionary
    consumption_data: Dict[datetime, float] = {}
    for dt, pred in zip(valid_times, predictions):
        consumption_data[dt] = max(0, float(pred))

    # Fill in any missing time slots with the last valid prediction or a reasonable default
    for dt in time_slots:
        if dt not in consumption_data:
            # Use the last valid prediction if available, otherwise use time-based estimate
            if consumption_data:
                last_pred = list(consumption_data.values())[-1]
            else:
                # Fallback to time-based estimate
                hour = dt.hour
                if 6 <= hour <= 8:
                    last_pred = 800
                elif 17 <= hour <= 21:
                    last_pred = 1200
                elif 22 <= hour or hour <= 5:
                    last_pred = 300
                else:
                    last_pred = 600
            consumption_data[dt] = last_pred

    return consumption_data


def get_consumption_with_history(
    start_date: datetime, end_date: datetime, historical_data: pd.DataFrame
) -> Dict[datetime, float]:
    """Get predicted consumption using historical data for better lag/rolling features"""
    # Snap start_date to the closest 5-minute interval
    start_date = start_date - timedelta(
        minutes=start_date.minute % 5,
        seconds=start_date.second,
        microseconds=start_date.microsecond,
    )

    # Load the improved model
    model_path = os.path.join(
        os.path.dirname(__file__), "../models/power-consumption-baseline.joblib"
    )

    if not os.path.exists(model_path):
        raise FileNotFoundError(
            f"Model not found at {model_path}. Please run analyze_consumption.py first to train the model."
        )

    model = joblib.load(model_path)

    # Generate time slots for prediction
    time_slots = []
    t = start_date
    while t <= end_date:
        time_slots.append(t)
        t += timedelta(minutes=5)

    # Create DataFrame with historical data + prediction times
    # Use historical data for lag/rolling features, then add prediction times
    if len(historical_data) > 0:
        # Get the last few rows of historical data for context
        last_historical = historical_data.tail(10).copy()

        # Create prediction rows
        pred_df = pd.DataFrame(
            {
                "time": time_slots,
                "value": [0.0] * len(time_slots),  # Will be filled with predictions
            }
        )

        # Combine historical and prediction data
        combined_df = pd.concat([last_historical, pred_df], ignore_index=True)
    else:
        # No historical data, use dummy approach
        combined_df = pd.DataFrame(
            {"time": time_slots, "value": [0.0] * len(time_slots)}
        )

    # Add all features
    df_with_features = add_features_for_prediction(combined_df)

    # Get features for prediction
    X = prepare_features_for_prediction(df_with_features)

    # Get only the rows corresponding to our prediction times
    pred_mask = df_with_features["time"].isin(time_slots)
    X_pred = X[pred_mask]
    pred_times = df_with_features["time"][pred_mask]

    # Remove rows with NaN values
    valid_mask = ~X_pred.isna().any(axis=1)
    X_valid = X_pred[valid_mask]
    valid_times = pred_times[valid_mask]

    if len(X_valid) == 0:
        print("Warning: No valid predictions possible due to insufficient history")
        return {}

    # Make predictions
    predictions = model.predict(X_valid)

    # Create result dictionary
    consumption_data: Dict[datetime, float] = {}
    for dt, pred in zip(valid_times, predictions):
        consumption_data[dt] = max(0, float(pred))

    # Fill in any missing time slots
    for dt in time_slots:
        if dt not in consumption_data:
            last_pred = list(consumption_data.values())[-1] if consumption_data else 0
            consumption_data[dt] = last_pred

    return consumption_data


def get_consumption_iterative(
    start_date: datetime,
    end_date: datetime,
    initial_lag_1: Optional[float] = None,
    initial_lag_2: Optional[float] = None,
    initial_rolling_mean: Optional[float] = None,
    initial_rolling_std: Optional[float] = None,
) -> Dict[datetime, float]:
    """
    Get predicted consumption using iterative prediction (using previous predictions as history)

    Args:
        start_date: Start time for predictions
        end_date: End time for predictions
        initial_lag_1: Initial value for lag_1 (5 minutes ago consumption)
        initial_lag_2: Initial value for lag_2 (10 minutes ago consumption)
        initial_rolling_mean: Initial rolling mean value
        initial_rolling_std: Initial rolling standard deviation value
    """
    # Snap start_date to the closest 5-minute interval
    start_date = start_date - timedelta(
        minutes=start_date.minute % 5,
        seconds=start_date.second,
        microseconds=start_date.microsecond,
    )

    # Load the improved model
    model_path = os.path.join(
        os.path.dirname(__file__), "../models/power-consumption-baseline.joblib"
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

    # Initialize with provided values or reasonable defaults
    if initial_lag_1 is None:
        hour = start_date.hour
        if 6 <= hour <= 8:
            initial_lag_1 = 800
        elif 17 <= hour <= 21:
            initial_lag_1 = 1200
        elif 22 <= hour or hour <= 5:
            initial_lag_1 = 300
        else:
            initial_lag_1 = 600

    if initial_lag_2 is None:
        initial_lag_2 = initial_lag_1

    if initial_rolling_mean is None:
        initial_rolling_mean = initial_lag_1

    if initial_rolling_std is None:
        initial_rolling_std = 100  # Reasonable default standard deviation

    # Create initial history (we need at least 6 periods for rolling features)
    # Create dummy history with the provided initial values
    history_times = []
    history_values = []

    # Create 6 periods of history before our prediction start
    for i in range(6, 0, -1):
        history_time = start_date - timedelta(minutes=5 * i)
        history_times.append(history_time)
        # Use provided values for the last 2 periods, rolling mean for earlier
        if i == 1:
            history_values.append(initial_lag_1)
        elif i == 2:
            history_values.append(initial_lag_2)
        else:
            # For earlier periods, use rolling mean with some variation
            history_values.append(
                initial_rolling_mean + np.random.normal(0, initial_rolling_std)
            )

    # Now predict iteratively, using each prediction as history for the next
    consumption_data: Dict[datetime, float] = {}

    for i, current_time in enumerate(time_slots):
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
                prediction = 800
            elif 17 <= hour <= 21:
                prediction = 1200
            elif 22 <= hour or hour <= 5:
                prediction = 300
            else:
                prediction = 600
        else:
            # Make prediction
            prediction = model.predict(current_features)[0]
            prediction = max(0, float(prediction))

        # Store prediction
        consumption_data[current_time] = prediction

        # Update history for next iteration
        history_times.append(current_time)
        history_values.append(prediction)

        # Keep only the last 10 periods to avoid memory issues
        if len(history_times) > 10:
            history_times = history_times[-10:]
            history_values = history_values[-10:]

    return consumption_data


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

    # Load the improved model
    model_path = os.path.join(
        os.path.dirname(__file__), "../models/power-consumption-baseline.joblib"
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
                prediction = 800
            elif 17 <= hour <= 21:
                prediction = 1200
            elif 22 <= hour or hour <= 5:
                prediction = 300
            else:
                prediction = 600
        else:
            # Make prediction
            prediction = model.predict(current_features)[0]
            prediction = max(0, float(prediction))

        # Store prediction
        consumption_data[current_time] = prediction

        # Update history for next iteration
        history_times.append(current_time)
        history_values.append(prediction)

        # Keep only the last 10 periods to avoid memory issues
        if len(history_times) > 10:
            history_times = history_times[-10:]
            history_values = history_values[-10:]

    return consumption_data


if __name__ == "__main__":
    # Test the different consumption prediction methods
    print("=== Testing Different Consumption Prediction Methods ===\n")

    start_time = datetime(2025, 6, 1, 11, 0, 0)
    end_time = datetime(2025, 6, 1, 11, 30, 0)

    try:
        print("1. Original method (using default estimates):")
        original_response = get_consumption(start_time, end_time)
        for dt, consumption in list(original_response.items())[:5]:  # Show first 5
            print(f"  {dt.strftime('%H:%M')}: {consumption:.1f} W")
        print("  ...")

        print("\n2. Iterative method (using predictions as history):")
        iterative_response = get_consumption_iterative(start_time, end_time)
        for dt, consumption in list(iterative_response.items())[:5]:  # Show first 5
            print(f"  {dt.strftime('%H:%M')}: {consumption:.1f} W")
        print("  ...")

        print("\n3. Iterative method with custom initial values:")
        custom_response = get_consumption_iterative(
            start_time,
            end_time,
            initial_lag_1=750.0,  # 5 minutes ago
            initial_lag_2=800.0,  # 10 minutes ago
            initial_rolling_mean=775.0,
            initial_rolling_std=50.0,
        )
        for dt, consumption in list(custom_response.items())[:5]:  # Show first 5
            print(f"  {dt.strftime('%H:%M')}: {consumption:.1f} W")
        print("  ...")

        print("\n4. Method with provided initial consumption values:")
        # Provide 6 periods of history (most recent last)
        initial_values = [600, 650, 700, 750, 800, 750]  # 30 minutes of history
        initial_response = get_consumption_with_initial_values(
            start_time, end_time, initial_values
        )
        for dt, consumption in list(initial_response.items())[:5]:  # Show first 5
            print(f"  {dt.strftime('%H:%M')}: {consumption:.1f} W")
        print("  ...")

        # Compare the methods
        print("\n=== Comparison ===")
        print("Original method uses default time-based estimates for all periods.")
        print(
            "Iterative method uses each prediction as history for the next prediction."
        )
        print("Custom initial values allow you to specify the starting conditions.")
        print(
            "Initial values method lets you provide actual historical consumption data."
        )

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please run analyze_consumption.py first to train the model.")
