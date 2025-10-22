# Installation Procedure

??? warning "System dependencies"
    Before running these steps, ensure you have completed the installation steps
    [for backend dependencies](/howler-docs/developer/getting_started/#backend-dependencies).

Running the howler server, once dependencies are installed, is fairly simple. First, we start up the dependencies. These
include:

1. Elasticsearch 8
2. A redis instance
3. A minio instance
4. Keycloak (for OAuth authentication)

```shell
cd ~/repos/howler/api/dev
docker compose up
```

Now we install the python packages Howler depends on using Poetry:

```shell
cd ~/repos/howler/api

# Install poetry if you don't have it
python3 -m pip install poetry

# Configure poetry to create virtualenv in project directory
poetry config virtualenvs.in-project true

# Install dependencies (including test dependencies)
poetry install --with test
```

We need to setup a few folders on the system howler will use:

```shell
sudo mkdir -p /etc/howler/conf
sudo mkdir -p /etc/howler/lookups
sudo mkdir -p /var/log/howler

sudo chown -R $USER /etc/howler
sudo chown -R $USER /var/log/howler
```

And then we initialize the configurations:

```shell
# Copy configuration files
cp build_scripts/classification.yml /etc/howler/conf/classification.yml
cp build_scripts/mappings.yml /etc/howler/conf/mappings.yml
cp test/unit/config.yml /etc/howler/conf/config.yml

# Generate MITRE ATT&CK lookups
poetry run mitre /etc/howler/lookups

# Generate Sigma rules
poetry run sigma
```

Create default users for testing:

```shell
poetry run python howler/odm/random_data.py users
```

Finally, we can run howler!

```shell
poetry run server
# Or alternatively: poetry run python howler/app.py
```

The API server will start on `http://localhost:5000` by default.
