#!/bin/bash

# Quick fix script to install missing joblib package on Alpine Linux
# Run this as a regular user, not root

echo "=== Quick Fix: Installing joblib on Alpine Linux ==="

# Check if we're running as root
if [ "$EUID" -eq 0 ]; then
    echo "ERROR: Don't run as root! Use a regular user."
    exit 1
fi

# Check if apk is available
if ! command -v apk &> /dev/null; then
    echo "ERROR: apk package manager not found!"
    echo "This script is designed for Alpine Linux"
    exit 1
fi

# Check if build tools are installed
if ! command -v gcc &> /dev/null; then
    echo "Installing build dependencies..."
    sudo apk add --no-cache build-base python3-dev gcc musl-dev
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "ERROR: Virtual environment not found!"
    echo "Please run the full installation script: ./deploy/install_dependencies_alpine.sh"
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Install joblib
echo "Installing joblib..."
pip install joblib==1.4.2

echo "Done! You can now run the optimizer."
