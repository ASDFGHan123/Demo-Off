@echo off
echo Starting OffChat for LAN usage...
echo.

REM Set environment variables for LAN usage
set DEBUG=True
set ALLOWED_HOSTS=*
set USE_REDIS=False

REM Start Django server on all interfaces
python manage.py runserver 0.0.0.0:8000

pause