# Rétention dans Howler

Afin de se conformer au règlement, Howler est configuré pour purger les alertes périmées après une période de temps spécifique. Dans cette instance, cette durée est `duration`.

Howler calcule s'il est temps de supprimer une alerte en fonction de la date `event.created` - une fois que celle-ci dépasse la date limite configurée, un travail automatisé nocturne supprimera l'alerte.

Afin de communiquer cela à l'utilisateur, voir l'exemple d'alerte ci-dessous :

`alert`

En haut à droite, le survol de l'horodatage indique le temps dont dispose l'utilisateur avant que l'alerte ne soit supprimée. Afin de se conformer au règlement, assurez-vous que `event.created` correspond à la date à laquelle les données sous-jacentes ont été collectées, ce qui permet à howler de s'assurer que les données sont purgées à temps.

```alert
Cela va bientôt changer - il y aura un champ dédié à définir qui remplacera cette approche.
```
