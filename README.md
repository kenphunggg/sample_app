# sample_app
Sample app for deploying to K8s/Knative

## Running local for testing

### Setting up virtual environment
```ShellSession
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running app
```ShellSession
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

Ensure you have successfully installed a `Kubernetes` cluster.

Instruction for installing Kubernetes cluster [here](https://github.com/kenphunggg/kubespray.git).

```ShellSession
kubectl apply -f sampleapp.yaml
```

### Using Kubernetes HPA

```ShellSession
kubectl patch pod hello-58c8ffd75-5blcm --subresource resize --patch \
  '{"spec":{"containers":[{"name":"sampleapp", "resources":{"requests":{"cpu":"1000m"}, "limits":{"cpu":"1000m"}}}]}}'
```
