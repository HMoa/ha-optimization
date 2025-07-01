#!/usr/bin/env python3
from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add both linear and cyclic time features"""

    # Calculate minutes of day for cyclic encoding
    minutes_of_day = df["time"].dt.hour * 60 + df["time"].dt.minute

    df["day_of_year"] = df["time"].dt.dayofyear
    df["minutes_of_day"] = minutes_of_day
    df["minutes_sin"] = np.sin(2 * np.pi * minutes_of_day / (24 * 60))
    df["minutes_cos"] = np.cos(2 * np.pi * minutes_of_day / (24 * 60))
    df["day_of_year_sin"] = np.sin(2 * np.pi * df["day_of_year"] / 365)
    df["day_of_year_cos"] = np.cos(2 * np.pi * df["day_of_year"] / 365)

    # Night time feature (22:00 - 09:00)
    df["night_time"] = ((df["time"].dt.hour >= 22) | (df["time"].dt.hour < 9)).astype(
        int
    )

    # Lagged features
    df["consumption_24h_ago"] = df["value"].shift(288)  # 24h * 12 (5-min intervals)
    df["consumption_7d_ago"] = df["value"].shift(2016)  # 7d * 24h * 12
    df["consumption_5m_ago"] = df["value"].shift(1)  # 5 minutes ago
    df["consumption_1h_ago"] = df["value"].shift(12)  # 1 hour ago
    df["consumption_2h_ago"] = df["value"].shift(24)  # 2 hours ago

    # Rolling averages
    df["consumption_24h_avg"] = df["value"].rolling(288).mean()
    df["consumption_7d_avg"] = df["value"].rolling(2016).mean()

    return df


def resample_to_5min(df: pd.DataFrame) -> pd.DataFrame:
    """Resample 1-minute data to 5-minute intervals"""
    # Only resample the 'value' column, keep time as index
    df_resampled = df.set_index("time")["value"].resample("5min").mean().reset_index()
    return df_resampled


def main() -> None:
    print("This is the main check for analyze_consumption.py")

    # Load the production data
    production_data = pd.read_csv("consumed-power.csv", parse_dates=["time"], sep=",")

    # Resample to 5-minute intervals
    # production_data = resample_to_5min(production_data)

    # Now add features (lagged features will be correct)
    production_data = add_time_features(production_data)

    # Remove rows where null
    production_data = production_data.dropna(subset=["time"])
    production_data = production_data.dropna(subset=["value"])

    best_yet = [
        "day_of_year",
        "minutes_of_day",
        "minutes_sin",
        "minutes_cos",
    ]

    # Define features and target
    X = production_data[
        [
            "day_of_year",
            # "day_of_year_sin",
            # "day_of_year_cos",
            "minutes_of_day",
            "minutes_sin",
            "minutes_cos",
            # "night_time",
            # "consumption_24h_ago",
            # "consumption_7d_ago",
            # "consumption_5m_ago",
            # "consumption_1h_ago",
            # "consumption_2h_ago",
            # "consumption_24h_avg",
            # "consumption_7d_avg",
        ]
    ]
    # y = production_data["production"]
    y = production_data["value"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Train a regression model
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    joblib.dump(model, "../models/power-consumption.joblib")

    # Make predictions
    y_pred = model.predict(X_test)

    # Evaluate the model
    mse = mean_squared_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    print(f"Mean Squared Error: {mse}")
    print(f"R^2 Score: {r2}")

    # Print feature importance
    feature_importance = pd.DataFrame(
        {"feature": X.columns, "importance": model.feature_importances_}
    ).sort_values("importance", ascending=False)

    print("\nFeature Importance:")
    print(feature_importance)


if __name__ == "__main__":
    main()
