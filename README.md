# OffChat - Production Deployment

This Django application is configured for production deployment using Docker, PostgreSQL, Redis, and Nginx.

## Features

- Real-time chat application with WebSocket support
- Docker containerization
- PostgreSQL database
- Redis for WebSocket channels
- Nginx reverse proxy
- Static file serving with WhiteNoise
- Environment-based configuration

## Quick Start

1. **Clone the repository and navigate to the project directory**

2. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your production values
   ```

3. **Build the application:**
   ```bash
   ./build.sh
   ```

4. **Deploy the application:**
   ```bash
   ./deploy.sh
   ```

The application will be available at `http://localhost`.

## Environment Variables

Key environment variables to configure:

- `DEBUG`: Set to `False` for production
- `SECRET_KEY`: Django secret key
- `DB_ENGINE`: Database engine (use `django.db.backends.postgresql` for PostgreSQL)
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`: Database configuration
- `REDIS_URL`: Redis connection URL
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts
- `STATIC_ROOT`, `MEDIA_ROOT`: Paths for static and media files

## Services

The deployment includes:

- **Web App**: Django application running on Daphne ASGI server
- **Database**: PostgreSQL database
- **Redis**: For WebSocket channel layers
- **Nginx**: Reverse proxy and static file serving

## Development vs Production

- **Development**: Uses SQLite, runs on Django's development server
- **Production**: Uses PostgreSQL, Daphne ASGI server, Nginx proxy, WhiteNoise for static files

## Commands

- `./build.sh`: Build Docker images
- `./deploy.sh`: Deploy the application (includes migrations and static file collection)
- `docker-compose up -d`: Start services in background
- `docker-compose down`: Stop services
- `docker-compose logs`: View logs

## WebSocket Support

The application supports real-time WebSocket connections through Daphne and Redis channel layers. WebSocket endpoint is available at `/ws/`.

## Static Files

Static files are served through Nginx in production, with WhiteNoise as a fallback. Files are collected to `STATIC_ROOT` during deployment.