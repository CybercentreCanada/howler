# Définir la requête correspondante

Le titre et la requête déterminent ce qu'est un dossier et où il apparaît. Donnez au dossier un titre reconnaissable, choisissez sa portée, puis écrivez une requête Lucene qui sélectionne les hits devant recevoir ses consignes.

`dossier_query`

## Valider avant d'enregistrer

Utilisez le contrôle de requête pour exécuter la recherche et vérifier le nombre de correspondances. L'éditeur exige un titre, un type, une requête et une validation de requête terminée avant d'activer **Enregistrer**. Une modification de la requête rend la validation précédente caduque; exécutez-la à nouveau avant d'enregistrer.

La requête est évaluée pour chaque hit, et non seulement pour la liste de résultats actuelle. Gardez-la assez précise pour que le dossier n'apparaisse pas dans des enquêtes non pertinentes. L'ouverture d'une carte de dossier dans la recherche est une bonne façon de vérifier ses correspondances actuelles.

## Concevoir une requête pratique

Commencez par des champs stables, comme `howler.analytic`, `howler.detection`, `event.dataset` ou un champ ECS qui identifie la télémétrie voulue. Ajoutez des conditions sur le statut, l'escalade ou le temps uniquement lorsqu'elles définissent réellement le flux de travail.

Par exemple, `howler.analytic:"VPN Monitor" AND howler.status:open` fournit du contexte seulement pendant l'enquête sur un hit ouvert de VPN Monitor. Préférez un dossier global à portée précise à une règle trop large avec des pistes ou pivots non pertinents.
