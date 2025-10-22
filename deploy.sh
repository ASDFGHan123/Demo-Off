#!/bin/bash

# Build and deploy script for OffChat production

set -e

echo "Starting deployment..."

# Copy environment file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "Please edit .env file with your production values before continuing."
    exit 1
fi

# Build and start services
echo "Building and starting services..."
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 30

# Run migrations
echo "Running database migrations..."
docker-compose exec web pipenv run python manage.py migrate

# Collect static files
echo "Collecting static files..."
docker-compose exec web pipenv run python manage.py collectstatic --noinput

# Create superuser if needed (optional)
echo "Deployment completed!"
echo "Application is running at http://localhost"
echo "WebSocket server is available at ws://localhost/ws/"