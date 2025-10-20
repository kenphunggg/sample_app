import os
import threading
import time
from torch import hub
from cv2 import VideoCapture
from flask import Flask, jsonify

app = Flask(__name__)

# --- Model Loading ---
# Load the model once when the application starts.
try:
    print("Loading YOLOv5 model...")
    model = hub.load("ultralytics/yolov5", "yolov5n", pretrained=True)
    print("Model loaded successfully.")
except Exception as e:
    print(f"FATAL: Could not load model. Error: {e}")
    model = None

# --- API Endpoints ---


@app.route("/stream/time/<int:duration>", methods=["GET"])
def handle_streaming_timed(duration):
    """
    API endpoint to process a stream for a specific duration.
    """
    if not model:
        return jsonify({"success": False, "error": "Model is not loaded"}), 500

    # Read the stream source from an environment variable
    rtmp_source = os.environ.get("RTMP_STREAM_URL", "192.168.17.130:2000")
    if not rtmp_source:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "RTMP_STREAM_URL environment variable not set.",
                }
            ),
            500,
        )

    try:
        detect_streaming(rtmp_streaming_url=rtmp_source, time_to_detect=duration)
    except Exception as e:
        print(f"Error during timed streaming: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    return jsonify({"success": True, "message": "Timed detection complete."}), 200


@app.route("/stream", methods=["GET"])
def handle_first_frame_streaming():
    """
    API endpoint that captures one frame, analyzes it, and returns the stats as JSON.
    """
    if not model:
        return jsonify({"success": False, "error": "Model is not loaded"}), 500

    # Read the stream source from an environment variable
    rtmp_source = os.environ.get("RTMP_STREAM_URL", "192.168.17.130:2000")
    if not rtmp_source:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "RTMP_STREAM_URL environment variable not set.",
                }
            ),
            500,
        )

    try:
        analysis_data = detect_one_frame(rtmp_streaming_url=rtmp_source)
        if analysis_data and analysis_data.get("success"):
            return jsonify(analysis_data), 200
        else:
            error_message = analysis_data.get(
                "error", "Unknown error during frame detection."
            )
            return jsonify({"success": False, "error": error_message}), 500

    except Exception as e:
        print(f"An unexpected error occurred in the API handler: {e}")
        return (
            jsonify(
                {"success": False, "error": "An unexpected server error occurred."}
            ),
            500,
        )


# --- Core Detection Logic (No changes needed here) ---


def detect_streaming(rtmp_streaming_url: str, time_to_detect: int):
    """
    Processes a stream for a given duration, printing results to the console.
    """
    path = f"rtmp://{rtmp_streaming_url}/live/source"
    cap = VideoCapture(path)
    if not cap.isOpened():
        print(f"Error: Could not open stream at {path}")
        return

    start_time = time.monotonic()
    frame_number = 0
    while time.monotonic() - start_time <= time_to_detect:
        ret, frame = cap.read()
        if not ret:
            print("Stream ended or frame could not be read.")
            break

        frame_number += 1
        print(f"\n--- FRAME {frame_number} | {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
        results = model(frame)
        results.print()
        print(results.pandas().xyxy[0])

    cap.release()
    print("--- Timed detection finished. ---")
    return


def detect_one_frame(rtmp_streaming_url: str):
    """
    Captures a single frame, analyzes it, and returns a dictionary with performance stats.
    """
    path = f"rtmp://{rtmp_streaming_url}/live/source"
    cap = VideoCapture(path)

    if not cap.isOpened():
        return {"success": False, "error": f"Could not connect to stream at {path}"}

    ret, frame = cap.read()
    cap.release()

    if not ret:
        return {"success": False, "error": "Failed to read a frame from the stream."}

    results = model(frame)
    preprocess_ms = results.t[0]
    inference_ms = results.t[1]
    nms_ms = results.t[2]
    df = results.pandas().xyxy[0]
    confidences = df["confidence"].tolist() if not df.empty else []
    summary_string = str(results)

    return {
        "success": True,
        "preprocess_ms": round(preprocess_ms, 2),
        "inference_ms": round(inference_ms, 2),
        "nms_ms": round(nms_ms, 2),
        "confidences": confidences,
        "detections_summary": summary_string.strip(),
    }


if __name__ == "__main__":
    # The application is now started via run.sh with gunicorn
    # This block can be left for direct `python main.py` testing if needed
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
