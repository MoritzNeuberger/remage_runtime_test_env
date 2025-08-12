#!/bin/bash

# Quick installation and setup script for remage_runtime_tests

echo "Setting up REMAGE Runtime Tests package..."

# Check if uv is available
if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed. Please install uv first:"
    echo "curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Install the package in development mode
echo "Installing package..."
cd "$(dirname "$0")"
uv pip install -e .

# Create a simple test config
echo "Creating test configuration..."
if [ ! -f "config.json" ]; then
    cp config_example.json config.json
    echo "Created config.json from example"
else
    echo "config.json already exists"
fi

# Create results directory
mkdir -p results plots

echo ""
echo "Installation complete!"
echo ""
echo "Available commands:"
echo "  rrt-run templates/simple_electron.mac      # Run tests locally"
echo "  rrt-submit templates/simple_electron.mac   # Submit SLURM jobs"
echo "  rrt-plot results/                          # Generate plots"
echo ""
echo "Edit config.json to customize test parameters."
