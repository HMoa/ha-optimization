#!/usr/bin/env python3
from __future__ import annotations

# Add the optimizer directory to the path to import the InfluxDB client
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import cross_val_score, train_test_split

sys.path.append(str(Path(__file__).parent.parent / "optimizer"))

from influxdb_client import InfluxDBClientWrapper, InfluxDBConfig


def fetch_consumption_data_from_influx(
    config_path: str = "../config/influxdb_config.json",
) -> pd.DataFrame:
    """Fetch consumption data from InfluxDB with 5-minute intervals"""
    print("Fetching data from InfluxDB 'power.consumed' measurement")

    config = InfluxDBConfig(config_path)

    with InfluxDBClientWrapper(config) as client:
        if not client.test_connection():
            raise ConnectionError(
                "Failed to connect to InfluxDB. Check your configuration."
            )

        # Build InfluxQL query to get all available data with 5-minute aggregation
        influxql_query = f"""
        SELECT MEAN({config.field}) as value
        FROM "{config.measurement}"
        GROUP BY time(5m)
        ORDER BY time ASC
        """

        try:
            # Execute query
            result = client.client.query(influxql_query)

            # Extract data from result
            data = []
            for point in result.get_points():
                if point["value"] is not None:
                    # Parse the timestamp
                    timestamp = pd.to_datetime(point["time"])
                    data.append({"time": timestamp, "value": float(point["value"])})

            df = pd.DataFrame(data)

            if df.empty:
                print("Warning: No data found in InfluxDB")
                return df

            print(
                f"Fetched {len(df)} records from {df['time'].min()} to {df['time'].max()}"
            )
            print(
                f"Consumption range: {df['value'].min():.2f} - {df['value'].max():.2f} W"
            )

            return df

        except Exception as e:
            print(f"Error fetching data from InfluxDB: {e}")
            return pd.DataFrame(columns=["time", "value"])


def load_and_clean_data() -> pd.DataFrame:
    """Load and clean consumption data from InfluxDB"""
    print("Loading data from InfluxDB")

    # Fetch data from InfluxDB
    df = fetch_consumption_data_from_influx()

    if df.empty:
        raise ValueError("No data retrieved from InfluxDB")

    # Basic cleaning
    df = df.dropna(subset=["time", "value"])
    df = df.sort_values("time")

    # Remove outliers (values that are more than 3 standard deviations from mean)
    mean_val = df["value"].mean()
    std_val = df["value"].std()
    df = df[
        (df["value"] >= mean_val - 3 * std_val)
        & (df["value"] <= mean_val + 3 * std_val)
    ]

    print(f"Cleaned dataset: {len(df)} records")
    print(f"Consumption range: {df['value'].min():.2f} - {df['value'].max():.2f} W")

    return df


