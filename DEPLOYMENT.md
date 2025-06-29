# Deployment Guide for Raspberry Pi

This guide covers multiple deployment options for your Home Energy Optimizer on Raspberry Pi.

## Option 1: Automated Package Deployment (Recommended)

### Build the Package
```bash
# Build a self-contained package
./deploy/build_package.sh
```

This creates `build/ha-optimizer-pi-1.0.0.tar.gz` with everything needed.

### Deploy on Raspberry Pi
```bash
# Copy to Raspberry Pi (replace with your Pi's IP)
scp build/ha-optimizer-pi-1.0.0.tar.gz pi@raspberrypi.local:~/

# SSH into Raspberry Pi
ssh pi@raspberrypi.local

# Extract and install
tar -xzf ha-optimizer-pi-1.0.0.tar.gz
cd ha-optimizer-pi-1.0.0
sudo ./deploy/install.sh
```

## Option 2: Manual Installation

### System Setup
```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Python and dependencies
sudo apt-get install -y python3 python3-pip python3-venv build-essential python3-dev

# Create virtual environment
python3 -m venv /opt/ha-optimizer/venv
source /opt/ha-optimizer/venv/bin/activate

# Install Python packages
pip install -r requirements.txt
```

## Configuration

### Battery Configuration
Edit `optimizer/battery_config.py`:
```python
BATTERY_CAPACITY = 10000  # Wh
MAX_POWER = 5000  # W
MIN_SOC = 0.1  # 10%
MAX_SOC = 0.9  # 90%
```

### API Configuration
Update `optimizer/elpris_api.py` with your API endpoints and credentials.

### Data Sources
Configure your consumption and production data sources in the respective provider files.

## Monitoring and Logs

### Service Status
```bash
sudo systemctl status ha-optimizer
```

### View Logs
```bash
# Real-time logs
sudo journalctl -u ha-optimizer -f

# Recent logs
sudo journalctl -u ha-optimizer --since "1 hour ago"
```

## Troubleshooting

### Common Issues

1. **Permission Denied**
   ```bash
   sudo chown -R pi:pi /opt/ha-optimizer
   ```

2. **Python Import Errors**
   ```bash
   # Reinstall in virtual environment
   source /opt/ha-optimizer/venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Memory Issues on Pi**
   ```bash
   # Add swap space
   sudo dphys-swapfile swapoff
   sudo nano /etc/dphys-swapfile
   # Set CONF_SWAPSIZE=1024
   sudo dphys-swapfile setup
   sudo dphys-swapfile swapon
   ```

### Performance Optimization

1. **Use SSD instead of SD card** for better I/O performance
2. **Increase swap space** for memory-intensive operations
3. **Use 5-minute data intervals** instead of 1-minute for reduced computational load
4. **Enable GPU acceleration** if available (Pi 4)

## Security Considerations

1. **Change default passwords** on Raspberry Pi
2. **Use SSH keys** instead of password authentication
3. **Configure firewall** to only allow necessary ports
4. **Keep system updated** regularly
5. **Use HTTPS** for any web interfaces
6. **Secure API credentials** using environment variables

## Backup and Recovery

### Backup Configuration
```bash
# Create backup
tar -czf ha-optimizer-backup-$(date +%Y%m%d).tar.gz \
    /opt/ha-optimizer/config \
    /opt/ha-optimizer/models \
    /opt/ha-optimizer/data
```

### Restore Configuration
```bash
# Extract backup
tar -xzf ha-optimizer-backup-YYYYMMDD.tar.gz -C /
```

## Updates

### Update Process
```bash
# Stop service
sudo systemctl stop ha-optimizer

# Backup current version
cp -r /opt/ha-optimizer /opt/ha-optimizer-backup

# Update code
cd /opt/ha-optimizer
git pull origin main

# Update dependencies
source venv/bin/activate
pip install -r requirements.txt

# Start service
sudo systemctl start ha-optimizer
```

## Performance Monitoring

### System Resources
```bash
# CPU and memory usage
htop

# Disk usage
df -h

# Network usage
iftop
```

### Application Metrics
Consider adding Prometheus metrics to your application for monitoring:
- Optimization run times
- Battery usage patterns
- Prediction accuracy

## Support

For issues and questions:
1. Check the logs first
2. Review this deployment guide
3. Check the main README.md for application-specific issues
