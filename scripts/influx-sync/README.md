# InfluxDB Sync System

A modular, cohesive system for syncing, backing up, and restoring InfluxDB data between production and local environments.

## Overview

This system provides a unified approach to managing InfluxDB data across environments with:
- **No redundancy**: Shared core operations
- **All measurements**: Handles all measurements automatically
- **Efficient syncing**: Only transfers new data
- **Modular design**: Easy to extend and maintain

## Architecture

```
scripts/influx-sync/
├── core.py           # Core InfluxDB operations manager
├── sync_all.py       # Sync all measurements from prod to local
├── backup_all.py     # Backup all measurements to CSV files
├── restore_all.py    # Restore all measurements from CSV files
├── status.py         # Show status of both environments
└── README.md         # This file
```

## Core Components

### `core.py` - InfluxDBManager
The central class that handles all InfluxDB operations:
- **Connection management**: Automatic client creation and cleanup
- **Data fetching**: Efficient queries with proper timestamp handling
- **Data writing**: Batch processing for optimal performance
- **Measurement discovery**: Automatic detection of available measurements

### Key Features
- **Context manager**: Automatic connection cleanup with `with` statements
- **Error handling**: Robust error handling with detailed logging
- **Batch processing**: Configurable batch sizes for optimal performance
- **Timezone handling**: Proper RFC3339 timestamp formatting

## Available Commands

### Sync Operations
```bash
# Sync all measurements from production to local
make sync

# Check what would be synced (dry run)
make sync-dry-run

# Check sync status
make sync-status

# Sync specific measurements
python scripts/influx-sync/sync_all.py --measurements "power.consumed" "battery.charge"
```

### Backup Operations
```bash
# Backup all measurements from production
make backup-all

# List available measurements in production
make list-measurements

# Backup specific measurements
python scripts/influx-sync/backup_all.py --measurements "power.consumed" "battery.charge"

# Backup with custom time range
python scripts/influx-sync/backup_all.py --start-time "2024-07-01T00:00:00Z" --end-time "2024-08-01T00:00:00Z"
```

### Restore Operations
```bash
# Restore all measurements to local
make restore-all

# List available measurements in backup
make list-backup-measurements

# Restore specific measurements
python scripts/influx-sync/restore_all.py --measurements "power.consumed" "battery.charge"
```

## Usage Examples

### Daily Development Workflow
```bash
# 1. Check current status
make sync-status

# 2. See if there's new data to sync
make sync-dry-run

# 3. Sync new data if available
make sync

# 4. Verify everything is up to date
make sync-status
```

### Initial Setup
```bash
# 1. Start local InfluxDB
make influxdb-up

# 2. Backup all production data
make backup-all

# 3. Restore to local
make restore-all

# 4. Verify setup
make sync-status
```

### Advanced Usage
```bash
# Custom batch sizes for large datasets
python scripts/influx-sync/sync_all.py --batch-size 500

# Backup with smaller chunks for large time ranges
python scripts/influx-sync/backup_all.py --chunk-size-hours 168  # 1 week chunks

# Restore with custom batch size
python scripts/influx-sync/restore_all.py --batch-size 2000
```

## Configuration

The system automatically uses the centralized configuration from `config/influxdb_env.py`:
- **Production config**: Used for reading data
- **Local config**: Used for writing data
- **Environment switching**: Use `INFLUXDB_ENV` environment variable

## File Structure

### Backup Files
```
backups/influxdb/
├── power_consumed/
│   ├── power_consumed_chunk_0000_20240701_20240731.csv
│   ├── power_consumed_chunk_0001_20240731_20240829.csv
│   └── backup_metadata.json
├── battery_charge/
│   └── ...
└── overall_backup_metadata.json
```

### Sync State
```
backups/influxdb/sync_state.json
```

## Error Handling

The system includes robust error handling:
- **Connection failures**: Automatic retry with detailed error messages
- **Data validation**: Checks for empty datasets and invalid timestamps
- **Partial failures**: Continues processing other measurements if one fails
- **Detailed logging**: Clear progress reporting and error messages

## Performance

- **Batch processing**: Configurable batch sizes (default: 1000 points)
- **Efficient queries**: Only fetches new data since last sync
- **Memory management**: Processes data in chunks to avoid memory issues
- **Connection pooling**: Reuses connections within operations

## Troubleshooting

### Common Issues

1. **Connection errors**: Check that both production and local InfluxDB are running
2. **No data synced**: Use `--dry-run` to see what would be synced
3. **Timezone issues**: All timestamps are handled in UTC/RFC3339 format
4. **Permission errors**: Ensure proper access to backup directories

### Debug Commands
```bash
# Check environment configuration
make show-influxdb-env

# Test local connection
make test-influxdb

# Check sync status
make sync-status

# Dry run to see what would happen
make sync-dry-run
```
