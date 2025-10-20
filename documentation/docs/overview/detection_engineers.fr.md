# Ingénieurs en détection

Vous venez d'écrire une analyse qui détecte une activité suspecte et vous aimeriez que votre centre d'opérations de sécurité (SOC) en bénéficie. Dans Howler, un événement intéressant est appelé un hit. Le terme alerte est réservé aux occurrences qui nécessitent un triage.

Pour créer un nouveau hit, produisez un objet JSON dans lequel vous avez normalisé les données de l'événement selon Elastic Common Schema. Nous procédons ainsi pour que les analystes de triage disposent d'un schéma unique à apprendre quelle que soit la source des alertes, ce qui leur facilitera grandement la tâche.

Ensuite, vous devez remplir certains champs spécifiques à Howler :

- `howler.detection` - Un identifiant court et unique pour la détection spécifique.
- `howler.analytic` - Le produit qui effectue la détection. Certains produits analytiques exécuteront plusieurs détections distinctes.
- `howler.outline.threat` - L'identifiant qui représente le mieux l'attaquant. Il peut s'agir d'une adresse IP, d'une adresse électronique, etc...
- `howler.outline.target` - L'identifiant qui représente le mieux la victime. Là encore, il peut s'agir d'une adresse IP, d'un domaine, d'une adresse électronique, etc...
- `howler.outline.indicators` - Une liste libre d'indicateurs de compromission (IoC). Il s'agit généralement d'adresses IP, de domaines et de hachages.
- `howler.outline.summary` - Un résumé expliquant l'activité détectée. Il décrit l'événement en supposant que la détection est correcte.
- `howler.data` - Une liste de dictionnaires de l'événement brut avant normalisation. Cela facilite la tâche des analystes s'ils doivent mener leur enquête en dehors de Howler.

Howler utilise des niveaux d'escalade (`howler.escalation`) pour catégoriser les hits :

- `miss` - L'événement est évalué comme n'étant pas lié à la détection (faux-positif).
- `hit` - (par défaut) L'événement peut ne pas être très fiable sans contexte supplémentaire.
- `alert` - L'événement doit être évalué par un analyste de triage.
- `evidence` - L'événement a été évalué comme étant lié à la détection (vrai-positif).

Vous pouvez promouvoir certains hits en alertes immédiates au moment de la création si l'on s'attend à ce que tous les hits méritent d'être triés.

Une fois l'objet JSON complété, utilisez le client Howler pour créer un nouveau résultat positif. Ce résultat sera immédiatement disponible pour les analystes de triage à partir de l'interface utilisateur de Howler.

## Les groupes des hits

Un ensemble est un regroupement logique de résultats qui doivent être évalués ensemble. Par exemple, si une série d'occurrences multiples se produit sur le même hôte dans un court laps de temps, un analyste de triage devrait effectuer une enquête unique qui les prend toutes en compte. L'interface utilisateur de Howler fournit un flux de travail permettant de travailler intuitivement avec ces ensembles.

Les bundles sont implémentés comme des hits dont le champ howler.is_bundle est défini sur true, et howler.hits contient une liste de valeurs howler.id. Cela signifie que des analyses peuvent être créées pour rechercher des occurrences liées et les regrouper.

## Page d'analyse

La section Analytics de l'interface utilisateur de Howler fournit une page de support pour les analyses et les détections individuelles. Elle contient des informations utiles à la fois pour l'auteur d'une analyse ou d'une détection et pour les analystes de triage qui enquêtent sur les hits.

### Vue d'ensemble

Ici, vous êtes encouragé à fournir de la documentation en Markdown. Celle-ci devrait fournir plus de détails sur le fonctionnement de l'analyse ou de la détection, sur ce qu'elle recherche et sur la manière de valider les résultats.

Des mesures sont automatiquement générées pour donner un aperçu des performances. Un taux de faux positifs très élevé peut être le signe que la détection doit être améliorée. En revanche, un taux élevé de vrais positifs peut justifier que les occurrences soient automatiquement promues au rang d'alertes.

### Commentaires

Dans cet onglet, les utilisateurs peuvent laisser des commentaires sur une analyse ou une détection. Il s'agit de la ligne de communication de l'utilisateur final avec vous.

### Commentaires sur les résultats

À partir de cet onglet, vous pouvez consulter tous les commentaires laissés sur des résultats spécifiques afin de mieux comprendre ce que les analystes de triage se signalent les uns aux autres.

### Carnets de notes

Si vos analystes de triage ont fréquemment besoin d'enquêter sur des alertes en dehors de Howler, vous pouvez créer un lien vers un carnet de notes Jupyter. Cela signifie qu'un bouton apparaîtra dans l'interface utilisateur de Howler. Lorsqu'un utilisateur clique sur le bouton, il est dirigé vers JupyterHub avec le Notebook spécifié ouvert et le hit spécifique chargé, ce qui permet aux requêtes d'être pré-remplies avec des valeurs pertinentes.
