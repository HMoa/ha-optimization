#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

# Add the project root to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.influxdb_env import (
    ENV_VAR_NAME,
    InfluxDBEnvironment,
    get_config_path,
    get_current_environment,
    print_environment_info,
)


def main() -> None:
    """Show current InfluxDB environment and provide switching instructions"""

    print("🔧 InfluxDB Environment Manager")
    print("=" * 40)

    # Show current environment
    print_environment_info()

    print("\n📋 Quick Commands:")
    print(f"# Switch to LOCAL environment:")
    print(f"export {ENV_VAR_NAME}={InfluxDBEnvironment.LOCAL.value}")
    print(f"# Switch to PRODUCTION environment:")
    print(f"export {ENV_VAR_NAME}={InfluxDBEnvironment.PRODUCTION.value}")
    print(f"# Reset to default (LOCAL):")
    print(f"unset {ENV_VAR_NAME}")

    print("\n🔍 Test current environment:")
    print("python scripts/test_local_influxdb.py")

    print("\n📊 Available measurements:")
    print("python scripts/list_measurements.py")

    print("\n💾 Backup/Restore commands:")
    print("make backup-all      # Backup from production")
    print("make restore-all     # Restore to local")
    print("make sync           # Sync new data")


if __name__ == "__main__":
    main()
