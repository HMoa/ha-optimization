#!/usr/bin/env python3
from __future__ import annotations

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split


def main() -> None:
    print("This is the main check for analyze.py")

    # Load the production data
    # production_data = pd.read_csv(
    #    "analytics/production2024.csv", parse_dates=["time"], sep="\t"
    # )
    production_data = pd.read_csv("PV-power.csv", parse_dates=["time"], sep=",")

    # Remove rows where null
    production_data = production_data.dropna(subset=["time"])
    production_data = production_data.dropna(subset=["value"])

    production_data["minutes_of_day"] = (
        production_data["time"].dt.hour * 60 + production_data["time"].dt.minute
    )
    production_data["day_of_week"] = production_data["time"].dt.dayofweek
    production_data["week"] = production_data["time"].dt.isocalendar()[
        1
    ]  # Fix: use [1] to get week number

    # Define features and target
    X = production_data[["minutes_of_day", "day_of_week", "week"]]
    y = production_data["value"]

    # Split the data into training and test sets
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Train a regression model
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    import joblib

    joblib.dump(model, "../models/pv_production.joblib")

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
