# LLM Edge Cloud

This repository contains the code for deploying open-source LLM models locally as microservices using the `llama_cpp` library. The model must be downloaded beforehand via Hugging Face in the GGUF format. The recommended model for edge deployment is [`gemma-2-2b-it-Q8_0.gguf`](https://huggingface.co/bartowski/gemma-2-2b-it-GGUF).

## Setup Instructions

### Prerequisites

1. Install the necessary compiler and build tools (build-essential includes gcc, g++, and make)

   ```bash
   sudo apt update
   sudo apt install build-essential cmake
   ```

2. Activate Python's virtual environment

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Make sure you have `hugginface-cli` installed

   ```bash
   pip install "huggingface_hub[cli]==0.23.0"
   ```

4. Install neccessary model

   ```bash
   # Text to text model
   huggingface-cli download bartowski/gemma-2-2b-it-GGUF --include "gemma-2-2b-it-Q8_0.gguf" --local-dir ./

   # Text to image model
   curl -L "https://huggingface.co/second-state/stable-diffusion-v1-5-GGUF/resolve/main/stable-diffusion-v1-5-pruned-emaonly-Q8_0.gguf?download=true" -o stable-diffusion-v1-5-pruned-emaonly-Q8_0.gguf
   ```

### Using model

1. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the server:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

3. Test the deployment from another terminal:

   Text to text model
   ```bash
   curl --get "http://localhost:8000/text2text" --data-urlencode "prompt=Write me a poem about winter"
   ```

   Text to image model
   ```bash
   curl --get "http://localhost:8000/text2image" --data-urlencode "prompt=A cat"
   ```
