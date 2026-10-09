# Structurer et réutiliser les résultats

Utilisez le curseur du nombre de lignes pour choisir une limite de réponse de 1, 5, 25, 50, 100, 250, 500, 1 000, 2 500 ou 10 000. Le réglage initial est 5. Ce que la limite compte dépend du langage et du mode de requête :

- **Défaut** et **Règle Sigma** : les hits retournés.
- **EQL** : les événements ou les séquences retournés, selon la requête.
- **Facette** : les groupes de valeurs retournés par champ sélectionné; les comptes utilisent l'ensemble correspondant, et non seulement ce nombre de hits.
- **Regrouper** : les groupes retournés, chacun avec un hit représentatif par défaut.

Commencez avec une petite limite lors de la validation d'une requête afin de garder la réponse JSON ciblée et réactive. Le mode Expliquer ignore la limite de lignes et les contrôles de sélection des champs.

`advanced_results`

## Choisir les champs de hit

Pour les recherches Lucene ordinaires et Sigma, **Afficher tous les champs** retourne chaque champ disponible. Désactivez cette option pour choisir une liste de champs ciblée. Si vous retirez le dernier champ sélectionné, Howler sélectionne de nouveau **Afficher tous les champs**. Le mode Facette demande toujours les champs à compter; la liste choisie fait partie de la demande de facette.

**EQL fait exception :** lorsque **Afficher tous les champs** est sélectionné, l'implémentation actuelle retourne seulement `howler.id` pour chaque événement. Décochez l'option et sélectionnez explicitement les champs nécessaires pour examiner les détails des événements ou des séquences EQL. Le retrait du dernier champ sélectionné recoche l'option et rétablit le comportement EQL par défaut, qui retourne seulement les identifiants.

Le panneau de réponse affiche la réponse du serveur comme JSON extensible. Sa structure dépend du langage et du mode d'exécution; examinez les sections d'agrégat ainsi que les données de hit individuelles.

## Ouvrir une requête Lucene dans la recherche

Après toute réponse Lucene réussie, **Ouvrir en recherche** devient disponible. Ce raccourci transfère le filtre Lucene normalisé vers la page Recherche, où vous pouvez continuer le triage, enregistrer une vue ou agir sur les hits correspondants.

Le raccourci transfère seulement le filtre. Il ne transfère pas la configuration de facette, de regroupement ou d'explication, les champs sélectionnés, ni la limite de lignes de la recherche avancée. Il utilise le contenu actuel de l'éditeur; exécutez donc la requête à nouveau après une modification avant d'ouvrir la recherche. Les réponses EQL et Sigma restent dans la recherche avancée puisqu'elles ne correspondent pas directement à une recherche de hit Lucene habituelle.
