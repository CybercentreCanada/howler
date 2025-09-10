# Créer un aperçu

Les aperçus peuvent être utilisés pour modifier la façon dont les données sont présentées sur les alertes qui correspondent aux paramètres de l'aperçu. Les aperçus sont, par conception, faciles à créer et assez flexibles.

## Premiers pas

Les éléments de base des aperçus sont :

1. Markdown
2. Handlebars

Nous allons rapidement expliquer ces éléments.

### Markdown

Citant de l'excellent [markdownguide.org](https://www.markdownguide.org/getting-started/) :

> Markdown est un langage de balisage léger que vous pouvez utiliser pour ajouter des éléments de formatage aux documents texte en texte brut. Créé par [John Gruber](https://daringfireball.net/projects/markdown/) en 2004, Markdown est maintenant l'un des langages de balisage les plus populaires au monde.
>
> L'utilisation de Markdown est différente de l'utilisation d'un éditeur [WYSIWYG](https://en.wikipedia.org/wiki/WYSIWYG). Dans une application comme Microsoft Word, vous cliquez sur des boutons pour formater les mots et les phrases, et les changements sont visibles immédiatement. Markdown n'est pas comme cela. Lorsque vous créez un fichier formaté en Markdown, vous ajoutez une syntaxe Markdown au texte pour indiquer quels mots et phrases doivent apparaître différemment.
>
> Par exemple, pour désigner un titre, vous ajoutez un signe dièse avant celui-ci (par ex., `# Titre Un`). Ou pour mettre une phrase en gras, vous ajoutez deux astérisques avant et après (par ex., `**ce texte est en gras**`). Il peut falloir un certain temps pour s'habituer à voir la syntaxe Markdown dans votre texte, surtout si vous êtes habitué aux applications WYSIWYG.

---

### Handlebars

Citant de [handlebarsjs.com](https://handlebarsjs.com/guide/) :

> Handlebars est un langage de template simple.
>
> Il utilise un template et un objet d'entrée pour générer du HTML ou d'autres formats de texte. Les templates Handlebars ressemblent à du texte normal avec des expressions Handlebars intégrées.
>
>```html
> <p>{{curly "firstname"}} {{curly "lastname"}}</p>
>```
>
> Une expression handlebars est une double accolade, du contenu, suivi d'un ensemble d'accolades fermantes doubles. Lorsque le template est exécuté, ces expressions sont remplacées par des valeurs d'un objet d'entrée.

---

Dans nos cas, nous utilisons handlebars pour remplacer des parties spécifiques du markdown par les valeurs incluses dans un résultat howler donné. Par exemple :

```markdown
Cette analytique est **{{curly "howler.analytic"}}**
```

devient :

> Cette analytique est **{{howler.analytic}}**.

Pour plus d'informations sur handlebars, consultez :

- [Qu'est-ce que Handlebars ?](https://handlebarsjs.com/guide/#what-is-handlebars)
- [Expressions Handlebars](https://handlebarsjs.com/guide/expressions.html)

## Combiner Markdown et Handlebars

Vous pouvez utiliser handlebars pour le remplacement de template dans tout votre markdown. Voici un exemple de tableau utilisant handlebars et markdown :

```markdown

| IP Source | IP Destination |
| --- | --- |
| {{curly "source.ip"}} |{{curly "destination.ip"}} |
```

s'affiche comme :

| IP Source | IP Destination |
| --- | --- |
| {{source.ip}} |{{destination.ip}} |

## Handlebars avancés

Howler intègre un certain nombre de fonctions d'aide avec lesquelles vous pouvez travailler.

### Expressions de contrôle

Pour utilisation comme sous-expressions, nous exposons un certain nombre de vérifications conditionnelles :

**Égalité :**

Étant donné que `howler.status` est {{howler.status}} :

```markdown
{{curly '#if (equals howler.status "open")'}}
Le résultat est ouvert !
{{curly "/if"}}
{{curly '#if (equals howler.status "resolved")'}}
Le résultat est résolu !
{{curly "/if"}}
```

{{#if (equals howler.status "open")}}
Le résultat est ouvert !
{{/if}}
{{#if (equals howler.status "resolved")}}
Le résultat est résolu !
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
S'affiche toujours !
{{curly "/if"}}
```

{{#if (or howler.is_bundle (not howler.is_bundle))}}
S'affiche toujours !
{{/if}}

---

### Opérations sur les chaînes

**Concaténation de chaînes :**

```markdown
{{curly 'join "chaîne une " "chaîne deux"'}}
```

{{join "chaîne une " "chaîne deux"}}

**Majuscules/Minuscules :**

```markdown
{{curly 'upper "mettre ceci en majuscules"'}}
{{curly 'lower "METTRE CECI EN MINUSCULES"'}}
```

{{upper "mettre ceci en majuscules"}}

{{lower "METTRE CECI EN MINUSCULES"}}

---

### Récupération de données

Vous pouvez également faire des requêtes fetch de base pour récupérer et analyser des données JSON de sources externes :

```markdown
{{curly 'fetch "/api/v1/configs" "api_response.c12nDef.UNRESTRICTED"'}}
```

{{fetch "/api/v1/configs" "api_response.c12nDef.UNRESTRICTED"}}

## Liste complète des assistants
