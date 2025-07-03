# Documentation du client Howler

Cette documentation explique comment interagir avec l'API howler en utilisant le client howler dans les environnements de développement Java et Python. Nous décrirons le processus de base de la création d'un nouveau hit dans chaque environnement ainsi que la recherche dans howler des hits correspondant à votre requête.

## Mise en route

### Installation

Afin d'utiliser le client howler, vous devez le lister comme une dépendance dans votre projet.

#### **Python**

Il suffit de l'installer à l'aide de pip:

```bash
pip install howler-client
```

Vous pouvez également l'ajouter à votre requirements.txt, ou à tout autre système de gestion des dépendances que vous utilisez.

### Authentification

Comme indiqué dans la [Documentation sur l'authentification](/help/auth), les utilisateurs peuvent s'authentifier de différentes manières. Pour interfacer avec le client howler, cependant, le flux suggéré est d'utiliser une clé API. Avant de commencer, générons une clé.

1. Ouvrez l'interface utilisateur Howler avec laquelle vous souhaitez vous interfacer.
2. Connectez-vous, puis cliquez sur votre profil en haut à droite.
3. Dans le menu utilisateur, cliquez sur Paramètres.
4. Sous Sécurité de l'utilisateur, appuyez sur l'icône (+) sur la ligne Clés API.
5. Nommez votre clé et donnez-lui les autorisations nécessaires.
6. Appuyez sur Create (Créer) et copiez la chaîne fournie dans un endroit sûr. \*\*Vous ne reverrez plus cette chaîne.

Cette clé API sera fournie à votre code par la suite.

## Client Python

Pour se connecter à howler en utilisant le client python, il y a un processus assez simple à suivre:

```python
from howler_client import get_client

USERNAME = 'user' # Obtenez-le à partir de la page des paramètres de l'utilisateur de l'interface utilisateur de Howler.
APIKEY = 'apikey_name:apikey_data'

apikey = (USERNAME, APIKEY)

howler = get_client("$CURRENT_URL", apikey=apikey)
```

Voilà, c'est fait ! Vous pouvez maintenant utiliser l'objet `howler` pour interagir avec le serveur. A quoi cela ressemble-t-il en réalité?

### Créer des hits en Python

Pour le client python, vous pouvez créer des hits en utilisant les fonctions `howler.hit.create` ou `howler.hit.create_from_map`.

#### `create`

Cette fonction prend un seul argument - soit un hit unique, soit une liste de hits, conforme au [Howler Schema] (/help/hit?tab=schema). Voici un exemple simple :

```python
# Quelques données bidons au format Howler Schema
exemple_hit = {
  "howler" : {
    "analytic" : "exemple",
    "score" : 10.0
  },
  "event" : {
    "reason" : "Exemple hit"
  }
}

howler.hit.create(example_hit)
```

Vous pouvez également ingérer des données dans un format plat :

```python
example_hit = {
  "howler.analytic": "example",
  "howler.score": 10.0,
  "event.reason": "Example hit"
}

howler.hit.create(example_hit)
```

#### `create_from_map`

This function takes in three arguments:

- `tool name`: Le nom de l'outil d'analyse qui crée le hit
- `map`: Une correspondance entre les données brutes que vous avez et le schéma howler
  - Le format est un dictionnaire où les clés sont le chemin aplati des données brutes, et les valeurs sont une liste de chemins aplatis pour les champs de Howler dans lesquels les données seront copiées.
- `documents`: Les données brutes que vous voulez ajouter à Howler.

Voici un exemple simple:

```python
# La correspondance entre nos données et le schéma de Howler
hwl_map = {
  "file.sha256": ["file.hash.sha256", "howler.hash"],
  "file.name": ["file.name"],
  "src_ip": ["source.ip", "related.ip"],
  "dest_ip": ["destination.ip", "related.ip"],
  "time.created": ["event.start"],
}

# Quelques fausses données dans un format personnalisé que nous voulons ajouter à howler
example_hit = {
  "src_ip": "0.0.0.0",
  "dest_ip": "8.8.8.8",
  "file": {
    "name": "hello.exe",
    "sha256": sha256(str("hello.exe").encode()).hexdigest()
  },
  "time": {
    "created": datetime.now().isoformat()
  },
}

# Notez que le troisième argument est de type liste!
howler.hit.create_from_map("example_ingestor", hwl_map, [example_hit])
```

### Interroger les hits en Python

L'interrogation des hits avec le client python howler se fait en utilisant la fonction `howler.search.hit`. Elle possède un certain nombre d'arguments obligatoires et optionnels:

- Obligatoire:
  - `query`: requête lucene (chaîne)
- Facultatif: `filters`: requête lucene (chaîne):
  - `filters`: Requêtes lucene additionnelles utilisées pour filtrer les données (liste de chaînes)
  - `fl`: Liste des champs à retourner (chaîne de champs séparés par des virgules)
  - `offset`: Offset auquel les éléments de la requête doivent commencer (entier)
  - `rows`: Nombre d'enregistrements à retourner (entier)
  - `sort`: Champ utilisé pour le tri avec direction (chaîne: ex. 'id desc')
  - `timeout`: Nombre maximum de millisecondes d'exécution de la requête (entier)
  - `use_archive`: Interroge également l'archive
  - `track_total_hits`: Nombre de hits à suivre (par défaut: 10k)

Voici quelques exemples de requêtes:

```python
# Rechercher tous les hits créés par assemblyline, afficher les 50 premiers et ne renvoyer que leurs identifiants.
howler.search.hit("howler.analytic:assemblyline", fl="howler.id", rows=50)

# Recherche de toutes les occurrences résolues créées au cours des cinq derniers jours, avec indication de leur identifiant et de l'analyste qui les a créées. N'en afficher que dix, décalés de 40
howler.search.hit("howler.status:resolved", filters=['event.created:[now-5d TO now]'] fl="howler.id,howler.analytic", rows=10, offset=40)

# Recherche de tous les résultats, délai d'attente si la requête prend plus de 100 ms
howler.search.hit("howler.id:*", track_total_hits=100000000, timeout=100, use_archive=True)
```

### Mise à jour des résultats

Afin de mettre à jour les hits, il existe un certain nombre de fonctions supportées :

- `howler.hit.update(...)`
- `howler.hit.update_by_query(...)`
- `howler.hit.overwrite(...)`

#### `update()`

Si vous souhaitez mettre à jour un hit de manière transactionnelle, vous pouvez utiliser le code suivant:

```python
hit_to_update = client.search.hit("howler.id:*", rows=1, sort="event.created desc")["items"][0]

result = client.hit.update(hit_to_update["howler"]["id"], [(UPDATE_SET, "howler.score", hit_to_update["howler"]["score"] + 100)])
```

Les opérations suivantes peuvent être exécutées pour mettre à jour un résultat.

**Opérations de liste:**

- `UPDATE_APPEND` : Utilisé pour ajouter une valeur à une liste donnée
- `UPDATE_APPEND_IF_MISSING` : Utilisé pour ajouter une valeur à une liste donnée si la valeur n'est pas déjà dans la liste.
- `UPDATE_REMOVE` : Supprime une valeur donnée d'une liste

**Opérations numériques:**

- `UPDATE_DEC` : Diminue une valeur numérique de la quantité spécifiée.
- `UPDATE_INC` : Incrémente une valeur numérique de la quantité spécifiée.
- `UPDATE_MAX` : Fixe une valeur numérique au maximum de la valeur existante et de la valeur spécifiée.
- `UPDATE_MIN` : Fixe une valeur numérique au minimum de la valeur existante et de la valeur spécifiée.

**Opérations polyvalentes:**

- `UPDATE_SET` : Fixe la valeur d'un champ à la valeur donnée.
- `UPDATE_DELETE` : Supprime la valeur d'un champ donné

#### `update_by_query()`

Cette fonction vous permet de mettre à jour un grand nombre d'occurrences à l'aide d'une requête :

```python
client.hit.update_by_query(f'howler.analytic : "Exemple d\'analytic"', [(UPDATE_INC, "howler.score", 100)])
```

Les mêmes opérations que dans `update()` peuvent être utilisées.

### `overwrite()`

Cette fonction vous permet d'écraser directement un hit avec un objet hit partiel. C'est la plus facile à utiliser, mais elle perd une partie de la validation et du traitement supplémentaire des fonctions de mise à jour.

```python
hit_to_update = client.search.hit("howler.id:*", rows=1, sort="event.created desc")["items"][0]

result = client.hit.overwrite(hit_to_update["howler"]["id"], {"source.ip" : "127.0.0.1", “destination.ip” : "8.8.8.8"})
```
