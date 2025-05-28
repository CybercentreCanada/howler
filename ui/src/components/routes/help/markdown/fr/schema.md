# Schéma du hit

Un hit howler peut contenir un grand nombre de champs uniques, chacun avec une définition particulière, afin de rendre les hits mutuellement intelligibles d'une analyse à l'autre. Vous trouverez ci-dessous un tableau contenant tous les champs de résultats donnés, ainsi que leur type et une brève description de leur utilisation. Alors que la grande majorité des champs sont basés sur le schéma commun Elastic (voir [ici](https://www.elastic.co/guide/en/ecs/8.5/index.html) pour la documentation), il existe également des champs personnalisés pour Howler.

## Champs Howler - Bonnes pratiques

Afin d'assurer une certaine cohérence entre les différents analytiques, il existe un certain nombre de champs dont le style est recommandé (mais pas obligatoire). Il s'agit notamment des champs suivants:

- `howler.analytic` : Indique l'analyse globale qui a généré le résultat. Par exemple, si le nom de votre analyse est Bad Guy Finder, vous pouvez définir ce champ à Bad Guy Finder. Exemples d'utilisation :

  - Bad Guy Finder (correct)
  - BadGuyFinder (acceptable, mais les espaces sont préférables)
  - bad.guy.finder (incorrect, ne pas utiliser de points)
  - bad_guy_finder (incorrect, n'utilisez pas de caractères de soulignement)
  - en général, vous pouvez utiliser [cette regex](https://regexr.com/7ikco) pour valider le nom analytique que vous proposez

- `howler.detection` : Indique l'algorithme spécifique ou la partie de l'analyse qui a généré le hit. Par exemple, si votre analyse a trois façons de détecter les hits qui devraient être examinés (Voyage impossible, Informations de connexion incorrectes, Détection d'attaque XSS), alors la façon dont le hit que vous créez a été détecté devrait être définie. Exemples d'utilisation :
  - Impossible Travel (correct)
  - ImpossibleTravel (acceptable, mais les espaces sont préférables)
  - impossible.travel (incorrect, ne pas utiliser de points)
  - impossible_travel (incorrect, ne pas utiliser de caractères de soulignement)
