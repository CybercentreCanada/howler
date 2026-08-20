# Dossiers overview

Dossiers add reusable investigation guidance to matching hits. They are not cases: a **case** is a shared workspace that collects investigation records, while a **dossier** defines information and pivots that Howler presents whenever an individual hit matches a query.

`dossier_delivery`

## When a dossier applies

Each dossier has a Lucene query. When a hit matches it, the dossier's **leads** become additional tabs in the hit viewer and its **pivots** become related-link actions. A single matching hit can receive content from more than one dossier.

This makes dossiers useful for recurring investigation context, such as analyst instructions, a Markdown runbook, or a link to an external investigation tool prefilled from the hit.

## Visibility and ownership

Create dossiers from **Manage > Dossiers**. A **Global** dossier is considered for every user, while a **Personal** dossier is considered only for its owner. Choose the scope deliberately: global content should be broadly useful and safe to expose to every user who can view a matching hit.

`dossier_scope`

The creator remains the owner. Only the owner or an administrator can update a dossier, including a global one.
