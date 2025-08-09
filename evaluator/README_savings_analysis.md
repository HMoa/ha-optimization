# Savings Analysis Script

This script provides detailed analysis of energy savings patterns by comparing actual energy flows (with battery optimization) against hypothetical scenarios (without battery optimization).

## Features

The script analyzes and visualizes:

1. **Energy Flows Comparison**: Purchased and sold energy per hour, both actual (with battery) and hypothetical (without battery)
2. **Cost/Revenue Analysis**: Detailed breakdown of costs and revenue for each hour
3. **Net Cost Comparison**: Shows the difference between actual and hypothetical net costs
4. **Hourly Savings**: Bar chart showing savings (positive) or losses (negative) for each hour
5. **Battery Activity**: Shows when the battery was charging or discharging
6. **Price Analysis**: Displays buy, sell, and spot prices throughout the day

## Usage

### Basic Usage (analyzes yesterday)
```bash
python -m evaluator.savings_analysis
```

### Analyze a specific date
```bash
python -m evaluator.savings_analysis --date 2024-01-15
```

### Save plots to file instead of displaying
```bash
python -m evaluator.savings_analysis --save-plots
```

### Combine both options
```bash
python -m evaluator.savings_analysis --date 2024-01-15 --save-plots
```

## Output

The script provides:

1. **Console Output**: Detailed summary statistics including:
   - Overall costs and savings
   - Energy flow totals
   - Battery activity summary
   - Hourly breakdown table
   - Best and worst savings hours

2. **Visualizations**: Six comprehensive plots showing:
   - Energy flows comparison
   - Cost/revenue comparison
   - Net cost comparison with savings area
   - Hourly savings bar chart
   - Battery activity timeline
   - Electricity price trends

## Data Sources

The script fetches data from InfluxDB:
- `energy.consumed` and `energy.produced`: Actual energy flows (with battery optimization)
- `power.consumed` and `power.pv`: Raw power data (without battery optimization)
- Electricity prices from the Elpris API

## Key Metrics

- **Actual Net Cost**: Total cost with battery optimization
- **Hypothetical Net Cost**: What the cost would be without battery optimization
- **Total Savings**: Difference between hypothetical and actual costs
- **Savings Percentage**: Savings as a percentage of hypothetical cost

## Example Output

```
============================================================
SAVINGS ANALYSIS SUMMARY - 2024-01-15
============================================================

OVERALL COSTS:
  Actual (with battery):     -12.45 SEK
  Hypothetical (no battery): 8.23 SEK
  Total savings:             20.68 SEK (251.3%)

ENERGY FLOWS:
  Total purchased (with battery):     2450 Wh
  Total sold (with battery):          5670 Wh
  Would purchase (no battery):        8230 Wh
  Would sell (no battery):            1450 Wh

BATTERY ACTIVITY:
  Total battery charging:    3220 Wh
  Total battery discharging: 1000 Wh
```

## Files Generated

When using `--save-plots`, the script creates:
- `savings_analysis_YYYY-MM-DD.png`: Comprehensive visualization of all metrics
