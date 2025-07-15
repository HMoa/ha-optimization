#!/bin/bash

# Deployment script for HA Optimizer on Alpine Linux (Home Assistant OS)
# This script should be run as a regular user, not root

set -e  # Exit on any error

echo "=== HA Optimizer Deployment Script for Alpine Linux ==="
echo "This script should be run as a regular user, not root"
echo ""

# Check if we're running as root
if [ "$EUID" -eq 0 ]; then
    echo "ERROR: This script should not be run as root!"
    echo "Please run as a regular user"
    echo "Usage: ./deploy/install_dependencies_alpine.sh"
    exit 1
fi

# Check if apk is available
if ! command -v apk &> /dev/null; then
    echo "ERROR: apk package manager not found!"
    echo "This script is designed for Alpine Linux"
    exit 1
fi

echo "Installing system dependencies with apk..."
echo "Note: This requires sudo privileges for system packages"

# Install build dependencies
sudo apk update
sudo apk add --no-cache \
    build-base \
    python3-dev \
    py3-pip \
    gcc \
    musl-dev \
    linux-headers

echo ""
echo "System dependencies installed successfully!"
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install production requirements (minimal set)
echo "Installing production Python requirements..."
pip install -r requirements_production_minimal.txt

echo ""
echo "=== Installation Complete ==="
echo "To run the optimizer:"
echo "1. Activate the virtual environment: source .venv/bin/activate"
echo "2. Run the optimizer: python -m optimizer.main [options]"
echo ""
echo "Example:"
echo "  source .venv/bin/activate"
echo "  python -m optimizer.main --fetch-influxdb"
echo ""
echo "Note: Plotting functionality is not available with minimal requirements."
echo "If you need plotting, install: pip install matplotlib==3.9.1"
