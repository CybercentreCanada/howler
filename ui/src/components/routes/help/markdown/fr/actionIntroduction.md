# Utilisation des actions dans Howler

Les actions sont une fonctionnalité de Howler qui permet aux utilisateurs d'effectuer des tâches particulières sur un grand nombre de hits, en automatisant l'exécution d'une tâche sur chaque hit. Il y a actuellement `action_count` opérations supportées dans Howler :

`action_list`

Toutes ces opérations peuvent être combinées ensemble dans des actions uniques - c'est-à-dire que les opérations sont essentiellement les blocs de construction des actions dans Howler. Chaque opération ne peut apparaître qu'une seule fois par action, et toutes les opérations sont configurées à travers une interface unifiée. Dans ce document, nous allons parcourir les étapes nécessaires à l'exécution et à la sauvegarde d'une action.

## Configuration d'une action

Pour commencer à configurer votre action, décidez s'il s'agit d'une action unique ou d'une action sauvegardée que vous souhaitez exécuter plusieurs fois. Si vous voulez l'exécuter une fois, utilisez l'entrée `t(route.actions.change)` dans la barre latérale, alors qu'une action sauvegardée est mieux configurée sous `t(route.actions.manager)` en appuyant sur "`t(route.actions.create)`".

La première étape de toute action sera de concevoir une requête sur laquelle vous voulez que cette action s'exécute. La boîte de recherche en haut de l'écran accepte n'importe quelle requête lucene - le même format que pour la recherche d'occurrences.

`tui_phrase`

Une fois que vous êtes satisfait des occurrences qui seront incluses dans cette requête, vous pouvez commencer à ajouter des opérations. Vous pouvez le faire en sélectionnant l'opération que vous voulez ajouter dans la liste déroulante:

`operation_select`

Une fois que vous avez sélectionné l'opération que vous souhaitez ajouter, une liste de paramètres à remplir vous est proposée. Voici un exemple d'ajout d'une étiquette.

`operation_configuration`

Une fois que l'opération est validée avec succès, vous pouvez répéter ce processus avec l'opération suivante. Une fois que vous avez ajouté toutes les opérations qui vous intéressent, vous pouvez exécuter ou sauvegarder l'action en utilisant le bouton situé sous la barre de recherche. Vous obtiendrez ainsi un rapport sur les étapes franchies.

`report`

Il peut arriver que des actions génèrent une erreur, soit lors de la validation, soit lors de l'exécution. Dans ce cas, une alerte d'erreur sera affichée, vous aidant à résoudre le problème.

## Automatiser une action

Pour automatiser une action, ouvrez une action sauvegardée. Les options disponibles pour l'automatisation (`automation_options`) apparaîtront sous forme de cases à cocher. En cochant la case, vous vous assurez que l'action s'exécutera ensuite - aucune autre opération n'est nécessaire.
