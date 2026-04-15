# Integrations and Plugins

> **Note:** This page is fallback documentation. In `Integrations.tsx`, when plugins provide integration views, those plugin tabs/content are rendered and this markdown is replaced.

Howler plugins let you extend both UI behavior and rendering paths without modifying core screens directly. Plugins are installed through the plugin store and then invoked across the app through `executeFunction(...)` hooks.

## How the plugin system works

- `HowlerPlugin` is the base class that defines extension points.
- `howlerPluginStore` keeps global plugin state (installed plugins, lead formats, pivot formats, operations, routes, menus, sitemap entries).
- On activation, each plugin can register named functions in the runtime plugin store.
- The app calls those functions via `pluginStore.executeFunction(...)` in specific locations.

In practice, this means plugins can contribute features incrementally rather than replacing full pages.

## What plugins can add

From `HowlerPlugin.ts` and store usage, plugins can provide:

- **Lead formats** (`addLead`) with:
  - a lead editor form (`lead.<format>.form`)
  - a lead renderer (`lead.<format>`)
- **Pivot formats** (`addPivot`) with:
  - a pivot form (`pivot.<format>.form`)
  - a pivot link renderer (`pivot.<format>`)
- **Custom action operations** (`addOperation`) with:
  - operation editor UI (`operation.<id>`)
  - operation help docs (`operation.<id>.documentation`)
- **Menu entries**:
  - user menu items
  - admin menu items
  - main menu insertions/dividers
- **Routing/navigation**:
  - routes
  - sitemap entries and breadcrumbs behavior
- **Global extension hooks**:
  - `provider()` wrapper for app-wide context
  - `setup()` startup logic
  - `localization(...)` translation bundles
  - `helpers()` custom handlebars helpers
  - `typography(...)` and `chip(...)` custom UI rendering
  - `actions(...)` hit actions
  - `status(...)` hit banner/status widgets
  - `support()`, `help()`, and section-specific `settings(...)`
  - `documentation(md)` markdown post-processing
  - `on(event, hit)` event callback

## Where hooks are executed

`executeFunction(...)` is used throughout the app to render plugin output at runtime, for example:

- lead rendering and lead form editors
- pivot rendering and pivot form editors
- custom operation editors and docs
- plugin actions in hit views/context menus
- hit status/banner components
- typography/chip wrappers
- plugin providers and startup setup
- settings sections (`admin`, `local`, `profile`, `security`)
- help/support panels
- markdown documentation transforms

## Clue plugin example

The Clue plugin (`ui/src/plugins/clue/index.tsx`) demonstrates a typical plugin:

- registers localization bundles in English/French
- provides a plugin provider + setup hook
- adds a custom lead format (`clue`) with:
  - a lead form component
  - a renderer that parses lead metadata and renders a `Fetcher`
- adds a custom pivot format (`clue`) with form + renderer
- provides custom handlebars helpers
- overrides plugin typography/chip renderers

This is the main pattern to follow when adding a new integration.
