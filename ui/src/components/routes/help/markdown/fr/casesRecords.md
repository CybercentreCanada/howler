# Ajouter des enregistrements aux cas

Les résultats et les événements peuvent être ajoutés comme éléments de cas sans dupliquer l'enregistrement sous-jacent. Le niveau d'escalade actuel d'un hit est reflété dans la barre latérale, et l'ouverture d'un élément affiche l'enregistrement dans l'espace de travail du cas.

## Ajouter des enregistrements sélectionnés

Depuis une recherche ou une vue d'enregistrement, sélectionnez un ou plusieurs résultats ou événements, ouvrez le menu contextuel et choisissez **Ajouter au cas**. Sélectionnez le cas cible, attribuez un nom clair à chaque enregistrement et choisissez facultativement un dossier. La boîte de dialogue fournit un titre utile basé sur l'analyse ou l'identifiant de l'événement, mais chaque titre peut être modifié indépendamment.

Choisissez **Créer un cas** dans le même menu pour démarrer un nouveau cas avec les enregistrements sélectionnés. Définissez le titre, le résumé, le niveau d'escalade, la vue d'ensemble et les noms des enregistrements dans la boîte de dialogue de création. Les enregistrements initiaux sont ajoutés à la racine du nouveau cas; créez des dossiers et déplacez-les ensuite. Le choix d'un dossier est offert seulement lors de l'ajout d'enregistrements à un cas existant qui contient déjà des dossiers.

`add_records`

## Créer un événement manuellement

Utilisez **Ajouter un événement** dans la barre latérale du cas pour consigner un élément de preuve qui n'a pas déjà été ingéré. La boîte de dialogue exige :

- Un titre et une date et heure de création d'événement valides.
- Une valeur **Source / provenance** qui indique l'origine de l'élément de preuve.
- Un niveau d'escalade : `hit`, `alert` ou `evidence`.
- Au moins une cible, une menace ou un indicateur.

Vous pouvez aussi fournir un résumé, choisir un dossier existant et utiliser la recherche dans les noms et descriptions de champs pour ajouter des champs ECS facultatifs. Saisissez un indicateur par ligne ou séparez-les par des virgules. L'événement hérite de la classification du cas et est ingéré comme nouvel enregistrement avant d'être attaché au cas; ce flux diffère donc de l'ajout d'un événement existant.

## Relations entre les éléments de preuve

L'ajout d'un hit ou d'un événement crée une référence de cas sur l'enregistrement sous-jacent ainsi qu'un élément dans le cas. Le retrait de l'élément supprime cette relation. Un enregistrement ne peut pas être ajouté deux fois au même cas, et sa classification source est conservée lors de l'ajout.

Lorsqu'un cas existant est lié comme cas connexe, il est présenté au haut de l'arborescence des éléments et dans le panneau Cas connexes du tableau de bord.
