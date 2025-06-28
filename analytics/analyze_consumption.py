#!/usr/bin/env python3

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split


def add_time_features(df):
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

    return df


def main():
    print("This is the main check for analyze_consumption.py")

    # Load the production data
    production_data = pd.read_csv("consumed-power.csv", parse_dates=["time"], sep=",")

    # Remove rows where null
    production_data = production_data.dropna(subset=["time"])
    production_data = production_data.dropna(subset=["value"])

    production_data = add_time_features(production_data)

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

    joblib.dump(model, "power-consumption.joblib")

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
