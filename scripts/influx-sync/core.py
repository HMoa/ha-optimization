#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from influxdb import InfluxDBClient

# Add the project root to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.influxdb_env import get_local_config_path, get_production_config_path
from optimizer.influxdb_client import InfluxDBConfig


class InfluxDBManager:
    """Core InfluxDB operations manager for syncing, backup, and restore operations"""

    def __init__(self, prod_config: InfluxDBConfig, local_config: InfluxDBConfig):
        self.prod_config = prod_config
        self.local_config = local_config
        self.prod_client = self._create_client(prod_config)
        self.local_client = self._create_client(local_config)

    def _create_client(self, config: InfluxDBConfig) -> InfluxDBClient:
        """Create an InfluxDB client from config"""
        url_parts = config.url.replace("http://", "").split(":")
        host = url_parts[0]
        port = int(url_parts[1]) if len(url_parts) > 1 else 8086

        return InfluxDBClient(
            host=host,
            port=port,
            username=config.username,
            password=config.password,
            database=config.database,
        )

    def close(self) -> None:
        """Close all client connections"""
        if hasattr(self, "prod_client"):
            self.prod_client.close()
        if hasattr(self, "local_client"):
            self.local_client.close()

    def __enter__(self) -> InfluxDBManager:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def get_measurements(self, client: InfluxDBClient) -> List[str]:
        """Get all measurements from the specified client"""
        try:
            query = "SHOW MEASUREMENTS"
            result = client.query(query)

            measurements = []
            for point in result.get_points():
                measurements.append(point["name"])

            return measurements
        except Exception as e:
            print(f"Error getting measurements: {e}")
            return []

    def get_production_measurements(self) -> List[str]:
        """Get all measurements from production"""
        return self.get_measurements(self.prod_client)

    def get_local_measurements(self) -> List[str]:
        """Get all measurements from local"""
        return self.get_measurements(self.local_client)

    def fetch_data(
        self, client: InfluxDBClient, measurement: str, start_time: str, end_time: str
    ) -> pd.DataFrame:
        """Fetch data for a measurement within a time range"""
        query = f"""
        SELECT *
        FROM "{measurement}"
        WHERE time >= '{start_time}' AND time < '{end_time}'
        ORDER BY time ASC
        """

        try:
            result = client.query(query)

            data = []
            for point in result.get_points():
                data.append(point)

            if data:
                return pd.DataFrame(data)
            else:
                return pd.DataFrame()

        except Exception as e:
            print(f"Error fetching data for {measurement}: {e}")
            return pd.DataFrame()

    def write_data(
        self,
        client: InfluxDBClient,
        measurement: str,
        df: pd.DataFrame,
        batch_size: int = 1000,
    ) -> int:
        """Write data to InfluxDB in batches"""
        if df.empty:
            return 0

        total_written = 0
        points = []

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
                    total_written += len(points)
                    points = []

        # Write remaining points
        if points:
            client.write_points(points)
            total_written += len(points)

        return total_written

    def sync_measurement(
        self, measurement: str, last_sync_time: datetime, batch_size: int = 1000
    ) -> int:
        """Sync new data for a single measurement from production to local"""
        current_time = datetime.now()

        # Format timestamps for InfluxDB
        start_str = last_sync_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = current_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        print(f"  Syncing {measurement}: {start_str} to {end_str}")

        # Fetch new data from production
        df = self.fetch_data(self.prod_client, measurement, start_str, end_str)

        if df.empty:
            print(f"    No new data for {measurement}")
            return 0

        print(f"    Found {len(df)} new data points")

        # Write to local
        total_written = self.write_data(self.local_client, measurement, df, batch_size)

        print(f"    Wrote {total_written} points to local")
        return total_written

    def backup_measurement(
        self,
        measurement: str,
        output_dir: str,
        start_time: str,
        end_time: str,
        chunk_size_hours: int = 720,
    ) -> int:
        """Backup a measurement to CSV files"""
        print(f"  Backing up {measurement}: {start_time} to {end_time}")

        # Create measurement-specific output directory
        measurement_dir = os.path.join(output_dir, measurement.replace(".", "_"))
        os.makedirs(measurement_dir, exist_ok=True)

        # Calculate time chunks
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        current_start = start_dt
        chunk_number = 0
        total_points = 0

        while current_start < end_dt:
            current_end = min(current_start + timedelta(hours=chunk_size_hours), end_dt)

            # Format timestamps
            start_str = current_start.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_str = current_end.strftime("%Y-%m-%dT%H:%M:%SZ")

            print(
                f"    Chunk {chunk_number + 1}: {current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')}"
            )

            # Fetch data
            df = self.fetch_data(self.prod_client, measurement, start_str, end_str)

            if not df.empty:
                # Save to CSV
                filename = f"{measurement.replace('.', '_')}_chunk_{chunk_number:04d}_{current_start.strftime('%Y%m%d')}_{current_end.strftime('%Y%m%d')}.csv"
                filepath = os.path.join(measurement_dir, filename)
                df.to_csv(filepath, index=False)
                print(f"      Saved {len(df)} records to {filename}")
                total_points += len(df)
            else:
                print(f"      No data found for chunk {chunk_number + 1}")

            current_start = current_end
            chunk_number += 1

        # Create metadata
        metadata = {
            "measurement": measurement,
            "database": self.prod_config.database,
            "start_time": start_time,
            "end_time": end_time,
            "chunk_size_hours": chunk_size_hours,
            "backup_timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_chunks": chunk_number,
            "total_points": total_points,
        }

        metadata_file = os.path.join(measurement_dir, "backup_metadata.json")
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

        print(f"    Backup complete: {total_points} total points")
        return total_points

    def restore_measurement(
        self, measurement: str, backup_dir: str, batch_size: int = 1000
    ) -> int:
        """Restore a measurement from CSV backup files"""
        measurement_backup_dir = os.path.join(backup_dir, measurement.replace(".", "_"))

        if not os.path.exists(measurement_backup_dir):
            print(f"  No backup directory found for {measurement}")
            return 0

        # Find all CSV files
        csv_files = [
            f for f in os.listdir(measurement_backup_dir) if f.endswith(".csv")
        ]
        csv_files.sort()

        if not csv_files:
            print(f"  No CSV files found for {measurement}")
            return 0

        print(f"  Restoring {measurement}: {len(csv_files)} files")

        total_points = 0
        for i, csv_file in enumerate(csv_files, 1):
            filepath = os.path.join(measurement_backup_dir, csv_file)
            print(f"    Processing file {i}/{len(csv_files)}: {csv_file}")

            try:
                df = pd.read_csv(filepath)
                if not df.empty:
                    points_written = self.write_data(
                        self.local_client, measurement, df, batch_size
                    )
                    total_points += points_written
                    print(f"      Wrote {points_written} points")
                else:
                    print(f"      No data in {csv_file}")
            except Exception as e:
                print(f"      Error processing {csv_file}: {e}")

        print(f"  Restore complete: {total_points} total points")
        return total_points


def create_manager() -> InfluxDBManager:
    """Create an InfluxDBManager with production and local configs"""
    prod_config = InfluxDBConfig(get_production_config_path())
    local_config = InfluxDBConfig(get_local_config_path())
    return InfluxDBManager(prod_config, local_config)


def get_sync_state_file() -> str:
    """Get the path to the sync state file"""
    return "backups/influxdb/sync_state.json"


def get_last_sync_time() -> datetime:
    """Get the last sync time from the sync state file"""
    sync_file = get_sync_state_file()
    if os.path.exists(sync_file):
        with open(sync_file, "r") as f:
            data = json.load(f)
            # Handle timezone-aware timestamps
            timestamp = data["last_sync_time"]
            if timestamp.endswith("Z"):
                timestamp = timestamp.replace("Z", "+00:00")
            return datetime.fromisoformat(timestamp)
    else:
        # Default to 24 hours ago if no sync file exists
        return datetime.now() - timedelta(hours=24)


def update_sync_time(sync_time: datetime) -> None:
    """Update the sync state file with the latest sync time"""
    sync_file = get_sync_state_file()
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
