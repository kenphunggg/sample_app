#!/bin/bash

# Set the source IP address from an environment variable.
SOURCE_IP=${SOURCE_IP:-"192.168.17.161"}

# Start the Nginx server in the background
echo "--- Starting Nginx RTMP Server ---"
nginx &

# --- FIX: Wait for Nginx to be ready on port 1935 ---
echo "Waiting for Nginx to accept connections..."
while ! nc -z 127.0.0.1 1935; do
  # Wait for 0.1 seconds before checking again
  sleep 0.1
done
echo "Nginx is ready!"
# ---------------------------------------------------

echo "--- Starting FFmpeg Transcoding ---"
echo "Source RTMP IP: ${SOURCE_IP}"
echo "Output RTMP: rtmp://0.0.0.0:1935/live/1080p"
echo "------------------------------------"

# Execute the FFmpeg command
ffmpeg \
-i "rtmp://${SOURCE_IP}/live/source" \
-vf "scale=1920:1080" \
-c:v libx264 \
-preset veryfast \
-g 48 \
-an \
-f flv "rtmp://0.0.0.0:1935/live/1080p"