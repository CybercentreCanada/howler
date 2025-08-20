# Créer un aperçu

Les aperçus peuvent être utilisés pour modifier la façon dont les données sont présentées sur les alertes qui correspondent aux paramètres de l'aperçu. Les aperçus sont, par conception, faciles à créer et assez flexibles.

## Commencer

Les éléments de base des aperçus sont :

1. Markdown
2. Handlebars

Nous allons expliquer rapidement ces éléments.

### Markdown

Citant l'excellent [markdownguide.org](https://www.markdownguide.org/getting-started/) :

> Markdown est un langage de balisage léger que vous pouvez utiliser pour ajouter des éléments de formatage aux documents texte en format brut. Créé par [John Gruber](https://daringfireball.net/projects/markdown/) en 2004, Markdown est maintenant l'un des langages de balisage les plus populaires au monde.
>
> Utiliser Markdown est différent d'utiliser un éditeur [WYSIWYG](https://en.wikipedia.org/wiki/WYSIWYG). Dans une application comme Microsoft Word, vous cliquez sur des boutons pour formater les mots et les phrases, et les changements sont visibles immédiatement. Markdown n'est pas comme ça. Quand vous créez un fichier formaté en Markdown, vous ajoutez la syntaxe Markdown au texte pour indiquer quels mots et phrases doivent paraître différents.
>
> Par exemple, pour désigner un titre, vous ajoutez un signe dièse avant celui-ci (par ex., `# Titre Un`). Ou pour mettre une phrase en gras, vous ajoutez deux astérisques avant et après (par ex., `**ce texte est en gras**`). Il peut falloir du temps pour s'habituer à voir la syntaxe Markdown dans votre texte, surtout si vous êtes habitué aux applications WYSIWYG.

---

### Handlebars

Citant [handlebarsjs.com](https://handlebarsjs.com/guide/) :

> Handlebars est un langage de modélisation simple.
>
> Il utilise un modèle et un objet d'entrée pour générer du HTML ou d'autres formats de texte. Les modèles Handlebars ressemblent à du texte régulier avec des expressions Handlebars intégrées.
>
>```html
> <p>{{curly "firstname"}} {{curly "lastname"}}</p>
>```
>
> Une expression handlebars est une double accolade, du contenu, suivi d'un ensemble d'accolades doubles de fermeture. Quand le modèle est exécuté, ces expressions sont remplacées par des valeurs d'un objet d'entrée.

---

Pour nos cas, nous utilisons handlebars pour remplacer des parties spécifiques de markdown par les valeurs incluses dans un hit howler donné. Par exemple :

```markdown
Cette analytique est **{{curly "howler.analytic"}}**
```

devient :

> Cette analytique est **{{howler.analytic}}**.

Pour plus d'informations sur handlebars, consultez :

- [Qu'est-ce que Handlebars ?](https://handlebarsjs.com/guide/#what-is-handlebars)
- [Expressions Handlebars](https://handlebarsjs.com/guide/expressions.html)

## Combiner Markdown et Handlebars

Vous pouvez utiliser handlebars pour le remplacement de modèles dans tout votre markdown. Voici un exemple de tableau utilisant handlebars et markdown :

```markdown

| IP Source | IP Destination |
| --- | --- |
| {{curly "source.ip"}} |{{curly "destination.ip"}} |
```

s'affiche comme :

| IP Source | IP Destination |
| --- | --- |
| {{source.ip}} |{{destination.ip}} |

## Handlebars Avancé

Howler intègre un certain nombre de fonctions d'aide avec lesquelles vous pouvez travailler.

### Expressions de Contrôle

Pour utilisation comme sous-expressions, nous exposons un certain nombre de vérifications conditionnelles :

**Égalité :**

Étant donné que `howler.status` est {{howler.status}} :

```markdown
{{curly '#if (equals howler.status "open")'}}
Le hit est ouvert !
{{curly "/if"}}
{{curly '#if (equals howler.status "resolved")'}}
Le hit est résolu !
{{curly "/if"}}
```

{{#if (equals howler.status "open")}}
Le hit est ouvert !
{{/if}}
{{#if (equals howler.status "resolved")}}
Le hit est résolu !
{{/if}}

**ET/OU/NON :**

Étant donné que `howler.status` est {{howler.status}}, et `howler.escalation` est {{howler.escalation}} :

```markdown
{{curly '#if (and (equals howler.status "open") (equals howler.escalation "alert"))'}}
C'est correct !
{{curly "/if"}}
{{curly '#if (and (equals howler.status "resolved") (equals howler.escalation "hit"))'}}
C'est incorrect !
{{curly "/if"}}
```

{{#if (and (equals howler.status "open") (equals howler.escalation "alert"))}}
C'est correct !
{{/if}}
{{#if (and (equals howler.status "resolved") (equals howler.escalation "hit"))}}
C'est incorrect !
{{/if}}

```markdown
{{curly '#if (or howler.is_bundle (not howler.is_bundle))'}}
Toujours affiché !
{{curly "/if"}}
```

{{#if (or howler.is_bundle (not howler.is_bundle))}}
Toujours affiché !
{{/if}}

---

### Opérations sur les Chaînes

**Concaténation de Chaînes :**

```markdown
{{curly 'join "chaîne un " "chaîne deux"'}}
```

{{join "chaîne un " "chaîne deux"}}

**Majuscules/Minuscules :**

```markdown
{{curly 'upper "mettre ceci en majuscules"'}}
{{curly 'lower "METTRE CECI EN MINUSCULES"'}}
```

{{upper "mettre ceci en majuscules"}}

{{lower "METTRE CECI EN MINUSCULES"}}

---

### Récupération de Données

Vous pouvez également faire des requêtes fetch de base pour, et analyser, des données JSON depuis des sources externes :

```markdown
{{curly 'fetch "/api/v1/configs" "api_response.c12nDef.UNRESTRICTED"'}}
```

{{fetch "/api/v1/configs" "api_response.c12nDef.UNRESTRICTED"}}

## Liste Complète des Helpers
