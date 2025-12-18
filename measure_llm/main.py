from flask import Flask, jsonify, request
from llama_cpp import Llama
import time
from typing import Dict, Any, Union
import os
from stable_diffusion_cpp import StableDiffusion

# --- ANSI Color Codes (Helper) ---
class TextColor:
    """Class containing ANSI color codes."""
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'

def colored_print(text: str, color_code: str):
    """Prints text in the specified color."""
    print(f"{color_code}{text}{TextColor.RESET}")
# ---------------------------------

# --- Flask Initialization ---
app = Flask(__name__)

# --- Initialize Models ---
# Global variables for models
text2text_model: Llama = None
text2image_pipe: StableDiffusion = None
loading_times = {
    "llm_load_time": 0.0,
    "sd_load_time": 0.0
}

# --- Configuration ---
LLAMA_MODEL_PATH = "gemma-2-2b-it-Q8_0.gguf"
STABLE_DIFFUSION_MODEL_PATH = "stable-diffusion-v1-5-pruned-emaonly-Q8_0.gguf"
IMAGE_OUTPUT_FOLDER = "generated_images"

# Create the output folder if it doesn't exist
if not os.path.exists(IMAGE_OUTPUT_FOLDER):
    os.makedirs(IMAGE_OUTPUT_FOLDER)

def initialize_models():
    """Initializes models and records the time taken to load each."""
    global text2text_model, text2image_pipe, loading_times

    # 1. Initialize LLM
    colored_print("Initializing Text-to-Text Model...", TextColor.CYAN)
    start = time.time()
    try:
        text2text_model = Llama(
            model_path=LLAMA_MODEL_PATH,
            n_gpu_layers=0,
            n_threads=8,
            verbose=False
        )
        loading_times["llm_load_time"] = round(time.time() - start, 2)
        colored_print(f"Llama Model loaded in: {loading_times['llm_load_time']}s", TextColor.GREEN)
    except Exception as e:
        colored_print(f"Error loading Llama model: {e}", TextColor.RED)

    # 2. Initialize Stable Diffusion
    colored_print("Initializing Text-to-Image Model...", TextColor.CYAN)
    start = time.time()
    try:
        text2image_pipe = StableDiffusion(
            model_path=STABLE_DIFFUSION_MODEL_PATH,
            wtype="default",
        )
        loading_times["sd_load_time"] = round(time.time() - start, 2)
        colored_print(f"SD Model loaded in: {loading_times['sd_load_time']}s", TextColor.GREEN)
    except Exception as e:
        colored_print(f"Error loading SD model: {e}", TextColor.RED)

# --- Text-to-Text Endpoint (Original) ---
@app.route("/text2text", methods=["GET"])
def query() -> Dict[str, Union[str, int]]:
    global text2text_model, loading_times

    # 1. Log Incoming Request
    prompt = request.args.get("prompt", "")
    colored_print(f"--- Incoming Text2Text Request ---", TextColor.CYAN)
    colored_print(f"Prompt: {prompt[:50]}..." if len(prompt) > 50 else f"Prompt: {prompt}", TextColor.YELLOW)

    if not text2text_model:
        colored_print("Error: Text-to-Text model is not initialized.", TextColor.RED)
        return jsonify({"error": "Text-to-Text model is not initialized."}), 503

    if not prompt:
        colored_print("Error: Missing 'prompt' query parameter.", TextColor.RED)
        return jsonify({"error": "Missing 'prompt' query parameter."}), 400

    # 2. Process and Log LLM Call
    inference_start = time.monotonic()
    try:
        out = text2text_model(prompt, max_tokens=200, stream=False)
        inference_time = round(time.monotonic() - inference_start, 2)

        reply = out["choices"][0]["text"]

        # 3. Log Success and Metrics
        colored_print(f"Inference complete in {inference_time}s", TextColor.GREEN)
        colored_print(f"Model Load Reference: LLM({loading_times['llm_load_time']}s) SD({loading_times['sd_load_time']}s)", TextColor.BLUE)

        return jsonify({
            "reply": reply,
            "text2text_loading_time": loading_times["llm_load_time"],
            "text2image_loading_time": loading_times["sd_load_time"]
        })

    except Exception as e:
        colored_print(f"Exception during inference: {e}", TextColor.RED)
        return jsonify({"error": "Internal model error"}), 500

