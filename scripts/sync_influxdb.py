#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from influxdb import InfluxDBClient

# Add the project root to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.influxdb_env import get_local_config_path, get_production_config_path
from optimizer.influxdb_client import InfluxDBConfig


def get_last_sync_time(sync_file: str) -> datetime:
    """Get the last sync time from the sync file"""
    if os.path.exists(sync_file):
        with open(sync_file, "r") as f:
            data = json.load(f)
            return datetime.fromisoformat(data["last_sync_time"])
    else:
        # Default to 24 hours ago if no sync file exists
        return datetime.now() - timedelta(hours=24)


def update_sync_time(sync_file: str, sync_time: datetime) -> None:
    """Update the sync file with the latest sync time"""
    os.makedirs(os.path.dirname(sync_file), exist_ok=True)
    with open(sync_file, "w") as f:
        json.dump(
            {
                "last_sync_time": sync_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "updated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            f,
            indent=2,
        )


def sync_measurement(
    prod_config: InfluxDBConfig,
    local_config: InfluxDBConfig,
    sync_file: str,
    batch_size: int = 1000,
) -> None:
    """
    Sync new data from production InfluxDB to local InfluxDB

    Args:
        prod_config: Production InfluxDB configuration
        local_config: Local InfluxDB configuration
        sync_file: File to track last sync time
        batch_size: Number of points to write in each batch
    """
    # Get last sync time
    last_sync = get_last_sync_time(sync_file)
    current_time = datetime.now()

    print(f"Syncing data from {last_sync} to {current_time}")

    # Parse production URL
    prod_url_parts = prod_config.url.replace("http://", "").split(":")
    prod_host = prod_url_parts[0]
    prod_port = int(prod_url_parts[1]) if len(prod_url_parts) > 1 else 8086

    # Parse local URL
    local_url_parts = local_config.url.replace("http://", "").split(":")
    local_host = local_url_parts[0]
    local_port = int(local_url_parts[1]) if len(local_url_parts) > 1 else 8086

    # Connect to production
    prod_client = InfluxDBClient(
        host=prod_host,
        port=prod_port,
        username=prod_config.username,
        password=prod_config.password,
        database=prod_config.database,
    )

    # Connect to local
    local_client = InfluxDBClient(
        host=local_host,
        port=local_port,
        username=local_config.username,
        password=local_config.password,
        database=local_config.database,
    )

    try:
        # Query new data from production
        query = f"""
        SELECT *
        FROM "{prod_config.measurement}"
        WHERE time > '{last_sync.strftime('%Y-%m-%dT%H:%M:%SZ')}'
        ORDER BY time ASC
        """

        print("Fetching new data from production...")
        result = prod_client.query(query)

        # Convert to DataFrame
        data = []
        for point in result.get_points():
            data.append(point)

        if not data:
            print("No new data to sync")
            return

        df = pd.DataFrame(data)
        print(f"Found {len(df)} new data points")

        # Write to local InfluxDB
        points = []
        total_written = 0

        for _, row in df.iterrows():
            # Extract fields and tags
            fields = {}
            tags = {}

            for col, value in row.items():
                if col == "time":
                    continue
                elif col.startswith("tag_"):
                    # Handle tags
                    tag_name = col[4:]  # Remove 'tag_' prefix
                    tags[tag_name] = str(value)
                else:
                    # Handle fields
                    if pd.notna(value):
                        if isinstance(value, (int, float)):
                            fields[col] = value
                        else:
                            fields[col] = str(value)

            if fields:  # Only add point if there are fields
                point = {
                    "measurement": local_config.measurement,
                    "fields": fields,
                    "time": row["time"],
                }

                if tags:
                    point["tags"] = tags

                points.append(point)

                # Write in batches
                if len(points) >= batch_size:
                    local_client.write_points(points)
                    total_written += len(points)
                    print(f"Wrote batch of {len(points)} points")
                    points = []

        # Write remaining points
        if points:
            local_client.write_points(points)
            total_written += len(points)
            print(f"Wrote final batch of {len(points)} points")

        # Update sync time
        update_sync_time(sync_file, current_time)

        print(f"Sync complete! Total points written: {total_written}")

    finally:
        prod_client.close()
        local_client.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync new data from production to local InfluxDB"
    )
    parser.add_argument(
        "--prod-config",
        default=None,
        help="Path to production InfluxDB config file (default: production config)",
    )
    parser.add_argument(
        "--local-config",
        default=None,
        help="Path to local InfluxDB config file (default: local config)",
    )
    parser.add_argument(
        "--sync-file",
        default="backups/influxdb/sync_state.json",
        help="File to track sync state (default: backups/influxdb/sync_state.json)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of points to write in each batch (default: 1000)",
    )

    args = parser.parse_args()

    try:
        prod_config_path = args.prod_config or get_production_config_path()
        local_config_path = args.local_config or get_local_config_path()
        prod_config = InfluxDBConfig(prod_config_path)
        local_config = InfluxDBConfig(local_config_path)

        sync_measurement(
            prod_config=prod_config,
            local_config=local_config,
            sync_file=args.sync_file,
            batch_size=args.batch_size,
        )
    except Exception as e:
        print(f"Sync failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
