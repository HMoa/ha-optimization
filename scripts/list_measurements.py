#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

# Add the project root to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from influxdb import InfluxDBClient

from config.influxdb_env import get_production_config_path
from optimizer.influxdb_client import InfluxDBConfig


def list_measurements(config_path: str | None = None) -> None:
    """List all measurements in the InfluxDB database"""

    if config_path is None:
        config_path = get_production_config_path()
    config = InfluxDBConfig(config_path)

    # Parse URL to get host and port
    url_parts = config.url.replace("http://", "").split(":")
    host = url_parts[0]
    port = int(url_parts[1]) if len(url_parts) > 1 else 8086

    client = InfluxDBClient(
        host=host,
        port=port,
        username=config.username,
        password=config.password,
        database=config.database,
    )

    try:
        # Query to get all measurements
        query = "SHOW MEASUREMENTS"
        result = client.query(query)

        measurements = []
        for point in result.get_points():
            measurements.append(point["name"])

        print(
            f"Found {len(measurements)} measurements in database '{config.database}':"
        )
        for i, measurement in enumerate(measurements, 1):
            print(f"  {i}. {measurement}")

        return measurements

    except Exception as e:
        print(f"Error listing measurements: {e}")
        return []
    finally:
        client.close()


if __name__ == "__main__":
    list_measurements()
