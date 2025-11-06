# Développement du client

## Introduction

Le client Python Howler (`howler-client`) est une bibliothèque qui fournit une interface simple et intuitive pour
interagir de manière programmatique avec l'API Howler. Il permet aux développeurs de :

- Créer et ingérer des hits provenant de diverses sources de données
- Rechercher et interroger des hits avec la syntaxe Lucene
- Mettre à jour, modifier et supprimer des hits
- Gérer les commentaires et métadonnées des hits
- Intégrer Howler dans des flux de travail et pipelines automatisés

Le client gère l'authentification, le formatage des requêtes et l'analyse des réponses, facilitant ainsi la création
d'outils et d'intégrations avec Howler.

Le package est publié sur [PyPI](https://pypi.org/project/howler-client/) et le code source se trouve dans le
dossier `client/` du [monorepo Howler](https://github.com/CybercentreCanada/howler).

## Installation

Le client Howler nécessite Python 3.9 ou supérieur. Installez-le avec pip :

```bash
pip install howler-client
```

## Authentification et connexion

### Générer une clé API

Pour vous authentifier avec l'API Howler, vous devrez générer une clé API :

1. Ouvrez l'interface utilisateur Howler et connectez-vous
2. Cliquez sur votre icône de profil dans le coin supérieur droit
3. Sélectionnez **Paramètres** dans le menu utilisateur
4. Sous **Sécurité utilisateur**, cliquez sur l'icône **(+)** à côté des clés API
5. Nommez votre clé et attribuez les permissions appropriées
6. Cliquez sur **Créer** et copiez la clé générée

**Important :** Conservez cette clé en sécurité - vous ne pourrez plus la voir !

### Se connecter à Howler

Le client prend en charge plusieurs méthodes d'authentification :

#### Utiliser une clé API (Recommandé)

Une fois que vous avez votre clé API, connectez-vous à Howler en utilisant la fonction `get_client()` :

```python
from howler_client import get_client

# Vos identifiants
USERNAME = 'votre_nom_utilisateur'  # Des paramètres utilisateur de l'interface Howler
APIKEY = 'nom_cle_api:donnees_cle_api'  # La clé que vous avez générée

# Créer le client
client = get_client("https://votre-instance-howler.com", apikey=(USERNAME, APIKEY))
```

#### Utiliser un jeton JWT

Si vous avez un jeton JWT (par exemple, d'un flux OAuth), vous pouvez vous authentifier en le passant au paramètre `auth` :

```python
from howler_client import get_client

# Votre jeton JWT
JWT_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'  # Votre jeton JWT

# Créer le client
client = get_client("https://votre-instance-howler.com", auth=JWT_TOKEN)
```

Maintenant vous pouvez utiliser l'objet `client` pour interagir avec Howler !

## Créer des hits

La création de hits est le cas d'utilisation principal du client Howler. Le client fournit deux méthodes principales
pour ingérer des données : `client.hit.create()` pour les données déjà au format du schéma Howler, et
`client.hit.create_from_map()` pour les données personnalisées qui doivent être mappées au schéma Howler.

### Utiliser `client.hit.create()`

La méthode `create()` accepte les données de hit au format imbriqué ou plat. Les données doivent être conformes au
schéma Howler.

#### Format imbriqué

C'est le format recommandé car il correspond étroitement au modèle de données Howler :

```python
from hashlib import sha256

# Créer un hit avec une structure imbriquée
hit = {
    "howler": {
        "analytic": "Un test pour créer un hit",
        "score": 0.8,
        "hash": sha256(b"identifiant_unique").hexdigest(),
        "outline": {
            "threat": "10.0.0.1",
            "target": "asdf123",
            "indicators": ["me.ps1"],
            "summary": "Ceci est un résumé",
        },
    },
}

# Créer le hit
response = client.hit.create(hit)

# Vérifier la réponse
print(f"Hits valides : {len(response['valid'])}")
print(f"Hits invalides : {len(response['invalid'])}")
```

#### Format plat

Vous pouvez également fournir les données de hit dans un format plat, avec notation par points :

```python
from hashlib import sha256

# Créer un hit avec une structure plate
hit = {
    "howler.analytic": "Test Dupes",
    "howler.score": 0.0,
    "howler.hash": sha256(b"identifiant_unique").hexdigest(),
}

# Créer le hit
response = client.hit.create(hit)
```

#### Création par lot

Vous pouvez créer plusieurs hits à la fois en passant une liste :

```python
hits = [
    {
        "howler.analytic": "Test par lot",
        "howler.score": 0.5,
        "howler.outline.threat": "192.168.1.1",
        "howler.outline.target": "serveur01",
        "howler.outline.indicators": ["malware.exe"],
        "howler.outline.summary": "Premier hit",
    },
    {
        "howler.analytic": "Test par lot",
        "howler.score": 0.8,
        "howler.outline.threat": "192.168.1.2",
        "howler.outline.target": "serveur02",
        "howler.outline.indicators": ["suspicious.dll"],
        "howler.outline.summary": "Deuxième hit",
    },
]

response = client.hit.create(hits)
```

#### Structure de la réponse

La méthode `create()` retourne un dictionnaire avec deux clés :

- `valid` : Liste des hits créés avec succès avec leurs ID
- `invalid` : Liste des hits qui ont échoué à la validation avec les messages d'erreur

```python
response = client.hit.create(hits)

# Traiter les hits valides
for hit in response['valid']:
    print(f"Hit créé avec l'ID : {hit['id']}")

# Gérer les hits invalides
for result in response['invalid']:
    print(f"Échec de création du hit : {result['error']}")
    print(f"Données du hit : {json.dumps(result['hit'], indent=2)}")
```

### Utiliser `client.hit.create_from_map()`

Lorsque vous avez des données dans un format personnalisé, `create_from_map()` vous permet de définir un mappage de
votre structure de données vers le schéma Howler. Ceci est particulièrement utile pour l'intégration avec des systèmes
externes ou l'ingestion de données provenant de diverses sources.

#### Exemple de base

```python
import datetime
from hashlib import sha256

# Définir le mappage de votre format de données vers le schéma Howler
# Les clés sont vos chemins de champs, les valeurs sont des listes de chemins de champs Howler
mapping = {
    "file.sha256": ["file.hash.sha256", "howler.hash"],
    "file.name": ["file.name"],
    "src_ip": ["source.ip", "related.ip"],
    "dest_ip": ["destination.ip", "related.ip"],
    "time.created": ["event.start"],
    "time.completed": ["event.end"],
}

# Vos données personnalisées
hits = [
    {
        "src_ip": "43.228.141.216",
        "dest_ip": "31.46.39.115",
        "file": {
            "name": "cool_file.exe",
            "sha256": sha256(b"cool_file.exe").hexdigest(),
        },
        "time": {
            "created": datetime.datetime(2020, 5, 17).isoformat() + "Z",
            "completed": datetime.datetime(2020, 5, 18).isoformat() + "Z",
        },
    },
]

# Créer des hits en utilisant le mappage
response = client.hit.create_from_map("mon_outil_analytique", mapping, hits)

# Vérifier les résultats
for hit in response:
    if hit["error"]:
        print(f"Erreur : {hit['error']}")
    else:
        print(f"Hit créé : {hit['id']}")
        if hit["warn"]:
            print(f"Avertissements : {hit['warn']}")
```

#### Structure de la réponse

La méthode `create_from_map()` retourne une liste de dictionnaires, un pour chaque hit d'entrée :

- `id` : L'ID du hit créé (en cas de succès)
- `error` : Message d'erreur si la création a échoué (None en cas de succès)
- `warn` : Liste de messages d'avertissement (par exemple, champs obsolètes utilisés)

### Gérer les erreurs de validation

Lors de la création de hits, des erreurs de validation peuvent se produire. Le client fournit des messages d'erreur détaillés :

```python
from howler_client.common.utils import ClientError

try:
    hits = [
        {
            "howler.analytic": "Test",
            "howler.score": 0.8,
            # Les champs requis manquants causeront l'échec de la validation
        },
        {
            "howler.analytic": "Test",
            # Champ score manquant
            "howler.outline.threat": "10.0.0.1",
        },
    ]

    response = client.hit.create(hits)
except ClientError as e:
    print(f"Erreur : {e}")
    print(f"Hits valides : {len(e.api_response['valid'])}")
    print(f"Hits invalides : {len(e.api_response['invalid'])}")

    for invalid_hit in e.api_response['invalid']:
        print(f"Erreur de validation : {invalid_hit['error']}")
```

### Détection des doublons

Howler détecte automatiquement les hits en double basés sur le champ `howler.hash`. Si vous tentez de créer un hit
avec le même hash qu'un hit existant, il sera ignoré :

```python
from hashlib import sha256

# Créer un hash unique
unique_hash = sha256(b"identifiant_unique").hexdigest()

# La première création réussit
hit1 = {
    "howler.analytic": "Test Dupes",
    "howler.score": 0,
    "howler.hash": unique_hash,
}
client.hit.create(hit1)

# La deuxième création avec le même hash est ignorée
hit2 = {
    "howler.analytic": "Test Dupes",
    "howler.score": 0,
    "howler.hash": unique_hash,  # Même hash !
}
response = client.hit.create(hit2)
# Ce hit ne sera pas créé car c'est un doublon
```

## Opérations de base sur les hits

### Rechercher des hits

La méthode `client.search.hit()` vous permet d'interroger des hits en utilisant la syntaxe Lucene :

```python
# Rechercher tous les hits
results = client.search.hit("howler.id:*")

print(f"Total de hits : {results['total']}")
print(f"Retournés : {len(results['items'])}")

# Accéder aux hits individuels
for hit in results['items']:
    print(f"ID du hit : {hit['howler']['id']}")
    print(f"Analytique : {hit['howler']['analytic']}")
    print(f"Score : {hit['howler']['score']}")
```

#### Paramètres de requête

La méthode `search.hit()` prend en charge plusieurs paramètres :

```python
# Rechercher avec des paramètres spécifiques
results = client.search.hit(
    "howler.analytic:mon_analytique",  # Requête Lucene
    rows=50,                            # Nombre de résultats à retourner (défaut : 25)
    offset=0,                           # Décalage de départ (défaut : 0)
    sort="event.created desc",          # Champ de tri et direction
    fl="howler.id,howler.score",       # Champs à retourner (séparés par des virgules)
    filters=["event.created:[now-7d TO now]"],  # Filtres additionnels
)
```

### Mettre à jour des hits

Le client fournit plusieurs méthodes pour mettre à jour les hits, `overwrite()` étant la plus simple pour la plupart
des cas d'utilisation.

#### Écraser les données de hit (Recommandé)

La méthode `client.hit.overwrite()` est la façon la plus simple de mettre à jour un hit. Fournissez simplement un
objet hit partiel avec les champs que vous souhaitez modifier :

```python
# Obtenir un hit à mettre à jour
hit = client.search.hit("howler.id:*", rows=1, sort="event.created desc")["items"][0]
hit_id = hit["howler"]["id"]

# Écraser des champs spécifiques
updated_hit = client.hit.overwrite(
    hit_id,
    {
        "source.ip": "127.0.0.1",
        "destination.ip": "8.8.8.8",
        "howler.score": 0.95,
        "howler.status": "resolved",
    }
)

print(f"Hit mis à jour : {updated_hit['howler']['id']}")
```

La méthode overwrite accepte à la fois les formats imbriqués et plats :

```python
# Format imbriqué
client.hit.overwrite(
    hit_id,
    {
        "howler": {
            "score": 0.9,
            "status": "open"
        },
        "source": {
            "ip": "10.0.0.1"
        }
    }
)

# Format plat (notation par points)
client.hit.overwrite(
    hit_id,
    {
        "howler.score": 0.9,
        "howler.status": "open",
        "source.ip": "10.0.0.1"
    }
)
```

#### Mises à jour transactionnelles (Pour les opérations en masse)

Pour des scénarios plus complexes comme les mises à jour en masse ou les opérations atomiques (incrément, ajout, etc.),
utilisez `client.hit.update()` :

```python
from howler_client.module.hit import UPDATE_SET, UPDATE_INC

# Obtenir un hit à mettre à jour
hit = client.search.hit("howler.id:*", rows=1)["items"][0]
hit_id = hit["howler"]["id"]

# Mettre à jour le hit avec des opérations
updated_hit = client.hit.update(
    hit_id,
    [
        (UPDATE_SET, "howler.score", 0.95),
        (UPDATE_INC, "howler.escalation", 1),
    ]
)

print(f"Score mis à jour : {updated_hit['howler']['score']}")
```

**Opérations de mise à jour disponibles :**

**Opérations sur les listes :**

```python
from howler_client.module.hit import UPDATE_APPEND, UPDATE_APPEND_IF_MISSING, UPDATE_REMOVE

# Ajouter une valeur à une liste
(UPDATE_APPEND, "howler.outline.indicators", "nouvel_indicateur.exe")

# Ajouter uniquement si pas déjà présent
(UPDATE_APPEND_IF_MISSING, "related.ip", "192.168.1.1")

# Retirer une valeur d'une liste
(UPDATE_REMOVE, "howler.outline.indicators", "faux_positif.exe")
```

**Opérations numériques :**

```python
from howler_client.module.hit import UPDATE_INC, UPDATE_DEC, UPDATE_MAX, UPDATE_MIN

# Incrémenter par montant
(UPDATE_INC, "howler.score", 10)

# Décrémenter par montant
(UPDATE_DEC, "howler.score", 5)

# Définir au maximum de la valeur actuelle et de la valeur spécifiée
(UPDATE_MAX, "howler.score", 50)

# Définir au minimum de la valeur actuelle et de la valeur spécifiée
(UPDATE_MIN, "howler.score", 20)
```

**Opérations générales :**

```python
from howler_client.module.hit import UPDATE_SET, UPDATE_DELETE

# Définir un champ à une valeur spécifique
(UPDATE_SET, "howler.status", "resolved")

# Supprimer un champ
(UPDATE_DELETE, "champ_personnalise", None)
```

#### Mise à jour en masse par requête

Utilisez `client.hit.update_by_query()` pour mettre à jour plusieurs hits correspondant à une requête :

```python
from howler_client.module.hit import UPDATE_INC

# Incrémenter le score pour tous les hits d'une analytique spécifique
client.hit.update_by_query(
    'howler.analytic:"mon_analytique"',
    [
        (UPDATE_INC, "howler.score", 100),
    ]
)

# Note : Cette opération est asynchrone et peut prendre du temps
```

### Supprimer des hits

Supprimez un ou plusieurs hits par leurs ID :

```python
# Supprimer un seul hit
client.hit.delete(["hit_id_1"])

# Supprimer plusieurs hits
client.hit.delete(["hit_id_1", "hit_id_2", "hit_id_3"])

# Exemple : Supprimer tous les hits d'une recherche
results = client.search.hit("howler.analytic:test_analytique")
hit_ids = [hit["howler"]["id"] for hit in results["items"]]
client.hit.delete(hit_ids)
```

## Contribuer au client

Si vous souhaitez contribuer au développement du client Howler, vous devrez configurer l'environnement de développement.

### Configuration du développement

Le code du client se trouve dans le dossier `client/` du monorepo Howler. Pour configurer pour le développement :

```bash
cd ~/repos/howler/client

# Installer Poetry si vous ne l'avez pas
python3 -m pip install poetry

# Configurer Poetry pour créer le virtualenv dans le répertoire du projet
poetry config virtualenvs.in-project true

# Installer les dépendances incluant les dépendances de test
poetry install --with test
```

### Exécuter les tests

Le client dispose d'une suite de tests complète qui s'exécute contre une instance Howler en direct :

```bash
# Démarrer les dépendances de test (API, Elasticsearch, Redis) avec Docker Compose
docker compose -f test/docker-compose.yml up -d

# Attendre que les services soient prêts, puis exécuter les tests
poetry run test
```

Les tests sont situés dans `client/test/` et incluent :

- Tests unitaires pour la fonctionnalité du client
- Tests d'intégration contre l'API

### Qualité du code

Avant de soumettre des modifications, assurez-vous que votre code passe toutes les vérifications de qualité :

```bash
# Exécuter les vérifications de formatage
poetry run ruff format howler_client --diff

# Exécuter les vérifications du linter
poetry run ruff check howler_client

# Exécuter la vérification des types
poetry run type_check
```

### Exécuter des tests spécifiques

Vous pouvez exécuter des fichiers de test spécifiques ou des fonctions de test :

```bash
# Exécuter un fichier de test spécifique
poetry run pytest test/integration/test_hit.py

# Exécuter une fonction de test spécifique
poetry run pytest test/integration/test_hit.py::test_create

# Exécuter avec sortie détaillée
poetry run pytest test/integration/test_hit.py -v
```

## Ressources supplémentaires

- **Documentation de l'API** : Explorez l'API complète sur `https://votre-instance-howler.com/api/doc`
- **Schéma Howler** : Consultez le schéma des hits dans l'interface sous Aide → Schéma des hits
- **Dépôt GitHub** : [https://github.com/CybercentreCanada/howler](https://github.com/CybercentreCanada/howler)
- **Package PyPI** : [https://pypi.org/project/howler-client/](https://pypi.org/project/howler-client/)
- **Suivi des problèmes** : Signalez des bugs ou demandez des fonctionnalités sur [GitHub Issues](https://github.com/CybercentreCanada/howler/issues)
