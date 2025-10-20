# Analystes de triage

Howler est conçu pour consolider les alertes provenant de toutes les sources et différencier celles qui nécessitent un triage de celles qui n'en nécessitent pas. Les ingénieurs de détection sont censés normaliser les alertes, de sorte qu'elles puissent toutes être consultées et comparées avec un schéma commun : Elastic Common Schema (ECS). En regroupant toutes les alertes sous un même schéma, il est beaucoup plus facile de trouver des événements corrélés qui justifient un examen minutieux de la part d'un analyste de triage. Par exemple, un analyste peut facilement trouver toutes les alertes liées à une IP source donnée avec un seul critère de filtrage, quel que soit le schéma de la télémétrie d'origine.

Howler exige que les ingénieurs de détection décrivent explicitement le qui, le quoi, le quand, le où et le pourquoi de chaque alerte qu'ils produisent. Cela signifie que les analystes de triage ne sont pas confrontés à des alertes cryptiques qui ne donnent aucun indice sur la manière de les valider. Par exemple, les champs *menace* et *cible* indiquent clairement qui attaque qui.

L'autre grande amélioration offerte par Howler est la personnalisation. Chaque type d'événement peut avoir une présentation personnalisée, de sorte que nous n'inondons pas l'écran de l'analyste de triage avec des informations sans importance ou que nous ne laissons pas des détails importants cachés derrière de multiples clics. Par exemple, pour certaines alertes, le champ HTTP referrer peut être critique, mais pour d'autres, il peut être sans importance.

Howler prend en charge l'automatisation en faisant correspondre les alertes aux filtres. Si une nouvelle alerte correspond au filtre préparé, les actions spécifiées seront automatiquement exécutées. Celles-ci incluent la priorisation, le marquage et les évaluations, pour n'en citer que quelques-unes. Si un analyste voit constamment des alertes pour le même script sys-admin alors qu'il sait qu'il s'agit d'une activité légitime, il peut ajouter une action pour appliquer une étiquette "sys-admin" aux alertes qui correspondent à un filtre soigneusement adapté. Ensuite, ils pourraient décider d'évaluer automatiquement toute alerte avec une étiquette "sys-admin" comme "légitime" afin d'éviter de gaspiller des efforts pour les trier.

Toutes ces fonctionnalités se combinent pour fournir aux équipes de triage une suite complète d'outils qui leur permet de traiter plus d'alertes de manière plus détaillée.

## Hits

Un grand nombre d'événements détectés ne sont que des indicateurs faibles et ne valent pas la peine d'être triés individuellement, c'est pourquoi nous les appelons **hits**. Howler utilise le terme **alerte** pour décrire le sous-ensemble qui doit être trié. Tous ceux qui sont considérés comme inexacts (faux positifs) peuvent être rétrogradés à **miss**, tandis que ceux qui sont considérés comme exacts sont promus à **evidence**.

Le continuum d'escalade est le suivant : **miss** -> **hit** -> **alert** -> **evidence**

Dans la plupart des cas, les analystes de triage s'intéressent aux alertes, qu'ils font passer à l'état de preuves ou qu'ils rétrogradent à l'état d'échec. Pour examiner les alertes, l'analyste de triage se rend sur la page **Alerts** dans la barre latérale gauche. Une boîte de filtre lui est alors présentée. La syntaxe du filtre est Lucene. Le schéma des données est Elastic Common Schema (ECS).

Pour filtrer une certaine escalade, filtrez sur `howler.escalation`. Par exemple, pour regarder les alertes, écrivez : `howler.escalation : alert`.

## Hit Cards

L'interface utilisateur de Howler affiche une version abrégée de chaque hit sous forme de carte. Ceci est conçu de manière à réduire la quantité d'efforts nécessaires à un analyste de triage pour comprendre la nature du hit et son contexte.

### Bannière

La bannière située en haut de chaque résultat fournit un contexte normalisé abordant les questions suivantes : qui, quoi, quand, où et pourquoi.

#### Titre

Le titre de la carte correspond à l'analyse et à la détection à l'origine du résultat positif. Le produit logiciel qui a créé la réponse positive est appelé **analytique**. La logique de recherche et de sélection d'événements spécifiques est appelée **détection**. Une analyse peut avoir plusieurs détections. Ces deux concepts sont exprimés dans les champs `howler.analytic` et `howler.detection`.

Vous pouvez filtrer les hits appartenant à une détection spécifique. Par exemple, pour regarder les hits produits par une détection appelée "User Creds Beacon", écrivez : `howler.detection : "User Creds Beacon"`.

#### Icône

Le nom représente l'organisation, le département ou l'équipe concernés. Il est stocké dans `organization.name`.
La gauche de la bannière est colorée en fonction du mécanisme de collecte des événements. Ceci est déterminé par le champ `event.provider`.
L'image représente le cadre Mitre ATT&CK spécifié dans `threat.tactic.id` ou `threat.technique.id`.

