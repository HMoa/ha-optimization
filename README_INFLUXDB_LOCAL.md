# Local InfluxDB Setup

This document describes how to set up and manage a local InfluxDB instance for development, with backup and sync capabilities from your production InfluxDB.

## Overview

The setup includes:
- **Local InfluxDB**: Docker container with persistent storage
- **Chronograf**: Web interface for exploring data and running queries
- **Backup System**: Export data from production to CSV files
- **Restore System**: Import backup data to local InfluxDB
- **Sync System**: Periodically fetch new data from production

## Quick Start

### 1. Start Local InfluxDB

```bash
make influxdb-up
```

This will:
- Start InfluxDB 1.8 in a Docker container
- Start Chronograf web interface
- Create the `homeassistant` database
- Create the `optimizer` user with password `tuggummi`
- Wait for the service to be ready

### 2. Full Setup (Backup + Restore)

```bash
# Setup with single measurement (power.consumed)
make setup-local-influxdb

# Setup with all measurements (recommended)
make setup-local-influxdb-all
```

This will:
- Start the local InfluxDB
- Backup data from production (single measurement or all measurements)
- Restore the data to your local instance

## Configuration Files

### Production Configuration
- **File**: `config/influxdb_config.json`
- **Purpose**: Points to your production InfluxDB instance
- **Used by**: Backup and sync scripts

### Local Configuration
- **File**: `config/influxdb_config_local.json`
- **Purpose**: Points to your local InfluxDB instance
- **Used by**: Your application when developing locally

## Available Commands

### Docker Management

```bash
# Start local InfluxDB and Chronograf
make influxdb-up

# Stop local InfluxDB and Chronograf
make influxdb-down

# View InfluxDB logs
make influxdb-logs

# View Chronograf logs
make chronograf-logs

# Access InfluxDB shell
make influxdb-shell
```

### Data Management

```bash
# Backup production data (last 7 days by default)
make backup

# Backup all measurements from production (monthly chunks from July)
make backup-all

# List available measurements in production
make list-measurements

# Restore backup data to local InfluxDB
make restore

# Restore all measurements to local InfluxDB
make restore-all

# List available measurements in backup directory
make list-backup-measurements

# Sync new data from production to local
make sync
```

### Environment Management

```bash
# Show current InfluxDB environment
make show-influxdb-env

# Test current environment
make test-influxdb
```

### Advanced Usage

```bash
# Backup specific time range
python scripts/backup_influxdb.py \
  --start-time "2024-01-01T00:00:00Z" \
  --end-time "2024-01-02T00:00:00Z" \
  --chunk-size-hours 6

# Backup all measurements with custom settings
python scripts/backup_all_measurements.py \
  --start-time "2024-07-01T00:00:00Z" \
  --end-time "2024-08-01T00:00:00Z" \
  --chunk-size-hours 720

# Backup specific measurements only
python scripts/backup_all_measurements.py \
  --measurements "power.consumed" "power.produced" "battery.level"

# Restore with custom batch size
python scripts/restore_influxdb.py --batch-size 500

# Restore all measurements with custom batch size
python scripts/restore_all_measurements.py --batch-size 500

# Sync with custom config files
python scripts/sync_influxdb.py \
  --prod-config config/influxdb_config.json \
  --local-config config/influxdb_config_local.json
```

## File Structure

```
├── docker-compose.yml              # Docker setup for local InfluxDB
├── config/
│   ├── influxdb_config.json        # Production configuration
│   └── influxdb_config_local.json  # Local configuration
├── scripts/
│   ├── init-influxdb.sh            # InfluxDB initialization script
│   ├── backup_influxdb.py          # Backup production data
│   ├── restore_influxdb.py         # Restore data to local
│   └── sync_influxdb.py            # Sync new data
└── backups/
    └── influxdb/                   # Backup files and sync state
```

## Development Workflow

### 1. Initial Setup
```bash
# Start local InfluxDB and populate with production data
make setup-local-influxdb
```

### 2. Daily Development
```bash
# Use local configuration in your code
from optimizer.influxdb_client import InfluxDBConfig
config = InfluxDBConfig("config/influxdb_config_local.json")
```

### 3. Periodic Sync
```bash
# Sync new data from production (run this periodically)
make sync
```

### 4. Manual Backup/Restore
```bash
# When you need fresh data
make backup
make restore
```

## Data Persistence

- **Docker Volume**: `influxdb_data` stores all InfluxDB data
- **Backup Files**: CSV files in `backups/influxdb/`
- **Sync State**: Tracks last sync time in `backups/influxdb/sync_state.json`

## Web Interface

### Chronograf
The Chronograf web interface provides a user-friendly way to explore your InfluxDB data:

- **URL**: http://localhost:8888
- **Features**:
  - Interactive query builder
  - Data visualization
  - Dashboard creation
  - Database management
  - User management

### InfluxDB API
The InfluxDB API is available at:
- **URL**: http://localhost:8086
- **Use**: For programmatic access and direct queries

## Troubleshooting

### InfluxDB Won't Start
```bash
# Check if port 8086 is available
lsof -i :8086

# View Docker logs
make influxdb-logs
```

### Chronograf Won't Start
```bash
# Check if port 8888 is available
lsof -i :8888

# View Chronograf logs
make chronograf-logs
```

### Connection Issues
```bash
# Test InfluxDB connection
curl http://localhost:8086/ping

# Test with credentials
curl -u optimizer:tuggummi http://localhost:8086/query?q=SHOW+DATABASES

# Test Chronograf
curl http://localhost:8888
```

### Backup/Restore Issues
```bash
# Check backup files
ls -la backups/influxdb/

# Verify sync state
cat backups/influxdb/sync_state.json
```

## Security Notes

- Local InfluxDB uses default credentials for development
- Production credentials are stored in `config/influxdb_config.json`
- Backup files may contain sensitive data - keep them secure
- Consider adding `backups/` to `.gitignore` if not already there

## Performance Tips

- Use appropriate chunk sizes for large backups (default: 24 hours)
- Adjust batch sizes for restore operations (default: 1000 points)
- Monitor disk space for backup files
- Consider periodic cleanup of old backup files

## Environment Management

### Centralized Configuration System

The project now uses a centralized configuration system that makes it easy to switch between local and production environments.

#### Show Current Environment
```bash
make show-influxdb-env
# or
python scripts/show_influxdb_env.py
```

#### Switch Environments

**Method 1: Environment Variable (Recommended)**
```bash
# Switch to LOCAL environment
export INFLUXDB_ENV=local

# Switch to PRODUCTION environment
export INFLUXDB_ENV=production

# Reset to default (LOCAL)
unset INFLUXDB_ENV
```

**Method 2: Edit Configuration File**
Edit `config/influxdb_env.py` and change:
```python
CURRENT_ENVIRONMENT: Final[InfluxDBEnvironment] = InfluxDBEnvironment.LOCAL
```
to:
```python
CURRENT_ENVIRONMENT: Final[InfluxDBEnvironment] = InfluxDBEnvironment.PRODUCTION
```

#### Integration with Your Application

The configuration system is now automatic - just use the default constructor:

```python
from optimizer.influxdb_client import InfluxDBConfig

# Automatically uses current environment
config = InfluxDBConfig()

# Or specify a custom config file
config = InfluxDBConfig("path/to/custom/config.json")
```

#### Environment-Aware Scripts

All scripts now automatically use the correct environment:
- **Backup scripts**: Use production config by default
- **Restore scripts**: Use local config by default
- **Test scripts**: Use current environment
- **Sync scripts**: Use both production and local configs
