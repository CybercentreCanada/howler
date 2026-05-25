# System Dependencies

In order to contribute to Howler, you will first need to prepare your development environment.

??? tip "Notes on Operating System"
    Please note that these commands were written for use in Ubuntu, either on Windows through WSL or a standalone Ubuntu
    OS. You will need to adapt the OS-specific instructions to your personal operating system.

```shell
# Clone the Howler monorepo
mkdir -p ~/repos && cd ~/repos
git clone git@github.com:CybercentreCanada/howler.git
cd howler
```

## Frontend Dependencies

### Node.js

Howler's UI is developed using [Vite](https://vitejs.dev/), which requires Node.js v20 or higher. We recommend using
[Node Version Manager (nvm)](https://github.com/nvm-sh/nvm) to manage Node.js versions.

??? tip "Installing without NVM"
    NVM isn't required - if you'd rather install Node.js yourself, you can do so. Just make sure the version you
    install is v20 or higher to be compatible with Vite.

```shell
# Install nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

# Restart your shell or run:
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"

# Install and use Node.js v20 (as specified in ui/.nvmrc)
nvm install v20
nvm use v20

# Optional: Set v20 as default
nvm alias default v20
```

### pnpm

Howler's UI uses [pnpm](https://pnpm.io/) for package management. The project enforces the use of pnpm through a
preinstall script.

```shell
# Install pnpm globally
npm install -g pnpm

# Verify installation
pnpm --version
```

## Backend Dependencies

### Docker

Howler's backend depends on Docker containers for services like databases, message queues, and other infrastructure
components. You'll need Docker and Docker Compose installed.

Follow the official Docker installation guide for your operating system:
[Docker Engine Installation](https://docs.docker.com/engine/install/)

For Ubuntu specifically, see: [Install Docker on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)

<!-- markdownlint-disable -->
??? tip "Post-Installation Steps"
    After installing Docker, you may want to add your user to the `docker` group to run Docker commands without `sudo`:

    ```shell
    # Add the docker group (may already exist)
    sudo groupadd docker

    # Add the current user to the docker group
    sudo usermod -aG docker $USER

    # Log out and back in for the group change to take effect
    ```

    Verify Docker is working:

    ```shell
    docker run hello-world
    ```
<!-- markdownlint-enable -->

### Python

Howler's backend requires Python 3.12. We recommend using [pyenv](https://github.com/pyenv/pyenv) to manage Python
versions, as it allows you to install and switch between multiple Python versions easily.

#### Installing pyenv

For detailed installation instructions, see the [pyenv installation guide](https://github.com/pyenv/pyenv#installation).

**Quick installation for Ubuntu/WSL:**

```shell
# Install build dependencies
sudo apt update
sudo apt install -y build-essential libssl-dev zlib1g-dev \
libbz2-dev libreadline-dev libsqlite3-dev curl git \
libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev

# Install pyenv
curl https://pyenv.run | bash

# Add pyenv to your shell configuration
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc

# If using zsh instead of bash, replace ~/.bashrc with ~/.zshrc in the above commands
```

Restart your shell or run:

```shell
exec "$SHELL"
```

#### Installing Python 3.12

```shell
# Install Python 3.12
pyenv install 3.12

# Set Python 3.12 as global default
pyenv global 3.12

# Verify installation
python --version  # Should show Python 3.12.x
```

??? tip "Installing without pyenv"
    If you prefer not to use pyenv, you can install Python 3.12 directly. Just ensure you have Python 3.12 or higher
    available in your environment.
