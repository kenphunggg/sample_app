# measure_yolo
Simple yolo_app that can proccess video for analystic purpose

## Table of contents

- [Testbed design](#testbed-design)
- [How to use](#how-to-use)
    - [Running using terminal](#running-using-terminal)
        - [Broadcast video](#broadcast-video)
        - [Receive video](#receive-video)
    - [Running using Docker](#running-using-docker)
- [How to contribute](#how-to-contribute)


## Testbed design
![streaming_testbed_des.png](./img/streaming_testbed_des.png)

## How to use
### Running using terminal

1. Convert origin video to 4K resolution

    ```bash
    ffmpeg -i input.mp4 -vf scale=3840x2160:flags=lanczos -c:v libx264 -preset slow -crf 19 output.mp4

    ```

    It may take a while until `ffmpeg` to convert video to 4K

2. Broadcast video at source

    ```bash
    # Replace *192.168.17.161* to your ip address 
    ffmpeg \
    -re \
    -stream_loop -1 \
    -r 24 \
    -i output.mp4 \
    -f flv \
    -c:a aac \
    -preset ultrafast \
    -c:v libx264 \
    rtmp://0.0.0.0:1935/live/source
    ```

3. Receive the stream, and detect it

    ```bash
    python3 main.py
    ```

4. Receive result
    
    Replace `192.168.17.161:5000` with your stream flow - where you host yolo app and replace `192.168.17.162:2000` with your stream source

    ```bash
    curl 192.168.17.161:5000/stream/192.168.17.162:2000/time/20
    ```

### Running using Docker

1. Broadcast video at source

    ```bash
    docker run -p 5000:5000 -p 2000:1935 docker.io/lazyken/broadcast-streaming:v1
    ```

2. Receive and detect

    ```bash
    docker run -p 8080:8080 -e SOURCE_IP="192.168.17.162:2000" docker.io/lazyken/measure-streaming:v2
    ```

3. Receive video

    ```bash
    # 1. Using rtmp
    ffmpeg -i "rtmp://192.168.17.162/live/1080p" -f null -

    # 2. Using hls
    ffmpeg -i "http://192.168.17.162/live/playlist.m3u8" -f null -
    # Get time to first frame
    time ffmpeg -i "http://192.168.17.162/live/playlist.m3u8" -vframes 1 -f null -
    ```

## How to contribute

1. For app that broadcast video at source

    Source code are located at [broadcast.py](/measure_streaming/broadcast.py) and Dockerfile to build code are located at [broadcast.Dockerfile](/measure_streaming/broadcast.Dockerfile).

    After change code, you can build the image.

    ```bash
    docker build -t docker.io/lazyken/broadcast-streaming:v1 -f broadcast.Dockerfile .
    ```

2. For app that receive and downscale

    ```bash
    docker build -t docker.io/lazyken/measure-streaming:v2 -f broadcast.Dockerfile .
    ```

