# Choisir un langage de requête

Le contrôle **Type de requête** modifie le langage de l'éditeur et le point de terminaison utilisé pour rechercher les hits. La sélection d'un autre langage charge un exemple adapté à cette syntaxe.

`advanced_languages`

## Requête Lucene

Utilisez **Requête Lucene** pour la même syntaxe orientée champs que la recherche habituelle de hits de Howler. C'est le seul langage qui offre les modes d'exécution Défaut, Facette, Regrouper et Expliquer. Les entrées sur plusieurs lignes sont normalisées avant d'être envoyées aux API de recherche de hits.

## Requête EQL

Utilisez **EQL** (Event Query Language) pour des séquences d'événements et des requêtes de type série temporelle. EQL a sa propre syntaxe et sa propre structure de réponse; examinez donc le résultat JSON plutôt que d'attendre une liste de hits habituelle. Le passage à EQL réinitialise le mode d'exécution propre à Lucene à Défaut.

## Règle Sigma

Utilisez **Règle Sigma** pour une règle Sigma complète écrite en YAML. Howler envoie le YAML comme recherche Sigma, y compris les métadonnées de la règle et la section de détection. Validez d'abord la règle avec un petit nombre de résultats, puis affinez ses sélections de champs ou sa condition avant d'élargir la requête.
