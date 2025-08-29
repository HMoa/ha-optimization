#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from influxdb import InfluxDBClient

# Add the project root to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from optimizer.influxdb_client import InfluxDBConfig


def restore_measurement(
    config: InfluxDBConfig,
    backup_dir: str,
    batch_size: int = 1000,
) -> None:
    """
    Restore a measurement from CSV backup files to InfluxDB

    Args:
        config: InfluxDB configuration
        backup_dir: Directory containing backup files
        batch_size: Number of points to write in each batch
    """
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
        # Check if backup directory exists
        if not os.path.exists(backup_dir):
            raise FileNotFoundError(f"Backup directory not found: {backup_dir}")

        # Find all CSV files in the backup directory
        csv_files = [f for f in os.listdir(backup_dir) if f.endswith(".csv")]
        csv_files.sort()  # Sort to process in chronological order

        if not csv_files:
            print("No CSV files found in backup directory")
            return

        print(f"Found {len(csv_files)} CSV files to restore")

        total_points = 0
        for i, csv_file in enumerate(csv_files, 1):
            filepath = os.path.join(backup_dir, csv_file)
            print(f"Processing file {i}/{len(csv_files)}: {csv_file}")

            try:
                # Read CSV file
                df = pd.read_csv(filepath)

                if df.empty:
                    print(f"No data in {csv_file}")
                    continue

                # Convert DataFrame to InfluxDB points
                points = []
                for _, row in df.iterrows():
                    # Extract fields (all columns except time and tags)
                    fields = {}
                    tags = {}

                    for col, value in row.items():
                        if col == "time":
                            continue
                        elif col.startswith("tag_"):
                            # Handle tags (columns starting with 'tag_')
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
                            "measurement": config.measurement,
                            "fields": fields,
                            "time": row["time"],
                        }

                        if tags:
                            point["tags"] = tags

                        points.append(point)

                        # Write in batches
                        if len(points) >= batch_size:
                            client.write_points(points)
                            total_points += len(points)
                            print(f"Wrote batch of {len(points)} points")
                            points = []

                # Write remaining points
                if points:
                    client.write_points(points)
                    total_points += len(points)
                    print(f"Wrote final batch of {len(points)} points")

            except Exception as e:
                print(f"Error processing {csv_file}: {e}")
                continue

        print(f"Restore complete! Total points written: {total_points}")

    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Restore InfluxDB measurement from CSV backup files"
    )
    parser.add_argument(
        "--config",
        default="config/influxdb_config_local.json",
        help="Path to InfluxDB config file (default: config/influxdb_config_local.json)",
    )
    parser.add_argument(
        "--backup-dir",
        default="backups/influxdb",
        help="Directory containing backup files (default: backups/influxdb)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of points to write in each batch (default: 1000)",
    )

    args = parser.parse_args()

    try:
        config = InfluxDBConfig(args.config)
        restore_measurement(
            config=config,
            backup_dir=args.backup_dir,
            batch_size=args.batch_size,
        )
    except Exception as e:
        print(f"Restore failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
