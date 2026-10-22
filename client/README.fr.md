# Bibliothèque cliente Howler

`howler-client` est le client Python de l'API [Howler](https://github.com/CybercentreCanada/howler). Il permet de :

- créer, rechercher, mettre à jour et supprimer des alertes (_hits_)
- gérer les commentaires, actions, utilisateurs et dossiers (_cases_)
- convertir hors ligne des lignes de tables brutes en alertes, avant leur ingestion

Il gère l'authentification, la mise en forme des requêtes, les nouvelles tentatives et l'analyse des réponses.

- **Paquet :** [howler-client sur PyPI](https://pypi.org/project/howler-client/)
- **Guide d'utilisation :** [documentation du client Howler](https://cybercentrecanada.github.io/howler/ingestion/client/)
- **Guide de contribution :** [développement du client](https://cybercentrecanada.github.io/howler/developer/client/)

## Installation

Le client requiert Python 3.10 ou une version ultérieure.

```bash
pip install howler-client
```

## Connexion à Howler

`get_client()` retourne un `Client` connecté à un serveur Howler. À la connexion, il vérifie que le serveur prend en
charge l'API v1; le serveur doit donc être joignable.

```python
from howler_client import get_client

# Clé d'API (recommandé) : à créer dans l'interface Howler, sous Paramètres -> Sécurité de l'utilisateur -> Clés d'API
client = get_client("https://howler.example.com", apikey=("mon_utilisateur", "nom_de_cle:secret_de_cle"))

# JWT, par exemple obtenu par un flux OAuth
client = get_client("https://howler.example.com", auth="eyJhbGciOi...")

# Nom d'utilisateur et mot de passe (seulement si le serveur permet l'authentification interne)
client = get_client("https://howler.example.com", auth=("mon_utilisateur", "mon_mot_de_passe"))
```

Autres options utiles de `get_client()` :

- `verify` : vérifier ou non les certificats TLS.
- `cert` : un certificat client.
- `timeout` : le délai d'expiration des requêtes.
- `retries` : le nombre de nouvelles tentatives. La valeur par défaut, `0`, réessaie indéfiniment.
- `throw_on_bad_request` et `throw_on_max_retries` : lever ou non une `ClientError` en cas d'échec.
- `authenticate` : une fonction de rappel qui retourne un jeton _bearer_.

## Fonctionnalités du client

| Attribut | Rôle |
| --- | --- |
| `client.hit` | Créer des alertes (`create`), en obtenir une par son ID (`client.hit(hit_id)`), `overwrite`, `update`, `update_by_query`, `delete`, `generate_hash`. Les commentaires sont sous `client.hit.comment` (`add`, `edit`, `delete`). |
| `client.search` | Recherche Lucene sur les alertes (`hit`) et les actions (`action`), ainsi que les utilitaires `facet`, `fields`, `grouped`, `histogram`, `stats` et `stream`, chacun avec une méthode `.hit(...)`. |
| `client.action` | Lister, créer et exécuter des actions enregistrées. |
| `client.user` | Ajouter, supprimer, lister et mettre à jour des utilisateurs; `whoami`. |
| `client.help` | Métadonnées du serveur, comme `classification_definition()`. |
| `client.v2.ingest` | Ingestion v2 pour les index `hit` et `event` : `create`, `validate` (vérifier des enregistrements sans les stocker), `overwrite`, `update_by_query`, `delete`. |
| `client.v2.search` | Recherche dans plusieurs index à la fois (`client.v2.search("hit,event", query)`), ainsi que `count`, `facet` et `explain`. |
| `client.v2.case` | Obtenir, créer, mettre à jour, masquer et supprimer des dossiers; gérer leurs éléments et leurs règles de corrélation. |
| `client.mapping` | `map_rows(...)`, identique à la fonction `howler_client.map_rows`. Voir plus bas. |

Par exemple :

```python
results = client.search.hit("howler.status:open", rows=10, sort="event.created desc")
for hit in results["items"]:
    print(hit["howler"]["id"], hit["howler"]["analytic"])

client.hit.create({"howler": {"analytic": "Mon analytique", "score": 0.5}})
```

Les requêtes qui échouent lèvent `howler_client.common.utils.ClientError`, qui a les attributs `status_code` et
`api_response`. Voir le [guide d'utilisation](https://cybercentrecanada.github.io/howler/ingestion/client/) pour
d'autres exemples.

## Mapper des lignes brutes vers des alertes

`RowMapping` convertit des lignes brutes en dictionnaires d'alertes Howler à l'aide d'un fichier de mappage YAML. Le
traitement est entièrement hors ligne :

- Il ne requiert aucune connexion à Howler.
- Il ne stocke ni n'ingère aucun enregistrement.
- Il ne définit jamais d'identifiants réservés au serveur, comme `howler.id`.

Pour stocker les résultats, les transmettre à `client.hit.create` ou à `client.v2.ingest.create`.

```python
from howler_client import RowMapping, map_rows

mapping = RowMapping.from_file("mapping.yaml")

for hit, error in map_rows(query_result_rows, mapping):
    if error is not None:
        handle_mapping_error(error)  # une MappingError indiquant le numéro de ligne et le champ cible
        continue
    process_hit(hit)
```

Comportement de `map_rows` :

- Il est paresseux : il ne lit chaque ligne source que lorsque le résultat suivant est demandé.
- Pour chaque ligne, dans l'ordre, il produit soit `(hit, None)`, soit `(None, MappingError)`.
- Une ligne invalide produit un résultat d'erreur, et les lignes suivantes sont quand même traitées.
- Un mappage invalide lève une erreur dès l'appel à `map_rows`, avant la lecture de toute ligne.
- Les exceptions levées par l'itérateur de lignes sont propagées sans modification.

Pour mapper une seule ligne, `mapping.map_row(row)` retourne l'alerte ou lève une `MappingError`.

### Format du fichier de mappage

```yaml
version: 1
on_null: error # valeur par défaut pour toutes les cibles : error (par défaut) ou omit
mappings:
  howler.analytic:
    value: Directory User Inventory # constante
  user.id:
    column: user_identifier # copier une colonne
  user.name:
    column: account_name
    transforms: [trim, lower]
  user.email:
    column: primary_email
    on_null: omit # omettre le champ si la valeur est nulle
  organization.name:
    column: profile
    path: [organization, name] # lire une valeur imbriquée dans la colonne
  user.roles:
    concat: [directory_role_names, elevated_role_names] # joindre des colonnes de type liste
```

Chaque clé sous `mappings` est un nom de champ Howler pointé. Chaque cible requiert exactement une source :

| Expression | Résultat |
| --- | --- |
| `column: nom` | La valeur de cette colonne. Une colonne absente est une erreur de ligne. |
| `column` + `path: [clé, 0, ...]` | Une valeur imbriquée dans la colonne, trouvée par clés de dictionnaire et index de liste. Une clé ou un index imbriqué absent compte comme nul. |
| `concat: [a, b, ...]` | Deux colonnes de type liste ou plus, jointes en une seule liste. |
| `value: ...` | Une constante, calculée une seule fois au chargement du mappage. |

Une cible peut aussi définir :

- `on_null`, qui remplace la valeur définie pour le document. Avec `error`, une valeur nulle fait échouer la ligne.
  Avec `omit`, le champ est omis.
- `transforms`, appliquées dans l'ordre :

| Transformation | Effet |
| --- | --- |
| `string` | Convertit une valeur scalaire en chaîne. Utiliser `json` pour les objets et les listes. |
| `integer`, `number`, `boolean` | Conversions strictes. `boolean` n'accepte que des booléens ou `"true"`/`"false"`. |
| `trim`, `lower`, `upper` | Nettoyage de chaînes. |
| `list` | Place une valeur scalaire dans une liste. |
| `json` | Convertit la valeur en texte JSON compact à clés triées. |
| `{op: timestamp}` | Convertit une chaîne ISO-8601 en UTC. Ajouter `assume_timezone: UTC` pour accepter les valeurs sans fuseau horaire. |

Les fichiers de mappage sont lus avec `yaml.safe_load`. Mettre entre guillemets les constantes qui doivent rester des
chaînes, comme `"yes"`, `"off"` ou `"2026-01-01"`.

On peut aussi créer un mappage à partir de texte YAML avec `RowMapping.from_yaml(text)`, ou à partir d'un dictionnaire
déjà chargé avec `RowMapping(document)`. `map_rows` accepte un `RowMapping`, un dictionnaire ou un chemin de fichier
YAML. Pour utiliser du texte YAML, passer par `from_yaml` afin qu'il ne soit pas pris pour un chemin.
[`examples/row_mapping/example_mapping.yaml`](examples/row_mapping/example_mapping.yaml) est un exemple complet.

### Vérifier les cibles par rapport aux champs Howler

On peut fournir les métadonnées de champs de Howler pour vérifier les cibles avant toute ingestion. Utiliser le
résultat de `client.search.fields.hit()` ou de l'outil MCP `get_hit_fields` :

```python
fields = client.search.fields.hit()
mapping = RowMapping.from_file("mapping.yaml", fields=fields)
```

Avec ces métadonnées, `RowMapping` vérifie que :

- chaque cible existe et n'est pas obsolète
- chaque cible `concat` est un champ de type liste

`RowMapping` ne valide pas les valeurs mappées par rapport au type du champ cible ni à la forme (liste ou valeur
unique). Vérifier les enregistrements avec `client.v2.ingest.validate("hit", hits)` ou laisser Howler les valider lors
de l'ingestion.

## Développement

Le client se trouve dans le dossier `client/` du monodépôt Howler. Il utilise son propre environnement
[Poetry](https://python-poetry.org/); exécuter toutes les commandes ci-dessous depuis `client/`.

### Installation

```bash
cd client
poetry install --with dev,test,types
```

Les crochets pre-commit du dépôt exécutent Ruff et vérifient les messages de commit. Depuis la racine du dépôt, les
installer avec `pre-commit install`.

### Qualité du code

Voici les vérifications exécutées par l'intégration continue :

```bash
poetry run ruff format howler_client --diff
poetry run ruff check howler_client --output-format=github
poetry run type_check # mypy sur howler_client
```

### Tests unitaires

Les tests unitaires de `test/unit/` s'exécutent hors ligne : ils ne requièrent ni serveur Howler, ni Elasticsearch,
ni Redis.

```bash
poetry run test test/unit                                   # tous les tests unitaires
poetry run test test/unit/test_row_mapping.py -k timestamp  # exécution ciblée; les arguments sont transmis à pytest
```

### Tests d'intégration

Les tests d'intégration de `test/integration/` appellent une API Howler en cours d'exécution à
`http://localhost:5000`. Définir `UI_HOST` pour utiliser une autre adresse. L'API requiert Elasticsearch, Redis et des
données de test. Pour reproduire la configuration de l'intégration continue, à partir de la racine du dépôt :

```bash
# 1. Préparer la configuration de l'API
sudo mkdir -p /etc/howler/conf /etc/howler/lookups /var/log/howler
sudo chown -R "$USER" /etc/howler /var/log/howler
cp api/build_scripts/classification.yml /etc/howler/conf/classification.yml
cp api/build_scripts/mappings.yml /etc/howler/conf/mappings.yml
cp client/test/config/config.ci.yml /etc/howler/conf/config.yml

# 2. Démarrer Elasticsearch et Redis
docker compose -f client/test/docker-compose.yml up -d

# 3. Installer et démarrer l'API (la laisser tourner dans son propre terminal)
cd api
poetry install --with test,dev
poetry run mitre /etc/howler/lookups
poetry run sigma
TESTING=true poetry run flask --app howler.app run --no-reload

# 4. Dans un autre terminal, créer les utilisateurs et des données aléatoires (crée la clé d'API admin utilisée par les tests)
cd api
poetry run python -m howler.odm.random_data

# 5. Exécuter toute la suite de tests du client, avec couverture
cd ../client
poetry run test
```

Sans argument, `poetry run test` exécute tout le contenu de `test/` avec la couverture des branches. Les tests
d'intégration requièrent les services en cours d'exécution. Pour n'exécuter qu'une partie de la suite, transmettre des
chemins ou des options pytest.

### Versions

Les versions sont publiées automatiquement par Release Please, à partir de commits conventionnels. Utiliser la portée
`client`, par exemple `feat(client): ...`. `CHANGELOG.md` est généré; ne pas le modifier à la main.
