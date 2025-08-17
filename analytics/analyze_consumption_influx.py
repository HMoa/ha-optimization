#!/usr/bin/env python3
from __future__ import annotations

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

# Add the optimizer directory to the path to import the InfluxDB client
import sys
sys.path.append(str(Path(__file__).parent.parent / "optimizer"))

from influxdb_client import InfluxDBConfig, InfluxDBClientWrapper


def fetch_consumption_data_from_influx(
    start_date: datetime, 
    end_date: datetime,
    config_path: str = "../config/influxdb_config.json"
) -> pd.DataFrame:
    """Fetch consumption data from InfluxDB for a specific date range"""
    print(f"Fetching data from InfluxDB from {start_date} to {end_date}")
    
    config = InfluxDBConfig(config_path)
    
    with InfluxDBClientWrapper(config) as client:
        if not client.test_connection():
            raise ConnectionError("Failed to connect to InfluxDB. Check your configuration.")
        
        # Build InfluxQL query for the specific date range
        start_time = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_time = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        influxql_query = f"""
        SELECT MEAN({config.field}) as value
        FROM "{config.measurement}"
        WHERE time >= '{start_time}' AND time <= '{end_time}'
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
                    data.append({
                        "time": timestamp,
                        "value": float(point["value"])
                    })
            
            df = pd.DataFrame(data)
            
            if df.empty:
                print("Warning: No data found for the specified date range")
                return df
            
            print(f"Fetched {len(df)} records from {df['time'].min()} to {df['time'].max()}")
            print(f"Consumption range: {df['value'].min():.2f} - {df['value'].max():.2f} W")
            
            return df
            
        except Exception as e:
            print(f"Error fetching data from InfluxDB: {e}")
            return pd.DataFrame(columns=["time", "value"])


def load_and_clean_data_influx(start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """Load and clean consumption data from InfluxDB"""
    print(f"Loading data from InfluxDB for {start_date.date()} to {end_date.date()}")

    # Fetch data from InfluxDB
    df = fetch_consumption_data_from_influx(start_date, end_date)

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


def add_basic_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add basic time-based features only"""
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


def prepare_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    """Prepare features and target for modeling"""
    # Select features including lags and rolling mean
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

    # Plot feature importance
    plt.figure(figsize=(10, 6))
    sns.barplot(data=importance_df, x="importance", y="feature")
    plt.title(f"Feature Importance - {model_name}")
    plt.xlabel("Importance")
    plt.tight_layout()
    plt.show()


def main() -> None:
    """Main function to train and evaluate consumption model with InfluxDB data"""
    print("=== Power Consumption Model with InfluxDB Data ===")
    print("Using data from InfluxDB 'power.consumed' measurement")

    # Set date range for August 8th, 2025 (has 1439 data points)
    start_date = datetime(2025, 8, 8, 0, 0, 0)
    end_date = datetime(2025, 8, 8, 23, 59, 59)

    # Load and prepare data
    df = load_and_clean_data_influx(start_date, end_date)

    # Add basic features only
    print("\nAdding basic time features...")
    df = add_basic_time_features(df)

    # Prepare features and target
    X, y = prepare_features(df)

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, shuffle=False
    )

    print(f"\nTraining set: {len(X_train)} samples")
    print(f"Test set: {len(X_test)} samples")

    # Define models
    models = {
        "Random Forest": RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        ),
        "Gradient Boosting": GradientBoostingRegressor(
            n_estimators=100, max_depth=6, learning_rate=0.1, random_state=42
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

        # Track best model
        if rmse < best_score:
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
    model_path = Path("../models/power-consumption-influx.joblib")
    model_path.parent.mkdir(exist_ok=True)
    joblib.dump(best_model, model_path)
    print(f"\nBest model saved to {model_path}")

    # Print summary
    print(f"\n{'='*50}")
    print("INFLUXDB MODEL COMPARISON SUMMARY:")
    print(f"{'Model':<20} {'RMSE':<10} {'MAE':<10} {'R²':<10}")
    print("-" * 50)
    for name, metrics in results.items():
        print(
            f"{name:<20} {metrics['rmse']:<10.2f} {metrics['mae']:<10.2f} {metrics['r2']:<10.4f}"
        )

    print(
        f"\nBest model: {best_model.__class__.__name__} (RMSE: {best_score:.2f} W)"
    )
    print(f"Data source: InfluxDB 'power.consumed' measurement")
    print(f"Date range: {start_date.date()} to {end_date.date()}")


if __name__ == "__main__":
    main()
