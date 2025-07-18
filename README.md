# sample_app
Sample app for deploying to K8s/Knative

## Running local for testing

### Setting up virtual environment
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running app
```
python3 main.py
```

## Running in Docker

### Building docker image 
```ShellSession
docker build -t kenphung/sampleapp:v1 .
```

### Running docker container
```ShellSession
docker run -d -p 5000:5000 -e NODE_NAME=$(hostname) -e USER_NAME='LAZYken' kenphung/sampleapp:v1
```

### Testing the app
```ShellSession
curl localhost:5000
```

## Running in Kubernetes
