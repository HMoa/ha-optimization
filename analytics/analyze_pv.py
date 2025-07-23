#!/usr/bin/env python3
from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split


def main() -> None:
    print("This is the main check for analyze.py")

    production_data = pd.read_csv("pv.23.07.csv", parse_dates=["time"], sep=",")

    # Remove rows where null
    production_data = production_data.dropna(subset=["time"])
    production_data = production_data.dropna(subset=["value"])

    # Cyclical features for time of day
    minutes_of_day = (
        production_data["time"].dt.hour * 60 + production_data["time"].dt.minute
    )
    production_data["sin_day"] = (minutes_of_day / 1440 * 2 * 3.141592653589793).apply(
        lambda x: np.sin(x)
    )
    production_data["cos_day"] = (minutes_of_day / 1440 * 2 * 3.141592653589793).apply(
        lambda x: np.cos(x)
    )

    # Cyclical features for time of year
    day_of_year = production_data["time"].dt.dayofyear
    production_data["sin_year"] = (day_of_year / 365 * 2 * 3.141592653589793).apply(
        lambda x: np.sin(x)
    )
    production_data["cos_year"] = (day_of_year / 365 * 2 * 3.141592653589793).apply(
        lambda x: np.cos(x)
    )

    # Define features and target
    X = production_data[["sin_day", "cos_day", "sin_year", "cos_year"]]
    y = production_data["value"]

    # Split the data into training and test sets
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Train a regression model
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

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
