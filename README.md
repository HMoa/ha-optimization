# ha-optimization

A small poc to optimize energy usage using batteries for the swedish market conditions

## Development Setup

This project uses strict typing with mypy. To set up the development environment:

```bash
# Install the package with development dependencies
make install-dev

# Run type checking
make type-check

# Run linting
make lint

# Format code
make format

# Run all checks
make check-all
```

### Type Checking

The project uses mypy with strict settings as defined in `pyproject.toml`. All Python files should:

- Include `from __future__ import annotations` at the top
- Have complete type annotations for all functions and class attributes
- Follow the typing guidelines defined in the cursor rules

### Code Quality Tools

- **mypy**: Static type checking with strict settings
- **ruff**: Fast Python linter
- **black**: Code formatter
- **isort**: Import sorting
- **pytest**: Testing framework

This takes some inspiration from:

- <https://medium.com/@yeap0022/basic-build-optimization-model-to-schedule-batterys-operation-in-power-grid-systems-51a8c04b3a0e>
- <https://github.com/davidusb-geek/emhass>

## Todo

- [x] Cloud coverage in model (failed, it sucked)
- [x] Make prediction model
- [x] Create better mocks for production / consumption
- [ ] Improve consumption model (Wait for larger training set)
- [ ] Test API for production forecast
  -- <https://openweathermap.org/api/solar-panels-and-energy-prediction>
- [ ] Compare with cloud coverage
- [ ] Split up tasks: fetch data & build models, generate schedule, act on schedule, review if we are on track

## Operational stuff

- [ ] Node-red: Create code to set the battery mode
- [ ] Node-red: Fetch current schedule item mode
- [ ] Test with a running home assistant - docker on machine?
- [ ] Test run on a Rpi (check speed of solver)

## Prediction notes

Seems the training set is too small yet to support more features.

Features:

- [ ] Temperature, Windspeed, humidity (square temp feature?)
- [ ] Night time
- [x] Cyclic time
- [ ] Previous values, 1h, 24h 7d and roling averages + std

```text
=== DAILY CONSUMPTION ANALYSIS ===
Number of days: 14
Average daily consumption: 15123.47 Wh (15.12 kWh)
Median daily consumption: 14870.95 Wh (14.87 kWh)
Standard deviation: 5157.72 Wh (5.16 kWh)
Min daily consumption: 6604.55 Wh (6.60 kWh)
Max daily consumption: 22844.59 Wh (22.84 kWh)
Coefficient of variation: 0.341 (34.1%)

Daily consumption values (Wh):
2025-06-07: 6604.55 Wh (6.60 kWh)
2025-06-08: 12538.34 Wh (12.54 kWh)
2025-06-09: 17358.74 Wh (17.36 kWh)
2025-06-10: 19127.99 Wh (19.13 kWh)
2025-06-11: 22426.26 Wh (22.43 kWh)
2025-06-12: 12520.32 Wh (12.52 kWh)
2025-06-13: 8214.26 Wh (8.21 kWh)
2025-06-14: 13845.14 Wh (13.85 kWh)
2025-06-15: 12400.15 Wh (12.40 kWh)
2025-06-16: 15896.77 Wh (15.90 kWh)
2025-06-17: 22844.59 Wh (22.84 kWh)
2025-06-18: 9586.83 Wh (9.59 kWh)
2025-06-19: 20736.05 Wh (20.74 kWh)
2025-06-20: 17628.58 Wh (17.63 kWh)

Additional insights:
Total consumption period: 211728.57 Wh (211.73 kWh)
Average hourly consumption: 630.14 Wh

Average consumption by day of week:
Friday: 25842.84 Wh (25.84 kWh)
Monday: 33255.51 Wh (33.26 kWh)
Saturday: 20449.69 Wh (20.45 kWh)
Sunday: 24938.49 Wh (24.94 kWh)
Thursday: 33256.37 Wh (33.26 kWh)
Tuesday: 41972.59 Wh (41.97 kWh)
Wednesday: 32013.09 Wh (32.01 kWh)
```
