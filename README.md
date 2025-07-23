# ha-optimization

A small poc to optimize energy usage using batteries for the swedish market conditions

## Prediction notes

The analytics folder contains code for building an ML model of production and consumption.
This model is later used to predict the day and we use it with the optimizer to make the best decision.

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
- [x] Improve consumption model (Wait for larger training set)
- [ ] Test API for production forecast
  -- <https://openweathermap.org/api/solar-panels-and-energy-prediction>
- [ ] Compare with cloud coverage
- [x] Split up tasks: fetch data & build models, generate schedule, act on schedule, review if we are on track
