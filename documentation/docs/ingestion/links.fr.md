<!-- docs/ingestion/links.fr.md -->

# Liens du hit

Afin de faciliter l'ajout d'outils supplémentaires que l'on peut utiliser pour suivre un hit, Howler permet aux utilisateurs de spécifier un ensemble de liens, ainsi qu'un titre et une icône à afficher. Cette documentation vous expliquera comment utiliser ces liens.

## Specification

Afin d'ajouter des liens, vous pouvez utiliser le champ `howler.links`. Ce champ contient une liste d'objets avec trois clés :

```python
hit = {
  "howler.links": [
    {
      "title": "Titre du lien avec image interne",
      "href": "https://example.com",
      # Notez qu'il s'agit d'une autre application, et non d'un lien vers une image.
      "icon": "superset",
    },
    {
      "title": "Titre du lien avec image externe",
      "href": "https://www.britannica.com/animal/goose-bird",
      # Notez qu'il s'agit d'un lien vers une image. Nous ne fournissons pas d'hébergement, vous devrez donc l'héberger ailleurs !
      "icon": "https://cdn.britannica.com/76/76076-050-39DDCBA1/goose-Canada-North-America.jpg",
    },
  ]
}
```

Notez que l'icône peut être soit :
1. Un nom identifiant une application interne, pour utiliser son icône
2. Une URL externe

Si vous souhaitez utiliser une application interne, les valeurs suivantes sont actuellement prises en charge :

$APP_LIST

L'utilisation de l'une de ces valeurs entraîne automatiquement l'utilisation de l'icône correspondante. Inutile d'héberger la vôtre !
