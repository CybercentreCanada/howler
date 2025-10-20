# Installation Procedure

??? warning "System dependencies"
    Before running these steps, ensure you have completed the installation steps
    [here](/howler-docs/developer/getting_started/#backend-dependencies).

Running the howler server, once dependencies are installed, is fairly simple. First, we start up the dependences. These
include:

1. Elasticsearch 8
2. A redis instance
3. A minio instance

```shell
cd ~/repos/howler-api
cd dev && docker compose up
```

Now we install the python packages Howler depends on:

```shell
cd ~/repos/howler-api

# If you don't have python3.9 as the default, use python3.9 here instead
python -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt -r test/requirements.txt

pip install -e .
```

We need to setup a few folders on the system howler will use:

```shell
sudo mkdir -p /etc/howler/conf
sudo mkdir -p /var/cache/howler
sudo mkdir -p /var/lib/howler
sudo mkdir -p /var/log/howler

sudo chown -R $USER /etc/howler
sudo chown $USER /var/cache/howler
sudo chown $USER /var/lib/howler
sudo chown $USER /var/log/howler
```

And then we initialize the configurations and add some users for testing:

```shell
./generate_howler_conf.sh

# Create default users
python howler/odm/random_data.py users
```

Finally, we can run howler!

```shell
python howler/app.py
```
