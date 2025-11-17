FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install all system dependencies in one go.
# ADDED git to this list so we can clone the repo.
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    tini \
    procps \
    git \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Install pip dependencies from your main requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- FIX ---
# Clone the yolov5 repo to the path your main.py expects
# This creates the '/app/ultralytics/yolov5/hubconf.py' file
RUN git clone https://github.com/ultralytics/yolov5 /app/ultralytics/yolov5

# Install the dependencies required by yolov5 itself
RUN pip install --no-cache-dir -r /app/ultralytics/yolov5/requirements.txt
# --- END FIX ---

# Copy all app files
COPY main.py .
COPY yolov5n.pt .

# Expose port
EXPOSE 8080

ENTRYPOINT ["/usr/bin/tini", "-g", "--"]

# Run with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--graceful-timeout", "5", "--access-logfile", "-", "--error-logfile", "-", "main:app"]