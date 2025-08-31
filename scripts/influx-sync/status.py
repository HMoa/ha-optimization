#!/usr/bin/env python3
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

# Add the project root to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core import create_manager, get_last_sync_time


def show_status() -> None:
    """Show the current status of production and local InfluxDB"""

    print("📊 InfluxDB Status Report")
    print("=" * 50)

    try:
        with create_manager() as manager:
            # Get measurements from both environments
            print("🔍 Getting measurements from production...")
            prod_measurements = manager.get_production_measurements()

            print("🔍 Getting measurements from local...")
            local_measurements = manager.get_local_measurements()

            # Show production status
            print(f"\n🌐 Production InfluxDB:")
            print(f"  URL: {manager.prod_config.url}")
            print(f"  Database: {manager.prod_config.database}")
            print(f"  Measurements: {len(prod_measurements)}")
            for i, measurement in enumerate(prod_measurements, 1):
                print(f"    {i}. {measurement}")

            # Show local status
            print(f"\n🏠 Local InfluxDB:")
            print(f"  URL: {manager.local_config.url}")
            print(f"  Database: {manager.local_config.database}")
            print(f"  Measurements: {len(local_measurements)}")
            for i, measurement in enumerate(local_measurements, 1):
                print(f"    {i}. {measurement}")

            # Show sync status
            last_sync = get_last_sync_time()
            current_time = datetime.now().replace(tzinfo=last_sync.tzinfo)
            print(f"\n🔄 Sync Status:")
            print(f"  Last sync: {last_sync}")
            print(f"  Time since last sync: {current_time - last_sync}")

            # Show differences
            prod_set = set(prod_measurements)
            local_set = set(local_measurements)

            missing_in_local = prod_set - local_set
            extra_in_local = local_set - prod_set

            if missing_in_local:
                print(f"\n⚠️  Missing in local ({len(missing_in_local)}):")
                for measurement in sorted(missing_in_local):
                    print(f"    - {measurement}")

            if extra_in_local:
                print(f"\n➕ Extra in local ({len(extra_in_local)}):")
                for measurement in sorted(extra_in_local):
                    print(f"    - {measurement}")

            if not missing_in_local and not extra_in_local:
                print(f"\n✅ Local and production have the same measurements")

            # Recommendations
            print(f"\n💡 Recommendations:")
            if missing_in_local:
                print(
                    f"  - Run sync to get missing measurements: python scripts/influx-sync/sync_all.py"
                )
            else:
                print(f"  - All measurements are synced")

            print(
                f"  - Check for new data: python scripts/influx-sync/sync_all.py --dry-run"
            )

    except Exception as e:
        print(f"❌ Error getting status: {e}")


if __name__ == "__main__":
    show_status()
