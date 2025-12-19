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

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "-g", "--"]

# Run with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--timeout", "3000", "--graceful-timeout", "5", "--access-logfile", "-", "--error-logfile", "-", "main:app"]