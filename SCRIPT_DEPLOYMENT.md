# Script Deployment Guide

Simple deployment guide for running the Home Energy Optimizer as standalone scripts.

## Quick Deployment

### 1. Build the Package
```bash
./deploy/build_script_package.sh
```

This creates `build/ha-optimizer-scripts-1.0.0.tar.gz`

### 2. Deploy to Raspberry Pi
```bash
# Copy to Raspberry Pi
scp build/ha-optimizer-scripts-1.0.0.tar.gz pi@raspberrypi.local:~/

# SSH into Raspberry Pi
ssh pi@raspberrypi.local

# Extract and setup
tar -xzf ha-optimizer-scripts-1.0.0.tar.gz
cd ha-optimizer-scripts-1.0.0
./install_deps.sh
```

### 3. Run the Optimizer
```bash
# Activate virtual environment
source venv/bin/activate

# Run the optimizer
python run_optimizer.py
```

## Manual Setup (Alternative)

If you prefer to copy files manually:

### 1. Copy Files
```bash
# Create directory on Raspberry Pi
mkdir -p ~/ha-optimizer
cd ~/ha-optimizer

# Copy from your development machine
scp -r optimizer/ pi@raspberrypi.local:~/ha-optimizer/
scp -r analytics/ pi@raspberrypi.local:~/ha-optimizer/
scp requirements.txt pi@raspberrypi.local:~/ha-optimizer/
```

### 2. Install Dependencies
```bash
# On Raspberry Pi
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Run
```bash
python -m optimizer.main
```

## Integration with External Tools

### Cron Job
```bash
# Edit crontab
crontab -e

# Add line to run every hour
0 * * * * cd /home/pi/ha-optimizer && source venv/bin/activate && python run_optimizer.py
```

### Systemd Timer (Alternative to Cron)
```bash
# Create timer file
sudo tee /etc/systemd/system/ha-optimizer.timer << EOF
[Unit]
Description=Run Home Energy Optimizer hourly

[Timer]
OnCalendar=hourly
Persistent=true

[Install]
WantedBy=timers.target
EOF

# Create service file
sudo tee /etc/systemd/system/ha-optimizer.service << EOF
[Unit]
Description=Home Energy Optimizer Script
After=network.target

[Service]
Type=oneshot
User=pi
WorkingDirectory=/home/pi/ha-optimizer
Environment=PATH=/home/pi/ha-optimizer/venv/bin
ExecStart=/home/pi/ha-optimizer/venv/bin/python run_optimizer.py

[Install]
WantedBy=multi-user.target
EOF

# Enable and start timer
sudo systemctl daemon-reload
sudo systemctl enable ha-optimizer.timer
sudo systemctl start ha-optimizer.timer
```

### Home Assistant Integration
If you're using Home Assistant, you can trigger the script via:

```yaml
# In your Home Assistant configuration
shell_command:
  run_optimizer: "cd /home/pi/ha-optimizer && source venv/bin/activate && python run_optimizer.py"

automation:
  - alias: "Run Energy Optimizer Daily"
    trigger:
      platform: time
      at: "06:00:00"
    action:
      service: shell_command.run_optimizer
```

## Configuration

### Environment Variables
You can set environment variables for configuration:

```bash
export BATTERY_CAPACITY=10000
export MAX_POWER=5000
export DEBUG=1
python run_optimizer.py
```

### Configuration File
Create a `config.json` file:

```json
{
  "battery": {
    "capacity": 10000,
    "max_power": 5000,
    "min_soc": 0.1,
    "max_soc": 0.9
  },
  "api": {
    "base_url": "https://api.example.com",
    "timeout": 30
  },
  "output": {
    "directory": "/home/pi/optimizer_results",
    "log_level": "INFO"
  }
}
```

Then run with:
```bash
python run_optimizer.py --config config.json
```

## Monitoring and Logging

### Basic Logging
The script will output to stdout/stderr. To capture logs:

```bash
python run_optimizer.py > optimizer.log 2>&1
```

### Rotating Logs
```bash
# Install logrotate
sudo apt-get install logrotate

# Create logrotate config
sudo tee /etc/logrotate.d/ha-optimizer << EOF
/home/pi/ha-optimizer/optimizer.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 pi pi
}
EOF
```

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Make sure virtual environment is activated
   source venv/bin/activate

   # Reinstall dependencies
   pip install -r requirements.txt
   ```

2. **Permission Errors**
   ```bash
   # Fix file permissions
   chmod +x run_optimizer.py
   chmod +x install_deps.sh
   ```

3. **Memory Issues**
   ```bash
   # Check memory usage
   free -h

   # Add swap if needed
   sudo dphys-swapfile swapoff
   sudo nano /etc/dphys-swapfile  # Set CONF_SWAPSIZE=1024
   sudo dphys-swapfile setup
   sudo dphys-swapfile swapon
   ```

4. **Network Issues**
   ```bash
   # Test network connectivity
   ping 8.8.8.8

   # Check DNS
   nslookup api.example.com
   ```

### Debug Mode
Run with debug mode for more information:

```bash
python run_optimizer.py --debug
```

## Performance Tips

1. **Use 5-minute data intervals** instead of 1-minute for reduced computational load
2. **Run during off-peak hours** to avoid system load
3. **Monitor system resources** with `htop` or `top`
4. **Use SSD storage** instead of SD card for better I/O performance

## Backup

### Backup Configuration
```bash
# Create backup
tar -czf ha-optimizer-backup-$(date +%Y%m%d).tar.gz \
    ~/ha-optimizer/optimizer \
    ~/ha-optimizer/config.json \
    ~/ha-optimizer/requirements.txt
```

### Restore
```bash
# Extract backup
tar -xzf ha-optimizer-backup-YYYYMMDD.tar.gz -C ~/
```
