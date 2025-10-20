# System Dependencies

In order to contribute to Howler, you will first need to prepare your development environment.

??? tip "Notes on Operating System"
    Please note that these commands were written for use in ubuntu, either on Windows through WSL or a standalone ubuntu
    OS. You will need to adapt the OS-specific instructions to your personal operating system.

```shell
# While not strictly necessary, it is suggested to keep all howler repositories in a single folder.
# Several scripts communicate across repositories, and are more efficient when sharing a parent folder.
mkdir ~/repos && cd ~/repos

# Clone the howler repositories
git clone git@github.com:CybercentreCanada/howler-ui.git
git clone git@github.com:CybercentreCanada/howler-api.git
git clone git@github.com:CybercentreCanada/howler-client.git
```

## Frontend dependencies

### Node

Howler's UI is developed using [vite](https://vitejs.dev/), which requires node v20 or higher. We'll use
[Node Version Manager](https://github.com/nvm-sh/nvm) to download and install node v20.

??? tip "Installing without NVM"
    NVM isn't required - if you'd rather install node yourself, you can do so - just make sure the version you install
    is compatible with vite.

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

# Optional if you have other projects depending on other versions of node
nvm alias default v20
```

### Yarn

Howler's UI uses [Yarn](https://yarnpkg.com/) for package management.

```shell
npm install -g yarn
```

## Backend Dependencies

Howler's backend depends on a number of docker containers in order to properly run. To this end, you must have docker
and docker-compose installed. To that end, follow the installation steps outlined
[here](https://docs.docker.com/engine/install/ubuntu/#install-using-the-repository), copied below for convenience:

??? tip "Alternative Installation Methods"
    Docker has a number of options for installation. This is the tested method, but other approaches should work without
    issue.

```shell
# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

# Install the latest version
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verify it's working
sudo docker run hello-world
```

If you'd rather not run `sudo` for every docker command:

```shell
# Add the docker group. If it fails, no problem
sudo groupadd docker

# Add the current user to the docker group
sudo usermod -aG docker $USER
```

Next up, Python. Howler runs on Python 3.9, so we'll install that:

```shell
sudo apt install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.9 python3.9-distutils python3.9-venv

python3.9 --version

# If you want to run python3.9 as default
sudo update-alternatives --install /usr/bin/python python /usr/bin/python3.9 1

python --version

# Install pip
python -m ensurepip

# If you want to run pip3.9 as default
sudo update-alternatives --install $HOME/.local/bin/pip python $HOME/.local/bin/pip3.9 1

pip --version
```
