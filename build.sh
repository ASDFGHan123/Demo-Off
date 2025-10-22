#!/bin/bash

# Build script for OffChat

set -e

echo "Building OffChat for production..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found. Please create it from .env.example"
    exit 1
fi

# Build Docker images
echo "Building Docker images..."
docker-compose build

echo "Build completed successfully!"
echo "Run './deploy.sh' to deploy the application."