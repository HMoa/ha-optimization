# InfluxDB Integration

This module provides integration with InfluxDB 1.x to fetch real-time consumption data for the battery optimizer.

## Setup

### 1. Install Dependencies

```bash
pip install influxdb==5.3.1
```

### 2. Configure InfluxDB

Edit `config/influxdb_config.json` with your InfluxDB settings:

```json
{
  "url": "http://192.168.XX.XX:8086",
  "username": "your_username_here",
  "password": "your_password_here",
  "database": "homeassistant",
  "measurement": "power.consumed",
  "field": "value",
  "time_window_minutes": 30,
  "aggregation_window_minutes": 5,
  "data_points": 6
}
```

### Configuration Fields

- **url**: InfluxDB server URL (e.g., `http://192.168.XX.XX:8086`)
- **username**: Your InfluxDB username
- **password**: Your InfluxDB password
- **database**: The database containing your consumption data (InfluxDB 1.x uses databases instead of buckets)
- **measurement**: The measurement name (e.g., `power.consumed`)
- **field**: The field name containing consumption values (usually `value`)
- **time_window_minutes**: How far back to fetch data (default: 30 minutes)
- **aggregation_window_minutes**: Aggregation window size (default: 5 minutes)
- **data_points**: Number of data points to return (default: 6)

## Usage

### Command Line

Fetch initial consumption values from InfluxDB:

```bash
python -m optimizer.main --use_influxdb
```

With custom config file:

```bash
python -m optimizer.main --use_influxdb --influxdb_config /path/to/config.json
```

### Programmatic Usage

```python
from optimizer.influxdb_client import get_initial_consumption_values

# Get consumption values from InfluxDB
values = get_initial_consumption_values()

# Use with optimizer
from optimizer.main import generate_schedule
generate_schedule(
    battery_percent=84,
    initial_consumption_values=values
)
```

## InfluxQL Query

The module uses this InfluxQL query to fetch data (InfluxDB 1.x):

```sql
SELECT MEAN(value) as value
FROM "power.consumed"
WHERE time > now() - 30m
GROUP BY time(5m)
ORDER BY time ASC
LIMIT 6
```

## Testing

Test the InfluxDB connection:

```bash
python optimizer/influxdb_client.py
```

## Troubleshooting

### Connection Issues

1. Check your InfluxDB URL, username, and password
2. Verify your database name exists
3. Ensure the measurement exists and contains data

### No Data Returned

1. Check the measurement name matches your data
2. Verify the field name (usually `value`)
3. Ensure data exists in the specified time window
4. Check if aggregation is working (try different functions like `MAX` instead of `MEAN`)

### Permission Issues

1. Verify your username and password have read access to the database
2. Check database permissions

### Version Compatibility

This module is designed for **InfluxDB 1.x**. If you're using InfluxDB 2.x, you'll need to use the `influxdb-client` library instead and modify the configuration to use buckets and organizations.
