# Vue d'ensemble des cas

Les cas regroupent alertes, événements, notes, liens et enquêtes connexes dans un même espace de travail. Ils offrent une structure commune pour suivre une enquête depuis les premiers éléments de preuve jusqu'à sa résolution.

## Trouver un cas

La page **Cas** recherche les titres, résumés, participants et détails des tâches des cas. Limitez une longue liste par statut, par participants ou assignés des tâches, et par date de création. Le filtre des assignés comprend un raccourci **Moi-même**.

Le filtre de statut initial sélectionne seulement **Ouvert** et **En cours**. Effacez ou modifiez ce filtre pour trouver les cas **En attente** ou **Résolu**; un cas absent des résultats initiaux peut simplement être exclu par le filtre.

Ouvrez un résultat pour accéder à l'espace de travail du cas. Une carte de cas résume son statut, les cibles, indicateurs et menaces dérivés des éléments de preuve, les participants, l'avancement des tâches et la période enregistrée lorsqu'elle est disponible.

## Créer un cas

Depuis un résultat ou un événement, ouvrez le menu contextuel et choisissez **Créer un cas**. Cette méthode est particulièrement utile après avoir sélectionné plusieurs enregistrements : la boîte de dialogue permet de donner un titre et un résumé court au cas, de sélectionner un niveau d'escalade et de rédiger une vue d'ensemble Markdown initiale.

Chaque enregistrement sélectionné reçoit un titre d'élément suggéré que vous pouvez ajuster avant de créer le cas. Les éléments de preuve sont ajoutés à la racine du nouveau cas après sa création; la boîte de dialogue de création n'offre pas de sélecteur de dossier. Créez ensuite des dossiers dans la barre latérale du cas et glissez-y les enregistrements. Lorsque vous ajoutez des enregistrements à un cas existant avec **Ajouter au cas**, vous pouvez sélectionner un dossier existant dans cette boîte de dialogue.

## Accès aux éléments de preuve

Chaque cas a son propre plafond de classification, qui correspond par défaut à la classification sans restriction du déploiement. La création d'un cas à partir d'enregistrements sélectionnés n'hérite pas automatiquement de leur classification et ne relève pas ce plafond. La boîte de dialogue de création n'offre pas de sélecteur de classification; la classification du cas peut être définie par l'API des cas.

Pour ajouter manuellement un hit ou un événement, vous devez avoir accès au cas et à l'enregistrement source, et la classification du cas doit permettre celle de l'enregistrement. Un enregistrement dépassant le plafond de classification du cas est refusé, et non simplement masqué après l'ajout. Les éléments de preuve conservent leur classification source. Vous devez avoir accès au cas lui-même pour ouvrir son espace de travail; dans un cas accessible, les éléments dépassant votre niveau d'accès sont omis.
