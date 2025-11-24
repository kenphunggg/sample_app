import os
import time
import cv2
import numpy as np
from PIL import Image
from flask import Flask, jsonify, request
from torch import hub
import sys
import threading

app = Flask(__name__)

# --- Color Codes for Terminal Output ---
class Colors:
    HEADER = '\033[95m'  # Purple
    BLUE = '\033[94m'    # Blue
    CYAN = '\033[96m'    # Cyan
    GREEN = '\033[92m'   # Green
    WARNING = '\033[93m' # Yellow
    FAIL = '\033[91m'    # Red
    ENDC = '\033[0m'     # Reset color
    BOLD = '\033[1m'     # Bold

# --- Global Model State ---
model = None
MODEL_STATUS = "LOADING" # Options: "LOADING", "READY", "FAILED"
MODEL_ERROR = None       # To store the exception message if loading fails
MODEL_LOAD_TIME = 0.0    # Stores how long (in seconds) the model took to load

def load_model_background():
    """
    Function running in a separate thread to load the model
    without blocking the Flask server from starting.
    """
    global model, MODEL_STATUS, MODEL_ERROR, MODEL_LOAD_TIME
    
    print(f"{Colors.BLUE}Loading 'yolov5n' from LOCAL files...{Colors.ENDC}")
    
    # Start timer for model loading
    load_start_time = time.monotonic()

    try:
        print(f"{Colors.BLUE}Downloading/Loading 'yolov5n' from Ultralytics GitHub...{Colors.ENDC}")
        
        # Load the model
        # trust_repo=True allows it to run without prompt (required for automation)
        loaded_model = hub.load(
            '/app/ultralytics/yolov5',  # Path to the cloned repo (contains hubconf.py)
            'custom',                   # Use 'custom' to load specific weights file
            path='/app/yolov5n.pt',     # Path to your local .pt file
            source='local'              # Tells torch to look locally, not GitHub
        )
        
        # Calculate load duration
        MODEL_LOAD_TIME = round(time.monotonic() - load_start_time)
        
        # Assign to global variable
        model = loaded_model
        MODEL_STATUS = "READY"
        print(f"{Colors.GREEN}{Colors.BOLD}Model loaded successfully in {MODEL_LOAD_TIME}s. Status: READY{Colors.ENDC}")

    except Exception as e:
        MODEL_STATUS = "FAILED"
        MODEL_ERROR = str(e)
        print(f"{Colors.FAIL}{Colors.BOLD}FATAL: Could not load model. Error: {e}{Colors.ENDC}")

# Start the loading process in a background thread immediately
loader_thread = threading.Thread(target=load_model_background, daemon=True)
loader_thread.start()


# --- API Endpoints ---

@app.route("/detect/time/<int:duration>", methods=["POST"])
def handle_image_upload_timed(duration):
    # --- INLINE WAIT LOOP ---
    # Get timeout from ENV, default to 60 seconds
    wait_timeout = int(os.environ.get("MODEL_LOAD_TIMEOUT", 60))
    start_wait = time.time()
    
    while MODEL_STATUS == "LOADING":
        if time.time() - start_wait > wait_timeout:
            return jsonify({
                "success": False, 
                "error": f"Timeout ({wait_timeout}s) waiting for model to load."
            }), 503
        time.sleep(0.1) # Check every 100ms

    # If loading failed, return the specific error
    if MODEL_STATUS == "FAILED":
        return jsonify({"success": False, "error": f"Model load failed: {MODEL_ERROR}"}), 500

    # --- Proceed with Request ---
    if 'image' not in request.files:
        return jsonify({"success": False, "error": "No 'image' file part in the request"}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"success": False, "error": "No selected file"}), 400

    try:
        img_pil = Image.open(file.stream)
        frame = np.array(img_pil)

        if len(frame.shape) == 3 and frame.shape[2] == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        elif len(frame.shape) == 3 and frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)

        # --- Timed Processing Loop ---
        start_time = time.monotonic()
        print(f"{Colors.CYAN}--- Starting timed processing for {duration}s ---{Colors.ENDC}")
        
        while time.monotonic() - start_time <= duration:
            analysis_data = detect_one_frame(frame)
            if not analysis_data.get("success"):
                error_message = analysis_data.get("error", "Unknown error.")
                print(f"{Colors.FAIL}Error in loop: {error_message}{Colors.ENDC}")
                return jsonify({"success": False, "error": error_message}), 500
            
            time.sleep(0.01)

        print(f"{Colors.GREEN}--- Timed processing finished. ---{Colors.ENDC}")
        return jsonify({"success": True, "message": "Timed detection complete."}), 200

    except Exception as e:
        print(f"{Colors.FAIL}An unexpected error occurred: {e}{Colors.ENDC}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/detect", methods=["POST"])
def handle_image_upload():
    # --- INLINE WAIT LOOP ---
    # Get timeout from ENV, default to 6000 seconds
    wait_timeout = int(os.environ.get("MODEL_LOAD_TIMEOUT", 6000))
    start_wait = time.time()
    
    while MODEL_STATUS == "LOADING":
        if time.time() - start_wait > wait_timeout and wait_timeout != 0:
            return jsonify({
                "success": False, 
                "error": f"Timeout ({wait_timeout}s) waiting for model to load."
            }), 503
        time.sleep(0.1)

    # If loading failed, return the specific error
    if MODEL_STATUS == "FAILED":
        return jsonify({"success": False, "error": f"Model load failed: {MODEL_ERROR}"}), 500

    # --- Proceed with Request ---
    if 'image' not in request.files:
        return jsonify({"success": False, "error": "No 'image' file part"}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"success": False, "error": "No selected file"}), 400

    try:
        start_time = time.monotonic()

        img_pil = Image.open(file.stream)
        frame = np.array(img_pil)

        if len(frame.shape) == 3 and frame.shape[2] == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        elif len(frame.shape) == 3 and frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)

        analysis_data = detect_one_frame(frame) 

        end_time = time.monotonic()
        total_time = round((end_time - start_time) * 1000, 2)

        if analysis_data and analysis_data.get("success"):
            return jsonify({
                "success": True,
                "text": analysis_data.get("detections_summary"),
                "total_server_time_ms": total_time,
                "model_loading_time_ms": MODEL_LOAD_TIME*1000, 
                "model_preprocess_ms": analysis_data.get("preprocess_ms"),
                "model_inference_ms": analysis_data.get("inference_ms"),
                "model_nms_ms": analysis_data.get("nms_ms"),
                "confidences": analysis_data.get("confidences")
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": analysis_data.get("error", "Unknown error"),
                "total_server_time_ms": total_time
            }), 500

    except Exception as e:
        print(f"{Colors.FAIL}Error in handler: {e}{Colors.ENDC}")
        return jsonify({"success": False, "error": str(e)}), 500


# --- Core Detection Logic ---

def detect_one_frame(frame):
    if frame is None:
        return {"success": False, "error": "Invalid frame provided."}

    if MODEL_STATUS != "READY" or not model:
        return {"success": False, "error": f"Model not ready. Status: {MODEL_STATUS}"}

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
        print(f"{Colors.FAIL}Error during inference: {e}{Colors.ENDC}")
        return {"success": False, "error": f"Inference failed: {str(e)}"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))