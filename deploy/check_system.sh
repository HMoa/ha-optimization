#!/bin/bash

echo "=== System Information ==="
echo ""

# Check OS
echo "Operating System:"
if [ -f /etc/os-release ]; then
    cat /etc/os-release | grep -E "^(NAME|VERSION|ID)="
else
    echo "Could not determine OS from /etc/os-release"
fi
echo ""

# Check kernel
echo "Kernel:"
uname -a
echo ""

# Check available package managers
echo "=== Package Manager Check ==="
echo ""

echo "Checking for apt-get:"
if command -v apt-get &> /dev/null; then
    echo "✓ apt-get is available"
    apt-get --version | head -1
else
    echo "✗ apt-get not found"
fi
echo ""

echo "Checking for yum:"
if command -v yum &> /dev/null; then
    echo "✓ yum is available"
    yum --version | head -1
else
    echo "✗ yum not found"
fi
echo ""

echo "Checking for dnf:"
if command -v dnf &> /dev/null; then
    echo "✓ dnf is available"
    dnf --version | head -1
else
    echo "✗ dnf not found"
fi
echo ""

echo "Checking for pacman:"
if command -v pacman &> /dev/null; then
    echo "✓ pacman is available"
    pacman --version | head -1
else
    echo "✗ pacman not found"
fi
echo ""

echo "Checking for zypper:"
if command -v zypper &> /dev/null; then
    echo "✓ zypper is available"
    zypper --version | head -1
else
    echo "✗ zypper not found"
fi
echo ""

echo "Checking for apk:"
if command -v apk &> /dev/null; then
    echo "✓ apk is available"
    apk --version | head -1
else
    echo "✗ apk not found"
fi
echo ""

# Check Python
echo "=== Python Check ==="
echo "Python version:"
python3 --version
echo ""

echo "pip version:"
pip3 --version
echo ""

echo "=== Build Tools Check ==="
echo ""

echo "Checking for gcc:"
if command -v gcc &> /dev/null; then
    echo "✓ gcc is available"
    gcc --version | head -1
else
    echo "✗ gcc not found"
fi
echo ""

echo "Checking for make:"
if command -v make &> /dev/null; then
    echo "✓ make is available"
    make --version | head -1
else
    echo "✗ make not found"
fi
echo ""

echo "=== Python Development Headers ==="
echo ""

# Check for Python dev headers
if [ -f /usr/include/python3.*/Python.h ] || [ -f /usr/local/include/python3.*/Python.h ]; then
    echo "✓ Python development headers found"
    find /usr/include /usr/local/include -name "Python.h" 2>/dev/null | head -3
else
    echo "✗ Python development headers not found"
fi
