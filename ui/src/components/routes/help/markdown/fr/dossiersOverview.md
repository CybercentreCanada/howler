# Vue d'ensemble des dossiers

Les dossiers ajoutent des consignes d'enquête réutilisables aux hits correspondants. Ils ne sont pas des cas : un **cas** est un espace de travail partagé qui rassemble des enregistrements d'enquête, alors qu'un **dossier** définit l'information et les pivots que Howler présente lorsqu'un hit individuel correspond à une requête.

`dossier_delivery`

## Quand un dossier s'applique

Chaque dossier contient une requête Lucene. Lorsqu'un hit y correspond, les **pistes** du dossier deviennent des onglets supplémentaires dans le visualiseur de hit et ses **pivots** deviennent des actions de liens associés. Un même hit peut recevoir le contenu de plusieurs dossiers.

Les dossiers conviennent donc au contexte récurrent d'une enquête, comme des consignes pour analystes, un guide Markdown ou un lien vers un outil externe prérempli à partir du hit.

## Visibilité et propriétaire

Créez des dossiers dans **Gérer > Dossiers**. Un dossier **Global** est pris en compte pour tous les utilisateurs, alors qu'un dossier **Personnel** est pris en compte uniquement pour son propriétaire. Choisissez cette portée avec soin : le contenu global doit être utile à l'ensemble des utilisateurs et pouvoir être montré à tous ceux qui peuvent voir un hit correspondant.

`dossier_scope`

Le créateur reste le propriétaire. Seul le propriétaire ou un administrateur peut modifier un dossier, y compris un dossier global.
