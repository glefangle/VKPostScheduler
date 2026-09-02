#!/bin/bash

# Navigate to script directory
cd "$(dirname "$0")"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip and install the package
python3 -m pip install --upgrade pip
python3 -m pip install -e .

# Run the installed package
python3 -m vkpostscheduler