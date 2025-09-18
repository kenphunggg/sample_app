from flask import Flask, jsonify
import subprocess
import os
import signal

app = Flask(__name__)

# A global variable to hold the FFmpeg process object.
# This is a simple approach for demonstration. See the production warning below.
stream_process = None

SOURCE_IP = "0.0.0.0"
SOURCE_VIDEO = "output.mp4"


@app.route("/stream/start")
def start_stream():
    """
    Starts the FFmpeg stream as a background process.
    """
    global stream_process

    # Check if the process is already running
    if stream_process and stream_process.poll() is None:
        return (
            jsonify({"status": "error", "message": "Stream is already running."}),
            400,
        )

    # The FFmpeg command to execute
    # Using a list of arguments is safer than a single string
    command = [
        "ffmpeg",
        "-re",
        "-stream_loop",
        "-1",
        "-r",
        "24",
        "-i",
        SOURCE_VIDEO,
        "-f",
        "flv",
        "-c:a",
        "aac",
        "-preset",
        "ultrafast",
        "-c:v",
        "libx264",
        f"rtmp://{SOURCE_IP}:1935/live/source",
    ]

    try:
        # Start the process. stdout and stderr can be piped to hide FFmpeg's output
        # from the console, or set to None to let it print.
        print("Starting FFmpeg stream...")
        stream_process = subprocess.Popen(command)

        return jsonify(
            {
                "status": "success",
                "message": "Stream started successfully.",
                "pid": stream_process.pid,
            }
        )
    except Exception as e:
        return (
            jsonify({"status": "error", "message": f"Failed to start stream: {e}"}),
            500,
        )


@app.route("/stream/stop")
def stop_stream():
    """
    Stops the currently running FFmpeg stream.
    """
    global stream_process

    # Check if the process exists and is running
    if not stream_process or stream_process.poll() is not None:
        return jsonify({"status": "error", "message": "Stream is not running."}), 400

    try:
        pid = stream_process.pid
        print(f"Stopping FFmpeg stream with PID: {pid}...")

        # Send a SIGTERM signal to gracefully terminate the process
        os.kill(pid, signal.SIGTERM)

        # Optional: wait a moment to ensure it has terminated
        stream_process.wait(timeout=5)

        stream_process = None  # Clear the process variable
        return jsonify(
            {"status": "success", "message": f"Stream stopped (PID: {pid})."}
        )
    except Exception as e:
        return (
            jsonify({"status": "error", "message": f"Failed to stop stream: {e}"}),
            500,
        )


@app.route("/stream/status")
def stream_status():
    """
    Checks the status of the FFmpeg stream.
    """
    global stream_process

    if stream_process and stream_process.poll() is None:
        # poll() returns None if the process is still running
        return jsonify({"status": "running", "pid": stream_process.pid})
    else:
        return jsonify(
            {"status": "stopped", "message": "Stream is not currently running."}
        )


if __name__ == "__main__":
    # Running on 0.0.0.0 makes the app accessible on your local network
    app.run(host="0.0.0.0", port=5000, debug=True)
