from flask import Flask, jsonify, request
from llama_cpp import Llama
import time
import os
from stable_diffusion_cpp import StableDiffusion

# --- ANSI Color Codes ---
class TextColor:
    RESET = '\033[0m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RED = '\033[91m'

def colored_print(text: str, color_code: str):
    print(f"{color_code}{text}{TextColor.RESET}")

app = Flask(__name__)

# --- Configuration & Global Variables ---
LLAMA_MODEL_PATH = "gemma-2-2b-it-Q8_0.gguf"
STABLE_DIFFUSION_MODEL_PATH = "stable-diffusion-v1-5-pruned-emaonly-Q8_0.gguf"
IMAGE_OUTPUT_FOLDER = "generated_images"

text2text_model = None
text2image_pipe = None
loading_times = {"text2text": 0.0, "text2image": 0.0}

if not os.path.exists(IMAGE_OUTPUT_FOLDER):
    os.makedirs(IMAGE_OUTPUT_FOLDER)

def initialize_models():
    global text2text_model, text2image_pipe, loading_times

    # Initialize LLM
    start = time.perf_counter()
    try:
        text2text_model = Llama(model_path=LLAMA_MODEL_PATH, n_ctx=2048, verbose=False)
        loading_times["text2text"] = round(time.perf_counter() - start, 2)
        colored_print(f"Llama loaded: {loading_times['text2text']}s", TextColor.GREEN)
    except Exception as e:
        colored_print(f"LLM Error: {e}", TextColor.RED)

    # Initialize SD
    start = time.perf_counter()
    try:
        text2image_pipe = StableDiffusion(model_path=STABLE_DIFFUSION_MODEL_PATH, wtype="default")
        loading_times["text2image"] = round(time.perf_counter() - start, 2)
        colored_print(f"SD loaded: {loading_times['text2image']}s", TextColor.GREEN)
    except Exception as e:
        colored_print(f"SD Error: {e}", TextColor.RED)

@app.route("/loading-stats", methods=["GET"])
def get_loading_stats():
    """Returns the time taken to initialize models on startup."""
    return jsonify({
        "status": "ready" if text2text_model and text2image_pipe else "partial_failure",
        "loading_times_seconds": loading_times,
    })

# --- Text-to-Text Endpoint ---
@app.route("/text2text", methods=["GET"])
def query():
    prompt = request.args.get("prompt", "")
    if not text2text_model or not prompt:
        return jsonify({"error": "Model not ready or prompt missing"}), 400

    start_time = time.perf_counter()
    try:
        # Inference
        out = text2text_model(prompt, max_tokens=200, stream=False)
        end_time = time.perf_counter()

        # Calculate Metrics
        duration = end_time - start_time
        tokens_generated = out["usage"]["completion_tokens"]
        # TPS = Tokens Per Second
        tps = round(tokens_generated / duration, 2) if duration > 0 else 0

        return jsonify({
            "reply": out["choices"][0]["text"].strip(),
            "performance": {
                "processing_time_second": round(duration, 3),
                "tokens_per_second": tps,
                "input_tokens": out["usage"]["prompt_tokens"],
                "output_tokens": out["usage"]["completion_tokens"],
                "total_tokens": out["usage"]["total_tokens"]
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Text-to-Image Endpoint ---
@app.route("/text2image", methods=["GET"])
def generate_image():
    global text2image_pipe
    prompt = request.args.get("prompt", "")

    if not text2image_pipe or not prompt:
        return jsonify({"error": "Model not ready or prompt missing"}), 400

    start_time = time.perf_counter()
    try:
        colored_print(f"Generating image: {prompt}", TextColor.MAGENTA)

        # We build a dictionary of arguments to pass to the model
        # This allows us to conditionally include sample_steps only if provided
        kwargs = {
            "prompt": prompt,
            "sample_method": "euler_a",
            "width": 512,
            "height": 512
        }

        # Generate the image using unpacking (**)
        # If steps_arg was None, sample_steps is never sent to the library
        output = text2image_pipe.generate_image(**kwargs)

        duration = time.perf_counter() - start_time

        # Save Logic
        image = output[0]
        filename = f"img_{int(time.time())}.png"
        save_path = os.path.join(IMAGE_OUTPUT_FOLDER, filename)
        image.save(save_path)

        # Get actual file size in Bytes
        image_size_bytes = os.path.getsize(save_path)

        return jsonify({
            "status": "success",
            "filename": filename,
            "image_size_bytes": image_size_bytes,
            "processing_time_second": round(duration, 3),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

initialize_models()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000)