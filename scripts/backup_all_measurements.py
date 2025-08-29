#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, List

import pandas as pd
from influxdb import InfluxDBClient

# Add the project root to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.influxdb_env import get_production_config_path
from optimizer.influxdb_client import InfluxDBConfig


def get_measurements(config: InfluxDBConfig) -> List[str]:
    """Get all measurements from the InfluxDB database"""

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

        return measurements

    except Exception as e:
        print(f"Error getting measurements: {e}")
        return []
    finally:
        client.close()


def backup_measurement(
    config: InfluxDBConfig,
    measurement: str,
    output_dir: str,
    start_time: str | None = None,
    end_time: str | None = None,
    chunk_size_hours: int = 720,  # 30 days default
) -> None:
    """
    Backup a single measurement from InfluxDB to CSV files

    Args:
        config: InfluxDB configuration
        measurement: Measurement name to backup
        output_dir: Directory to save backup files
        start_time: Start time for backup (ISO format, defaults to July 1st)
        end_time: End time for backup (ISO format, defaults to now)
        chunk_size_hours: Size of time chunks to backup (default: 720 hours = 30 days)
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
        # Set default times if not provided
        if not end_time:
            end_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        if not start_time:
            # Default to July 1st of current year
            current_year = datetime.now().year
            start_time = datetime(current_year, 7, 1).strftime("%Y-%m-%dT%H:%M:%SZ")

        print(f"Backing up measurement '{measurement}' from {start_time} to {end_time}")
        print(f"Chunk size: {chunk_size_hours} hours ({chunk_size_hours // 24} days)")

        # Create measurement-specific output directory
        measurement_dir = os.path.join(output_dir, measurement.replace(".", "_"))
        os.makedirs(measurement_dir, exist_ok=True)

        # Calculate time chunks
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        current_start = start_dt
        chunk_number = 0

        while current_start < end_dt:
            current_end = min(current_start + timedelta(hours=chunk_size_hours), end_dt)

            # Build query for this chunk - use RFC3339 format for InfluxDB 1.8
            start_str = current_start.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_str = current_end.strftime("%Y-%m-%dT%H:%M:%SZ")

            query = f"""
            SELECT *
            FROM "{measurement}"
            WHERE time >= '{start_str}' AND time < '{end_str}'
            ORDER BY time ASC
            """

            print(
                f"  Backing up chunk {chunk_number + 1}: {current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')}"
            )

            try:
                result = client.query(query)

                # Convert to DataFrame
                data = []
                for point in result.get_points():
                    data.append(point)

                if data:
                    df = pd.DataFrame(data)

                    # Save to CSV
                    filename = f"{measurement.replace('.', '_')}_chunk_{chunk_number:04d}_{current_start.strftime('%Y%m%d')}_{current_end.strftime('%Y%m%d')}.csv"
                    filepath = os.path.join(measurement_dir, filename)
                    df.to_csv(filepath, index=False)
                    print(f"    Saved {len(df)} records to {filename}")
                else:
                    print(f"    No data found for chunk {chunk_number + 1}")

            except Exception as e:
                print(f"    Error backing up chunk {chunk_number + 1}: {e}")

            current_start = current_end
            chunk_number += 1

        # Create metadata file for this measurement
        metadata = {
            "measurement": measurement,
            "database": config.database,
            "start_time": start_time,
            "end_time": end_time,
            "chunk_size_hours": chunk_size_hours,
            "backup_timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_chunks": chunk_number,
        }

        metadata_file = os.path.join(measurement_dir, "backup_metadata.json")
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

        print(
            f"  Backup complete for '{measurement}'! Metadata saved to {metadata_file}"
        )

    finally:
        client.close()


def backup_all_measurements(
    config: InfluxDBConfig,
    output_dir: str,
    measurements: List[str] | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    chunk_size_hours: int = 720,  # 30 days default
) -> None:
    """
    Backup multiple measurements from InfluxDB

    Args:
        config: InfluxDB configuration
        output_dir: Base directory to save backup files
        measurements: List of measurements to backup (None = all measurements)
        start_time: Start time for backup (ISO format, defaults to July 1st)
        end_time: End time for backup (ISO format, defaults to now)
        chunk_size_hours: Size of time chunks to backup (default: 720 hours = 30 days)
    """

    # Get all measurements if not specified
    if measurements is None:
        print("Getting list of all measurements...")
        measurements = get_measurements(config)

        if not measurements:
            print("No measurements found!")
            return

    print(f"Backing up {len(measurements)} measurements:")

    # Create base output directory
    os.makedirs(output_dir, exist_ok=True)

    # Backup each measurement
    for i, measurement in enumerate(measurements, 1):
        print(f"\n[{i}/{len(measurements)}] Backing up measurement: {measurement}")
        try:
            backup_measurement(
                config=config,
                measurement=measurement,
                output_dir=output_dir,
                start_time=start_time,
                end_time=end_time,
                chunk_size_hours=chunk_size_hours,
            )
        except Exception as e:
            print(f"Failed to backup measurement '{measurement}': {e}")
            continue

    # Create overall metadata file
    overall_metadata = {
        "database": config.database,
        "start_time": start_time
        or datetime(datetime.now().year, 7, 1).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_time": end_time or datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "chunk_size_hours": chunk_size_hours,
        "backup_timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "measurements": measurements,
        "total_measurements": len(measurements),
    }

    overall_metadata_file = os.path.join(output_dir, "overall_backup_metadata.json")
    with open(overall_metadata_file, "w") as f:
        json.dump(overall_metadata, f, indent=2)

    print(
        f"\n🎉 All backups complete! Overall metadata saved to {overall_metadata_file}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backup all InfluxDB measurements to CSV files"
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to InfluxDB config file (default: production config)",
    )
    parser.add_argument(
        "--output-dir",
        default="backups/influxdb",
        help="Output directory for backup files (default: backups/influxdb)",
    )
    parser.add_argument(
        "--measurements",
        nargs="+",
        help="Specific measurements to backup (default: all measurements)",
    )
    parser.add_argument(
        "--start-time",
        help="Start time for backup (ISO format, e.g., 2024-07-01T00:00:00Z)",
    )
    parser.add_argument(
        "--end-time",
        help="End time for backup (ISO format, e.g., 2024-08-01T00:00:00Z)",
    )
    parser.add_argument(
        "--chunk-size-hours",
        type=int,
        default=720,  # 30 days
        help="Size of time chunks in hours (default: 720 = 30 days)",
    )
    parser.add_argument(
        "--list-measurements",
        action="store_true",
        help="List all available measurements and exit",
    )

    args = parser.parse_args()

    try:
        config_path = args.config or get_production_config_path()
        config = InfluxDBConfig(config_path)

        if args.list_measurements:
            print("Available measurements:")
            measurements = get_measurements(config)
            for i, measurement in enumerate(measurements, 1):
                print(f"  {i}. {measurement}")
            return

        backup_all_measurements(
            config=config,
            output_dir=args.output_dir,
            measurements=args.measurements,
            start_time=args.start_time,
            end_time=args.end_time,
            chunk_size_hours=args.chunk_size_hours,
        )
    except Exception as e:
        print(f"Backup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
