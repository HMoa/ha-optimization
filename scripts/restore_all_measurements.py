#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, List

import pandas as pd
from influxdb import InfluxDBClient

# Add the project root to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.influxdb_env import get_local_config_path
from optimizer.influxdb_client import InfluxDBConfig


def restore_measurement(
    config: InfluxDBConfig,
    measurement: str,
    backup_dir: str,
    batch_size: int = 1000,
) -> None:
    """
    Restore a single measurement from CSV backup files to InfluxDB

    Args:
        config: InfluxDB configuration
        measurement: Measurement name to restore
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
        # Look for measurement-specific backup directory
        measurement_backup_dir = os.path.join(backup_dir, measurement.replace(".", "_"))

        if not os.path.exists(measurement_backup_dir):
            print(
                f"  No backup directory found for measurement '{measurement}' at {measurement_backup_dir}"
            )
            return

        # Find all CSV files in the measurement backup directory
        csv_files = [
            f for f in os.listdir(measurement_backup_dir) if f.endswith(".csv")
        ]
        csv_files.sort()  # Sort to process in chronological order

        if not csv_files:
            print(f"  No CSV files found for measurement '{measurement}'")
            return

        print(f"  Found {len(csv_files)} CSV files to restore for '{measurement}'")

        total_points = 0
        for i, csv_file in enumerate(csv_files, 1):
            filepath = os.path.join(measurement_backup_dir, csv_file)
            print(f"    Processing file {i}/{len(csv_files)}: {csv_file}")

            try:
                # Read CSV file
                df = pd.read_csv(filepath)

                if df.empty:
                    print(f"      No data in {csv_file}")
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
                            "measurement": measurement,
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
                            print(f"      Wrote batch of {len(points)} points")
                            points = []

                # Write remaining points
                if points:
                    client.write_points(points)
                    total_points += len(points)
                    print(f"      Wrote final batch of {len(points)} points")

            except Exception as e:
                print(f"      Error processing {csv_file}: {e}")
                continue

        print(
            f"  Restore complete for '{measurement}'! Total points written: {total_points}"
        )

    finally:
        client.close()


def restore_all_measurements(
    config: InfluxDBConfig,
    backup_dir: str,
    measurements: List[str] | None = None,
    batch_size: int = 1000,
) -> None:
    """
    Restore multiple measurements from CSV backup files to InfluxDB

    Args:
        config: InfluxDB configuration
        backup_dir: Directory containing backup files
        measurements: List of measurements to restore (None = all available)
        batch_size: Number of points to write in each batch
    """

    # Check if backup directory exists
    if not os.path.exists(backup_dir):
        raise FileNotFoundError(f"Backup directory not found: {backup_dir}")

    # If no measurements specified, find all available
    if measurements is None:
        print("Looking for available measurements in backup directory...")
        measurements = []

        for item in os.listdir(backup_dir):
            item_path = os.path.join(backup_dir, item)
            if os.path.isdir(item_path) and not item.startswith("."):
                # Convert directory name back to measurement name
                measurement_name = item.replace("_", ".")
                measurements.append(measurement_name)

        if not measurements:
            print("No measurement backup directories found!")
            return

    print(f"Restoring {len(measurements)} measurements:")
    for i, measurement in enumerate(measurements, 1):
        print(f"  {i}. {measurement}")

    # Restore each measurement
    for i, measurement in enumerate(measurements, 1):
        print(f"\n[{i}/{len(measurements)}] Restoring measurement: {measurement}")
        try:
            restore_measurement(
                config=config,
                measurement=measurement,
                backup_dir=backup_dir,
                batch_size=batch_size,
            )
        except Exception as e:
            print(f"Failed to restore measurement '{measurement}': {e}")
            continue

    print(f"\n🎉 All measurements restored!")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Restore all InfluxDB measurements from CSV backup files"
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to InfluxDB config file (default: local config)",
    )
    parser.add_argument(
        "--backup-dir",
        default="backups/influxdb",
        help="Directory containing backup files (default: backups/influxdb)",
    )
    parser.add_argument(
        "--measurements",
        nargs="+",
        help="Specific measurements to restore (default: all available measurements)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of points to write in each batch (default: 1000)",
    )
    parser.add_argument(
        "--list-available",
        action="store_true",
        help="List all available measurements in backup directory and exit",
    )

    args = parser.parse_args()

    try:
        config_path = args.config or get_local_config_path()
        config = InfluxDBConfig(config_path)

        if args.list_available:
            print("Available measurements in backup directory:")
            if os.path.exists(args.backup_dir):
                measurements = []
                for item in os.listdir(args.backup_dir):
                    item_path = os.path.join(args.backup_dir, item)
                    if os.path.isdir(item_path) and not item.startswith("."):
                        measurement_name = item.replace("_", ".")
                        measurements.append(measurement_name)

                for i, measurement in enumerate(measurements, 1):
                    print(f"  {i}. {measurement}")
            else:
                print(f"Backup directory not found: {args.backup_dir}")
            return

        restore_all_measurements(
            config=config,
            backup_dir=args.backup_dir,
            measurements=args.measurements,
            batch_size=args.batch_size,
        )
    except Exception as e:
        print(f"Restore failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