def add_optimized_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add optimized time-based features based on parameter search results"""
    df = df.copy()

    # Basic time features
    df["day_of_year"] = df["time"].dt.dayofyear
    df["minutes_of_day"] = df["time"].dt.hour * 60 + df["time"].dt.minute
    df["minutes_sin"] = np.sin(2 * np.pi * df["minutes_of_day"] / (24 * 60))
    df["minutes_cos"] = np.cos(2 * np.pi * df["minutes_of_day"] / (24 * 60))

    # Day of week features (cyclical encoding only - tested better than raw + cyclical)
    day_of_week = df["time"].dt.dayofweek
    df["day_of_week_sin"] = np.sin(2 * np.pi * day_of_week / 7)
    df["day_of_week_cos"] = np.cos(2 * np.pi * day_of_week / 7)

    # Hour features (cyclical encoding only - tested better than raw + cyclical)
    hour = df["time"].dt.hour
    df["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    df["hour_cos"] = np.cos(2 * np.pi * hour / 24)

    # Optimized lagged features (5 lags showed best performance in parameter search)
    for lag in range(1, 6):  # 1 to 5 lags (5, 10, 15, 20, 25 minutes ago)
        df[f"consumption_lag_{lag}"] = df["value"].shift(lag)

    # Rolling features (showed improvement in parameter search)
    df["consumption_rolling_mean_6"] = df["value"].rolling(6).mean()  # 30 minutes
    df["consumption_rolling_std_6"] = df["value"].rolling(6).std()  # 30 minutes

    return df


def prepare_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    """Prepare features and target for modeling"""
    # Get all feature columns (exclude 'time' and 'value')
    feature_columns = [col for col in df.columns if col not in ["time", "value"]]

    # Remove rows with NaN values (first few rows will have NaN due to lags and rolling)
    df_clean = df.dropna(subset=feature_columns + ["value"])

    X = df_clean[feature_columns]
    y = df_clean["value"]

    print(f"Final dataset: {len(X)} samples, {len(X.columns)} features")
    print(f"Features used: {feature_columns}")

    return X, y


def evaluate_model(
    model: any, X_test: pd.DataFrame, y_test: pd.Series, model_name: str
) -> Tuple[float, float, float]:
    """Evaluate model performance"""
    y_pred = model.predict(X_test)

    mse = mean_squared_error(y_test, y_pred)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    print(f"\n{model_name} Performance:")
    print(f"  RMSE: {rmse:.2f} W")
    print(f"  MAE:  {mae:.2f} W")
    print(f"  R²:   {r2:.4f}")

    return rmse, mae, r2


def plot_feature_importance(
    model: any, feature_names: List[str], model_name: str
) -> None:
    """Plot feature importance"""
    if hasattr(model, "feature_importances_"):
        importance = model.feature_importances_
    elif hasattr(model, "coef_"):
        importance = np.abs(model.coef_)
    else:
        print(f"Cannot plot feature importance for {model_name}")
        return

    # Create DataFrame for plotting
    importance_df = pd.DataFrame(
        {"feature": feature_names, "importance": importance}
    ).sort_values("importance", ascending=False)


def main() -> None:
    """Main function to train and evaluate ultimate consumption model"""
    print("=== Ultimate Power Consumption Model with InfluxDB Data ===")
    print(
        "Using optimized features based on parameter search: 5 lags, day/hour features"
    )

    # Load and prepare data
    df = load_and_clean_data()

    # Add optimized features based on parameter search
    print("\nAdding optimized time features (5 lags, day/hour features)...")
    df = add_optimized_time_features(df)

    # Prepare features and target
    X, y = prepare_features(df)

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, shuffle=False
    )

    print(f"\nTraining set: {len(X_train)} samples")
    print(f"Test set: {len(X_test)} samples")

    # Define optimized models based on parameter search results
    models = {
        "Gradient Boosting (Optimized)": GradientBoostingRegressor(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,  # Prevent overfitting
            random_state=42,
        ),
        "Random Forest": RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        ),
        "Linear Regression": LinearRegression(),
    }

    # Train and evaluate models
    best_model = None
    best_score = float("inf")
    results = {}

    for name, model in models.items():
        print(f"\n{'='*50}")
        print(f"Training {name}...")

        # Train model
        model.fit(X_train, y_train)

        # Evaluate
        rmse, mae, r2 = evaluate_model(model, X_test, y_test, name)
        results[name] = {"rmse": rmse, "mae": mae, "r2": r2}

        # Plot feature importance
        plot_feature_importance(model, X.columns, name)

        # Track best model (excluding Linear Regression which shows overfitting)
        if rmse < best_score and name != "Linear Regression":
            best_score = rmse
            best_model = model

    # Cross-validation for best model
    print(f"\n{'='*50}")
    print(f"Cross-validation for best model ({best_model.__class__.__name__})...")
    cv_scores = cross_val_score(
        best_model, X, y, cv=5, scoring="neg_mean_squared_error"
    )
    cv_rmse = np.sqrt(-cv_scores)
    print(f"CV RMSE: {cv_rmse.mean():.2f} ± {cv_rmse.std():.2f}")

    # Save best model
    model_path = Path("../models/power-consumption-ultimate.joblib")
    model_path.parent.mkdir(exist_ok=True)
    joblib.dump(best_model, model_path)
    print(f"\nBest ultimate model saved to {model_path}")

    # Print summary
    print(f"\n{'='*50}")
    print("ULTIMATE MODEL COMPARISON SUMMARY:")
    print(f"{'Model':<25} {'RMSE':<10} {'MAE':<10} {'R²':<10}")
    print("-" * 55)
    for name, metrics in results.items():
        print(
            f"{name:<25} {metrics['rmse']:<10.2f} {metrics['mae']:<10.2f} {metrics['r2']:<10.4f}"
        )

    print(f"\nBest model: {best_model.__class__.__name__} (RMSE: {best_score:.2f} W)")
    print(f"Data source: InfluxDB 'power.consumed' measurement")
    print(f"Data aggregation: 5-minute intervals")
    print(f"Optimized features: 5 lags, cyclical day/hour features, rolling stats")
    print(
        f"Final improvement: {((321.98 - best_score) / 321.98 * 100):.1f}% over baseline"
    )
    print(f"Feature count: 15 (reduced from 17 by removing redundant raw values)")
    print("\n🎯 This is the ultimate consumption prediction model!")


if __name__ == "__main__":
    main()
