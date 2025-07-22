# HA Optimizer Deployment on Alpine Linux (Home Assistant OS)

This guide is specifically for deploying the HA Optimizer on Home Assistant OS, which runs Alpine Linux.

## Summary
Run: cd /root/addon_configs/a0d7b954_nodered/files && /tmp/optimizer_venv/bin/python -m optimizer.main --current-schedule to get current schedule to pass to the inverter.

## System Requirements

- Home Assistant OS on Raspberry Pi
- SSH access (via Home Assistant SSH add-on or direct SSH)
- Regular user account (not root)

## Package Manager Differences

Home Assistant OS uses **Alpine Linux**, which uses `apk` instead of `apt-get`:

| Alpine Linux (apk) | Debian/Ubuntu (apt-get) |
|-------------------|------------------------|
| `build-base` | `build-essential` |
| `python3-dev` | `python3-dev` |
| `musl-dev` | `libc6-dev` |
| `linux-headers` | `linux-headers-*` |

## Installation Steps

### 1. Install System Dependencies

```bash
# Update package index
sudo apk update

# Install build dependencies
sudo apk add --no-cache \
    build-base \
    python3-dev \
    py3-pip \
    gcc \
    musl-dev \
    linux-headers
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate
```

### 3. Install Python Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt
```

## Quick Fix for Missing Packages

If you encounter missing packages like `joblib`:

```bash
# Run the quick fix script
./deploy/quick_fix_alpine.sh
```

Or manually:

```bash
# Install build tools if missing
sudo apk add --no-cache build-base python3-dev gcc musl-dev

# Activate virtual environment
source .venv/bin/activate

# Install the missing package
pip install joblib==1.4.2
```

## Running the Optimizer

```bash
# Activate virtual environment
source /tmp/optimizer_venv/bin/activate

# Run with InfluxDB integration
python -m optimizer.main --fetch-influxdb

# Run without InfluxDB (uses sample data)
python -m optimizer.main
```

## Troubleshooting

### Permission Issues
- Don't run as root
- Use a regular user account
- Use `sudo` only for system package installation

### Build Errors
- Ensure `build-base` and `python3-dev` are installed
- Alpine uses `musl` instead of `glibc`, so some packages may need to be compiled

### Memory Issues
- Some packages require significant memory to compile
- Consider using pre-compiled wheels when available
- Monitor system resources during installation

## Alpine-Specific Notes

- Alpine Linux is minimal and security-focused
- Uses `musl` libc instead of `glibc`
- Package names may differ from Debian/Ubuntu
- Some Python packages may need to be compiled from source
- Smaller disk footprint but potentially longer compilation times

---

**Summary:**
Moving a venv on the same machine is fine. Just update your references to the new path. If you run into issues, you can always recreate the venv in the new location and reinstall your requirements.

Let me know if you want a command to update the activation script or need help with anything else!
