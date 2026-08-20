# Utiliser les modes d'exécution Lucene

Lorsque **Requête Lucene** est sélectionné, le contrôle **Méthode de requête** détermine comment Howler exécute la requête.

`advanced_modes`

## Défaut

**Défaut** exécute une recherche de hit normale. Utilisez-le pour examiner les enregistrements correspondants, tester des filtres, puis déplacer une requête réussie vers la page de recherche habituelle ou une vue enregistrée.

## Facette

**Facette** compte les valeurs des champs sélectionnés. Ce mode est utile pour répondre à des questions comme les analyses, sources ou statuts qui apparaissent dans un ensemble correspondant. Sélectionnez les champs à compter; pour les champs tableau, chaque valeur unique est incluse dans la réponse et comptée une fois par hit.

## Regrouper

**Regrouper** groupe les résultats correspondants selon un champ de hit choisi. Sélectionnez le champ de regroupement avant l'exécution; Howler désactive **Exécuter** tant qu'aucun champ n'est choisi. Utilisez ce mode pour comparer les groupes sans trier manuellement une grande liste de hits.

## Expliquer

**Expliquer** retourne l'explication Elasticsearch d'une requête Lucene au lieu des enregistrements correspondants ordinaires. Ce mode sert à déboguer le comportement d'une requête et à examiner la demande que Howler envoie au cluster, pas à trier un ensemble de résultats.
