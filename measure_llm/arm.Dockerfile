FROM python:3.12-slim

WORKDIR /app

# Add tini to the list of packages to install
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/*

COPY . .

# --- FIX START ---
# Disable native CPU optimization. This prevents the "Illegal Instruction" (132) error
# caused by building on an advanced CPU (Mac M1/M2) and running on a Raspberry Pi.
ENV CMAKE_ARGS="-DGGML_NATIVE=OFF"

# We add --force-reinstall and --no-binary to ensure the libraries actually 
# compile from source using the flags above, rather than using a pre-built wheel.
RUN pip install --no-cache-dir --force-reinstall --no-binary llama-cpp-python,stable-diffusion-cpp-python -r requirements.txt
# --- FIX END ---

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "-g", "--"]

# Run with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--timeout", "3000", "--graceful-timeout", "5", "--access-logfile", "-", "--error-logfile", "-", "main:app"]
