# Examiner les éléments de preuve

La navigation du cas propose trois vues complémentaires des éléments de preuve. Elles utilisent seulement les hits et événements actuellement attachés au cas; organisez donc les éléments de preuve d'abord lorsque vous souhaitez une enquête ciblée.

`investigation_views`

## Rechercher dans le cas

La vue **Recherche** exécute une recherche approximative limitée au cas actuel et aux cas directement liés. Utilisez-la pour trouver des hits, événements ou cas connexes correspondants sans quitter l'espace de travail. Sélectionnez un index pour limiter le type de résultat, puis utilisez les termes de recherche et la pagination pour parcourir les éléments de preuve.

## Explorer les observables

La vue **Observables** déduplique les valeurs des champs liés des hits et événements du cas, notamment les hachages, hôtes, adresses IP, utilisateurs, identifiants, URI et signatures. Filtrez par type d'observable, origine de la source, rôle ou escalade, et recherchez les valeurs directement.

Chaque observable affiche le rôle que Howler lui a attribué, son nombre de sources, les éléments sources et leur escalade. Les liens sources conservent le chemin de l'élément et vous ramènent à l'élément de preuve qui a produit la valeur.

## Lire la chronologie

La vue **Chronologie** affiche les hits et événements du cas dans l'ordre chronologique. Filtrez-la par tactique ou technique MITRE ATT&CK et par escalade. Elle sélectionne initialement le niveau d'escalade Evidence; effacez ou modifiez ce filtre pour élargir la vue. La sélection d'une entrée ouvre cet enregistrement dans son contexte d'élément de cas.
