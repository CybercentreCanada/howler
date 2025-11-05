# Procédure d'installation

??? warning "Dépendances système"
    Avant d'exécuter ces étapes, assurez-vous d'avoir complété les étapes d'installation
    [pour les dépendances backend](/howler-docs/developer/getting_started/#backend-dependencies).

L'exécution du serveur Howler, une fois les dépendances installées, est assez simple. Tout d'abord, nous démarrons les
dépendances. Celles-ci incluent :

1. Elasticsearch 8
2. Une instance Redis
3. Une instance Minio
4. Keycloak (pour l'authentification OAuth)

```shell
cd ~/repos/howler/api/dev
docker compose up
```

Maintenant, nous installons les packages Python dont Howler dépend en utilisant Poetry :

```shell
cd ~/repos/howler/api

# Installer poetry si vous ne l'avez pas
python3 -m pip install poetry

# Configurer poetry pour créer le virtualenv dans le répertoire du projet
poetry config virtualenvs.in-project true

# Installer les dépendances (incluant les dépendances de test)
poetry install --with test
```

Nous devons configurer quelques dossiers sur le système que Howler utilisera :

```shell
sudo mkdir -p /etc/howler/conf
sudo mkdir -p /etc/howler/lookups
sudo mkdir -p /var/log/howler

sudo chown -R $USER /etc/howler
sudo chown -R $USER /var/log/howler
```

Ensuite, nous initialisons les configurations :

```shell
# Copier les fichiers de configuration
cp build_scripts/classification.yml /etc/howler/conf/classification.yml
cp build_scripts/mappings.yml /etc/howler/conf/mappings.yml
cp test/unit/config.yml /etc/howler/conf/config.yml

# Générer les lookups MITRE ATT&CK
poetry run mitre /etc/howler/lookups

# Générer les règles Sigma
poetry run sigma
```

Créer des utilisateurs par défaut pour les tests :

```shell
poetry run python howler/odm/random_data.py users
```

Finalement, nous pouvons exécuter Howler !

```shell
poetry run server
# Ou alternativement : poetry run python howler/app.py
```

Le serveur API démarrera sur `http://localhost:5000` par défaut.
