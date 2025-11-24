#!/bin/bash

# --- Config ---
SOURCE_IP=${SOURCE_IP:-"192.168.17.130:2000"}
SCALE_VALUE=${SCALE_VALUE:-"1280x720"}
RTMP_TARGET="rtmp://0.0.0.0:1935/live/stream"

# --- Cleanup Function ---
# When the Pod stops, we must kill both processes.
cleanup() {
    echo "--- Shutting down ---"
    kill -TERM "$NGINX_PID" 2>/dev/null
    kill -TERM "$FFMPEG_PID" 2>/dev/null
    wait
    exit 0
}

# Catch termination signals from Kubernetes
trap cleanup TERM INT

echo "--- 1. Starting Nginx Server ---"
# Run Nginx in background, but keep it as a child process of this script
nginx &
NGINX_PID=$!

# Wait for Nginx to open port 1935 before starting FFmpeg
echo "Waiting for Nginx to be ready..."
while ! nc -z 127.0.0.1 1935; do
  sleep 0.1
done
echo "Nginx is UP (PID: $NGINX_PID)"

echo "--- 2. Starting FFmpeg Worker ---"
ffmpeg \
  -i "rtmp://${SOURCE_IP}/live/source" \
  -vf "scale=${SCALE_VALUE}" \
  -c:v libx264 \
  -preset ultrafast \
  -tune zerolatency \
  -g 30 \
  -sc_threshold 0 \
  -c:a aac \
  -f flv \
  "${RTMP_TARGET}" &

FFMPEG_PID=$!

# --- 3. Keep Alive ---
# Wait for FFmpeg to finish or crash.
wait "$FFMPEG_PID"