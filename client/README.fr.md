# Bibliothèque cliente Howler

La bibliothèque cliente Howler facilite l'envoi de requêtes à Howler.

## Configuration requise

1. Python 3.9 et versions ultérieures

## Exécution des tests

### Préparation de l'API

```bash
sudo mkdir -p /etc/howler/conf
sudo mkdir -p /var/cache/howler
sudo mkdir -p /var/lib/howler
sudo mkdir -p /var/log/howler

sudo chown -R $USER /etc/howler
sudo chown $USER /var/cache/howler
sudo chown $USER /var/lib/howler
sudo chown $USER /var/log/howler

cd api/dev
docker compose up -d --build

cd ..
poetry install --with dev,test,types
cp test/unit/config.yml /etc/howler/conf/config.yml
cp build_scripts/classification.yml /etc/howler/conf/classification.yml
poetry run server

poetry run python howler/odm/random_data.py
```

### Exécuter des tests

```bash
cd client

poetry run test
```
