# measure_yolo
Simple yolo_app that can proccess video for analystic purpose

## Table of contents

- [Testbed design](#testbed-design)
- [How to use](#how-to-use)
    - [Running on local](#1-running-on-local)
    - [Running using Docker](#2-running-using-docker)
    - [Running using Kubnernetes](#3-running-using-kubernetes)
    - [Running using Knative](#4-running-using-knative)
- [How to contribute](#how-to-contribute)


## Testbed design
![yolo_testbed_des.png](./img/yolo-testbed.png)
In this testbed, `video` is a docker image that broadcast its video. When `Actor` request for `yolo service`, `Func-pod` will request for video from `video` and using `yolo` to analysis it.

## How to use

### 1. Running on local

First, you need to install all dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

Load/unload model

```bash
curl localhost:8080/model/load

curl localhost:8080/model/unload
```

Then you can use yolo to detect streaming now.
```bash
# curl yolo service to analyze one frame
curl -X POST -F "image=@analyze_image/4k.jpg" http://localhost:8080/detect

# It should retun like this
{"confidences":[0.8860411047935486,0.8586447834968567,0.8408066034317017,0.8164324760437012,0.38944581151008606,0.28988006711006165],"model_inference_ms":81.81,"model_nms_ms":27.01,"model_preprocess_ms":8.87,"success":true,"text":"image 1/1: 2160x3840 6 persons\nSpeed: 8.9ms pre-process, 81.8ms inference, 27.0ms NMS per image at shape (1, 3, 384, 640)","total_server_time_ms":290.45}

# curl yolo service to analyze video in <time_to_detect>
curl -X POST -F "image=@analyze_image/4k.jpg" http://localhost:8080/detect/time/5
```

### 2. Running using Docker

First, you need to run container of the yolo service

```bash
docker run -d -p 8080:8080 docker.io/lazyken/measure-yolo:v1
```

Load/unload model

```bash
curl localhost:8080/model/load

curl localhost:8080/model/unload
```

Then you can use yolo to detect streaming now.
```bash
# curl yolo service to analyze one frame
curl -X POST -F "image=@analyze_image/4k.jpg" http://localhost:8080/detect

# curl yolo service to analyze video in <time_to_detect>
curl -X POST -F "image=@analyze_image/4k.jpg" http://localhost:8080/detect/time/5
```

### 3. Running using Kubernetes

First, you need to run container of the yolo service

```bash
kubectl apply -f deploy/kubernetes.yaml
```

Load/unload model

```bash
curl measure-yolo.default/model/load

curl measure-yolo.default/model/unload
```

Then you can use yolo to detect streaming now.
```bash
# curl yolo service to analyze one frame
curl -X POST -F "image=@analyze_image/4k.jpg" http://measure-yolo.default/detect

# curl yolo service to analyze video in <time_to_detect>
curl -X POST -F "image=@analyze_image/4k.jpg" http://measure-yolo.default/detect/time/5
```

### 4. Running using Knative

First, you need to run container of the yolo service

```bash
kubectl apply -f deploy/knative.yaml
```

Then you can use yolo to detect streaming now.
```bash
# curl yolo service to analyze one frame
curl -X POST -F "image=@analyze_image/4k.jpg" http://measure-yolo.default/detect

# curl yolo service to analyze video in <time_to_detect>
curl -X POST -F "image=@analyze_image/4k.jpg" http://measure-yolo.default/detect/time/5

## How to contribute

After modify source code under [main.py](./main.py), you can build your own Docker image

```bash
docker build -t docker.io/lazyken/measure-yolo:v1 .

# Then you can push it to Dockerhub for future uses
docker push docker.io/lazyken/measure-yolo:v1
```


