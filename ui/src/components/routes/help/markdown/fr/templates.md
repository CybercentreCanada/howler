# Modèles de Howler

Howler est, fondamentalement, une application qui permet aux analystes de trier les hits et les alertes. Afin de s'assurer que les analystes puissent le faire aussi efficacement que possible, nous voulons avoir la possibilité de présenter les données pertinentes pour une alerte donnée aux analystes d'une manière facile et compréhensible.

À cette fin, Howler permet aux analystes et aux ingénieurs de détection de créer des **modèles**, qui permettent à diverses analyses et à leurs détections de présenter des champs et des données pertinents pour le triage des alertes générées par cette analyse/détection. Par exemple, considérons deux alertes différentes, générées par deux détections différentes :

```json
$ALERT_1
```

```json
$ALERT_2
```

Notez que si les deux cartes partagent des champs similaires, elles diffèrent également. Nous voulons que chacune de ces cartes d'alerte présente des données différentes - pour cela, nous pouvons utiliser des modèles. Cela nous permet d'afficher les deux occurrences dans la même liste, mais avec des champs différents :

===SPLIT===

Comme nous pouvons le voir, en spécifiant un modèle pour chacune des détections, des données différentes seront présentées à l'analyste.Pour ce faire, vous pouvez utiliser le créateur de modèles [ici]($CURRENT_URL/templates/view?type=personal).

```alert
Notez que vous devez avoir ingéré des hits pour la paire analyse/détection donnée pour qu'elle apparaisse en tant qu'option dans l'interface utilisateur de création de modèle !
```
