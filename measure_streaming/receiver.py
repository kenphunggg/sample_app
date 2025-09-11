#!/usr/bin/env python3

import subprocess
import threading
import re
import os
import signal
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- Global dictionary to hold the state of the monitoring process ---
monitor_state = {
    "process": None,
    "latest_data": {},
    "is_running": False,
    "srt_url": None,
}


def parse_ffmpeg_output(line):
    """
    Parses a single line of FFmpeg's progress output into a dictionary.
    """
    data = {}
    pairs = re.findall(r"(\w+)=\s*([^ ]+)", line)

    for key, value in pairs:
        try:
            if key in ["frame", "fps", "q", "size", "bitrate", "speed"]:
                if "kB" in value:
                    data[key] = float(value.replace("kB", ""))
                elif "kbits/s" in value:
                    data[key] = float(value.replace("kbits/s", ""))
                elif "x" in value:
                    data[key] = float(value.replace("x", ""))
                else:
                    data[key] = float(value)
            else:
                data[key] = value.strip()
        except ValueError:
            data[key] = value.strip()

    time_match = re.search(r"time=(\S+)", line)
    if time_match:
        data["time"] = time_match.group(1)

    return data


def ffmpeg_monitor_thread(process):
    """
    A thread that reads stderr from the ffmpeg process and updates the global state.
    """
    global monitor_state
    for line in iter(process.stderr.readline, b""):
        line_str = line.decode("utf-8").strip()
        if "frame=" in line_str and "fps=" in line_str:
            parsed_data = parse_ffmpeg_output(line_str)
            monitor_state["latest_data"] = parsed_data

    print("FFmpeg process has ended. Monitoring thread is stopping.")
    monitor_state["is_running"] = False


@app.route("/monitor/start/<ip_address>", methods=["GET"])
def start_monitor(ip_address):
    """Starts the FFmpeg monitoring process using an IP from the URL path."""
    global monitor_state

    if monitor_state["is_running"]:
        return jsonify({"error": "A monitor process is already running."}), 409

    if not ip_address:
        return jsonify({"error": "No IP address provided in the URL."}), 400

    # Build the full SRT URL from the provided IP
    srt_url = f"srt://{ip_address}:1935?mode=caller"

    command = ["ffmpeg", "-i", srt_url, "-f", "null", "-"]
    
    try:
        process = subprocess.Popen(command, stderr=subprocess.PIPE)
        
        monitor_state["process"] = process
        monitor_state["is_running"] = True
        monitor_state["srt_url"] = srt_url
        monitor_state["latest_data"] = {"status": "initializing..."}

        thread = threading.Thread(target=ffmpeg_monitor_thread, args=(process,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "message": f"FFmpeg monitoring started for {srt_url}",
            "pid": process.pid
        }), 201

    except FileNotFoundError:
        return jsonify({"error": "'ffmpeg' not found. Is it installed and in your PATH?"}), 500
    except Exception as e:
        return jsonify({"error": f"Failed to start monitor: {e}"}), 500


@app.route("/monitor/stop", methods=["GET"])
def stop_monitor():
    """Stops the running FFmpeg monitoring process."""
    global monitor_state

    if not monitor_state["is_running"] or not monitor_state["process"]:
        return jsonify({"error": "No monitor process is currently running."}), 404

    try:
        process = monitor_state["process"]
        os.kill(process.pid, signal.SIGTERM)
        process.wait(timeout=5)

        monitor_state["is_running"] = False
        monitor_state["process"] = None
        monitor_state["srt_url"] = None

        return jsonify({"message": "Monitor stopped successfully."}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to stop monitor: {e}"}), 500


@app.route("/monitor/latest", methods=["GET"])
def get_latest_data():
    """Returns the most recently parsed JSON data from the FFmpeg output."""
    if not monitor_state["is_running"]:
        return jsonify({"status": "stopped", "data": {}}), 200

    return jsonify(monitor_state["latest_data"])


@app.route("/monitor/status", methods=["GET"])
def get_status():
    """Returns the overall status of the monitor."""
    return jsonify(
        {
            "is_running": monitor_state["is_running"],
            "pid": monitor_state["process"].pid if monitor_state["process"] else None,
            "monitoring_url": monitor_state["srt_url"],
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