#### Statut

À droite de la bannière se trouve le statut. Il comporte un horodatage, l'utilisateur auquel le hit est attribué et l'escalade pour le hit. En outre, si d'autres utilisateurs sont en train d'examiner cette réponse positive, leur icône apparaîtra dans cette section.

#### Contexte

La partie inférieure de la bannière présente les principaux aspects du contexte nécessaires à la compréhension de la réponse positive.

##### Menace

L'identifiant qui représente le mieux l'attaquant. Il peut s'agir d'une adresse IP, d'une adresse électronique, etc.
Utilisez-le pour trouver d'autres résultats qui semblent provenir du même attaquant. (`howler.outline.threat`)

##### Cible

L'identifiant qui représente le mieux l'attaquant. Il peut s'agir d'une adresse IP, d'une adresse électronique, etc.
Utilisez-le pour trouver d'autres hits qui semblent affecter la même victime. (`howler.outline.target`)

##### Indicateurs

Une liste libre d'indicateurs de compromission (IoC). Il s'agit généralement d'adresses IP, de domaines et de hachages.
Utilisez-la pour trouver des attaques similaires basées sur leur infrastructure et leurs tactiques. (`howler.outline.indicators`)

##### Résumé

Un résumé expliquant l'activité détectée. Lors de l'évaluation d'un hit, vous essayez de corroborer ou de réfuter cette déclaration. (`howler.outline.summary`)

### Détails

Cette section peut afficher des métadonnées supplémentaires contenues dans une alerte. Les champs affichés doivent être ceux qui sont les plus importants pour l'évaluation de cette détection particulière.

## Modèles

Les modèles sont le mécanisme utilisé pour personnaliser les champs affichés dans la section des détails d'une carte d'occurrences.
En haut à droite de la section des détails d'une fiche de résultat, une icône indique si vous êtes en train de consulter un modèle global ou personnel. En cliquant sur cette icône, vous pourrez modifier le modèle.

Vous pouvez indiquer ici si vous créez un modèle pour toutes les occurrences d'une analyse donnée ou, en option, pour les occurrences d'une détection spécifique.

Vous pouvez en faire un filtre personnel qui n'affecte que les fiches de résultats que vous voyez. Ce filtre prévaudra sur tout filtre global. Si votre filtre est global, il affectera le modèle de tout utilisateur qui n'a pas créé de modèle personnel.

Lors de la conception d'un modèle, vous pouvez ajouter ou supprimer n'importe quel champ figurant dans les métadonnées de la réponse. Tous les champs présents seront affichés dans les détails des occurrences correspondant à l'analyse ou à la détection. Évitez d'ajouter des champs qui ne sont pas nécessaires à une évaluation, car ils ralentiront la vitesse à laquelle les analystes peuvent interpréter la fiche de résultat.

## Dossier

En cliquant sur une carte de correspondance, vous ouvrirez son dossier sur le côté droit de l'interface utilisateur de Howler. Une série d'onglets fournit des informations supplémentaires sur une correspondance donnée. En haut se trouve la même bannière que celle qui figure en haut d'une fiche d'occurrences. Si l'ingénieur de détection a prévu une intégration avec des outils externes, son bouton (image) apparaîtra sous la bannière.

### Commentaires

Cette section vous permet d'écrire des commentaires pour vous-même ou vos collègues.

### JSON

Cette section affiche une représentation JSON des métadonnées de la réponse positive, y compris tous les champs que l'ingénieur de détection a mis en correspondance avec ECS.

### Données brutes

Il s'agit de l'événement brut identifié par la détection. Il s'agira d'une liste d'événements si plusieurs sont concernés. Utilisez-la si vous avez besoin de poursuivre votre enquête en dehors de Howler. Il montrera les noms de champs originaux avant le mappage à ECS, afin que vous puissiez construire les bonnes requêtes.

### Journal de travail

Toutes les modifications apportées à un résultat donné sont enregistrées ici.

### Liens connexes

Ces liens sont fournis s'ils offrent un contexte supplémentaire utile qui n'a pas pu être intégré à Howler.

### Contrôles

Au bas du dossier se trouve une série de contrôles qui permettent aux analystes d'affecter les résultats de différentes manières.

#### Gérer

- **Promouvoir** : Passer d'une réponse positive à une alerte
- **Démissionner** : Passer de l'alerte à la réponse positive
- **Attribuer à moi** : Signaler aux autres que vous évaluerez cette réponse positive.
- **Déléguer** : signaler à une personne ou à une équipe qu'elle doit évaluer ce résultat : Signaler à une personne ou à une équipe qu'elle doit évaluer ce résultat.
- **Relâcher** : Ramène le résultat à l'état non attribué.
- **Pause** : Signale que vous retardez votre évaluation.
- **Reprise** : Signale que vous travaillez à nouveau sur votre évaluation.

