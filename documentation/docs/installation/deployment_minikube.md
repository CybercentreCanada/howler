# Installing Howler on a New Ubuntu VM

This setup document allows you to setup Howler and its dependencies on a new, standalone ubuntu distribution. While a dedicated kubernetes cluster is likely a better way to handle deployments, this approach is useful if you have only a single machine available.

## Install Minikube and Dependencies

In order to configure and run the minikube cluster, we need to install docker, minikube, kubectl, helm and k9s.

```shell
# Install Docker
sudo apt update
sudo apt install -y docker.io
sudo systemctl enable docker
sudo systemctl start docker
sudo docker run hello-world
sudo usermod -aG docker $USER && newgrp docker

# Install minikube
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube
minikube addons enable ingress

# Install kubectl
# https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl.sha256"
echo "$(cat kubectl.sha256)  kubectl" | sha256sum --check
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
kubectl version --client

# Install helm
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
chmod 700 get_helm.sh
./get_helm.sh

# Install k9s
curl -sS https://webinstall.dev/k9s | bash
source ~/.config/envman/PATH.env
```

## Install Build Dependencies and Build Images

Since there are currently no public builds of the Howler docker image, you'll need to build them either ahead of time or on the machine.

We will first install the build dependencies:

```shell
# Install nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

# You can skip these commands if you restart your shell
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"                   # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion" # This loads nvm bash_completion

# Install and use node version 20
nvm install v20
nvm use v20

# Install the build programs
npm install -g yarn vite

# Install Python 3.9
sudo apt install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.9 python3.9-distutils python3.9-venv
sudo update-alternatives --install /usr/bin/python python /usr/bin/python3.9 1
python -m ensurepip
python -m pip install wheel

```

Now we can clone and build the images:

```shell
# Clone the howler repositories
mkdir ~/repos && cd ~/repos
git clone git@github.com:CybercentreCanada/howler-api.git
git clone git@github.com:CybercentreCanada/howler-ui.git

# Build howler-api docker image
cd ~/repos/howler-api/docker
./build_container.sh

cd ~/repos/howler-ui/docker
./build_container.sh
```

Now we can start and configure the minikube deployment:

```shell
# Upload the images to minikube (this takes a while)
minikube image load cccs/howler-ui:latest
minikube image load cccs/howler-api:latest

minikube start

# Input the yml below
vim minio-credentials.yml
kubectl apply -f minio-credentials.yml

# Create the interpod secret
kubectl create secret generic howler-interpod-comms-secret
  --from-literal=secret="<INTERPOD_COMMS_SECRET>"

# Clone the howler repository, to get the helm chart
git clone git@github.com:CybercentreCanada/howler.git
cd howler/howler-helm

# Install the howler helm chart
helm install howler .

# Check that everything loads correctly
k9s

# After everything loads, can we access the ingress?
curl $(minikube ip)

# Install and configure nginx
sudo apt install nginx
sudo rm /etc/nginx/sites-enabled/default

# Input the conf file below
sudo vim /etc/nginx/site-enabled/howler

sudo service nginx restart

# Is nginx working?
curl localhost
```

At this point, you should have an open port 80 on your machine serving a functional howler instance.

### Required Files

minio-credentials.yml:

```yml
apiVersion: v1
kind: Secret
metadata:
  name: minio-credentials
  annotations:
    "helm.sh/resource-policy": "keep"
data:
  root-user: <SOME_USERNAME>
  root-password: <SOME_PASSWORD>
```

nginx configuration:

```conf
server {
    listen 80 default_server;
    sendfile on;
    server_name howler;

    location / {
        proxy_pass http://<MINIKUBE_IP>;
        proxy_set_header Host $host:$server_port;
    }
}
```
