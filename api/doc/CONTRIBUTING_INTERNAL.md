# Howler API

This repo contains the API server for Howler

## Installation Pre-requisites

The setup script assumes the following:

- You are running this on a Ubuntu machine / VM (20.04 and up)
- VSCode does not have to be running on the same host where you run the installation instructions on if you want to use VSCode in remote development

## Installation instructions

### Setup Howler folders

```bash
sudo mkdir -p /etc/howler/conf
sudo mkdir -p /var/cache/howler
sudo mkdir -p /var/lib/howler
sudo mkdir -p /var/log/howler
sudo mkdir /etc/howler/lookups

sudo chown -R $USER /etc/howler
sudo chown $USER /var/cache/howler
sudo chown $USER /var/lib/howler
sudo chown $USER /var/log/howler
```

### Clone the source

Create your repo directory

```bash
mkdir -p ~/repos
```

Clone repos

```bash
    (cd ~/repos && git clone git@github.com:CybercentreCanada/howler-api.git)
```

### Setup APT dependencies

```bash
sudo apt update
sudo apt install -yy software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt install -yy python3-venv python3.12 python3.12-dev python3.12-venv
sudo apt install -yy libsasl2-2 build-essential libsasl2-dev libssl-dev zip
```

### Setup pipx/poetry

```bash
pip install pipx
pipx install poetry
```

### Install dependencies with poetry

```bash
cd ~/repos/howler-api
poetry install --with dev,test,types
```

### Setup default configuration files

Create default classification.yml and config.yml files:

Both Keycloak and Azure are optional. It is heavily recommended to use [hogwarts-mini](https://github.com/CybercentreCanada/hogwarts-mini) to enable keycloak's OAuth authentication.

```bash
# This keycloak secret applies to the hogwarts-mini instance. You'll need a different one if you're using a different
# instance of Keycloak
export KEYCLOAK_CLIENT_SECRET=09RhSF7tp0ShDdDMCszqI4zk8HMroTTZ
# This is currently the spellbook-scylladev app registration
# Replace <secret-here> with a generated secret from here:
# https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationMenuBlade/~/Credentials/appId/883e7856-e3a6-480f-b958-5289d5d8a7ad
export AZURE_CLIENT_ID=883e7856-e3a6-480f-b958-5289d5d8a7ad
export AZURE_CLIENT_SECRET=<secret-here>
poetry shell
./generate_howler_conf.sh
```

#### Generate mitre lookups

```bash
poetry run python howler/external/generate_mitre.py /etc/howler/lookups
```

## Setup default environment

### Install docker

Install packages

```bash
sudo apt update
sudo apt install -yy apt-transport-https ca-certificates curl gnupg-agent software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo apt-key fingerprint 0EBFCD88
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
sudo apt install -yy docker-ce docker-ce-cli containerd.io
```

Setup sudo-less docker

```bash
sudo groupadd docker
sudo usermod -aG docker $USER
```

Install docker-compose

```bash
sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
sudo curl -L https://raw.githubusercontent.com/docker/compose/1.29.2/contrib/completion/bash/docker-compose -o /etc/bash_completion.d/docker-compose
```

### Install VSCode (optional)

If you want to run VSCode from inside the VM, you can install it with the following:

```bash
sudo snap install code --classic
```

### Reboot

```bash
sudo reboot
```

## Running development environment

Now that the installation instructions are completed, you can now load your `howler-api` folder in VSCode. We strongly advise installing the recommended extensions when prompted or typing '@recommended' in the Extensions tab.

### Launch dependency containers

You can run the dependency containers either manually in a shell:

```bash
(cd ~/repos/howler-api/dev && docker-compose up)
```

Or directly in VSCode using the tasks in Task Explorer

![Task explorer](doc/tasks.png)

### Launch the API

Once the dependencies are launched, you can start the API Server. The API server will be loaded with the default configuration found in your `/etc/howler/conf` folder that we've created during the setup. So if you want to enable/disable feature, do it there.

To launch the API server manually you can use this command:

```bash
cd ~/repos/howler-api
poetry run server
```

Launching the API Server manually unfortunately does not give you access to a debugger. If you want to be able to debug your code, you can use the predefined launch target inside of VSCode:

![Task explorer](doc/run_debug.png)

## Running Tests

In order to run the tests, you can use a convenience script:

```bash
# Install test dependencies
poetry install --with test

# Generate mitre lookups
poetry run mitre /etc/howler/lookups

# run the server and the pytest command, along with coverage results
poetry run test
```

## Pipeline hanging on elastic? try this

SSH to the buildhost and run these commands while the pipeline is running or the elastic container is active.

1. curl localhost:9200/\_cluster/health

   If this says "red", that means it's not healthy, so it's broken somehow. continue to step 2.

2. curl localhost:9200/\_cat/shards?v=true&s=state

   If the shards say "UNASSIGNED", we now need to know why, continue to step 3.

3. curl localhost:9200/\_cluster/allocation/explain?filter_path=index,node_allocation_decisions.node_name,node_allocation_decisions.deciders.\*

   this should tell you why the shard(s) are unassigned. It might say something about no disk space or not enough disk space.
