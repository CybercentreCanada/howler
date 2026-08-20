# Corrélation et automatisation

Les règles de corrélation placent automatiquement dans un cas les enregistrements correspondants qui viennent d'être ingérés. Ouvrez **Règles** depuis la barre latérale du cas pour créer, examiner, activer, désactiver ou supprimer les règles appartenant à ce cas.

## Créer une règle de corrélation

Une règle contient une requête Lucene de correspondance, un chemin de destination et un ou les deux index pris en charge : **hit** et **event**. Utilisez la commande de recherche dans la boîte de dialogue pour tester la requête avant de créer la règle.

La destination est un modèle Mustache pour le chemin de l'élément de cas. Par exemple, `alerts/{{howler.analytic}}` crée ou utilise un dossier `alerts` et nomme l'élément correspondant selon son analyse. Les dossiers d'une destination rendue sont créés au besoin. Le tableau des règles affiche la destination, la requête, les index, l'auteur, l'expiration et l'état d'activation.

`correlation_rule`

## Définir la durée de vie de la règle

Les règles sont activées par défaut. Une expiration finie est mesurée en jours à partir de la création de la règle. Choisissez **Sans expiration** pour garder une règle active indéfiniment.

**Démarrer l'expiration après la résolution du cas** est disponible seulement lorsqu'une expiration finie est définie. Lorsqu'elle est activée, le compte à rebours commence à la résolution la plus récente du cas; si le cas n'a jamais été résolu, le délai ne commence pas. Désactivez une règle pour interrompre les correspondances sans supprimer sa configuration.

## Automatiser une recherche existante

L'action **Ajouter au cas** est offerte aux utilisateurs autorisés pour l'automatisation. Elle exécute une requête de hit pour le cas sélectionné et utilise une destination Mustache telle que `related/{{howler.analytic}} ({{howler.id}})`. Cette action est utile pour ajouter un groupe existant d'alertes correspondantes et les organiser dans des dossiers générés, tandis que les règles de corrélation traitent les enregistrements au moment de leur ingestion.