Les options proposées ici changent en fonction de l'état actuel de la réponse positive, de sorte que vous ne verrez que quelques choix à un moment donné.

#### Évaluer

C'est ici que vous pouvez indiquer le verdict final de votre enquête. (`howler.assessment`)

- **Ambiguous**: Il n'y avait pas assez d'informations pour faire une évaluation.
- **Security**: L'événement est une activité de cybersécurité autorisée, comme des exercices d'entraînement.
- **Development**: La réponse positive a été obtenue à des fins de développement et doit être ignorée.
- **False-Positive**: L'événement ne correspond pas aux circonstances recherchées par la détection.
- **Legitimate**: L'événement correspond à une activité autorisée.
- **Trivial**: L'événement n'a pas d'impact significatif : L'impact de l'événement n'est pas suffisamment important pour mériter d'être atténué.
- **Recon**: L'événement représente une reconnaissance, mais ne constitue pas une menace imminente.
- **Attempt**: L'événement représente une tentative d'attaque qui ne constitue pas une menace imminente : L'événement représente une tentative d'attaque qui ne semble pas avoir abouti.
- **Compromise**: L'événement représente une compromission réussie qui doit être atténuée.
- **Mitigated**: L'événement représente une compromission réussie qui doit être atténuée : L'événement représente une compromission réussie pour laquelle des mesures d'atténuation sont en cours.

**Justification** : Une fois que vous avez ajouté une évaluation, il vous est demandé de fournir une justification sous forme de texte libre. Il s'agit d'un résumé rapide expliquant à vos collègues, ou à votre futur vous-même, pourquoi vous avez confiance en cette évaluation. (`howler.rationale`)

#### Vote

Lorsqu'un analyste ne dispose pas de suffisamment d'informations pour procéder à une évaluation fiable, mais qu'il a une "intuition" concernant l'événement, il peut placer un vote. C'est à l'équipe de triage de décider comment elle utilise les votes, mais on pourrait suggérer qu'un consensus dans les votes soit utilisé pour faire une évaluation. (`howler.votes.bening/obscure/malicieux`)

## Vues

La rédaction de filtres peut prendre beaucoup de temps. Les analystes de triage ont souvent besoin d'utiliser les mêmes filtres pour leur flux de travail. Howler rationalise cela grâce aux vues. Après avoir écrit un filtre, cliquez sur l'icône en forme de cœur à droite du filtre et spécifiez un nom. Cette vue est maintenant accessible à partir du **Gestionnaire de vues** sur la barre latérale gauche. Si vous cliquez sur l'étoile à droite d'un filtre ici, il apparaîtra sous **Vues sauvegardées** dans la barre latérale de gauche.

### Vues globales

Les membres d'une équipe utilisent souvent les mêmes filtres. En spécifiant une vue comme **globale** lors de sa création, les autres utilisateurs verront cette vue dans la page Vues globales sous le filtre GLOBAL.

## Groupes des Hits

Lorsque plusieurs événements semblent liés les uns aux autres, ils peuvent être regroupés sous la forme d'un ensemble.Il s'agit d'un type spécial de résultat qui renvoie à d'autres résultats.Ils peuvent être identifiés par le filtre `howler.is_bundle:true`. Les hits associés peuvent être trouvés dans la liste `howler.hits` qui contient la valeur `howler.id` de chacun.Lorsqu'un analyste de triage clique sur la carte d'une liasse, la bannière de la liasse est déplacée au-dessus de la barre de filtre et les cartes des occurrences de la liasse sont affichées sous la barre de filtre.Tout filtre fourni ne s'appliquera qu'aux occurrences associées à la liasse.

Tout contrôle utilisé sur l'offre groupée sera automatiquement propagé aux résultats qui lui sont associés.

Un bon exemple de résultats que vous souhaiteriez regrouper serait une séquence de résultats se produisant sur le même hôte dans un court laps de temps.Individuellement, ces résultats pourraient être beaucoup trop peu fiables pour envisager de les trier, mais avec le contexte supplémentaire que plusieurs d'entre eux se produisent sur le même hôte dans une courte fenêtre de temps, il serait raisonnable de promouvoir automatiquement le regroupement en alerte pour s'assurer que quelqu'un le triera.En les regroupant, nous nous assurons que non seulement un analyste de triage examine l'hôte, mais qu'il est également au courant de toutes les autres activités potentiellement liées qui ont lieu.### Résumé de l'offre groupéeLes offres groupées disposent d'un onglet supplémentaire dans le dossier de l'offre groupée, appelé **Résumé**.Si vous cliquez sur le bouton Créer un résumé, il comptera les valeurs distinctes de chaque fichier des occurrences. Utilisez cette fonction pour vous faire une idée de la situation globale.
