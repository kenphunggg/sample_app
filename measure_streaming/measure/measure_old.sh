#!/bin/bash

# Set the source IP address from an environment variable.
SOURCE_IP=${SOURCE_IP:-"192.168.17.161"}

# --- HLS Setup ---
# Directory where HLS files will be created. Your Nginx config must serve files from this path.
HLS_DIR="/var/www/hls"
mkdir -p "$HLS_DIR"
echo "HLS output directory is ${HLS_DIR}"
# ------------------

# Start the Nginx server in the background to act as a web server for HLS files.
echo "--- Starting Nginx Web Server for HLS ---"
nginx &

# --- Optional: Wait for Nginx to be ready on its HTTP port ---
# Knative's default user port is 8080. This check ensures Nginx is ready before transcoding starts.
echo "Waiting for Nginx to accept connections on port 8080..."
while ! nc -z 127.0.0.1 8080; do
  # Wait for 0.1 seconds before checking again
  sleep 0.1
done
echo "Nginx is ready to serve HLS files!"
# ----------------------------------------------------------------

echo "--- Starting FFmpeg Transcoding to HLS ---"
echo "Source RTMP IP: ${SOURCE_IP}"
echo "Output HLS Playlist: ${HLS_DIR}/playlist.m3u8"
echo "---------------------------------------------"

# Execute the FFmpeg command to produce HLS.
# This runs in the foreground, keeping the container alive.
# NOTE: The video codec was corrected from 'libx24' to 'libx264'.
ffmpeg \
-i "rtmp://${SOURCE_IP}/live/source" \
-vf "scale=1920:1080" \
-c:v libx264 \
-preset veryfast \
-g 48 \
-sc_threshold 0 \
-f hls \
-hls_time 4 \
-hls_list_size 5 \
-hls_flags delete_segments \
-hls_segment_filename "${HLS_DIR}/segment%03d.ts" \
"${HLS_DIR}/playlist.m3u8"