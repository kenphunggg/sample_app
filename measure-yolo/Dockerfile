FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install all system dependencies in one go.
# This includes the fix for OpenCV (libgl1) and your other tools (tini, procps).
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    tini \
    procps \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Install pip dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all app files
COPY . .

# Expose port
EXPOSE 8080

ENTRYPOINT ["/usr/bin/tini", "-g", "--"]

# Run with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--graceful-timeout", "5", "--access-logfile", "-", "--error-logfile", "-", "main:app"]