@app.route("/text2text/time/<int:duration>", methods=["GET"])
def query_timed(duration):
    global text2text_model
    if not text2text_model:
        return jsonify({"error": "Text-to-Text model is not initialized."}), 503

    prompt = request.args.get("prompt", "")
    if not prompt:
        return jsonify({"error": "Missing 'prompt' query parameter."}), 400

    start_time = time.monotonic()
    count = 0

    colored_print(f"--- Starting timed Text Generation for {duration}s ---", TextColor.CYAN)

    while time.monotonic() - start_time <= duration:
        try:
            # Generate but we don't need to store the result in a list anymore
            text2text_model(prompt, max_tokens=150, stream=False)
            count += 1
            colored_print(f"Generated response {count}", TextColor.GREEN)
            time.sleep(0.01)
        except Exception as e:
            colored_print(f"Error: {e}", TextColor.RED)
            break

    # Only return success and model loading time
    return jsonify({
        "success": True,
    }), 200


# --- NEW Text-to-Image Endpoint ---
@app.route("/text2image", methods=["GET"])
def generate_image():
    global text2image_pipe
    if not text2image_pipe:
        return jsonify({"error": "Text-to-Image model is not initialized."}), 503

    prompt = request.args.get("prompt", "")
    width = 512
    height = 512
    seed = int(request.args.get("seed", -1))

    if not prompt:
        return jsonify({"error": "Missing 'prompt' query parameter."}), 400

    # New colored print for generation
    colored_print(f"Generating image for prompt: '{prompt}'", TextColor.MAGENTA)
    try:
        # ... (image generation logic remains the same) ...
        output = text2image_pipe.generate_image(
            prompt=prompt,
            sample_method="euler_a",
            width=width,
            height=height,
            seed=seed
        )

        image = output[0]
        timestamp = int(time.time())
        filename = f"image_{timestamp}.png"
        save_path = os.path.join(IMAGE_OUTPUT_FOLDER, filename)

        image.save(save_path)
        colored_print(f"Image saved to: {save_path}", TextColor.GREEN) # Success message color

        return jsonify({
            "status": "success",
            "message": "Image generated successfully.",
            "prompt": prompt,
            "filename": filename,
            "path": save_path
        })
    except Exception as e:
        colored_print(f"An error occurred during image generation: {e}", TextColor.RED) # Error message color
        return jsonify({
            "status": "error",
            "message": f"An error occurred during image generation: {e}"
        }), 500

@app.route("/text2image/time/<int:duration>", methods=["GET"])
def generate_image_timed(duration):
    global text2image_pipe
    if not text2image_pipe:
        return jsonify({"error": "Text-to-Image model is not initialized."}), 503

    prompt = request.args.get("prompt", "")
    if not prompt:
        return jsonify({"error": "Missing 'prompt' query parameter."}), 400

    width = 512
    height = 512

    start_time = time.monotonic()
    images_generated = 0
    generated_files = []

    colored_print(f"--- Starting timed Image Generation for {duration}s ---", TextColor.CYAN)

    # The loop runs until the duration is exceeded
    while time.monotonic() - start_time <= duration:
        try:
            iteration_start = time.monotonic()
            colored_print(f"Generating image {images_generated + 1}...", TextColor.MAGENTA)

            # Generate the image
            output = text2image_pipe.generate_image(
                prompt=prompt,
                sample_method="euler_a",
                width=width,
                height=height
            )

            # Save the image with a unique name
            image = output[0]
            timestamp = int(time.time())
            filename = f"timed_{timestamp}_{images_generated}.png"
            save_path = os.path.join(IMAGE_OUTPUT_FOLDER, filename)
            image.save(save_path)

            generated_files.append(filename)
            images_generated += 1

            colored_print(f"Image {images_generated} saved: {filename}", TextColor.GREEN)

            # Small safety sleep to prevent CPU spiking between calls
            time.sleep(0.1)

        except Exception as e:
            colored_print(f"Error during timed generation: {e}", TextColor.RED)
            break

    colored_print(f"--- Timed processing finished. Generated {images_generated} images. ---", TextColor.CYAN)

    return jsonify({
        "success": True,
        "total_images": images_generated,
        "files": generated_files,
        "duration_requested": duration,
        "actual_time": round(time.monotonic() - start_time, 2)
    }), 200

if __name__ == "__main__":
    initialize_models()
    colored_print("Flask server starting on http://0.0.0.0:8000", TextColor.YELLOW)
    app.run(host='0.0.0.0', port=8000)