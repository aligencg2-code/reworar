FROM python:3.11-slim

WORKDIR /app

# System dependencies for Pillow, cryptography etc.
RUN apt-get update && apt-get install -y \
    gcc \
    libjpeg-dev \
    zlib1g-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY main.py .
COPY Procfile .

# Create data directories
RUN mkdir -p /data/sessions /data/uploads /data/backups /data/logs \
    /data/uploads/photos /data/uploads/videos /data/uploads/stories \
    /data/uploads/reels /data/uploads/thumbnails

# Port
EXPOSE ${PORT:-8000}

# Start
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
