from flask import Flask, jsonify, request
from llama_cpp import Llama
import time
from typing import Dict, Any, Union
import io
import sys
import re

# --- Flask Initialization ---
app = Flask(__name__)

# --- Initialize LLM ---
start_time = time.time()
llm = Llama(
    model_path="gemma-2-2b-it-Q8_0.gguf",
    n_gpu_layers=0,
    n_threads=8,
    verbose=True  # Keep this for console logging/fallback capture
)
end_time = time.time()
model_load_time = end_time - start_time
print(f"Model loading time: {model_load_time} seconds")

# --- Helper function to parse the console output (Fallback method) ---
def parse_llama_perf_from_stdout(output: str) -> Dict[str, Union[float, int]]:
    # ... (Keep the robust parsing logic from the previous successful attempt,
    # as it remains the necessary FALLBACK if the API call fails) ...

    metrics = {
        "load_time_ms": 0.0, "prompt_eval_time_ms": 0.0, "prompt_tokens": 0, "prompt_tps": 0.0,
        "eval_time_ms": 0.0, "eval_tokens": 0, "eval_tps": 0.0, "total_time_ms": 0.0, "graphs_reused": 0
    }

    # --- CRITICAL FIX: AGGRESSIVE STRING CLEANUP AND LINE-BY-LINE EXTRACTION ---
    # (Reusing the robust parsing logic from the previous step)
    sanitized_output = output.replace('\xa0', ' ').strip()

    # Regex for complex performance lines
    perf_line_pattern = re.compile(
        r"llama_perf_context_print: ([\w\s]+) = ([\d\.]+) ms / (\d+) (tokens|runs) \( ([\d\.]+) ms per token, ([\d\.]+) tokens per second\)"
    )

    for line in sanitized_output.splitlines():
        # Clean line further for reliable parsing
        line_clean = re.sub(r'[\s]+', ' ', line.strip())

        # Try Complex Performance Line (Prompt/Eval)
        match_perf = perf_line_pattern.search(line)
        if match_perf:
            metric_name = match_perf.group(1).strip()
            time_ms = float(match_perf.group(2))
            tokens_runs = int(match_perf.group(3))
            tps = float(match_perf.group(6))

            if 'prompt eval time' in metric_name:
                metrics['prompt_eval_time_ms'] = time_ms
                metrics['prompt_tokens'] = tokens_runs
                metrics['prompt_tps'] = tps
            elif 'eval time' in metric_name:
                metrics['eval_time_ms'] = time_ms
                metrics['eval_tokens'] = tokens_runs
                metrics['eval_tps'] = tps
            continue

        # Try Simple Lines (Load Time, Total Time, Graphs Reused)
        if "load time" in line:
            match = re.search(r"load time = ([\d\.]+) ms", line)
            if match:
                metrics['load_time_ms'] = float(match.group(1))

        elif "total time" in line:
            match = re.search(r"total time = ([\d\.]+) ms", line)
            if match:
                metrics['total_time_ms'] = float(match.group(1))

        elif "graphs reused" in line:
             match = re.search(r"graphs reused = (\d+)", line)
             if match:
                metrics['graphs_reused'] = int(match.group(1))

    if metrics['prompt_tokens'] == 0 or metrics['eval_tokens'] == 0:
         return {}

    return metrics


@app.route("/query", methods=["GET"])
def query() -> tuple[Union[Dict[str, Any], str], int]:
    prompt = request.args.get("prompt", "")
    if not prompt:
        return jsonify({"error": "Missing 'prompt' query parameter."}), 400

    # --- 0. Try getting metrics directly from the API method ---
    # We must run the LLM call before trying to get metrics.
    generation_start_time = time.time()
    out = llm(prompt, max_tokens=200, stream=False)
    generation_end_time = time.time()

    parsed_metrics = {}
    api_success = False

    # Try the standard API method for retrieving performance info
    if hasattr(llm, 'eval_times'):
        try:
            # Note: The exact structure of eval_times() varies by version,
            # but this is the cleanest way to check for success.
            # We assume it returns a dictionary or an object with the required keys.
            api_metrics = llm.eval_times()
            if isinstance(api_metrics, dict) and api_metrics.get('prompt_eval_time'):
                parsed_metrics = {
                    'prompt_eval_time_ms': api_metrics['prompt_eval_time'] * 1000,
                    'eval_time_ms': api_metrics['eval_time'] * 1000,
                    'prompt_tokens': api_metrics['n_prompt_tokens'],
                    'eval_tokens': api_metrics['n_eval_tokens'],
                    'prompt_tps': api_metrics['prompt_tps'],
                    'eval_tps': api_metrics['eval_tps'],
                    'total_time_ms': api_metrics['total_time'] * 1000,
                    # We can't guarantee load time or graphs reused from this generic method
                }
                api_success = True
        except Exception as e:
            # API method exists but failed (e.g., not properly implemented in C++ binding)
            print(f"API method llm.eval_times() failed: {e}. Falling back to STDOUT capture.")

    # --- FALLBACK: If API method failed, use STDOUT capture and parsing ---
    if not api_success:
        # Re-run the LLM call while capturing stdout
        old_stdout = sys.stdout
        redirected_output = io.StringIO()
        sys.stdout = redirected_output

        # Note: We must re-run the LLM call inside the capture block
        try:
            llm(prompt, max_tokens=200, stream=False)
        except Exception:
            pass # Ignore generation error during second run if needed

        finally:
            sys.stdout = old_stdout
            captured_text = redirected_output.getvalue()
            # Print the captured text back to the real console
            print(captured_text, end="")

        parsed_metrics = parse_llama_perf_from_stdout(captured_text)

    # Check if parsing was successful
    if parsed_metrics.get("prompt_tokens", 0) == 0:
         return jsonify({
            "error": "Metrics retrieval failed.",
            "detail": "Failed to get metrics via API method and failed to parse metrics via stdout capture. The library's metrics output is inaccessible."
        }), 500

    # --- 5. Structure the Latency Data ---

    model_load_time_ms = round(model_load_time * 1000, 2)

    perf_data = {
        "model_load_time_ms": model_load_time_ms,
        "total_request_time_ms": round((generation_end_time - generation_start_time) * 1000, 2),

        "prompt_eval": {
            "time_ms": parsed_metrics.get('prompt_eval_time_ms', 0),
            "tokens": parsed_metrics.get('prompt_tokens', 0),
            "tps": parsed_metrics.get('prompt_tps', 0.0)
        },
        "generation_eval": {
            "time_ms": parsed_metrics.get('eval_time_ms', 0),
            "tokens": parsed_metrics.get('eval_tokens', 0),
            "tps": parsed_metrics.get('eval_tps', 0.0)
        },
        "llama_cpp_info": {
            "total_inference_time_ms": parsed_metrics.get('total_time_ms', 0),
            "graphs_reused": parsed_metrics.get('graphs_reused', 'N/A'),
            "total_tokens": parsed_metrics.get('prompt_tokens', 0) + parsed_metrics.get('eval_tokens', 0)
        }
    }

    # --- 6. Return the comprehensive result using jsonify ---
    return jsonify({
        "reply": out["choices"][0]["text"],
        "prompt": prompt,
        "metrics": perf_data
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000)