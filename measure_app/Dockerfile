FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install pip dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get install -y tini procps tzdata --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy all app files
COPY . .

# Expose port
EXPOSE 5000

ENTRYPOINT ["/usr/bin/tini", "-g", "--"]

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--graceful-timeout", "5", "--access-logfile", "-", "--error-logfile", "-", "main:app"]