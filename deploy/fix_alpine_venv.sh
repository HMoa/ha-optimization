#!/bin/bash

# Fix script for Alpine Linux virtual environment issues
# This script properly sets up a virtual environment and installs packages

set -e  # Exit on any error

echo "=== Alpine Linux Virtual Environment Fix ==="
echo "This script will properly set up a virtual environment and install packages"
echo ""

# Check if we're running as root
if [ "$EUID" -eq 0 ]; then
    echo "ERROR: This script should not be run as root!"
    echo "Please run as a regular user"
    exit 1
fi

# Check if apk is available
if ! command -v apk &> /dev/null; then
    echo "ERROR: apk package manager not found!"
    echo "This script is designed for Alpine Linux"
    exit 1
fi

echo "Step 1: Installing system dependencies..."
sudo apk update
sudo apk add --no-cache \
    build-base \
    python3-dev \
    py3-pip \
    gcc \
    musl-dev \
    linux-headers

echo ""
echo "Step 2: Removing existing virtual environment (if any)..."
if [ -d ".venv" ]; then
    echo "Removing existing .venv directory..."
    rm -rf .venv
fi

echo ""
echo "Step 3: Creating new virtual environment..."
python3 -m venv .venv

echo ""
echo "Step 4: Activating virtual environment..."
source .venv/bin/activate

# Verify we're in the virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "ERROR: Virtual environment activation failed!"
    exit 1
fi

echo "✓ Virtual environment activated: $VIRTUAL_ENV"

echo ""
echo "Step 5: Verifying Python and pip paths..."
echo "Python: $(which python3)"
echo "Pip: $(which pip)"

# Check if they're from the virtual environment
if [[ "$(which python3)" != *".venv"* ]]; then
    echo "ERROR: Python is not from virtual environment!"
    exit 1
fi

if [[ "$(which pip)" != *".venv"* ]]; then
    echo "ERROR: Pip is not from virtual environment!"
    exit 1
fi

echo "✓ Python and pip are from virtual environment"

echo ""
echo "Step 6: Upgrading pip..."
pip install --upgrade pip

echo ""
echo "Step 7: Installing production requirements..."
pip install -r requirements_production_minimal.txt

echo ""
echo "=== Installation Complete ==="
echo ""
echo "To use the optimizer:"
echo "1. Activate the virtual environment: source .venv/bin/activate"
echo "2. Run the optimizer: python -m optimizer.main [options]"
echo ""
echo "Example:"
echo "  source .venv/bin/activate"
echo "  python -m optimizer.main --fetch-influxdb"
echo ""
echo "Note: Always activate the virtual environment before running the optimizer!"
