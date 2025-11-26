# Rétention dans Howler

Afin de se conformer aux politiques organisationnelles, Howler est configuré pour purger les alertes
périmées après une période de temps spécifique. Dans cette instance, cette durée est `duration`.

## Comment fonctionne la rétention

Howler utilise un travail de rétention automatisé qui s'exécute selon un calendrier configurable
(généralement nocturne) pour supprimer les alertes qui ont dépassé leur période de rétention. Le système
évalue deux critères de suppression :

1. **Rétention standard** : Les alertes sont supprimées lorsque `event.created` dépasse la période de
   rétention configurée
2. **Expiration personnalisée** : Les alertes sont supprimées lorsque le champ `howler.expiry` indique
   que l'alerte doit expirer

Une alerte sera supprimée lorsque **l'une ou l'autre** condition est remplie - selon celle qui arrive en
premier.

## Expiration personnalisée (`howler.expiry`)

Le champ `howler.expiry` permet aux ingénieurs de détection de définir des périodes de rétention
personnalisées pour des alertes spécifiques lors de l'ingestion. Ce champ remplace le calcul de
rétention standard et est couramment utilisé quand :

- Les clients ont demandé des périodes de rétention de données plus courtes que la valeur par défaut
  du déploiement
- Des opérations spécifiques nécessitent un stockage de données à durée limitée (par ex., une opération
  de cybersécurité où les données ne peuvent être conservées que deux semaines après ingestion)
- Les exigences réglementaires imposent une suppression plus précoce pour certains types de données

```alert
Le champ howler.expiry ne peut que raccourcir les périodes de rétention, pas les
prolonger. Quoi qu'il arrive, les alertes ne peuvent pas être conservées plus longtemps que la limite de
rétention système basée sur event.created.
```

## Configuration

Les administrateurs peuvent configurer les paramètres de rétention dans la configuration système :

```yaml
system:
  type: staging
  retention:
    limit_amount: 120      # Durée de la période de rétention
    limit_unit: days       # Unité de temps (days, hours, etc.)
    crontab: "0 0 * * *"    # Calendrier (nocturne à minuit)
    enabled: true          # Si la rétention est active
```

## Interface utilisateur

Afin de communiquer le délai de rétention aux utilisateurs, voir l'exemple d'alerte ci-dessous :

`alert`

En haut à droite, le survol de l'horodatage indique le temps dont dispose l'utilisateur avant que
l'alerte ne soit supprimée. Afin de se conformer aux politiques, assurez-vous que `event.created`
correspond à la date à laquelle les données sous-jacentes ont été collectées, permettant à Howler de
s'assurer que les données sont purgées à temps.
