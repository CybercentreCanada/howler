<!-- docs/ingestion/bundles.fr.md -->

# Les groupes des hits Howler

Les groupes des hits peuvent être utilisés pour regrouper facilement un grand nombre d'alertes similaires, ce qui permet aux analystes de les traiter comme un seul incident. Prenons l'exemple d'un ordinateur qui effectue à plusieurs reprises un appel réseau vers `baddomain.ru` - bien qu'une alerte puisse être générée pour chaque cas où cet ordinateur accède à ce domaine, il est logique que les analystes traitent toutes ces alertes comme un seul et même cas.

## Création de groupes via le client Howler

Il y a plusieurs façons de créer un groupe via le client Howler:

```python
from howler_client import get_client

howler = get_client("https://howler.dev.analysis.cyber.gc.ca")

"""Création simultanée d'un groupe howler et de hits"""
howler.bundle.create(
    # Le premier argument est le hit de l'offre groupée
    {
        "howler.analytic": "example-test",
        "howler.score": 0
    },
    # Le deuxième argument est un hit ou une liste de hits à inclure dans l'offre groupée.
    [
        {
            "howler.analytic": "example-test",
            "howler.score": 0
        },
        {
            "howler.analytic": "example-test",
            "howler.score": 0
        }
    ]
)

"""Création d'un groupe howler à partir de hits existants"""
howler.bundle.create(
    {
        "howler.analytic": "example-test",
        "howler.score": 0,
        "howler.hits": ["YcUsL8QsjmwwIdstieROk", "6s7MztwuSvz6tM0PgGJhvz"]
    },
    # Noter: Dans les prochaines versions, vous n'aurez plus besoin d'inclure cet argument.
    []
)


"""Création à partir d'une carte"""
bundle_hit = {
    "score": 0,
    "bundle": True
}

map = {
    "score": ["howler.score"],
    "bundle": ["howler.is_bundle"]
}

howler.bundle.create_from_map("example-test", bundle_hit, map, [{"score": 0}])
```

## Visualiser les groupes sur l'interface utilisateur de Howler

Afin de visualiser les groupes créés sur l'interface utilisateur de Howler, vous pouvez utiliser la requête `howler.is_bundle:true`. Cela fournira une liste de groupes créés que vous pourrez consulter. Pour un exemple, vous pouvez consulter l'instance de développement de Howler ([lien](https://howler.dev.analysis.cyber.gc.ca/hits?query=howler.is_bundle%3Atrue)).

En cliquant sur un groupe, vous ouvrirez une interface de recherche légèrement différente de l'interface normale. Dans ce cas, nous filtrons automatiquement les résultats de la recherche pour n'inclure que les résultats inclus dans le groupe. Pour que cela soit évident, l'en-tête représentant le groupe apparaît au-dessus de la barre de recherche.

Vous pouvez continuer à filtrer les résultats en utilisant les mêmes requêtes que d'habitude et à les visualiser comme d'habitude. Lors du triage d'un groupe, son évaluation s'appliquera à tous les hits du groupe, **sauf ceux qui ont déjà été triés**. En d'autres termes, si le groupe est ouvert, tous les hits ouverts seront évalués lorsque vous l'évaluerez.

Les groupes disposent également d'un onglet **Résumé** qui n'est pas disponible pour les hits ordinaires. Cet onglet vous aidera à regrouper les données relatives à tous les résultats du groupe. Il suffit d'ouvrir l'onglet et de cliquer sur "Créer un sommaire". Notez que cette opération peut prendre un certain temps, car un grand nombre de requêtes sont exécutées pour agréger les données.
