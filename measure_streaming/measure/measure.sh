#!/bin/bash

# Set the source IP address from an environment variable.
SOURCE_IP=${SOURCE_IP:-"192.168.17.161"}

# --- HLS Setup ---
HLS_DIR="/var/www/hls"
mkdir -p "$HLS_DIR"
echo "HLS output directory is ${HLS_DIR}"
# ------------------

# --- Cleanup Function ---
# This function is called when the script receives a signal to terminate.
cleanup() {
    echo "--- Received signal, cleaning up... ---"

    # Kill the Nginx process
    if [ -n "$NGINX_PID" ]; then
        echo "Stopping Nginx (PID $NGINX_PID)..."
        # Use kill -TERM for graceful shutdown
        kill -TERM "$NGINX_PID"
        wait "$NGINX_PID" 2>/dev/null
    fi

    # Kill the FFmpeg process
    if [ -n "$FFMPEG_PID" ]; then
        echo "Stopping FFmpeg (PID $FFMPEG_PID)..."
        kill -TERM "$FFMPEG_PID"
        wait "$FFMPEG_PID" 2>/dev/null
    fi

    echo "Cleanup complete."
}

# --- Trap Setup ---
# This tells bash to call the 'cleanup' function when the script
# receives a TERM or INT signal.
trap cleanup SIGTERM SIGINT

# --- Start Nginx ---
echo "--- Starting Nginx Web Server for HLS ---"
nginx &
# Store the PID of the Nginx process
NGINX_PID=$!
echo "Nginx started with PID $NGINX_PID"

# --- Wait for Nginx to be ready ---
echo "Waiting for Nginx to accept connections on port 8080..."
while ! nc -z 127.0.0.1 8080; do
  sleep 0.1
done
echo "Nginx is ready to serve HLS files!"
# ------------------------------------

echo "--- Starting FFmpeg Transcoding to HLS ---"
echo "Source RTMP IP: ${SOURCE_IP}"
echo "Output HLS Playlist: ${HLS_DIR}/playlist.m3u8"
echo "---------------------------------------------"

# Execute FFmpeg in the background AND store its PID
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
"${HLS_DIR}/playlist.m3u8" &

FFMPEG_PID=$!

# Wait for FFmpeg to exit. This keeps the script alive.
# The 'trap' will handle killing it when the script is stopped.
wait "$FFMPEG_PID"