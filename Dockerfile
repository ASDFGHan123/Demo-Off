# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install pipenv
RUN pip install pipenv

# Copy Pipfile and Pipfile.lock
COPY Pipfile Pipfile.lock ./

# Install dependencies
RUN pipenv install --deploy --ignore-pipfile

# Copy project
COPY . .

# Collect static files
RUN pipenv run python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Run the application with Daphne
CMD ["pipenv", "run", "daphne", "-b", "0.0.0.0", "-p", "8000", "offchat.asgi:application"]