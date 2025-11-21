FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    tzdata libgl1-mesa-glx ffmpeg \
    zlib1g zlib1g-dev nano python3-pip curl \
    nginx libnginx-mod-rtmp tini \
    && apt-get clean

# Copy nginx config
COPY broadcast/nginx.conf /etc/nginx/nginx.conf

# Log ra stdout/stderr
RUN ln -sf /dev/stdout /var/log/nginx/access.log && \
    ln -sf /dev/stderr /var/log/nginx/error.log

WORKDIR /app

COPY broadcast/input.mp4  broadcast/broadcast.py ./

RUN pip3 install Flask gunicorn 

EXPOSE 5000 1935

ENTRYPOINT ["/usr/bin/tini", "--"]

CMD ["bash", "-c", "nginx && exec gunicorn -b 0.0.0.0:5000 broadcast:app"]
