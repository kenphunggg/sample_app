# hello_app
Hello app for deploying to K8s/Knative

There are several ways to using this app:
- [Running in local device](#running-local-for-testing)
- [Using `Docker`](#running-in-docker)
- [Using `Kubernertes`](#running-in-kubernetes)
- [Using `Knative`](#running-in-knative)

## Running local for testing

Setting up virtual environment

```shell
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Running app

```shell
python3 main.py
```

Now, you can use the app using

```shell
curl localhost:5000
# It should return
# Hello from LAZYken | master-node

curl localhost:5000/nodename
# It should return
# master-node
```

## Running in Docker

Building docker image 

```shell
docker build -t lazyken/sampleapp:v1 .
```

Running docker container

```shell
docker run -d -p 5000:5000 -e NODE_NAME=$(hostname) -e USER_NAME='LAZYken' lazyken/sampleapp:v1
```

Testing the app

```shell
curl localhost:5000
# It should return
# Hello from LAZYken | master-node

curl localhost:5000/nodename
# It should return
# master-node
```

If you want to push the image, you can use following command

```shell
# Make sure you have logged into your Docker repository by executing docker login
docker image push docker.io/lazyken/sampleapp:v1
```

## Running in Kubernetes

Ensure you have successfully installed a `Kubernetes` cluster.

You can install a product ready `Kubernetes` cluste using [this guild](https://github.com/kenphunggg/kubespray.git).

> [!NOTE]
> Port configuration

|Kind|Port type|Purpose|Who use it|Port range|
|----|---------|-------|----------|----------|
|`Service`|`targetPort`|The port the application container is actually listening on inside the Pod.|Kubernetes' Service|1-65535|
|`Service`|`port`|Exposes the Service on an internal IP within the cluster.|Other Pods/Services within the cluster|1-65535|
|`Servie`|`nodePort`|Exposes the Service on each Node's IP at a static port.|External users/traffic from outside the cluster|30000-32767|
|`Deployment`|`containerPort`|port that the application inside your container is listening on.|Debugging inside container, if do not have a service created|All port accepted|

> [!IMPORTANT]
> `targetPort` and `containerPort` should be configured into same port

Then, you can apply `.yaml` file

```shell
kubectl apply -f deploy/kubernetes.yaml
```

Testing the app
```shell
curl hello.default        # <service_name>.<namespace>:<port>
curl 192.168.17.161:32593 # <any_node_ip_in_your_cluster>:<nodePort>
```

Using `Kubernetes` vertical pod autoscaler

```shell
kubectl patch pod hello-58c8ffd75-5blcm --subresource resize --patch \
  '{"spec":{"containers":[{"name":"sampleapp", "resources":{"requests":{"cpu":"1000m"}, "limits":{"cpu":"1000m"}}}]}}'
```

## Running in Knative
