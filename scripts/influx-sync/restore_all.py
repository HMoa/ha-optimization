#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List

# Add the project root to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core import create_manager


def restore_all_measurements(
    backup_dir: str,
    measurements: List[str] | None = None,
    batch_size: int = 1000,
) -> None:
    """
    Restore all measurements from backup files to local InfluxDB

    Args:
        backup_dir: Directory containing backup files
        measurements: List of measurements to restore (None = all available)
        batch_size: Number of points to write in each batch
    """

    print("🔄 InfluxDB Restore - All Measurements")
    print("=" * 50)

    # Check if backup directory exists
    if not os.path.exists(backup_dir):
        print(f"❌ Backup directory not found: {backup_dir}")
        return

    with create_manager() as manager:
        # Get measurements to restore
        if measurements is None:
            print("📊 Looking for available measurements in backup directory...")
            measurements = []

            for item in os.listdir(backup_dir):
                item_path = os.path.join(backup_dir, item)
                if os.path.isdir(item_path) and not item.startswith("."):
                    # Convert directory name back to measurement name
                    measurement_name = item.replace("_", ".")
                    measurements.append(measurement_name)

            if not measurements:
                print("❌ No measurement backup directories found!")
                return

        print(f"\n📋 Found {len(measurements)} measurements to restore:")
        for i, measurement in enumerate(measurements, 1):
            print(f"  {i}. {measurement}")

        # Restore each measurement
        total_points = 0
        successful_restores = 0

        for i, measurement in enumerate(measurements, 1):
            print(f"\n[{i}/{len(measurements)}] Restoring: {measurement}")

            try:
                points_restored = manager.restore_measurement(
                    measurement=measurement,
                    backup_dir=backup_dir,
                    batch_size=batch_size,
                )
                total_points += points_restored
                if points_restored > 0:
                    successful_restores += 1

            except Exception as e:
                print(f"  ❌ Error restoring {measurement}: {e}")
                continue

        print(f"\n🎉 Restore complete!")
        print(f"📈 Summary:")
        print(f"  - Measurements processed: {len(measurements)}")
        print(f"  - Successful restores: {successful_restores}")
        print(f"  - Total points restored: {total_points}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Restore all measurements from backup files to local InfluxDB"
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
            backup_dir=args.backup_dir,
            measurements=args.measurements,
            batch_size=args.batch_size,
        )
    except Exception as e:
        print(f"❌ Restore failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
