# Use the Ubuntu 20.04 base image
FROM ubuntu:20.04

# Set non-interactive mode for package installations
ENV DEBIAN_FRONTEND=noninteractive

# Install all necessary dependencies
# (nginx, ffmpeg, netcat for the script; python3-pip, tini for the server)
RUN apt-get update && apt-get install -y \
    netcat \
    tzdata \
    libgl1-mesa-glx \
    ffmpeg \
    python3-pip \
    nginx \
    libnginx-mod-rtmp \
    tini \
    && apt-get clean

# Copy nginx config (assuming it's in a local 'measure' dir)
COPY measure/nginx.conf /etc/nginx/nginx.conf

# Redirect Nginx logs to container stdout/stderr
RUN ln -sf /dev/stdout /var/log/nginx/access.log && \
    ln -sf /dev/stderr /var/log/nginx/error.log

# Set the working directory for the application
WORKDIR /app

# Install Python dependencies for the Flask app
RUN pip3 install Flask gunicorn

# Copy the application files into the container
# Assumes app.py is in the build root
# Assumes measure.sh is in the 'measure' subdirectory
COPY measure/app.py .
COPY measure/measure.sh .

# Make the shell script executable
RUN chmod +x measure.sh

# Expose ports:
# 5000: For the Flask/Gunicorn API server (start/stop/status)
# 8080: For the Nginx HLS stream (defined in your measure.sh)
EXPOSE 5000
EXPOSE 8080

# Use 'tini' as the init system to manage processes
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default command to run the Flask app using Gunicorn
# This starts the API server.
# The server will then start/stop measure.sh (and nginx) via API calls.
CMD ["gunicorn", "--workers", "1", "--timeout", "120", "-b", "0.0.0.0:5000", "app:app"]