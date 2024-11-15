# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 80 for Gunicorn
EXPOSE 80

# Command to run the app in development environment
# CMD ["python", "./flask_app.py"]

# Command to run the app with Gunicorn (WSGI) in production
CMD ["gunicorn", "--workers", "3", "--bind", "0.0.0.0:80", "flask_app:app"]
