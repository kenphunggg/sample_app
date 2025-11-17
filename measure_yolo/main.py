import os
import time
import cv2
import numpy as np
from PIL import Image
from flask import Flask, jsonify, request
from torch import hub

app = Flask(__name__)

# --- Model Loading ---
# Model is set to None initially and will be loaded via API.
model = None
print("Model is initially unloaded. Use POST /model/load to load it.")

MODEL_PATH = "yolov5n.pt"

# --- API Endpoints ---
@app.route("/model/load", methods=["GET"])
def load_model():
    """
    API endpoint to load the YOLOv5 model into memory.
    This version loads from a LOCAL model file.
    """
    global model
    if model is not None:
        return jsonify({"success": True, "message": "Model is already loaded."}), 200

    # Check if the model file exists before trying to load it
    if not os.path.exists(MODEL_PATH):
        print(f"FATAL: Model file not found at {MODEL_PATH}")
        return jsonify({"success": False, "error": f"Model file not found at {MODEL_PATH}"}), 500

    try:
        # --- This version loads from a local file ---
        print(f"Loading local model from {MODEL_PATH}...")

        # 'ultralytics/yolov5': Still needed, as it's the repo that defines the model *code*.
        # 'custom': Tells hub.load you are providing your own weights file.
        # path=MODEL_PATH: Points to your local .pt file.
        # source='local': CRITICAL! This tells hub.load to NOT check the internet.
        model = hub.load("ultralytics/yolov5", "custom", path=MODEL_PATH, source="local")
        # --- End of logic ---

        print("Model loaded successfully.")
        return jsonify({"success": True, "message": "Model loaded successfully."}), 200

    except Exception as e:
        print(f"FATAL: Could not load model. Error: {e}")
        model = None
        # This will fail in Knative with a connection error
        return jsonify({"success": False, "error": f"Failed to load model: {str(e)}"}), 500


@app.route("/model/unload", methods=["GET"])
def unload_model():
    """
    API endpoint to unload the YOLOv5 model from memory.
    """
    global model
    if model is None:
        return jsonify({"success": True, "message": "Model is already unloaded."}), 200

    print("Unloading model...")
    model = None
    # Note: This just removes the reference. Python's garbage collector
    # will free the memory if there are no other references.
    # For more complex GPU memory, torch.cuda.empty_cache() might be needed
    # but for this simple case, setting to None is sufficient.
    print("Model unloaded.")
    return jsonify({"success": True, "message": "Model unloaded."}), 200


@app.route("/detect/time/<int:duration>", methods=["POST"])
def handle_image_upload_timed(duration):
    """
    API endpoint that accepts an image upload, continuously processes
    that single image for a specific duration, and then returns "done".
    """
    if not model:
        return jsonify({"success": False, "error": "Model is not loaded. Use POST /model/load."}), 503

    # Check if an image file is part of the request
    if 'image' not in request.files:
        return jsonify({"success": False, "error": "No 'image' file part in the request"}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"success": False, "error": "No selected file"}), 400

    try:
        # Read image using PIL, convert to NumPy array
        img_pil = Image.open(file.stream)
        frame = np.array(img_pil)

        # Ensure image is in BGR format for OpenCV compatibility if it's color
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        elif len(frame.shape) == 3 and frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)

        # --- Timed Processing Loop ---
        start_time = time.monotonic()
        print(f"--- Starting timed processing for {duration}s ---")
        while time.monotonic() - start_time <= duration:
            # Continuously process the *same* frame
            analysis_data = detect_one_frame(frame)
            if not analysis_data.get("success"):
                # Stop if an error occurs during processing
                error_message = analysis_data.get(
                    "error", "Unknown error during processing."
                )
                return jsonify({"success": False, "error": error_message}), 500
            # Optional: Log to console to show work is being done
            print(f"Processed frame, summary: {analysis_data.get('detections_summary')}")
            # Add a small delay to prevent 100% CPU lock in the loop
            time.sleep(0.01)

        print("--- Timed processing finished. ---")
        # Return "done" as requested
        return jsonify({"success": True, "message": "Timed detection complete."}), 200

    except Exception as e:
        print(f"An unexpected error occurred in the API handler: {e}")
        return (
            jsonify(
                {"success": False, "error": f"An unexpected server error occurred: {str(e)}"}
            ),
            500,
        )


@app.route("/detect", methods=["POST"])
def handle_image_upload():
    """
    API endpoint that accepts an image upload, analyzes it, and returns
    a structured JSON response with detection text and timings.
    """
    if not model:
        # Return 503 Service Unavailable if model isn't ready
        return jsonify({"success": False, "error": "Model is not loaded. Use POST /model/load."}), 503

    # Check if an image file is part of the request
    if 'image' not in request.files:
        return jsonify({"success": False, "error": "No 'image' file part in the request"}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"success": False, "error": "No selected file"}), 400

    try:
        # --- Start Timer ---
        # Use a monotonic clock for reliable duration measurement
        start_time = time.monotonic()

        # Read image using PIL, convert to NumPy array
        # This handles decompression (e.g., from JPG)
        img_pil = Image.open(file.stream)
        frame = np.array(img_pil)

        # Ensure image is in BGR format for OpenCV/YOLO compatibility
        # PIL loads as RGB, but OpenCV (which YOLO uses) expects BGR
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            # Convert RGB (PIL) to BGR (OpenCV)
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        elif len(frame.shape) == 3 and frame.shape[2] == 4:
            # Handle RGBA images (e.g., PNGs) by converting and dropping alpha
            frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)

        # Run detection
        analysis_data = detect_one_frame(frame)  # Pass the BGR NumPy frame

        # --- End Timer ---
        end_time = time.monotonic()
        # Calculate total processing time in milliseconds
        total_processing_time_ms = round((end_time - start_time) * 1000, 2)

        if analysis_data and analysis_data.get("success"):
            # Return the structured JSON response
            return jsonify({
                "success": True,
                "text": analysis_data.get("detections_summary"),
                "total_server_time_ms": total_processing_time_ms,
                "model_preprocess_ms": analysis_data.get("preprocess_ms"),
                "model_inference_ms": analysis_data.get("inference_ms"),
                "model_nms_ms": analysis_data.get("nms_ms"),
                "confidences": analysis_data.get("confidences")
            }), 200
        else:
            # Handle errors from the detection function
            error_message = analysis_data.get(
                "error", "Unknown error during frame detection."
            )
            return jsonify({
                "success": False,
                "error": error_message,
                "total_server_time_ms": total_processing_time_ms
            }), 500

    except Exception as e:
        # Catch-all for server-level errors (e.g., file read error)
        print(f"An unexpected error occurred in the API handler: {e}")
        return (
            jsonify(
                {"success": False, "error": f"An unexpected server error occurred: {str(e)}"}
            ),
            500,
        )


# --- Core Detection Logic ---


def detect_one_frame(frame):
    """
    Analyzes a single frame (as a numpy array) and returns a dictionary
    with performance stats and detection summary.
    """
    if frame is None:
        return {"success": False, "error": "Invalid frame provided."}

    if not model:
        return {"success": False, "error": "Model is not loaded."}

    try:
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
    except Exception as e:
        print(f"Error during model inference: {e}")
        return {"success": False, "error": f"Inference failed: {str(e)}"}


if __name__ == "__main__":
    # This block is for direct `python main.py` testing
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

