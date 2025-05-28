# Intégration de carnets

Howler offre la possibilité d'ajouter des carnets aux analyses afin de faciliter le triage des hits et des alertes. Il permet aux utilisateurs de créer rapidement un carnet dans un environnement Jupyter avec des informations analytiques et/ou des informations sur les hits.

Howler cherchera des variables à remplacer dans la première cellule de code d'un notebook, ce qui permettra de fournir un contexte dans les premières cellules à l'aide de markdown.

Voici un exemple de la façon dont Howler remplacera les variables dans votre carnet :

```notebook tab="Modèle"
{
  "cells": [
    {
      "cell_type": "code",
      "id": "fe6f810f-2459-4ad7-92ac-1e925ce892d4",
      "outputs": [],
      "source": [
        "HowlerHitId = \"{{hit.howler.id}}\"\n",
        "HowlerAnalyticId = \"{{analytic.analytic_id}}\""
      ]
    },
    {
      "cell_type": "code",
      "id": "586470ef-c8e6-45b1-bd17-17ccd083eef1",
      "outputs": [],
      "source": [
        "from howler_client import get_client\n\n",
        "howler = get_client(\"$CURRENT_URL\")\n",
        "hit = howler.hit(howlerHitId)"
      ]
    }
  ],
  "nbformat": 4,
  "nbformat_minor": 5
}
```

```notebook tab="Traité"
{
  "cells": [
    {
      "cell_type": "code",
      "id": "fe6f810f-2459-4ad7-92ac-1e925ce892d4",
      "outputs": [],
      "source": [
        "HowlerHitId = \"7dxHCat0Y2Sj48qyU7ZkVV\"\n",
        "HowlerAnalyticId = \"2SXKl6Cq4rOxWLps2SFHyB\""
      ]
    },
    {
      "cell_type": "code",
      "id": "586470ef-c8e6-45b1-bd17-17ccd083eef1",
      "outputs": [],
      "source": [
        "from howler_client import get_client\n\n",
        "howler = get_client(\"$CURRENT_URL\")\n",
        "hit = howler.hit(howlerHitId)"
      ]
    }
  ],
  "nbformat": 4,
  "nbformat_minor": 5
}
```

ou avec du markdown dans la première cellule :

```notebook tab="Modèle"
{
  "cells": [
    {
      "cell_type": "markdown",
      "id": "e17cbaa8-9849-462f-9bd2-bf30943f76b3",
      "source": [
        "### Exemple de carnet"
      ]
    },
    {
      "cell_type": "code",
      "id": "fe6f810f-2459-4ad7-92ac-1e925ce892d4",
      "outputs": [],
      "source": [
        "HowlerHitId = \"{{hit.howler.id}}\"\n",
        "HowlerAnalyticId = \"{{analytic.analytic_id}}\""
      ]
    },
    {
      "cell_type": "code",
      "id": "586470ef-c8e6-45b1-bd17-17ccd083eef1",
      "outputs": [],
      "source": [
        "from howler_client import get_client\n\n",
        "howler = get_client(\"$CURRENT_URL\")\n",
        "hit = howler.hit(howlerHitId)"
      ]
    }
  ],
  "nbformat": 4,
  "nbformat_minor": 5
}
```

```notebook tab="Traité"
{
  "cells": [
    {
      "cell_type": "markdown",
      "id": "e17cbaa8-9849-462f-9bd2-bf30943f76b3",
      "source": [
        "### Exemple de carnet"
      ]
    },
    {
      "cell_type": "code",
      "id": "fe6f810f-2459-4ad7-92ac-1e925ce892d4",
      "outputs": [],
      "source": [
        "HowlerHitId = \"7dxHCat0Y2Sj48qyU7ZkVV\"\n",
        "HowlerAnalyticId = \"2SXKl6Cq4rOxWLps2SFHyB\""
      ]
    },
    {
      "cell_type": "code",
      "id": "586470ef-c8e6-45b1-bd17-17ccd083eef1",
      "outputs": [],
      "source": [
        "from howler_client import get_client\n\n",
        "howler = get_client(\"$CURRENT_URL\")\n",
        "hit = howler.hit(howlerHitId)"
      ]
    }
  ],
  "nbformat": 4,
  "nbformat_minor": 5
}
```

Présentement, Howler n'essaiera de remplacer que les objets de hit et d'analytic.

# Conditions requises pour que l'intégration de carnets fonctionne

- Une configuration NBGallery fonctionnelle est nécessaire.
  - Si l'utilisateur peut envoyer un carnet depuis NBGallery vers son environnement Jupyter, il fonctionnera aussi en utilisant le bouton open in jupyhub sur Howler.
- Comme pour NBGallery, l'utilisateur doit s'assurer que son environnement Jupyter est en cours d'exécution, sinon Howler ne parviendra pas à envoyer le carnet.

Howler ajoutera l'identifiant du Hit/Alert lorsqu'il enverra un carnet à Jupyter, ce qui facilitera son suivi pour l'analyse. Il est possible d'ouvrir un carnet à partir d'une page analytique. Dans ce cas, aucun identifiant de résultat ne sera ajouté au nom de fichier du carnet et Howler ne sera pas en mesure de remplacer les informations de hit dans le carnet modèle puisqu'aucun hit n'a été fourni.

# Ajout d'un carnet à une analyse

Pour ajouter un carnet à une analyse, il suffit de fournir le lien NBGallery du carnet. Le lien ressemblera à l'exemple ci-dessous. Le carnet ne doit pas être privé, sinon seul l'utilisateur qui l'a ajouté pourra l'utiliser sur Howler.

```
$NBGALLERY_URL/notebooks/5-example
```

```alert
Il est conseillé d'effacer toutes les sorties d'un carnet avant de l'ajouter sur NBGallery afin d'éviter la fuite de données sensibles.
```
