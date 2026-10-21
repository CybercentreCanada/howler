# Bibliothèque cliente Howler

La bibliothèque cliente Howler facilite l'envoi de requêtes à Howler.

## Mapper des lignes brutes vers des alertes

`howler_client.mapping` applique un mappage YAML version 1 révisé à des lignes
brutes, sans contacter Howler, enregistrer les alertes ni créer d'identifiants
réservés au serveur. Les deux API sont des générateurs : chaque ligne est lue
seulement lorsqu'elle est demandée, et produit soit `(hit, None)`, soit
`(None, MappingError)`, dans l'ordre source. Une erreur de ligne est retournée au
lieu d'interrompre l'itération, qui peut donc continuer. Les erreurs de
configuration sont levées avant la consommation de la source; les exceptions de
l'itérateur source sont propagées sans modification.

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

On peut aussi créer un `RowMapping` à partir d'un document déjà chargé ou utiliser
`RowMapping.from_yaml(text)`. La fonction `map_rows(rows, mapping)` accepte un
document, un `RowMapping` ou un **chemin de fichier** YAML; utiliser `from_yaml`
pour transmettre explicitement du texte YAML. Un instantané MCP sauvegardé peut
être fourni pour vérifier le point de terminaison, l'empreinte, les champs, les
listes et les types. Sans instantané, seules la structure du mappage et la sûreté
des lignes rendues sont vérifiées; l'existence des champs ou l'acceptation par le
serveur ne sont pas garanties. Voir
[`examples/row_mapping/example_mapping.yaml`](examples/row_mapping/example_mapping.yaml)
pour un exemple assaini avec des métadonnées synthétiques. Cette fonctionnalité
transforme uniquement les lignes en dictionnaires; la persistance et l'ingestion
n'en font pas partie. Les valeurs mappées, constantes et métadonnées d'instantané
sont limitées à 128 conteneurs JSON imbriqués. Les colonnes source non mappées ne
sont ni parcourues ni copiées.

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
