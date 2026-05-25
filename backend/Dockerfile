FROM python:3.12-slim

# Install system dependencies (ffmpeg required for audio processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Use shell form so ${PORT:-8080} is expanded at runtime
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
