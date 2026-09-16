# Structurer et réutiliser les résultats

Utilisez le curseur du nombre de lignes pour limiter la réponse à 1, 5, 25, 50, 100, 250, 500, 1 000, 2 500 ou 10 000 lignes. Commencez avec peu de lignes lors de la validation d'une requête afin de garder la réponse JSON ciblée et réactive. Le mode Expliquer ignore la limite de lignes et les contrôles de sélection des champs.

`advanced_results`

## Choisir les champs de hit

Lorsque **Afficher tous les champs** est sélectionné, les hits retournés contiennent chaque champ disponible. Désactivez-le pour choisir une liste de champs ciblée. Si vous retirez le dernier champ sélectionné, Howler revient à l'affichage de tous les champs. Le mode Facette demande toujours les champs à compter; la liste choisie fait partie de la demande de facette.

Le panneau de réponse affiche la réponse du serveur comme JSON extensible. Sa structure dépend du langage et du mode d'exécution; examinez les sections d'agrégat ainsi que les données de hit individuelles.

## Ouvrir une requête Lucene dans la recherche

Après toute réponse Lucene réussie, **Ouvrir en recherche** devient disponible. Ce raccourci transfère le filtre Lucene normalisé vers la page Recherche, où vous pouvez continuer le triage, enregistrer une vue ou agir sur les hits correspondants.

Le raccourci transfère seulement le filtre. Il ne transfère pas la configuration de facette, de regroupement ou d'explication, les champs sélectionnés, ni la limite de lignes de la recherche avancée. Il utilise le contenu actuel de l'éditeur; exécutez donc la requête à nouveau après une modification avant d'ouvrir la recherche. Les réponses EQL et Sigma restent dans la recherche avancée puisqu'elles ne correspondent pas directement à une recherche de hit Lucene habituelle.
