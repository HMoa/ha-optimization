# Requirements Files for HA Optimizer

This project includes multiple requirements files for different use cases:

## Requirements Files Overview

### `requirements.txt` (Full Development)
- **Purpose**: Complete development environment with all dependencies
- **Includes**: All packages for development, testing, analysis, and production
- **Use when**: Developing, running analytics, training models, or testing
- **Size**: ~25 packages

### `requirements_production.txt` (Production with Plotting)
- **Purpose**: Production deployment with optional plotting functionality
- **Includes**: Core production packages + matplotlib for plotting
- **Use when**: Production deployment where you might need to generate plots
- **Size**: ~7 packages

### `requirements_production_minimal.txt` (Minimal Production)
- **Purpose**: Minimal production deployment without plotting
- **Includes**: Only essential packages for core functionality
- **Use when**: Production deployment on resource-constrained systems (like Raspberry Pi)
- **Size**: ~6 packages

## Package Breakdown

| Package | Development | Production | Minimal | Purpose |
|---------|-------------|------------|---------|---------|
| `joblib` | ✓ | ✓ | ✓ | Load ML models |
| `numpy` | ✓ | ✓ | ✓ | Numerical operations |
| `pandas` | ✓ | ✓ | ✓ | Data manipulation |
| `requests` | ✓ | ✓ | ✓ | HTTP API calls |
| `influxdb` | ✓ | ✓ | ✓ | InfluxDB client |
| `ortools` | ✓ | ✓ | ✓ | Linear optimization |
| `matplotlib` | ✓ | ✓ | ✗ | Plotting (optional) |
| `scikit-learn` | ✓ | ✗ | ✗ | ML model training |
| `seaborn` | ✓ | ✗ | ✗ | Advanced plotting |
| `mypy` | ✓ | ✗ | ✗ | Type checking |
| `absl-py` | ✓ | ✗ | ✗ | Google OR-Tools dependency |
| `protobuf` | ✓ | ✗ | ✗ | Google OR-Tools dependency |
| `certifi` | ✓ | ✗ | ✗ | SSL certificates |
| `charset-normalizer` | ✓ | ✗ | ✗ | Character encoding |
| `idna` | ✓ | ✗ | ✗ | Internationalized domain names |
| `immutabledict` | ✓ | ✗ | ✗ | Immutable dictionaries |
| `mypy-extensions` | ✓ | ✗ | ✗ | MyPy extensions |
| `ortools-stubs` | ✓ | ✗ | ✗ | OR-Tools type stubs |
| `python-dateutil` | ✓ | ✗ | ✗ | Date utilities |
| `pytz` | ✓ | ✗ | ✗ | Timezone support |
| `six` | ✓ | ✗ | ✗ | Python 2/3 compatibility |
| `types-requests` | ✓ | ✗ | ✗ | Requests type stubs |
| `typing_extensions` | ✓ | ✗ | ✗ | Typing extensions |
| `tzdata` | ✓ | ✗ | ✗ | Timezone data |
| `urllib3` | ✓ | ✗ | ✗ | HTTP library |

## Installation Commands

### For Development
```bash
pip install -r requirements.txt
```

### For Production (with plotting)
```bash
pip install -r requirements_production.txt
```

### For Minimal Production (recommended for Raspberry Pi)
```bash
pip install -r requirements_production_minimal.txt
```

## Alpine Linux (Home Assistant OS) Deployment

For Home Assistant OS on Raspberry Pi, use the minimal requirements:

```bash
# Install system dependencies
sudo apk add --no-cache build-base python3-dev gcc musl-dev

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install minimal production requirements
pip install -r requirements_production_minimal.txt
```

## Adding Plotting Later

If you need plotting functionality after installing minimal requirements:

```bash
source .venv/bin/activate
pip install matplotlib==3.9.1
```

## Benefits of Minimal Requirements

1. **Faster Installation**: Fewer packages to download and install
2. **Smaller Footprint**: Less disk space usage
3. **Fewer Dependencies**: Reduced risk of conflicts
4. **Faster Startup**: Less code to load
5. **Better for Embedded**: Ideal for resource-constrained systems

## Production Deployment Recommendations

- **Home Assistant OS**: Use `requirements_production_minimal.txt`
- **Docker Containers**: Use `requirements_production_minimal.txt`
- **Cloud Deployment**: Use `requirements_production.txt` if plotting is needed
- **Development**: Use `requirements.txt` for full functionality
