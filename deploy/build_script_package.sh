#!/bin/bash

# Build script for creating a simple script package
# This creates a tarball with just the code and dependencies

set -e

PACKAGE_NAME="ha-optimizer-scripts"
VERSION="1.0.0"
BUILD_DIR="build"
PACKAGE_DIR="${BUILD_DIR}/${PACKAGE_NAME}-${VERSION}"

echo "=== Building Home Energy Optimizer Script Package ==="

# Clean previous builds
rm -rf ${BUILD_DIR}
mkdir -p ${PACKAGE_DIR}

# Copy source code
echo "Copying source code..."
cp -r optimizer ${PACKAGE_DIR}/
cp -r analytics ${PACKAGE_DIR}/
cp -r tests ${PACKAGE_DIR}/
cp -r sample_data ${PACKAGE_DIR}/

# Copy configuration files
cp requirements.txt ${PACKAGE_DIR}/
cp README.md ${PACKAGE_DIR}/

# Create a simple run script
cat > ${PACKAGE_DIR}/run_optimizer.py << 'EOF'
#!/usr/bin/env python3
"""
Simple runner script for the Home Energy Optimizer
Usage: python run_optimizer.py [options]
"""

import sys
import os
import argparse

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    parser = argparse.ArgumentParser(description='Home Energy Optimizer')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--config', type=str, help='Path to config file')
    parser.add_argument('--output', type=str, help='Output directory for results')

    args = parser.parse_args()

    # Set debug mode if requested
    if args.debug:
        os.environ['DEBUG'] = '1'

    # Import and run the optimizer
    try:
        from optimizer.main import main as optimizer_main
        optimizer_main()
    except ImportError as e:
        print(f"Error importing optimizer: {e}")
        print("Make sure all dependencies are installed:")
        print("pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"Error running optimizer: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
EOF

# Create a requirements file optimized for Raspberry Pi
cat > ${PACKAGE_DIR}/requirements-pi.txt << 'EOF'
# Optimized requirements for Raspberry Pi
# Pinned to versions known to work well on ARM
numpy==1.24.3
pandas==2.0.3
ortools==9.7.2996
requests==2.31.0
python-dateutil==2.8.2
pytz==2023.3
joblib==1.3.2
scikit-learn==1.3.0
EOF

# Create a simple installation script
cat > ${PACKAGE_DIR}/install_deps.sh << 'EOF'
#!/bin/bash

# Simple dependency installation script
echo "Installing Python dependencies..."

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
fi

# Upgrade pip
pip install --upgrade pip

# Install dependencies
echo "Installing packages..."
pip install -r requirements-pi.txt

echo "Dependencies installed successfully!"
echo "To run the optimizer:"
echo "  source venv/bin/activate  # if not already activated"
echo "  python run_optimizer.py"
EOF

chmod +x ${PACKAGE_DIR}/install_deps.sh

# Create a quick start guide
cat > ${PACKAGE_DIR}/QUICKSTART.md << 'EOF'
# Quick Start Guide

## Installation

1. **Install dependencies:**
   ```bash
   chmod +x install_deps.sh
   ./install_deps.sh
   ```

2. **Activate virtual environment (if not already active):**
   ```bash
   source venv/bin/activate
   ```

## Running the Optimizer

### Basic Usage
```bash
python run_optimizer.py
```

### With Options
```bash
# Debug mode
python run_optimizer.py --debug

# Specify output directory
python run_optimizer.py --output /path/to/results

# Specify config file
python run_optimizer.py --config my_config.json
```

### Direct Module Execution
```bash
python -m optimizer.main
```

## Configuration

1. **Battery settings:** Edit `optimizer/battery_config.py`
2. **API settings:** Edit `optimizer/elpris_api.py`
3. **Data sources:** Configure in respective provider files

## File Structure

```
ha-optimizer-scripts-1.0.0/
├── optimizer/           # Main optimizer code
├── analytics/          # Analysis scripts
├── sample_data/        # Sample data files
├── tests/              # Test files
├── run_optimizer.py    # Main runner script
├── install_deps.sh     # Dependency installer
├── requirements-pi.txt # Optimized requirements
└── QUICKSTART.md       # This file
```

## Troubleshooting

- **Import errors:** Make sure virtual environment is activated
- **Missing dependencies:** Run `./install_deps.sh`
- **Permission errors:** Check file permissions with `ls -la`
- **Memory issues:** Consider using 5-minute data intervals instead of 1-minute
EOF

# Create the tarball
echo "Creating package tarball..."
cd ${BUILD_DIR}
tar -czf ${PACKAGE_NAME}-${VERSION}.tar.gz ${PACKAGE_NAME}-${VERSION}/

echo "=== Package Created Successfully ==="
echo "Package: ${BUILD_DIR}/${PACKAGE_NAME}-${VERSION}.tar.gz"
echo "Size: $(du -h ${PACKAGE_NAME}-${VERSION}.tar.gz | cut -f1)"
echo ""
echo "To deploy on Raspberry Pi:"
echo "1. Copy the tarball to your Raspberry Pi"
echo "2. Extract: tar -xzf ${PACKAGE_NAME}-${VERSION}.tar.gz"
echo "3. Install dependencies: cd ${PACKAGE_NAME}-${VERSION} && ./install_deps.sh"
echo "4. Run: python run_optimizer.py"
