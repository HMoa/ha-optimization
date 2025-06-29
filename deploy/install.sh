#!/bin/bash

# Home Energy Optimizer - Raspberry Pi Installation Script
# This script installs the optimizer on a Raspberry Pi

set -e  # Exit on any error

echo "=== Home Energy Optimizer - Raspberry Pi Installation ==="

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "Warning: This script is designed for Raspberry Pi. Continue anyway? (y/N)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 1
    fi
fi

# Update system packages
echo "Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install Python and pip if not already installed
echo "Installing Python dependencies..."
sudo apt-get install -y python3 python3-pip python3-venv

# Install system dependencies for optimization libraries
echo "Installing system dependencies..."
sudo apt-get install -y build-essential python3-dev

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv /opt/ha-optimizer/venv
source /opt/ha-optimizer/venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install the optimizer package
echo "Installing optimizer package..."
pip install -e .

# Create systemd service file
echo "Creating systemd service..."
sudo tee /etc/systemd/system/ha-optimizer.service > /dev/null <<EOF
[Unit]
Description=Home Energy Optimizer
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/ha-optimizer
Environment=PATH=/opt/ha-optimizer/venv/bin
ExecStart=/opt/ha-optimizer/venv/bin/python -m optimizer.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
echo "Enabling and starting service..."
sudo systemctl daemon-reload
sudo systemctl enable ha-optimizer
sudo systemctl start ha-optimizer

echo "=== Installation Complete ==="
echo "Service status:"
sudo systemctl status ha-optimizer --no-pager

echo ""
echo "Useful commands:"
echo "  Check status: sudo systemctl status ha-optimizer"
echo "  View logs: sudo journalctl -u ha-optimizer -f"
echo "  Stop service: sudo systemctl stop ha-optimizer"
echo "  Start service: sudo systemctl start ha-optimizer"
echo "  Restart service: sudo systemctl restart ha-optimizer"
