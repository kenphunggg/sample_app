FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    netcat \
    tzdata libgl1-mesa-glx ffmpeg \
    zlib1g zlib1g-dev nano python3-pip curl \
    nginx libnginx-mod-rtmp tini \
    && apt-get clean

# # Copy nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# # Log ra stdout/stderr
RUN ln -sf /dev/stdout /var/log/nginx/access.log && \
    ln -sf /dev/stderr /var/log/nginx/error.log

WORKDIR /app

# COPY test.py ./
# # COPY measure.py ./

# RUN pip3 install Flask gunicorn python-dotenv

# EXPOSE 6000

# ENTRYPOINT ["/usr/bin/tini", "--"]

# CMD ["bash", "-c", "nginx && exec gunicorn -b 0.0.0.0:6000 test:app"]
# CMD ["bash", "-c", "nginx && exec gunicorn --workers 1 --timeout 120 -b 0.0.0.0:6000 measure:app"]




# Copy the bash script into the container's working directory
# Note: The user's log refers to measure.sh, so we use that here.
COPY measure.sh .

# Make the script executable
RUN chmod +x measure.sh

# Expose the RTMP port that the output stream will be published to.
# This allows other services to connect to this container on port 1935.
EXPOSE 1935

# --- FIX: Explicitly run the script with /bin/sh ---
# The base Alpine image does not include bash. By specifying /bin/sh as the
# interpreter, we bypass the script's #!/bin/bash shebang. This is safe
# because the script's syntax is compatible with the default shell.
ENTRYPOINT ["/bin/sh", "./measure.sh"]

