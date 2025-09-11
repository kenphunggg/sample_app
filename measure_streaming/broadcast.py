#!/usr/bin/env python3

import subprocess
import os
import signal
from flask import Flask, request, jsonify

# --- Configuration ---
INPUT_FILE = "input.mp4"
PORT = "1935"
PRESET = "ultrafast"
TUNE = "zerolatency"
# ---------------------

app = Flask(__name__)

# A global dictionary to hold the state of the streaming process
stream_process = {"process": None, "resolution": None}

# A dictionary to map vertical resolutions to full W:H format
ALLOWED_RESOLUTIONS = {
    "240": "426:240",
    "360": "640:360",
    "480": "854:480",
    "720": "1280:720",
    "1080": "1920:1080",
    "1440": "2560:1440",
    "2160": "3840:2160",
}


@app.route("/stream/start/<resolution>", methods=["GET"])
def start_stream(resolution):
    """Starts the FFmpeg stream using a resolution from the URL path."""
    global stream_process

    # Check if a stream is already running
    if stream_process.get("process") and stream_process["process"].poll() is None:
        return jsonify({"error": "A stream is already running."}), 409

    resolution_key = str(resolution)
    if resolution_key not in ALLOWED_RESOLUTIONS:
        return (
            jsonify(
                {
                    "error": "Invalid resolution specified.",
                    "allowed": list(ALLOWED_RESOLUTIONS.keys()),
                }
            ),
            400,
        )

    full_resolution = ALLOWED_RESOLUTIONS[resolution_key]

    # Construct the FFmpeg command
    command = [
        "ffmpeg",
        "-re",
        "-stream_loop",
        "-1",
        "-i",
        INPUT_FILE,
        "-vf",
        f"scale={full_resolution}",
        "-c:v",
        "libx264",
        "-preset",
        PRESET,
        "-tune",
        TUNE,
        "-f",
        "mpegts",
        f"srt://0.0.0.0:{PORT}?mode=listener",
    ]

    try:
        # Start the process without blocking
        process = subprocess.Popen(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        stream_process["process"] = process
        stream_process["resolution"] = resolution_key
        return (
            jsonify(
                {
                    "message": "Stream started successfully.",
                    "pid": process.pid,
                    "resolution": resolution_key,
                }
            ),
            201,
        )
    except FileNotFoundError:
        return (
            jsonify({"error": "'ffmpeg' not found. Is it installed and in your PATH?"}),
            500,
        )
    except Exception as e:
        return jsonify({"error": f"Failed to start stream: {e}"}), 500


@app.route("/stream/stop", methods=["GET"])
def stop_stream():
    """Stops the running FFmpeg stream."""
    global stream_process

    process = stream_process.get("process")
    if not process or process.poll() is not None:
        return jsonify({"error": "No stream is currently running."}), 404  # Not Found

    try:
        # Send a SIGTERM signal for a graceful shutdown
        os.kill(process.pid, signal.SIGTERM)
        process.wait(timeout=5)  # Wait for the process to terminate

        stream_process["process"] = None
        stream_process["resolution"] = None

        return jsonify({"message": "Stream stopped successfully."}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to stop stream: {e}"}), 500


@app.route("/stream/status", methods=["GET"])
def get_status():
    """Gets the status of the current stream."""
    process = stream_process.get("process")

    if process and process.poll() is None:
        # process.poll() returns None if the process is still running
        return (
            jsonify(
                {
                    "status": "running",
                    "pid": process.pid,
                    "resolution": stream_process.get("resolution"),
                }
            ),
            200,
        )
    else:
        return jsonify({"status": "stopped"}), 200


if __name__ == "__main__":
    # Runs the Flask app on host 0.0.0.0 to be accessible on your network
    app.run(host="0.0.0.0", port=5000)
