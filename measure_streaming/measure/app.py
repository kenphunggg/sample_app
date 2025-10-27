import os
import subprocess

from flask import Flask, jsonify, request

app = Flask(__name__)

# --- Global state ---
STREAM_PROCESS = None
# The script must exist in the same directory
SCRIPT_PATH = "measure.sh"


def setup_script():
    """
    Checks if measure.sh exists and makes it executable.
    """
    # Check if the script file exists
    if not os.path.exists(SCRIPT_PATH):
        print(f"Error: '{SCRIPT_PATH}' not found.")
        print("Please create the 'measure.sh' file in the same directory.")
        # Raise an error to stop the server from starting
        raise FileNotFoundError(f"{SCRIPT_PATH} is required to run this server.")

    try:
        # Make the script executable (chmod +x)
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
    Source IP is determined in this order:
    1. URL parameter: /stream/start?source_ip=YOUR_IP
    2. Environment variable: docker run -e SOURCE_IP=YOUR_IP
    3. Hardcoded default
    """
    global STREAM_PROCESS

    # Check if process is already running
    if STREAM_PROCESS and STREAM_PROCESS.poll() is None:
        return jsonify({"error": "Stream is already running"}), 400

    # --- UPDATED IP LOGIC ---
    # 1. Check URL query arguments
    url_ip = request.args.get("source_ip")

    # 2. If not in URL, check the container's environment variables
    env_ip = os.environ.get("SOURCE_IP")

    # 3. If not in either, use the hardcoded default
    default_ip = "192.168.17.161"

    # Prioritize URL, then Env Var, then Default
    source_ip = url_ip or env_ip or default_ip
    # --- END UPDATED LOGIC ---

    # Set the SOURCE_IP environment variable for the subprocess
    env = os.environ.copy()
    env["SOURCE_IP"] = source_ip

    print(f"Starting stream from source: {source_ip}")

    # Start the external script
    STREAM_PROCESS = subprocess.Popen(["/bin/bash", SCRIPT_PATH], env=env)

    return jsonify(
        {
            "message": "Stream started successfully",
            "pid": STREAM_PROCESS.pid,
            "source_ip": source_ip,
        }
    ), 200


@app.route("/stream/stop", methods=["GET"])
def stop_stream():
    """
    Stops the running transcoding script gracefully.
    """
    global STREAM_PROCESS

    if not STREAM_PROCESS or STREAM_PROCESS.poll() is not None:
        return jsonify({"error": "Stream is not running"}), 400

    print(f"Stopping stream process (PID {STREAM_PROCESS.pid})...")

    # Send SIGTERM (terminate) signal.
    # The script's 'trap' will catch this and clean up Nginx.
    STREAM_PROCESS.terminate()

    try:
        # Wait up to 10 seconds for graceful shutdown
        STREAM_PROCESS.wait(timeout=10)
        print("Process terminated gracefully.")
    except subprocess.TimeoutExpired:
        # If it doesn't stop, force-kill it
        print("Process did not terminate, sending SIGKILL.")
        STREAM_PROCESS.kill()
        STREAM_PROCESS.wait()

    STREAM_PROCESS = None
    return jsonify({"message": "Stream stopped successfully"}), 200


@app.route("/stream/status", methods=["GET"])
def get_status():
    """
    Checks the status of the streaming process.
    """
    global STREAM_PROCESS

    if STREAM_PROCESS:
        # poll() returns None if running, or exit code if stopped
        exit_code = STREAM_PROCESS.poll()

        if exit_code is None:
            # Process is still running
            return jsonify({"status": "running", "pid": STREAM_PROCESS.pid}), 200
        else:
            # Process has stopped/crashed
            STREAM_PROCESS = None  # Clear the dead process
            return jsonify({"status": "crashed", "exit_code": exit_code}), 200

    # No process
    return jsonify({"status": "stopped"}), 200


# --- Main execution ---
if __name__ == "__main__":
    try:
        # Check for measure.sh and make it executable on startup
        setup_script()

        # Run the Flask app
        print("Starting Flask server on http://0.0.0.0:5000")
        app.run(host="0.0.0.0", port=5000)

    except FileNotFoundError as e:
        print(f"Server could not start: {e}")
        exit(1)  # Exit with an error code
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        exit(1)
