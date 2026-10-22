# Bibliothèque cliente Howler

La bibliothèque cliente Howler facilite l'envoi de requêtes à Howler.

## Mapper des lignes brutes vers des alertes

`RowMapping` applique un mappage YAML version 1 à des lignes brutes, sans
contacter Howler, enregistrer les alertes ni créer d'identifiants réservés au
serveur. Le traitement est paresseux : chaque ligne est lue seulement
lorsqu'elle est demandée, et produit soit `(hit, None)`, soit
`(None, MappingError)`, dans l'ordre source. Une erreur de ligne est retournée au
lieu d'interrompre l'itération, qui peut donc continuer. Les erreurs de
configuration sont levées dès l'appel à `map_rows`; les exceptions de
l'itérateur source sont propagées sans modification. Aucune connexion à Howler
n'est requise.

```python
from howler_client import RowMapping, map_rows

mapping = RowMapping.from_file("mapping.yaml")
for hit, error in map_rows(query_result_rows, mapping):
    if error is not None:
        handle_mapping_error(error)
        continue
    if hit is not None:
        process_hit(hit)
```

Un document de mappage contient `version: 1`, un `on_null` par défaut facultatif
(`error` ou `omit`, `error` par défaut) et `mappings`, qui associe des noms de
champs Howler pointés à une expression : `column` (avec un `path` facultatif de
clés/index dans les valeurs imbriquées; une clé imbriquée absente est traitée
comme nulle), `concat` de deux colonnes de type liste ou plus, ou une constante
`value`. Chaque expression peut définir son propre `on_null` et une liste de
`transforms` (`string`, `integer`, `number`, `boolean`, `trim`, `lower`,
`upper`, `list`, `json` ou `{op: timestamp, assume_timezone: UTC}`). Les
mappages sont lus avec `yaml.safe_load`; mettre entre guillemets les constantes
comme `"yes"` ou `"2026-01-01"` qui doivent rester des chaînes.

On peut aussi créer un `RowMapping` à partir d'un document déjà chargé ou utiliser
`RowMapping.from_yaml(text)`. La fonction `map_rows(rows, mapping)` accepte un
document, un `RowMapping` ou un **chemin de fichier** YAML; utiliser `from_yaml`
pour transmettre explicitement du texte YAML. Les métadonnées de champs Howler
(par exemple le résultat de `client.search.fields.hit()` ou de l'outil MCP
`get_hit_fields`) peuvent être fournies avec `fields=...` pour vérifier que les
champs existent, ne sont pas obsolètes et reçoivent des valeurs de forme (liste)
et de type de base corrects. Sinon, la validation des champs est laissée à
Howler (voir `client.v2.ingest.validate`). Voir
[`examples/row_mapping/example_mapping.yaml`](examples/row_mapping/example_mapping.yaml)
pour un exemple assaini. Cette fonctionnalité transforme uniquement les lignes en
dictionnaires; la persistance et l'ingestion n'en font pas partie.

## Configuration requise

1. Python 3.10 et versions ultérieures

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
