# Howler Releases

## Howler UI `v2.19.0`

- **View Grid Preferences** _(new feature)_: Added list/grid display preferences to views, including configurable grid columns and widths, persisted local settings, view-composer controls, and safeguards for views whose grid configuration is inactive ([#444](https://github.com/CybercentreCanada/howler/pull/444)).
- **Dossier Tooltips in Hits** _(new feature)_: Added tooltips for dossier information displayed inside hit rows and cards.
- **Last Assessment Submitter** _(new feature)_: Displays the user who submitted the latest assessment on hits, clears the assessor when an assessment is reassigned or removed, and keeps the UI and API models synchronized ([#406](https://github.com/CybercentreCanada/howler/pull/406)).
- **In-place Search Result Updates** _(new feature)_: Search results now update in place after entity modifications instead of always issuing another search request; delete and write operations can wait for Elasticsearch refresh and provide consistent success/error feedback ([#401](https://github.com/CybercentreCanada/howler/pull/401)).
- **Deletion Confirmation Dialogues** _(new feature)_: Added confirmation prompts before deleting actions, dossiers, overviews, templates, views, rules, and analytics ([#390](https://github.com/CybercentreCanada/howler/pull/390)).
- **Query Summary Graph Toggle** _(new feature)_: Added a user preference to show or hide the query summary graph ([#346](https://github.com/CybercentreCanada/howler/pull/346)).
- **Template Edit Persistence** _(bugfix)_: Preserved template edits and session state when switching tabs, and removed deleted or saved templates from stale lists ([#361](https://github.com/CybercentreCanada/howler/pull/361)).
- **Custom Timespan Persistence** _(bugfix)_: Fixed custom search timespans being lost during navigation or reloads ([#388](https://github.com/CybercentreCanada/howler/pull/388)).
- **Detection Template Removal Handling** _(bugfix)_: Added an error and deletion prompt when a detection's backing template no longer exists ([#362](https://github.com/CybercentreCanada/howler/pull/362)).
- **Search Refresh Dependency Fix** _(bugfix)_: Search callbacks now react to changed result rows, preventing stale results when a response changes ([#477](https://github.com/CybercentreCanada/howler/pull/477)).
- **Case Socket Update Synchronization** _(bugfix)_: Kept the case sidebar, dashboard, and details synchronized when case updates arrive through the websocket.
- **Hostname and Markdown Safety Fix** _(bugfix)_: Hostname parsing in rendered markdown now fails safely instead of producing an invalid result.
- **Localization Fixes** _(bugfix)_: Corrected several UI localization issues ([#387](https://github.com/CybercentreCanada/howler/pull/387)).
- **Open Links in New Tabs** _(improvement)_: Added safer, more convenient new-tab behavior for links and clickable source-alert links on hit cards ([#301](https://github.com/CybercentreCanada/howler/pull/301)).
- **Dependency and Test Maintenance** _(technical update)_: Updated UI dependencies and expanded utility/component test coverage; package updates are grouped here rather than listed individually.
- **Case Viewer Shell** _(new feature)_: Added the core case workspace shell for opening, browsing, and managing a case from one place, including the viewer, dashboard, details, overview, and supporting panels.
- **Case Navigation and Structure** _(new feature)_: Added the sidebar, folder tree, root drop zone, folder context menu, and item pages so case content can be organized hierarchically instead of as a flat bundle of alerts.
- **Add and Create Flow** _(new feature)_: Added the create case modal, add-to-case modal, and add-record-to-case modal so cases can be created and populated from the UI without bouncing between workflows.
- **Case Item Operations** _(new feature)_: Added moving items between folders, renaming case folders, deleting items, and handling related case links so analysts can reshape a case as it evolves.
- **Evidence and Observable Views** _(new feature)_: Added dedicated observables, alert, related-case, and markdown views so case content can show alerts, supporting evidence, and context-specific rendering.
- **Case Search and Filters** _(improvement)_: Improved case search with fuzzy matching, date/status/assignee filters, and better sidebar-driven filtering so large cases remain navigable.
- **Case Timeline and Tasks** _(new feature)_: Added the case timeline page and task panel to show case progression, task state, and triage activity over time.
- **Case Rules and Resolution** _(new feature)_: Added the case rules page and resolve modal flow, including multistage triage and the ability to change case escalation during case handling.
- **Case UI Consistency** _(improvement)_: Standardized observable terminology and related UI interactions across the case pages so the overall experience behaves like a unified incident-management workspace.

## Howler API `v4.0.0`

- **Correlation Worker Test Isolation** _(bugfix)_: Isolated each API test run's HTTP endpoint, correlation queue, and datastore indices so parallel runs cannot consume or delete one another's records.
- **ODM Inheritance and Plugin Support** _(new feature)_: Added compatibility shims and improved enum/model type handling, `id_field` validation, and caching so plugins can define ODM subclasses ([#331](https://github.com/CybercentreCanada/howler/pull/331)).
- **Action Execution Queue** _(improvement)_: Added a queue and worker for action execution to limit Elasticsearch query pressure and improve action-service reliability ([#385](https://github.com/CybercentreCanada/howler/pull/385)).
- **Action Runner Roles** _(new feature)_: Added granular roles that control which users may execute actions ([#316](https://github.com/CybercentreCanada/howler/pull/316)).
- **Index Lifecycle Management Support** _(new feature)_: Added configuration and datastore support for ILM, including lifecycle settings, improved collection handling, and integration coverage ([#386](https://github.com/CybercentreCanada/howler/pull/386)).
- **ILM Index Scope** _(bugfix)_: Disabled ILM by default for non-telemetry indices and added per-index opt-out support.
- **Reindexing Improvements** _(improvement)_: Refactored the reindexing process for more reliable index and mapping operations ([#416](https://github.com/CybercentreCanada/howler/pull/416)).
- **Stale Analytics Cleanup** _(new feature)_: Added a scheduled job to remove analytics that no longer have matching hits ([#353](https://github.com/CybercentreCanada/howler/pull/353)).
- **Redis Resiliency and Health Checks** _(improvement)_: Upgraded Redis handling, added connection resiliency, and exposed Redis ping status through the health endpoint ([#428](https://github.com/CybercentreCanada/howler/pull/428), [#427](https://github.com/CybercentreCanada/howler/pull/427)).
- **Domain Validation** _(new feature)_: Added special-use and private top-level domains to domain validation ([#422](https://github.com/CybercentreCanada/howler/pull/422)).
- **OAuth Client Callbacks** _(new feature)_: Added authentication callbacks for alternative client authentication implementations and corrected related client alert-deduplication behavior ([#392](https://github.com/CybercentreCanada/howler/pull/392)).
- **Configurable Eureka Discovery** _(new feature)_: Added configuration to enable or disable Eureka discovery and removed the obsolete discovery flag ([#384](https://github.com/CybercentreCanada/howler/pull/384), [#400](https://github.com/CybercentreCanada/howler/pull/400)).
- **Assessment Assessor Tracking** _(new feature)_: Stores the user who submitted the latest hit assessment and clears the value when the assessment changes ([#406](https://github.com/CybercentreCanada/howler/pull/406)).
- **Long-Value Schema Updates** _(breaking change)_: Changed `process.pid` and `file.size` from integer to long fields, requiring the corresponding Elasticsearch mappings to be reindexed ([#414](https://github.com/CybercentreCanada/howler/pull/414), [#391](https://github.com/CybercentreCanada/howler/pull/391)).
- **Search and Datastore Fixes** _(bugfix)_: Preserved bare `*` field-list searches, ignored empty field-list entries, allowed long fields in numeric stats, handled uninitialized dossier mappings, and improved datastore behavior after Elasticsearch certificate resets ([#404](https://github.com/CybercentreCanada/howler/pull/404)).
- **ODM and Validation Fixes** _(bugfix)_: Allowed nested identifier fields, corrected certificate-reset handling, and fixed dossier mapping initialization and classification edge cases.
- **ECS Host Field** _(new feature)_: Added `host.hostname` to the supported ECS fields.
- **Audit Logging Fallback** _(bugfix)_: Audit events generated outside a request context now use a safe fallback instead of failing.
- **Classification Type Corrections** _(bugfix)_: Corrected classification type handling across configuration, ODM serialization, and classification helpers.
- **Swagger Query Parameter Documentation** _(improvement)_: API documentation now derives query parameter names, requiredness, and Swagger types from endpoint signatures and docstrings, with improved optional-parameter handling ([#485](https://github.com/CybercentreCanada/howler/pull/485)).
- **API Release and Deployment Updates** _(infrastructure update)_: Updated the API to version 4 to reflect reindexing changes and modernized deployment configuration, including Helm chart alignment and removal of obsolete Elasticsearch deployment templates.
- **Dependency and Validation Maintenance** _(technical update)_: Updated dependencies across the API, client, and plugins and expanded regression, integration, type-checking, and coverage validation; package updates are grouped here rather than listed individually.
- **Case Correlation Rules** _(new feature)_: Added backend support for creating and updating case correlation rules, including validation that `expire_after_resolved` is only allowed when a finite timeframe exists.
- **Incident-Compatible Hierarchies** _(new feature)_: Added the case-backed hierarchical item model needed to represent an incident with multiple alerts, folders, and supporting evidence instead of a single flat bundle.
- **Add to Case Automation** _(new feature)_: Added the case automation action that can search for matching alerts and append them into a case with configurable item names, paths, and titles.
- **Bundle Migration Compatibility** _(technical update)_: Reworked the legacy bundle add/remove actions so they resolve through case storage, preserving older automation while the incident model replaces bundles.
- **Case Item Services** _(technical update)_: Added service-layer support for case item creation, removal, parent-folder resolution, reference handling, and duplicate/skipped item behavior.
- **Case API Surface** _(technical update)_: Updated the API blueprint, viewer query endpoints, and websocket/comms plumbing required for the new case workflow and case viewer screens.
- **Case Model and Access Support** _(technical update)_: Added backend model and datastore updates for case-aware operations, including case lookup, item traversal, and related metadata used by the UI.
- **Case Workflow Validation** _(technical update)_: Added service validation and workflow safeguards so rule and automation behavior stays consistent when cases are created, updated, or resolved.

## Howler Client `v2.4.0`

- **Authentication Callbacks** _(new feature)_: Added callbacks for alternative authentication implementations and incorporated general client fixes and updates ([#392](https://github.com/CybercentreCanada/howler/pull/392)).
- **Client Test and Dependency Maintenance** _(technical update)_: Updated client dependencies and corrected unit-test coverage for the new API/client behavior.

## Howler UI `v2.18.0`

- **Action Outcome Messages** _(new feature)_: Actions now display an appropriate success or failure message according to the outcome of the operation.
- **Right-click Menu Action Count** _(improvement)_: Increased the number of actions available in the hit right-click context menu.
- **Plugin Route Registration Fix** _(bugfix)_: Fixed a race condition where plugin routes were not fully registered before the router was created, causing navigation failures for plugin-defined routes.
- **Embedded Related Link Target Fix** _(bugfix)_: Fixed embedded related links inside alert content so they open in a new tab instead of navigating in-place.

## Howler API `v3.3.0`

- **OpenTelemetry Tracing** _(new feature)_: Replaced ElasticAPM with OpenTelemetry for distributed tracing across the API, enabling vendor-neutral observability ([#297](https://github.com/CybercentreCanada/howler/pull/297)).
- **OAuth Group Role Resolution** _(new feature)_: Added role resolution from OAuth provider groups so that group membership is translated into Howler roles at login ([#233](https://github.com/CybercentreCanada/howler/pull/233)).
- **Chainguard Base Image** _(infrastructure update)_: Migrated the API Docker image from `python:3.12-alpine` to a Chainguard hardened image, and updated ownership to the `nonroot` user for improved supply-chain security.
- **Hit Graph Filter Fix** _(bugfix)_: Added a filter so the hit graph query is correctly bounded to the same number of hits as the main search, preventing count mismatches ([#277](https://github.com/CybercentreCanada/howler/pull/277)).

## Howler UI `v2.17.3`

- **Append-Results Null Crash Fix** _(bugfix)_: Fixed a crash (`can't access property "offset", q is null`) that occurred when a load-more (append) search response resolved after the component had remounted with a null response state (e.g., after a page refresh); the updater now falls back to replacing the response instead of merging into null.

## Howler UI `v2.17.2`

- **Table Settings Persistence** _(new feature)_: Added persistence to table settings in grid view so display preferences are retained across sessions.
- **Field Count in Layout Settings** _(new feature)_: Added field count control to layout settings for more granular display configuration.
- **Dossier Save Notifications** _(new feature)_: Added success notifications when a dossier is created or updated in the dossier editor.
- **Template Field Count in Details** _(bugfix)_: Fixed issue where template field count was incorrectly affecting the details view.
- **View Card Navigation** _(bugfix)_: Fixed view card to correctly open the view it is referring to.
- **Dashboard Edit Controls** _(improvement)_: Moved dashboard edit/refresh icons to the App Bar to reclaim some vertical space.

## Howler API `v3.2.1`

- **Dossier Query Visibility** _(bugfix)_: Fixed dossier queries not respecting dossier visibility settings.
- **Lucene AND NOT / Negation Fix** _(bugfix)_: Fixed `AND NOT` and minus-prefix (`-field:value`) negation in `lucene_service` not being respected. A inverted short-circuit condition in `visit_bool_operation` caused prohibited terms to be ignored, so dossier queries like `_exists_:threat.technique.id AND NOT howler.labels.assignments:msfit` would incorrectly match alerts that should have been excluded.

## Howler UI `v2.17.1`

- **Dashboard Refresh Re-render Fix** _(bugfix)_: Fixed full-page re-renders caused by the auto-refresh countdown timer living in the root dashboard component.
- **Pivot Link Security Fix** _(bugfix)_: Added rel="noopener noreferrer" to dossier links to protect references back to Howler.
- **Template field count** _(new feature)_: Added ability to more granularly control how many fields to show from a template.
- **Search Pane Layout Settings** _(new feature)_: Extracted display-type and hit-density controls from `SearchPane` into a dedicated `LayoutSettings` component. The settings chip now shows labelled toggle buttons for both list/grid display type and dense/normal/comfy hit layout, matching the layout controls already available on the Settings page.
- **Shared Local Storage State** _(improvement)_: Enhanced `useLocalStorageItem` so that all components using the same key share a single logical state. Updates in one component are now reflected immediately in all others on the same page, and changes from other browser tabs are picked up via the native `storage` event.
- **useLocalStorageItem Unit Tests** _(technical update)_: Added a comprehensive unit test suite for `useLocalStorageItem` covering initialization, the setter, the reset function, same-tab cross-component synchronization, and cross-tab synchronization via `StorageEvent`.

## Howler UI `v2.17.0`

- **Dashboard Auto Refresh** _(new feature)_: Added automatic refresh functionality to the dashboard for up-to-date data without manual reloading ([#226](https://github.com/CybercentreCanada/howler/pull/226))
- **Pivot Link Improvements** _(new feature)_: Improved pivot link presentation and layout, including uniform height across all pivot links and enhanced rendering
- **Replace Handlebars Helper** _(new feature)_: Added `replace`handlebars template helper for string manipulation in templates
- **Simplified Sidebar Navigation** _(new feature)_: Removed nesting from the sidebar for a cleaner, flatter navigation structure ([#238](https://github.com/CybercentreCanada/howler/pull/238))
- **Include By Function** _(new feature)_: Added "Include By" function to the hit context menu for more flexible hit filtering ([#176](https://github.com/CybercentreCanada/howler/pull/176))
- **Improved Clue Type Support** _(new feature)_: Enhanced clue type support and UI plugin integration ([#137](https://github.com/CybercentreCanada/howler/pull/137))
- **Dossier Card Overflow** _(bugfix)_: Fixed dossier cards overflowing their container bounds
- **Pivot Initialization** _(bugfix)_: Fixed bug causing incorrect pivot initialization on load
- **Empty Pivot Mapping Crash** _(bugfix)_: Fixed crash when an empty pivot mapping was encountered
- **Pivot and Link Presentation** _(bugfix)_: Fixed display issues with pivots and links rendering ([#234](https://github.com/CybercentreCanada/howler/pull/234))
- **Custom Date Searching** _(bugfix)_: Fixed custom date range searching in Howler ([#235](https://github.com/CybercentreCanada/howler/pull/235))
- **Integrations Check** _(bugfix)_: Added guard for when no integrations are enabled to prevent UI errors
- **Dependencies** _(technical update)_: Updated dompurify to v3.3.2, axios to v1.13.5, @fontsource/roboto to v5.2.9, and various other npm packages

## Howler API `v3.2.0`

- **HMAC-SHA256 API Key Caching** _(new feature)_: Implemented HMAC-SHA256 caching of API key validation for improved authentication performance ([#229](https://github.com/CybercentreCanada/howler/pull/229))
- **Pyright Type Checking** _(new feature)_: Enabled pyright static type checker and resolved resulting type errors for improved code correctness ([#190](https://github.com/CybercentreCanada/howler/pull/190))
- **Improved Clue Type Support** _(new feature)_: Enhanced clue type support in the API ([#137](https://github.com/CybercentreCanada/howler/pull/137))
- **Lucene Timespan Query Fix** _(bugfix)_: Fixed incorrect query generation for timespan fields in Lucene search ([#241](https://github.com/CybercentreCanada/howler/pull/241))
- **Lucene Explanation Bug** _(bugfix)_: Fixed a bug with Lucene query explanation introduced in the latest Elasticsearch v8
- **Minor Bug Fixes** _(bugfix)_: Various minor bug fixes across the API ([#220](https://github.com/CybercentreCanada/howler/pull/220))
- **Type Safety Fixes** _(bugfix)_: Resolved mypy type errors throughout the codebase for improved type correctness
- **Helm Chart Update** _(bugfix)_: Updated howler-helm chart to remove the MinIO dependency ([#189](https://github.com/CybercentreCanada/howler/pull/189))
- **dict_utils.flatten Performance** _(backend improvement)_: Significant performance improvements to the `dict_utils.flatten` function ([#183](https://github.com/CybercentreCanada/howler/pull/183))
- **Dependencies** _(technical update)_: Updated flask to v3.1.3, werkzeug to v3.1.6, cryptography, authlib, ruff, and numerous other pip packages across the API and plugins

## Howler UI `v2.16.1`

- **Rationale Modal Filter Query** _(bugfix)_: Fixed malformed Lucene query in rationale modal that had an extra closing parenthesis
- **Translation Updates** _(technical update)_: Added English and French translations for preset rationale type

## Howler UI `v2.16.0`

- **Composable Views** _(new feature)_: Added support for composable views allowing users to combine and layer multiple views for more flexible data exploration
- **Howler Score Sort Field** _(new feature)_: Added howler.score as a valid sort field for improved result ordering
- **Documentation Editing Plugin** _(new feature)_: Added ability for plugins to modify some documentation pages
- **Preset Rationale Configuration** _(new feature)_: Added ability to configure preset rationales for Howler analytics to streamline workflow
- **Action Button Error Reporting** _(bugfix)_: Improved error reporting for Howler action buttons in markdown content
- **Complex Component Rendering** _(bugfix)_: Removed extra newlines from rendering complex components
- **Dependencies** _(technical update)_: Updated various npm packages

## Howler API `v3.1.0`

- **Configuration Folder Support** _(new feature)_: Added support for HWL_CONF_FOLDER environment variable to allow custom configuration locations while maintaining backward compatibility
- **Elasticsearch Certificate Verification** _(new feature)_: Added ability to specify custom certificate and certificate fingerprint for Elasticsearch client connections for enhanced security when communicating in-cluster
- **Preset Rationale Configuration** _(new feature)_: Added backend support for configuring preset rationales for Howler analytics
- **Enhanced Logging** _(backend improvement)_: Added improved logging throughout the API for better debugging and monitoring
- **Demo Docker Compose** _(infrastructure update)_: Added demo docker-compose configuration for easier project setup and testing
- **Dependabot Configuration** _(infrastructure update)_: Added Dependabot configuration for automated dependency management
- **Dependencies** _(infrastructure update)_: Updated various pip packages

## Howler UI `v2.15.0`

- **Dossier Page URL State Persistence** _(new feature)_: Added URL parameter synchronization for dossier editor tabs
  and indices to maintain UI state across page refreshes and navigation
- **Dossier Card Navigation Enhancements** _(UI/UX improvement)_: Enhanced dossier cards with clickable lead and pivot
  chips for direct navigation, and added "Open in Search" button for quick query execution
- **View Link Enhancements** _(new feature)_: Added additional functionality to ViewLink component for improved
  navigation and interaction
- **Previous Rationales Display** _(new feature)_: Added ability to view previous rationales in the rationale modal for
  better context
- **Exclude By Function** _(new feature)_: Added "Exclude By" function to hit context menu for more flexible filtering options
- **Improved Plugin Components** _(UI/UX improvement)_: Enhanced plugin chip component with mapping support for better
  data visualization
- **View Filtering** _(bugfix)_: Fixed bug where null viewIds would trigger search errors
- **User Profile Settings** _(bugfix)_: Fixed issue where user profile would immediately close when editing settings
- **Custom Pivot Types** _(bugfix)_: Fixed adding custom pivot types to ensure proper functionality
- **Dashboard Enhancements** _(UI/UX improvement)_: Optimizations and fixes for improved dashboard performance and stability
- **Markdown Component Injection** _(bugfix)_: Fixed injection of markdown components to prevent security issues
- **Markdown Retention** _(UI/UX improvement)_: Improved markdown retention across navigation and state changes
- **Borealis to Clue Refactor** _(technical update)_: Completed refactoring from borealis to clue for improved maintainability
- **Dependencies** _(technical update)_: Updated glob to v11.1.0, vite to v6.4.1, axios to v1.12.0
- **Build System** _(technical update)_: Improved UI publishing workflow with better pnpm package handling and type checking
- **Translation Updates** _(technical update)_: Added French translations for new features including dossier "Open in
  Search" functionality and starting markdown templates

## Howler API `v3.0.0`

**⚠️ BREAKING CHANGES - This release requires complete data reindexing. See [migration guide](../documentation/docs/migration.md) for details.**

- **Schema Breaking Changes** _(breaking change)_: Introduction of new data types requiring complete Elasticsearch reindexing:
  - New `odm.Long` data type for handling large integer values with proper Elasticsearch long datatype mapping
  - Migrated `source.bytes` and `destination.bytes` fields from `Integer` to `Long` type
  - Migrated analytic and view titles/names to `odm.CaseInsensitiveKeyword` for improved search functionality
  - Migrated hit outline values from `odm.Text` to `odm.Keyword` for better indexing and querying performance
- **Reindexing Script Improvements** _(new feature)_: Enhanced reindexing script with selective index reindexing,
  safety warnings, and improved user feedback
- **Search API Explanation Endpoint** _(new feature)_: Added explanation endpoint to search API for better query
  debugging and optimization
- **Namespace Management** _(new feature)_: Added add_namespace and remove_namespace functions with comprehensive unit
  tests for better index organization
- **Basic Authentication Support** _(new feature)_: Added basic auth alternative for connecting to datastore as an
  option alongside existing authentication methods
- **Index Mapping Output** _(new feature)_: Added index mapping output to reindex_data.py for better visibility into
  schema changes
- **View Dashboard Cleanup** _(new feature)_: Added cron job for cleaning up references to deleted views from dashboards
- **Dossier Validation** _(bugfix)_: Fixed dossier validation to handle edge cases and improve data integrity
- **Lead Format Validation** _(bugfix)_: Removed enum validation from lead format for more flexible configuration
- **Namespace Index Mappings** _(bugfix)_: Fixed add_namespace function as it relates to index mappings for proper
  schema handling
- **Python 3.9 Support Removed** _(infrastructure update)_: Removed support for Python 3.9, now requires Python 3.10 or higher
- **Filestore Configuration Cleanup** _(infrastructure update)_: Removed references to unused filestore configurations
  for cleaner codebase
- **Docker Image Updates** _(infrastructure update)_: Updated image tags from cccsaurora/howler-api to cccs/howler-api,
  added nightly build tags
- **Dockerfile Reorganization** _(infrastructure update)_: Moved Dockerfile from api/docker/Dockerfile to api/Dockerfile
  for simplified structure
- **Poetry Migration** _(infrastructure update)_: Migrated from abatilo/actions-poetry to direct poetry installation for
  more reliable builds
- **CI/CD Improvements** _(infrastructure update)_: Fixed API dependency build issues and improved workflow reliability
  with better git merge base handling
- **Dependency Updates** _(infrastructure update)_: Updated urllib3 to v2.6.0, werkzeug to v3.1.4, authlib to v1.6.5 for
  security and stability
- **Elasticsearch Shards Configuration** _(database & storage)_: Updated default shards configuration for better cluster
  performance

## Howler UI `v2.14.1`

- **Publishing Script Fix** _(bugfix)_: Fixed publishing script to correctly handle NPM package releases

## Howler UI `v2.14.0`

- **Application Menu Plugin Injection** _(new feature)_: Added support for plugins to inject items into the application
  menu for enhanced extensibility
- **Pinned View Sorting** _(new feature)_: Added ability to sort pinned views for better organization
- **Dashboard Panel Management** _(bugfix)_: Fixed bug preventing users from adding duplicate panels to dashboard
- **Analytic Dashboard Loading** _(bugfix)_: Fixed issue with eagerly fetching all analytics for dashboard to improve performance
- **Tab Rendering** _(bugfix)_: Fixed tab rendering bug that caused display issues in the UI
- **Analytic Hit Comments** _(bugfix)_: Fixed bug affecting analytic hit comments functionality
- **View Deletion** _(bugfix)_: Fixed 404 error when deleting favourited view on Views page
- **Hit Details Pane** _(bugfix)_: Removed redundant metadata from hit details pane for cleaner interface
- **Dossier Creation Validation** _(bugfix)_: Fixed dossier creation validation flow to ensure proper data integrity
- **Plugin Documentation** _(technical update)_: Added comprehensive documentation for UI plugin development with examples
- **Build System** _(technical update)_: Split pnpm packaging and Docker build into separate jobs for better CI/CD workflow
- **Dependency Updates** _(technical update)_: Various dependency updates for improved security and performance

## Howler API `v2.12.0`

- **Reindexing Enhancements** _(backend improvement)_: Various fixes and improvements to the reindexing process for
  better reliability
- **Documentation Updates** _(infrastructure update)_: Migrated documentation to new location, expanded plugin
  development documentation with codebase overview
- **Markdown Documentation** _(infrastructure update)_: Added comprehensive CONTRIBUTING.md and plugin documentation
  for developers
- **README Updates** _(infrastructure update)_: Updated documentation links from howler-docs to howler for consistency
- **Pre-commit Hooks** _(infrastructure update)_: Added UI import validation to pre-commit checks for better code quality

## Howler UI `v2.13.2`

- **Fixed View Panel Configuration** _(bugfix)_: Fixed bug that stopped users from configuring new view panels on the dashboard.
- **Fixed Dossier Presentation Error** _(bugfix)_: Fixed bug that crashed the hit viewer if a dossier with no led was configured.
- **Fixed View Selection Error** _(bugfix)_: Fixed bug that caused views to not use the correct query when first
  navigating to the search page.

## Howler API `v2.11.2`

- **Fixed Compare Metadata Functionality** _(bugfix)_: Added check to not run matching when no hits are provided

## Howler API `v2.11.1`

- **Fixed Compare Metadata Functionality** _(bugfix)_: Added case for when type of an overview/template is `None`.

## Howler UI `v2.13.1`

- **Fixed Chart.js Adapter** _(bugfix)_: Updated to use the correct dayjs adapter for the chart.js charts.

## Howler UI `v2.13.0`

- **Advanced Search Improvements** _(new feature)_: Enhanced advanced search functionality with improved QueryBuilder
- **Action Buttons in Markdown** _(new feature)_: Added button functionality to trigger Howler actions directly from
  markdown content
- **Borealis Plugin** _(new feature)_: New plugin with comprehensive components including chips, pivot forms, and typography
- **Clear Query Button** _(new feature)_: Added clear button with icon for query input fields
- **Theme Toggle** _(new feature)_: Added theme toggle for overview editor
- **Quick Save Button** _(new feature)_: Added quick save functionality for views
- **Search Documentation** _(new feature)_: Added comprehensive documentation for Text vs Keyword search functionality
- **Hit Banner** _(bugfix)_: Fixed middle click functionality for analytic names
- **View Editing** _(bugfix)_: Fixed view editing to allow changing of view type
- **View Filtering** _(bugfix)_: Fixed filtering functionality in views
- **FZF History** _(bugfix)_: Fixed fuzzy finder history mode in query editor
- **Information Pane** _(bugfix)_: Fixed to properly support overview functionality
- **Clear Button** _(bugfix)_: Fixed clear button functionality in hit queries
- **Analytics Provider** _(bugfix)_: Fixed missing AnalyticsProvider issue
- **Query Editor Height** _(bugfix)_: Fixed height issues for multiline queries
- **Timeout Issues** _(bugfix)_: Fixed various timeout-related problems
- **JSON Viewer Search** _(bugfix)_: Fixed JSON search bar not being visible on scroll
- **Related Links** _(UI/UX improvement)_: Refactored PivotLink and RelatedLink components with optional parameters
- **Analytic Context** _(UI/UX improvement)_: Refactored and optimized analytic context for better performance
- **Hit Metadata** _(UI/UX improvement)_: Enhanced hit metadata functionality and network optimization
- **View Optimizations** _(UI/UX improvement)_: Performance improvements for view-related operations
- **Facet Search** _(UI/UX improvement)_: Optimized facet searching functionality
- **Dependencies** _(technical update)_: Updated mermaid to v11.10.0, axios to v1.11.0
- **Docker** _(technical update)_: Converted UI Docker images to Alpine Linux
- **Build System** _(technical update)_: Various build system improvements and test enhancements
- **Configuration** _(technical update)_: Added Howler fields mapping to Borealis plugin
- **Translation Updates** _(technical update)_: Added French translations for new features and updated translation files
  for clear button, theme toggle, and documentation

## Howler API `v2.11.0`

- **Hit Metadata Functionality** _(new feature)_: Enhanced hit metadata with ETag support for improved caching and
  network optimization
- **Search API Optimization** _(new feature)_: Optimized facet searching with improved performance for large datasets
- **View API Enhancement** _(new feature)_: Enhanced view editing capabilities to support changing view types
- **Lucene Query Parser** _(bugfix)_: Fixed query parsing issues in Lucene service
- **Authentication Endpoints** _(bugfix)_: Fixed various authentication-related issues
- **Dossier Service** _(bugfix)_: Improved dossier service reliability and error handling
- **Datastore Optimization** _(backend improvement)_: Handling deprecation warnings and removing unused code for better performance
- **ETag Module** _(backend improvement)_: Added comprehensive ETag support for better caching mechanisms
- **Service Layer** _(backend improvement)_: Refactored analytic and hit services for improved efficiency
- **Test Coverage** _(backend improvement)_: Enhanced unit and integration test coverage across multiple services
- **Docker** _(infrastructure update)_: Converted API Docker images to Alpine Linux for reduced image size
- **Dependencies** _(infrastructure update)_: Removed netifaces dependency, updated various backend dependencies
- **Documentation** _(infrastructure update)_: Added comprehensive API documentation and datastore README
- **Collection Management** _(database & storage)_: Improved collection handling with better shard management
- **Reindexing** _(database & storage)_: Added robust reindexing functionality with better error handling
- **Data Models** _(database & storage)_: Enhanced Link model with optional parameters for better flexibility
