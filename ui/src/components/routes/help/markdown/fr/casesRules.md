# Corrélation et automatisation

Les règles de corrélation placent automatiquement dans un cas les enregistrements correspondants qui viennent d'être ingérés. Ouvrez **Règles** depuis la barre latérale du cas pour créer, examiner, activer, désactiver ou supprimer les règles appartenant à ce cas.

## Créer une règle de corrélation

Une règle contient une requête Lucene de correspondance, un chemin de destination et un ou les deux index pris en charge : **hit** et **event**. Utilisez la commande de recherche dans la boîte de dialogue pour tester la requête avant de créer la règle.

La destination est un modèle Mustache pour le chemin de l'élément de cas. Par exemple, `alerts/{{howler.analytic}}` crée ou utilise un dossier `alerts` et nomme l'élément correspondant selon son analyse. Les dossiers d'une destination rendue sont créés au besoin. Le tableau des règles affiche la destination, la requête, les index, l'auteur, l'expiration et l'état d'activation.

`correlation_rule`

## Définir la durée de vie de la règle

Les règles sont activées par défaut. Une expiration finie est mesurée en jours à partir de la création de la règle. Choisissez **Sans expiration** pour garder une règle active indéfiniment.

**Démarrer l'expiration après la résolution du cas** est disponible seulement lorsqu'une expiration finie est définie. Lorsqu'elle est activée, le compte à rebours commence à la résolution la plus récente du cas; si le cas n'a jamais été résolu, le délai ne commence pas. Désactivez une règle pour interrompre les correspondances sans supprimer sa configuration.

## Rattraper les correspondances historiques

La création d'une règle n'ajoute pas automatiquement les enregistrements historiques. Pour l'appliquer aux éléments de preuve existants :

1. Activez la règle, puis sélectionnez sa commande **Rattraper les alertes**, représentée par une icône d'historique dans le tableau des règles.
2. Choisissez **Alertes depuis**. La limite initiale correspond à 30 jours auparavant; Howler recherche dans les index `hit` et/ou `event` configurés pour la règle les correspondances accessibles dont le champ `timestamp` est égal ou postérieur à cette limite. Ce filtre n'utilise ni `event.created` ni l'heure d'ingestion.
3. Sélectionnez **Aperçu des correspondances** et examinez le compte. Une modification de la limite exige un nouvel aperçu.
4. S'il y a des correspondances, sélectionnez **Soumettre à la corrélation** pour les placer en file d'attente pour un traitement en arrière-plan avec le modèle de destination de cette règle.

Le rattrapage exige une règle activée, mais peut exécuter explicitement une règle dont l'expiration normale est passée. Le compte de l'aperçu inclut toutes les correspondances accessibles, y compris les enregistrements déjà attachés au cas; il ne garantit pas l'ajout de ce nombre de nouveaux éléments. Les enregistrements en double sont ignorés, et les mises à jour du cas peuvent apparaître après la fin du traitement en arrière-plan.

## Automatiser une recherche existante

L'action **Ajouter au cas** est offerte aux utilisateurs autorisés pour l'automatisation. Elle exécute une requête de hit pour le cas sélectionné et utilise une destination Mustache telle que `related/{{howler.analytic}} ({{howler.id}})`. Cette action est utile pour ajouter un groupe existant d'alertes correspondantes et les organiser dans des dossiers générés, tandis que les règles de corrélation traitent les enregistrements au moment de leur ingestion ou par rattrapage explicite.

Cette opération d'automatisation récupère au plus **1 000 hits correspondants par exécution**; un ensemble plus grand n'est pas ajouté au complet. Limitez la requête à des lots distincts ou utilisez le rattrapage d'une règle, qui parcourt les correspondances historiques par pages et prend en charge les index hit et event.
