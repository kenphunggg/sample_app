from flask import Flask, jsonify, request
import subprocess
import os
import signal

app = Flask(__name__)

# Global process variable
stream_process = None

# --- Constants ---
SOURCE_IP = "0.0.0.0"
ORIGINAL_VIDEO = "input.mp4"
RESCALED_VIDEO = "new_output.mp4" # The new file we will create

# --- NEW: Resolution Preset Mapping ---
# Maps friendly names (e.g., "720p") to FFmpeg size strings ("widthxheight")
# All are 16:9 aspect ratio. Add your own custom ones here!
RESOLUTION_PRESETS = {
    "240p": "426x240",
    "360p": "640x360",
    "480p": "854x480",
    "720p": "1280x720",
    "1080p": "1920x1080",
    "1440p": "2560x1440",
    "2160p": "3840x2160"  # 4K
}


@app.route("/stream/start")
def start_stream():
    """
    Checks for a 'resolution' query param (e.g., ?resolution=720p).
    Looks up the preset, rescales the video, and starts the stream.
    """
    global stream_process

    # 1. Get the resolution PRESET from the URL query parameter
    res_key = request.args.get('resolution') # e.g., "720p"
    if not res_key:
        return (
            jsonify({"status": "error", "message": "Missing 'resolution' query parameter. (e.g., ?resolution=720p)"}),
            400,
        )

    # --- NEW: Look up the resolution ---
    ffmpeg_resolution = RESOLUTION_PRESETS.get(res_key)
    
    if not ffmpeg_resolution:
        # Inform the user of valid options if their key isn't found
        valid_options = ", ".join(RESOLUTION_PRESETS.keys())
        return (
            jsonify({
                "status": "error", 
                "message": f"Invalid resolution preset '{res_key}'. Valid options are: {valid_options}"
            }), 400
        )
    # At this point, ffmpeg_resolution is a string like "1280x720"


    # 2. Check if the process is already running
    if stream_process and stream_process.poll() is None:
        return (
            jsonify({"status": "error", "message": "Stream is already running."}),
            400,
        )

    # 3. --- Rescale the video (Blocking) ---
    print(f"Rescaling {ORIGINAL_VIDEO} to {res_key} ({ffmpeg_resolution}) -> {RESCALED_VIDEO}...")
    rescale_command = [
        "ffmpeg",
        "-i", ORIGINAL_VIDEO,
        "-s", ffmpeg_resolution,  # <-- ***USE THE LOOKED-UP VALUE***
        "-c:a", "aac",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-y",
        RESCALED_VIDEO
    ]

    try:
        subprocess.run(rescale_command, check=True, capture_output=True)
        print("Rescale complete.")

    except subprocess.CalledProcessError as e:
        return (
            jsonify({
                "status": "error", 
                "message": f"Failed to rescale video: {e.stderr.decode()}"
            }), 500
        )
    except Exception as e:
        return (
            jsonify({"status": "error", "message": f"Failed to start rescale: {e}"}),
            500,
        )


    # 4. --- Start the stream (Non-blocking) ---
    stream_command = [
        "ffmpeg",
        "-re",
        "-stream_loop", "-1",
        "-r", "24",
        "-i", RESCALED_VIDEO,
        "-f", "flv",
        "-c:a", "aac",
        "-preset", "ultrafast",
        "-c:v", "libx264",
        f"rtmp://{SOURCE_IP}:1935/live/source",
    ]

    try:
        print(f"Starting FFmpeg stream with {RESCALED_VIDEO}...")
        stream_process = subprocess.Popen(stream_command)

        return jsonify(
            {
                "status": "success",
                "message": f"Rescaled to {res_key} ({ffmpeg_resolution}) and stream started.",
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
    """ Stops the currently running FFmpeg stream. (Unchanged) """
    global stream_process

    if not stream_process or stream_process.poll() is not None:
        return jsonify({"status": "error", "message": "Stream is not running."}), 400

    try:
        pid = stream_process.pid
        print(f"Stopping FFmpeg stream with PID: {pid}...")
        
        os.kill(pid, signal.SIGTERM)
        stream_process.wait(timeout=5)

        stream_process = None
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
    """ Checks the status of the FFmpeg stream. (Unchanged) """
    global stream_process

    if stream_process and stream_process.poll() is None:
        return jsonify({"status": "running", "pid": stream_process.pid})
    else:
        return jsonify(
            {"status": "stopped", "message": "Stream is not currently running."}
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
