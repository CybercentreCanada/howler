# Creating an Overview

Overviews can be used to modify the way data is presented on alerts that match the overview's settings. Overviews are, by design, easy to create and quite flexible.

## Getting Started

The basic building blocks of overviews are:

1. Markdown
2. Handlebars

We will quickly explain these.

### Markdown

Quoting from the excellent [markdownguide.org](https://www.markdownguide.org/getting-started/):

> Markdown is a lightweight markup language that you can use to add formatting elements to plaintext text documents. Created by [John Gruber](https://daringfireball.net/projects/markdown/) in 2004, Markdown is now one of the world's most popular markup languages.
>
> Using Markdown is different than using a [WYSIWYG](https://en.wikipedia.org/wiki/WYSIWYG) editor. In an application like Microsoft Word, you click buttons to format words and phrases, and the changes are visible immediately. Markdown isn't like that. When you create a Markdown-formatted file, you add Markdown syntax to the text to indicate which words and phrases should look different.
>
> For example, to denote a heading, you add a number sign before it (e.g., `# Heading One`). Or to make a phrase bold, you add two asterisks before and after it (e.g., `**this text is bold**`). It may take a while to get used to seeing Markdown syntax in your text, especially if you're accustomed to WYSIWYG applications.

---

### Handlebars

Quoting from [handlebarsjs.com](https://handlebarsjs.com/guide/):

> Handlebars is a simple templating language.
>
> It uses a template and an input object to generate HTML or other text formats. Handlebars templates look like regular text with embedded Handlebars expressions.
>
>```html
> <p>{{curly "firstname"}} {{curly "lastname"}}</p>
>```
>
> A handlebars expression is a double curly bracket, some contents, followed by a set of closing double curly brackets. When the template is executed, these expressions are replaced with values from an input object.

---

For our cases, we use handlebars to replace specific parts of markdown with the values included in a given howler hit. For example:

```markdown
This analytic is **{{curly "howler.analytic"}}**
```

becomes:

> This analytic is **{{howler.analytic}}**.

For more information on handlebars, check out:

- [What is Handlebars?](https://handlebarsjs.com/guide/#what-is-handlebars)
- [Handlebars Expressions](https://handlebarsjs.com/guide/expressions.html)

## Combining Markdown the Handlebars

You can use handlebars for template replacement throughout your markdown. Below is an example table using handlebars and markdown:

```markdown
| Source IP | Destination IP |
| --- | --- |
| {{curly "source.ip"}} |{{curly "destination.ip"}} |
```

renders as:

| Source IP | Destination IP |
| --- | --- |
| {{source.ip}} |{{destination.ip}} |

## Advanced Handlebars

Howler integrates a number of helper functions for you to work with.

### Control Expressions

For use as subexpressions, we expose a number of conditional checks:

**Equality:**

Given `howler.status` is {{howler.status}}:

```markdown
{{curly '#if (equals howler.status "open")'}}
Hit is open!
{{curly "/if"}}
{{curly '#if (equals howler.status "resolved")'}}
Hit is resolved!
{{curly "/if"}}
```

{{#if (equals howler.status "open")}}
Hit is open!
{{/if}}
{{#if (equals howler.status "resolved")}}
Hit is resolved!
{{/if}}

**AND/OR/NOT:**

Given `howler.status` is {{howler.status}}, and `howler.escalation` is {{howler.escalation}}:

```markdown
{{curly '#if (and (equals howler.status "open") (equals howler.escalation "alert"))'}}
This is correct!
{{curly "/if"}}
{{curly '#if (and (equals howler.status "resolved") (equals howler.escalation "hit"))'}}
This is wrong!
{{curly "/if"}}
```

{{#if (and (equals howler.status "open") (equals howler.escalation "alert"))}}
This is correct!
{{/if}}
{{#if (and (equals howler.status "resolved") (equals howler.escalation "hit"))}}
This is wrong!
{{/if}}

```markdown
{{curly '#if (or howler.is_bundle (not howler.is_bundle))'}}
Always shows!
{{curly "/if"}}
```

{{#if (or howler.is_bundle (not howler.is_bundle))}}
Always shows!
{{/if}}

---

### String Operations

**String Concatenation:**

```markdown
{{curly 'join "string one " "string two"'}}
```

{{join "string one " "string two"}}

**Uppercase/Lowercase:**

```markdown
{{curly 'upper "make this uppercase"'}}
{{curly 'lower "MAKE THIS LOWERCASE"'}}
```

{{upper "make this uppercase"}}

{{lower "MAKE THIS LOWERCASE"}}

---

### Fetching Data

You can also make basic fetch requests for, and parse, JSON data from external sources:

```markdown
{{curly 'fetch "/api/v1/configs" "api_response.c12nDef.UNRESTRICTED"'}}
```

{{fetch "/api/v1/configs" "api_response.c12nDef.UNRESTRICTED"}}

## Full Helper List
