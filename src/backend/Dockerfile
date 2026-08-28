# Moodometer Backend Dockerfile
#
# This Dockerfile creates a containerized environment for the Moodometer FastAPI application.
# It uses a slim Python 3.13 image to minimize container size while providing all necessary
# dependencies for running the web application.

# Use Python 3.13 slim variant as the base image
# The slim variant reduces image size by excluding unnecessary packages
FROM python:3.13-slim

# Set the working directory inside the container
# All subsequent commands will be executed relative to this directory
WORKDIR /usr/src/app

# Copy requirements first for better Docker layer caching
COPY ./app/requirements.txt .

# Install Python dependencies from requirements.txt
# --no-cache-dir flag prevents pip from caching packages, reducing image size
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application directory from host to container
# This includes all Python modules, HTML, CSS, and static files
COPY ./app .

# Copy alembic configuration and migrations
COPY ./alembic ./alembic
COPY ./alembic.ini .

# Expose port 8000 to allow external access to the FastAPI application
# This is the default port for the Uvicorn ASGI server
EXPOSE 8000

# Define the command to run when the container starts
# Uvicorn serves the FastAPI app with the following configuration:
# - app:app -> module:application_instance (from app.py)
# - --host 0.0.0.0 -> Listen on all network interfaces (required for Docker)
# - --port 8000 -> Listen on port 8000 (matches EXPOSE directive)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]