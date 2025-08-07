# Battery Configuration

This file contains the configuration for the battery optimization system.

## Configuration Options

### `grid_area`
- **Type**: String
- **Description**: The electricity grid area code (e.g., "SE3" for Stockholm)
- **Default**: "SE3"

### `storage_size_wh`
- **Type**: Integer
- **Description**: Total battery storage capacity in Watt-hours
- **Default**: 44000 (44 kWh)

### `initial_energy`
- **Type**: Float
- **Description**: Initial battery energy level in Watt-hours
- **Default**: 1000.0 (1 kWh)

### `max_charge_speed_w`
- **Type**: Integer
- **Description**: Maximum charging power in Watts
- **Default**: 8000 (8 kW)

### `max_discharge_speed_w`
- **Type**: Integer
- **Description**: Maximum discharging power in Watts
- **Default**: 9000 (9 kW)

## Example Configuration

```json
{
  "grid_area": "SE3",
  "storage_size_wh": 44000,
  "initial_energy": 1000.0,
  "max_charge_speed_w": 8000,
  "max_discharge_speed_w": 9000
}
```

## Notes

- The system will fall back to default values if the configuration file cannot be loaded
- All power values are in Watts (W) or Watt-hours (Wh)
- Grid area codes follow the Swedish electricity market standard
