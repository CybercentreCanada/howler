# Intégrations et plugins

> **Remarque :** cette page est une documentation de secours. Dans `Integrations.tsx`, quand des plugins fournissent des vues d’intégration, ces onglets/contenus plugins sont affichés et ce markdown est remplacé.

Les plugins Howler permettent d’étendre le comportement de l’interface et le rendu sans modifier directement les écrans principaux. Les plugins sont installés via le magasin de plugins, puis appelés dans l’application à l’aide des points d’extension `executeFunction(...)`.

## Fonctionnement du système de plugins

- `HowlerPlugin` est la classe de base qui définit les points d’extension.
- `howlerPluginStore` conserve l’état global (plugins installés, formats de lead, formats de pivot, opérations, routes, menus, sitemap).
- À l’activation, un plugin enregistre des fonctions nommées dans le magasin de plugins.
- L’application exécute ensuite ces fonctions via `pluginStore.executeFunction(...)` à des endroits précis.

Ce mécanisme permet d’ajouter des capacités de façon incrémentale, sans remplacer des pages complètes.

## Ce qu’un plugin peut ajouter

D’après `HowlerPlugin.ts` et les usages du store, un plugin peut fournir :

- **Formats de lead** (`addLead`) avec :
  - un formulaire d’édition (`lead.<format>.form`)
  - un rendu (`lead.<format>`)
- **Formats de pivot** (`addPivot`) avec :
  - un formulaire (`pivot.<format>.form`)
  - un rendu de lien pivot (`pivot.<format>`)
- **Opérations d’action personnalisées** (`addOperation`) avec :
  - l’UI d’édition de l’opération (`operation.<id>`)
  - la documentation de l’opération (`operation.<id>.documentation`)
- **Entrées de menu** :
  - menu utilisateur
  - menu administrateur
  - insertions/séparateurs dans le menu principal
- **Routage/navigation** :
  - routes
  - entrées de sitemap et logique de fil d’Ariane
- **Points d’extension globaux** :
  - `provider()` pour injecter un contexte global
  - `setup()` au démarrage
  - `localization(...)` pour les traductions
  - `helpers()` pour les helpers handlebars
  - `typography(...)` et `chip(...)` pour le rendu UI
  - `actions(...)` pour les actions sur les hits
  - `status(...)` pour la bannière/statut d’un hit
  - `support()`, `help()` et `settings(...)` par section
  - `documentation(md)` pour post-traiter du markdown
  - `on(event, hit)` pour les événements

## Où les hooks sont exécutés

`executeFunction(...)` est utilisé dans plusieurs parties de l’UI, notamment pour :

- le rendu des leads et leurs formulaires
- le rendu des pivots et leurs formulaires
- les éditeurs d’opérations et leur documentation
- les actions plugin dans les vues/context menus de hit
- les composants de statut/bannière des hits
- les composants typographie/chip
- les providers plugins et la logique `setup`
- les sections de paramètres (`admin`, `local`, `profile`, `security`)
- les vues d’aide/support
- la transformation de markdown de documentation

## Exemple : plugin Clue

Le plugin Clue (`ui/src/plugins/clue/index.tsx`) montre un exemple concret :

- enregistre des bundles de traduction EN/FR
- expose un provider et un hook de setup
- ajoute un format de lead `clue` avec :
  - un composant de formulaire
  - un renderer qui lit les métadonnées du lead et affiche un `Fetcher`
- ajoute un format de pivot `clue` (formulaire + rendu)
- fournit des helpers handlebars personnalisés
- fournit des rendus personnalisés pour `typography` et `chip`

C’est le modèle recommandé pour développer de nouvelles intégrations.
