# Ajouter des pivots

Un pivot est une action affichée avec un hit correspondant. Il peut ouvrir une ressource associée, comme un SIEM, un système de tickets ou un tableau de bord d'enquête, en utilisant des valeurs du hit.

`dossier_pivot`

## Pivots de lien

Le format intégré **link** utilise la valeur du pivot comme modèle Handlebars. Ajoutez des mappages pour exposer des champs du hit ou des valeurs personnalisées sous des clés de modèle, puis référencez-les dans la valeur. Par exemple, mappez `host.name` à la clé `hostname` et utilisez `https://investigate.example/?host={{hostname}}` comme valeur.

Chaque clé de mappage doit être unique. Un mappage a aussi besoin d'un champ de hit sélectionné, ou d'une valeur personnalisée lorsque son champ est `custom`. Lorsqu'un champ de hit mappé est un tableau, Howler utilise sa première valeur. Vérifiez les liens générés avec un hit représentatif avant de partager le dossier.

## Formats de pivot des plugins

Les plugins peuvent fournir d'autres formats de pivot et leurs formulaires de configuration. Ces pivots sont rendus par le plugin installé plutôt que comme un lien ordinaire. Si l'implémentation requise est absente, Howler affiche un indicateur d'erreur au lieu d'ouvrir silencieusement une mauvaise destination.

Comme les pistes, les pivots exigent des étiquettes anglaise et française, une icône Iconify valide et un format configuré. Une valeur de pivot est toujours requise; un pivot de lien peut n'avoir aucun mappage seulement lorsque sa destination n'a besoin d'aucune valeur du hit.
