#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List

# Add the project root to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core import create_manager


def backup_all_measurements(
    output_dir: str,
    measurements: List[str] | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    chunk_size_hours: int = 720,
) -> None:
    """
    Backup all measurements from production InfluxDB

    Args:
        output_dir: Directory to save backup files
        measurements: List of measurements to backup (None = all measurements)
        start_time: Start time for backup (ISO format, defaults to July 1st)
        end_time: End time for backup (ISO format, defaults to now)
        chunk_size_hours: Size of time chunks to backup (default: 720 hours = 30 days)
    """

    print("💾 InfluxDB Backup - All Measurements")
    print("=" * 50)

    # Set default times if not provided
    if not end_time:
        end_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    if not start_time:
        # Default to July 1st of current year
        current_year = datetime.now().year
        start_time = datetime(current_year, 7, 1).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"⏰ Backup time range: {start_time} to {end_time}")
    print(f"📦 Chunk size: {chunk_size_hours} hours ({chunk_size_hours // 24} days)")

    with create_manager() as manager:
        # Get measurements to backup
        if measurements is None:
            print("\n📊 Getting list of all measurements from production...")
            measurements = manager.get_production_measurements()

            if not measurements:
                print("❌ No measurements found in production!")
                return

        print(f"\n📋 Found {len(measurements)} measurements to backup:")
        for i, measurement in enumerate(measurements, 1):
            print(f"  {i}. {measurement}")

        # Create base output directory
        os.makedirs(output_dir, exist_ok=True)

        # Backup each measurement
        total_points = 0
        successful_backups = 0

        for i, measurement in enumerate(measurements, 1):
            print(f"\n[{i}/{len(measurements)}] Backing up: {measurement}")

            try:
                points_backed_up = manager.backup_measurement(
                    measurement=measurement,
                    output_dir=output_dir,
                    start_time=start_time,
                    end_time=end_time,
                    chunk_size_hours=chunk_size_hours,
                )
                total_points += points_backed_up
                if points_backed_up > 0:
                    successful_backups += 1

            except Exception as e:
                print(f"  ❌ Error backing up {measurement}: {e}")
                continue

        # Create overall metadata file
        overall_metadata = {
            "database": manager.prod_config.database,
            "start_time": start_time,
            "end_time": end_time,
            "chunk_size_hours": chunk_size_hours,
            "backup_timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "measurements": measurements,
            "total_measurements": len(measurements),
            "successful_backups": successful_backups,
            "total_points": total_points,
        }

        overall_metadata_file = os.path.join(output_dir, "overall_backup_metadata.json")
        with open(overall_metadata_file, "w") as f:
            json.dump(overall_metadata, f, indent=2)

        print(f"\n🎉 Backup complete!")
        print(f"📈 Summary:")
        print(f"  - Measurements processed: {len(measurements)}")
        print(f"  - Successful backups: {successful_backups}")
        print(f"  - Total points backed up: {total_points}")
        print(f"  - Overall metadata saved to: {overall_metadata_file}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backup all measurements from production InfluxDB"
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
        if args.list_measurements:
            with create_manager() as manager:
                measurements = manager.get_production_measurements()
                print("Available measurements in production:")
                for i, measurement in enumerate(measurements, 1):
                    print(f"  {i}. {measurement}")
            return

        backup_all_measurements(
            output_dir=args.output_dir,
            measurements=args.measurements,
            start_time=args.start_time,
            end_time=args.end_time,
            chunk_size_hours=args.chunk_size_hours,
        )
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
