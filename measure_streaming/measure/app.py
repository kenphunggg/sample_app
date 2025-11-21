import glob
import os
import subprocess

from flask import Flask, jsonify, request

app = Flask(__name__)

# --- Global state ---
STREAM_PROCESS = None
SCRIPT_PATH = "measure.sh"
HLS_DIR = "/var/www/hls"


# --- NEW: Resolution Preset Mapping ---
# Maps "720p" to "1280:720" for ffmpeg's scale filter
RESOLUTION_PRESETS = {
    "240p": "426:240",
    "360p": "640:360",
    "480p": "854:480",
    "720p": "1280:720",
    "1080p": "1920:1080",
    "1440p": "2560:1440",
    "2160p": "3840:2160"  # 4K
}


def setup_script():
    """
    Checks if measure.sh exists and makes it executable.
    """
    if not os.path.exists(SCRIPT_PATH):
        print(f"Error: '{SCRIPT_PATH}' not found.")
        print("Please create the 'measure.sh' file in the same directory.")
        raise FileNotFoundError(f"{SCRIPT_PATH} is required to run this server.")

    try:
        os.chmod(SCRIPT_PATH, 0o755)
        print(f"Successfully found and set '{SCRIPT_PATH}' as executable.")
    except Exception as e:
        print(f"Error setting permissions for script: {e}")
        raise


# --- API Endpoints ---


@app.route("/stream/start", methods=["GET"])
def start_stream():
    """
    Starts the transcoding script as a subprocess.
    Accepts 'source_ip' and 'resolution' query parameters.
    """
    global STREAM_PROCESS

    if STREAM_PROCESS and STREAM_PROCESS.poll() is None:
        return jsonify({"error": "Stream is already running"}), 400

    # --- 1. Get Source IP ---
    url_ip = request.args.get("source_ip")
    env_ip = os.environ.get("SOURCE_IP")
    default_ip = "192.168.17.161"
    source_ip = url_ip or env_ip or default_ip

    # --- 2. Get Resolution ---
    resolution_param = request.args.get("resolution")
    env_scale = os.environ.get("SCALE_VALUE", "1920:1080")

    if resolution_param:
        if resolution_param in RESOLUTION_PRESETS:
            scale_value = RESOLUTION_PRESETS[resolution_param]
        else:
            scale_value = resolution_param
    else:
        scale_value = env_scale
    # If resolution_param is None, scale_value remains default_scale

    # --- 3. Set up environment for the script ---
    env = os.environ.copy()
    env["SOURCE_IP"] = source_ip
    env["SCALE_VALUE"] = scale_value  # <-- NEW ENV VAR

    print(f"Starting stream from {source_ip} with resolution {scale_value}")
    STREAM_PROCESS = subprocess.Popen(["/bin/bash", SCRIPT_PATH], env=env)

    return jsonify(
        {
            "message": "Stream started successfully",
            "pid": STREAM_PROCESS.pid,
            "source_ip": source_ip,
            "resolution": scale_value,
        }
    ), 200


@app.route("/stream/stop", methods=["GET"])
def stop_stream():
    """
    Stops the running transcoding script gracefully AND cleans up HLS files.
    """
    global STREAM_PROCESS

    if not STREAM_PROCESS or STREAM_PROCESS.poll() is not None:
        return jsonify({"error": "Stream is not running"}), 400

    print(f"Stopping stream process (PID {STREAM_PROCESS.pid})...")

    # --- 1. Stop the FFmpeg Process ---
    STREAM_PROCESS.terminate()
    try:
        STREAM_PROCESS.wait(timeout=10)
        print("Process terminated gracefully.")
    except subprocess.TimeoutExpired:
        print("Process did not terminate, sending SIGKILL.")
        STREAM_PROCESS.kill()
        STREAM_PROCESS.wait()

    STREAM_PROCESS = None

    # --- 2. NEW: Clean up old HLS files ---
    print(f"Cleaning up HLS files from {HLS_DIR}...")
    try:
        # Find all .ts and .m3u8 files in the HLS directory
        files_to_delete = glob.glob(os.path.join(HLS_DIR, "*.ts"))
        files_to_delete.extend(glob.glob(os.path.join(HLS_DIR, "*.m3u8")))

        if not files_to_delete:
            print("No HLS files found to delete.")

        for f in files_to_delete:
            try:
                os.remove(f)
                print(f"Deleted: {f}")
            except OSError as e:
                print(f"Error deleting file {f}: {e}")

    except Exception as e:
        print(f"An error occurred during HLS file cleanup: {e}")

    # --- 3. Return Success ---
    return jsonify({"message": "Stream stopped and files cleaned successfully"}), 200


@app.route("/stream/status", methods=["GET"])
def get_status():
    """
    Checks the status of the streaming process.
    """
    global STREAM_PROCESS

    if STREAM_PROCESS:
        exit_code = STREAM_PROCESS.poll()
        if exit_code is None:
            return jsonify({"status": "running", "pid": STREAM_PROCESS.pid}), 200
        else:
            STREAM_PROCESS = None
            return jsonify({"status": "crashed", "exit_code": exit_code}), 200

    return jsonify({"status": "stopped"}), 200


# --- Main execution ---
if __name__ == "__main__":
    try:
        setup_script()
        print("Starting Flask server on http://0.0.0.0:5000")
        app.run(host="0.0.0.0", port=5000)
    except FileNotFoundError as e:
        print(f"Server could not start: {e}")
        exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        exit(1)
