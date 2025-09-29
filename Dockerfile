FROM python:3.12-slim

# Set working directory
WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

# Cloud Run uses PORT environment variable
ENV PORT=8080

# Use gunicorn for production
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app