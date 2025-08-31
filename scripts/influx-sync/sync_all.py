#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import List

# Add the project root to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core import create_manager, get_last_sync_time, update_sync_time


def sync_all_measurements(
    measurements: List[str] | None = None,
    batch_size: int = 1000,
    dry_run: bool = False,
) -> None:
    """
    Sync all measurements from production to local InfluxDB

    Args:
        measurements: List of measurements to sync (None = all measurements)
        batch_size: Number of points to write in each batch
        dry_run: If True, only show what would be synced without actually syncing
    """

    print("🔄 InfluxDB Sync - All Measurements")
    print("=" * 50)

    with create_manager() as manager:
        # Get measurements to sync
        if measurements is None:
            print("Getting list of all measurements from production...")
            measurements = manager.get_production_measurements()

            if not measurements:
                print("❌ No measurements found in production!")
                return

        print(f"📊 Found {len(measurements)} measurements to sync:")
        for i, measurement in enumerate(measurements, 1):
            print(f"  {i}. {measurement}")

        # Get last sync time
        last_sync = get_last_sync_time()
        current_time = datetime.now()

        print(f"\n⏰ Sync time range: {last_sync} to {current_time}")

        if dry_run:
            print("\n🔍 DRY RUN MODE - No data will be written")

        # Sync each measurement
        total_synced = 0
        successful_syncs = 0

        for i, measurement in enumerate(measurements, 1):
            print(f"\n[{i}/{len(measurements)}] Processing: {measurement}")

            try:
                if dry_run:
                    # For dry run, just check if there's data to sync
                    start_str = last_sync.strftime("%Y-%m-%dT%H:%M:%SZ")
                    end_str = current_time.strftime("%Y-%m-%dT%H:%M:%SZ")

                    df = manager.fetch_data(
                        manager.prod_client, measurement, start_str, end_str
                    )
                    if not df.empty:
                        print(f"  Would sync {len(df)} points for {measurement}")
                        total_synced += len(df)
                    else:
                        print(f"  No new data for {measurement}")
                else:
                    # Actual sync
                    points_synced = manager.sync_measurement(
                        measurement, last_sync, batch_size
                    )
                    total_synced += points_synced
                    if points_synced > 0:
                        successful_syncs += 1

            except Exception as e:
                print(f"  ❌ Error syncing {measurement}: {e}")
                continue

        # Update sync time if not dry run
        if not dry_run and successful_syncs > 0:
            update_sync_time(current_time)
            print(f"\n✅ Sync complete! Updated sync time to {current_time}")
        elif dry_run:
            print(f"\n🔍 Dry run complete! Would sync {total_synced} total points")
        else:
            print(f"\n⚠️  Sync complete, but no new data was found")

        print(f"📈 Summary:")
        print(f"  - Measurements processed: {len(measurements)}")
        print(f"  - Successful syncs: {successful_syncs}")
        print(f"  - Total points synced: {total_synced}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync all measurements from production to local InfluxDB"
    )
    parser.add_argument(
        "--measurements",
        nargs="+",
        help="Specific measurements to sync (default: all measurements)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of points to write in each batch (default: 1000)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be synced without actually syncing",
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

        sync_all_measurements(
            measurements=args.measurements,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )
    except Exception as e:
        print(f"❌ Sync failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
