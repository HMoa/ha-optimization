#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

# Add the project root to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.influxdb_env import get_config_path, print_environment_info
from optimizer.influxdb_client import InfluxDBClientWrapper, InfluxDBConfig


def test_local_influxdb() -> None:
    """Test the local InfluxDB connection and basic operations"""

    print("Testing local InfluxDB setup...")

    try:
        # Test with current environment config
        print_environment_info()
        config = InfluxDBConfig()
        print(f"✓ Loaded config: {config.url}")

        with InfluxDBClientWrapper(config) as client:
            # Test connection
            if client.test_connection():
                print("✓ Successfully connected to local InfluxDB")
            else:
                print("✗ Failed to connect to local InfluxDB")
                return

            # Test basic query
            try:
                # Try to get some data
                values = client.get_consumption_data(
                    time_window_minutes=10, data_points=1
                )
                if values:
                    print(f"✓ Successfully queried data: {len(values)} points")
                else:
                    print(
                        "✓ Connected but no data found (this is normal for a fresh instance)"
                    )

            except Exception as e:
                print(f"✗ Query failed: {e}")
                return

        print("\n🎉 Local InfluxDB setup is working correctly!")
        print("\nNext steps:")
        print("1. Run 'make backup' to backup production data")
        print("2. Run 'make restore' to restore data to local instance")
        print("3. Use the centralized config system for easy environment switching")

    except Exception as e:
        print(f"✗ Test failed: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure Docker is running")
        print("2. Run 'make influxdb-up' to start the local InfluxDB")
        print("3. Check 'make influxdb-logs' for any errors")


if __name__ == "__main__":
    test_local_influxdb()
