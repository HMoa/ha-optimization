#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from typing import Any, List, Optional

import pandas as pd
from influxdb import InfluxDBClient

from config.influxdb_env import get_config_path


class InfluxDBConfig:
    """Configuration class for InfluxDB connection"""

    def __init__(self, config_path: str | None = None):
        if config_path is None:
            config_path = get_config_path()
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        """Load configuration from JSON file"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(
                f"InfluxDB config file not found: {self.config_path}"
            )

        with open(self.config_path, "r") as f:
            config = json.load(f)

        # Validate required fields
        required_fields = ["url", "username", "password", "database", "measurement"]
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required config field: {field}")

        return dict(config)

    @property
    def url(self) -> str:
        return str(self.config["url"])

    @property
    def username(self) -> str:
        return str(self.config["username"])

    @property
    def password(self) -> str:
        return str(self.config["password"])

    @property
    def database(self) -> str:
        return str(self.config["database"])

    @property
    def measurement(self) -> str:
        return str(self.config["measurement"])

    @property
    def field(self) -> str:
        return str(self.config.get("field", "value"))

    @property
    def time_window_minutes(self) -> int:
        return int(self.config.get("time_window_minutes", 30))

    @property
    def aggregation_window_minutes(self) -> int:
        return int(self.config.get("aggregation_window_minutes", 5))

    @property
    def data_points(self) -> int:
        return int(self.config.get("data_points", 6))


class InfluxDBClientWrapper:
    """Wrapper for InfluxDB 1.x client with consumption data fetching"""

    def __init__(self, config: InfluxDBConfig):
        self.config = config
        # Parse URL to get host and port
        url_parts = config.url.replace("http://", "").split(":")
        host = url_parts[0]
        port = int(url_parts[1]) if len(url_parts) > 1 else 8086

        self.client = InfluxDBClient(
            host=host,
            port=port,
            username=config.username,
            password=config.password,
            database=config.database,
        )

    def __enter__(self) -> InfluxDBClientWrapper:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close the InfluxDB client connection"""
        if hasattr(self, "client"):
            self.client.close()

    def get_consumption_data(
        self,
        time_window_minutes: Optional[int] = None,
        aggregation_window_minutes: Optional[int] = None,
        data_points: Optional[int] = None,
    ) -> List[float]:
        """
        Fetch consumption data from InfluxDB 1.x using InfluxQL query

        Args:
            time_window_minutes: Time window to fetch data from (default from config)
            aggregation_window_minutes: Aggregation window size (default from config)
            data_points: Number of data points to return (default from config)

        Returns:
            List of consumption values in chronological order (oldest to newest)
        """
        # Use config defaults if not provided
        time_window = time_window_minutes or self.config.time_window_minutes
        agg_window = (
            aggregation_window_minutes or self.config.aggregation_window_minutes
        )
        points = data_points or self.config.data_points

        # Build InfluxQL query for InfluxDB 1.x
        influxql_query = f"""
        SELECT MEAN({self.config.field}) as value
        FROM "{self.config.measurement}"
        WHERE time > now() - {time_window}m
        GROUP BY time({agg_window}m)
        ORDER BY time ASC
        LIMIT {points}
        """

        try:
            # Execute query
            result = self.client.query(influxql_query)

            # Extract values from result
            values = []
            for point in result.get_points():
                if point["value"] is not None:
                    values.append(float(point["value"]))

            if len(values) < points:
                print(f"Warning: Only got {len(values)} data points, expected {points}")

            return values

        except Exception as e:
            print(f"Error fetching data from InfluxDB: {e}")
            return []

    def get_consumption_data_with_timestamps(
        self,
        time_window_minutes: Optional[int] = None,
        aggregation_window_minutes: Optional[int] = None,
        data_points: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Fetch consumption data with timestamps from InfluxDB 1.x

        Returns:
            DataFrame with 'timestamp' and 'value' columns
        """
        # Use config defaults if not provided
        time_window = time_window_minutes or self.config.time_window_minutes
        agg_window = (
            aggregation_window_minutes or self.config.aggregation_window_minutes
        )
        points = data_points or self.config.data_points

        # Build InfluxQL query for InfluxDB 1.x
        influxql_query = f"""
        SELECT MEAN({self.config.field}) as value
        FROM "{self.config.measurement}"
        WHERE time > now() - {time_window}m
        GROUP BY time({agg_window}m)
        ORDER BY time ASC
        LIMIT {points}
        """

        try:
            # Execute query
            result = self.client.query(influxql_query)

            # Extract data from result
            data = []
            for point in result.get_points():
                if point["value"] is not None:
                    data.append(
                        {"timestamp": point["time"], "value": float(point["value"])}
                    )

            df = pd.DataFrame(data)
            if len(df) < points:
                print(f"Warning: Only got {len(df)} data points, expected {points}")

            return df

        except Exception as e:
            print(f"Error fetching data from InfluxDB: {e}")
            return pd.DataFrame(columns=["timestamp", "value"])

    def test_connection(self) -> bool:
        """Test the InfluxDB connection"""
        try:
            # Simple query to test connection
            influxql_query = f"""
            SELECT {self.config.field}
            FROM "{self.config.measurement}"
            WHERE time > now() - 10m
            LIMIT 1
            """
            self.client.query(influxql_query)
            return True
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False

    def write_point(
        self,
        measurement: str,
        fields: dict[str, Any],
        tags: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> None:
        """
        Write a single point to InfluxDB.
        Args:
            measurement: Measurement name
            fields: Dictionary of field values
            tags: Optional dictionary of tags
            timestamp: Optional ISO8601 timestamp string
        """
        point = {
            "measurement": measurement,
            "fields": fields,
        }
        if tags:
            point["tags"] = tags
        if timestamp:
            point["time"] = timestamp
        self.client.write_points([point])


def get_initial_consumption_values(
    config_path: str | None = None,
) -> List[float]:
    """
    Convenience function to get initial consumption values from InfluxDB 1.x

    Args:
        config_path: Path to InfluxDB config file (defaults to current environment)

    Returns:
        List of consumption values in chronological order (oldest to newest)
    """
    if config_path is None:
        config_path = get_config_path()
    config = InfluxDBConfig(config_path)

    with InfluxDBClientWrapper(config) as client:
        if not client.test_connection():
            print("Failed to connect to InfluxDB. Check your configuration.")
            return []

        values = client.get_consumption_data()

        return list(values)


if __name__ == "__main__":
    # Test the InfluxDB client
    try:
        values = get_initial_consumption_values()
        if values:
            print(f"Test successful! Got {len(values)} values: {values}")
        else:
            print("Test failed - no data retrieved")
    except Exception as e:
        print(f"Test failed with error: {e}")
