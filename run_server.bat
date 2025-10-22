@echo off
echo Starting OffChat server for LAN/offline usage...
echo Access the app at: http://localhost:8000 or http://YOUR_LOCAL_IP:8000
echo Press Ctrl+C to stop the server.
pipenv run python manage.py runserver 0.0.0.0:8000
pause