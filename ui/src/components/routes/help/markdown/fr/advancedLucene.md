# Utiliser les modes d'exécution Lucene

Lorsque **Requête Lucene** est sélectionné, le contrôle **Méthode de requête** détermine comment Howler exécute la requête.

`advanced_modes`

## Défaut

**Défaut** exécute une recherche de hit normale. Utilisez-le pour examiner les enregistrements correspondants, tester des filtres, puis déplacer une requête réussie vers la page Recherche ou une vue enregistrée.

## Facette

**Facette** compte les valeurs des champs sélectionnés. Ce mode est utile pour répondre à des questions comme les analyses, sources ou statuts qui apparaissent dans un ensemble correspondant. Pour les champs tableau, chaque valeur distincte contribue une fois par hit correspondant.

Le curseur du nombre de lignes limite le nombre de groupes de valeurs retournés pour chaque champ sélectionné, et non le nombre de hits correspondants qui contribuent aux comptes. Le réglage initial retourne jusqu'à cinq groupes de valeurs par champ. Si le nombre de valeurs distinctes dépasse la limite choisie, certaines valeurs sont omises; une valeur omise n'est donc pas nécessairement absente des données correspondantes.

## Regrouper

**Regrouper** groupe les résultats correspondants selon un champ de hit choisi. Sélectionnez le champ de regroupement avant l'exécution; Howler désactive **Exécuter** tant qu'aucun champ n'est choisi. Utilisez ce mode pour comparer les groupes sans trier manuellement une grande liste de hits.

Chaque groupe retourné comprend sa valeur, le nombre de hits correspondants et un hit représentatif par défaut. Le curseur du nombre de lignes augmente le nombre de groupes retournés, et non le nombre de hits affichés dans chaque groupe. Le champ `total` au premier niveau de la réponse compte les hits correspondants, pas les groupes distincts.

## Expliquer

**Expliquer** utilise l'API Validate Query d'Elasticsearch pour retourner la validité et la représentation analysée d'une requête Lucene au lieu des enregistrements correspondants. Utilisez ce mode pour déboguer la syntaxe et l'interprétation d'une requête. Il n'affiche pas la demande de recherche complète de Howler et n'explique pas le score de pertinence d'un hit individuel. La limite de lignes et les contrôles de sélection des champs ne s'appliquent pas au mode Expliquer.

Une réponse a une structure comme celle-ci :

```json
{
  "valid": true,
  "explanations": [
    {
      "valid": true,
      "explanation": "ConstantScore(FieldExistsQuery [field=howler.id])"
    }
  ]
}
```
