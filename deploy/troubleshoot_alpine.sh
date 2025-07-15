#!/bin/bash

echo "=== Alpine Linux Virtual Environment Troubleshooting ==="
echo ""

# Check if we're in a virtual environment
echo "1. Checking virtual environment status:"
if [ -n "$VIRTUAL_ENV" ]; then
    echo "✓ Virtual environment is active: $VIRTUAL_ENV"
else
    echo "✗ No virtual environment detected"
fi
echo ""

# Check Python path
echo "2. Checking Python path:"
which python3
echo ""

# Check pip path
echo "3. Checking pip path:"
which pip
echo ""

# Check if pip is from virtual environment
echo "4. Checking if pip is from virtual environment:"
if [[ "$(which pip)" == *".venv"* ]]; then
    echo "✓ pip is from virtual environment"
else
    echo "✗ pip is NOT from virtual environment"
    echo "  This is likely the system pip"
fi
echo ""

# Check Python executable
echo "5. Checking Python executable:"
python3 -c "import sys; print('Python executable:', sys.executable)"
echo ""

# Check if Python is from virtual environment
echo "6. Checking if Python is from virtual environment:"
if [[ "$(python3 -c 'import sys; print(sys.executable)')" == *".venv"* ]]; then
    echo "✓ Python is from virtual environment"
else
    echo "✗ Python is NOT from virtual environment"
    echo "  This is likely the system Python"
fi
echo ""

# Check virtual environment directory
echo "7. Checking virtual environment directory:"
if [ -d ".venv" ]; then
    echo "✓ .venv directory exists"
    echo "  Contents:"
    ls -la .venv/
    echo ""
    if [ -d ".venv/bin" ]; then
        echo "  bin directory contents:"
        ls -la .venv/bin/
    fi
else
    echo "✗ .venv directory does not exist"
fi
echo ""

# Check if we're running as root
echo "8. Checking user permissions:"
if [ "$EUID" -eq 0 ]; then
    echo "✗ Running as root - this can cause issues"
else
    echo "✓ Running as regular user"
fi
echo ""

echo "=== Recommendations ==="
echo ""
echo "If virtual environment is not working properly:"
echo "1. Delete the existing .venv directory"
echo "2. Create a new virtual environment"
echo "3. Activate it properly"
echo "4. Install packages"
echo ""
echo "Commands to fix:"
echo "  rm -rf .venv"
echo "  python3 -m venv .venv"
echo "  source .venv/bin/activate"
echo "  pip install -r requirements_production_minimal.txt"
