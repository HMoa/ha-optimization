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

from optimizer.influxdb_client import InfluxDBConfig


def backup_measurement(
    config: InfluxDBConfig,
    output_dir: str,
    start_time: str | None = None,
    end_time: str | None = None,
    chunk_size_hours: int = 24,
) -> None:
    """
    Backup a measurement from InfluxDB to CSV files

    Args:
        config: InfluxDB configuration
        output_dir: Directory to save backup files
        start_time: Start time for backup (ISO format, defaults to 7 days ago)
        end_time: End time for backup (ISO format, defaults to now)
        chunk_size_hours: Size of time chunks to backup
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
            end_time = datetime.now().isoformat()
        if not start_time:
            start_time = (datetime.now() - timedelta(days=7)).isoformat()

        print(f"Backing up {config.measurement} from {start_time} to {end_time}")
        print(f"Chunk size: {chunk_size_hours} hours")

        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # Calculate time chunks
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        current_start = start_dt
        chunk_number = 0

        while current_start < end_dt:
            current_end = min(current_start + timedelta(hours=chunk_size_hours), end_dt)

            # Build query for this chunk
            query = f"""
            SELECT *
            FROM "{config.measurement}"
            WHERE time >= '{current_start.isoformat()}' AND time < '{current_end.isoformat()}'
            ORDER BY time ASC
            """

            print(
                f"Backing up chunk {chunk_number + 1}: {current_start} to {current_end}"
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
                    filename = f"{config.measurement}_chunk_{chunk_number:04d}_{current_start.strftime('%Y%m%d_%H%M')}_{current_end.strftime('%Y%m%d_%H%M')}.csv"
                    filepath = os.path.join(output_dir, filename)
                    df.to_csv(filepath, index=False)
                    print(f"Saved {len(df)} records to {filename}")
                else:
                    print(f"No data found for chunk {chunk_number + 1}")

            except Exception as e:
                print(f"Error backing up chunk {chunk_number + 1}: {e}")

            current_start = current_end
            chunk_number += 1

        # Create metadata file
        metadata = {
            "measurement": config.measurement,
            "database": config.database,
            "start_time": start_time,
            "end_time": end_time,
            "chunk_size_hours": chunk_size_hours,
            "backup_timestamp": datetime.now().isoformat(),
            "total_chunks": chunk_number,
        }

        metadata_file = os.path.join(output_dir, "backup_metadata.json")
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

        print(f"Backup complete! Metadata saved to {metadata_file}")

    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backup InfluxDB measurement to CSV files"
    )
    parser.add_argument(
        "--config",
        default="config/influxdb_config.json",
        help="Path to InfluxDB config file (default: config/influxdb_config.json)",
    )
    parser.add_argument(
        "--output-dir",
        default="backups/influxdb",
        help="Output directory for backup files (default: backups/influxdb)",
    )
    parser.add_argument(
        "--start-time",
        help="Start time for backup (ISO format, e.g., 2024-01-01T00:00:00Z)",
    )
    parser.add_argument(
        "--end-time",
        help="End time for backup (ISO format, e.g., 2024-01-02T00:00:00Z)",
    )
    parser.add_argument(
        "--chunk-size-hours",
        type=int,
        default=240,
        help="Size of time chunks in hours (default: 24)",
    )

    args = parser.parse_args()

    try:
        config = InfluxDBConfig(args.config)
        backup_measurement(
            config=config,
            output_dir=args.output_dir,
            start_time=args.start_time,
            end_time=args.end_time,
            chunk_size_hours=args.chunk_size_hours,
        )
    except Exception as e:
        print(f"Backup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
