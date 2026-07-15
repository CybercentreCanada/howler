# Howler Releases

## Howler UI `v2.19.0`

- **View Grid Preferences** *(new feature)*: Added list/grid display preferences to views, including configurable grid columns and widths, persisted local settings, view-composer controls, and safeguards for views whose grid configuration is inactive ([#444](https://github.com/CybercentreCanada/howler/pull/444)).
- **Dossier Tooltips in Hits** *(new feature)*: Added tooltips for dossier information displayed inside hit rows and cards.
- **Last Assessment Submitter** *(new feature)*: Displays the user who submitted the latest assessment on hits, clears the assessor when an assessment is reassigned or removed, and keeps the UI and API models synchronized ([#406](https://github.com/CybercentreCanada/howler/pull/406)).
- **In-place Search Result Updates** *(new feature)*: Search results now update in place after entity modifications instead of always issuing another search request; delete and write operations can wait for Elasticsearch refresh and provide consistent success/error feedback ([#401](https://github.com/CybercentreCanada/howler/pull/401)).
- **Deletion Confirmation Dialogues** *(new feature)*: Added confirmation prompts before deleting actions, dossiers, overviews, templates, views, rules, and analytics ([#390](https://github.com/CybercentreCanada/howler/pull/390)).
- **Query Summary Graph Toggle** *(new feature)*: Added a user preference to show or hide the query summary graph ([#346](https://github.com/CybercentreCanada/howler/pull/346)).
- **Template Edit Persistence** *(bugfix)*: Preserved template edits and session state when switching tabs, and removed deleted or saved templates from stale lists ([#361](https://github.com/CybercentreCanada/howler/pull/361)).
- **Custom Timespan Persistence** *(bugfix)*: Fixed custom search timespans being lost during navigation or reloads ([#388](https://github.com/CybercentreCanada/howler/pull/388)).
- **Detection Template Removal Handling** *(bugfix)*: Added an error and deletion prompt when a detection's backing template no longer exists ([#362](https://github.com/CybercentreCanada/howler/pull/362)).
- **Search Refresh Dependency Fix** *(bugfix)*: Search callbacks now react to changed result rows, preventing stale results when a response changes ([#477](https://github.com/CybercentreCanada/howler/pull/477)).
- **Hostname and Markdown Safety Fix** *(bugfix)*: Hostname parsing in rendered markdown now fails safely instead of producing an invalid result.
- **Localization Fixes** *(bugfix)*: Corrected several UI localization issues ([#387](https://github.com/CybercentreCanada/howler/pull/387)).
- **Open Links in New Tabs** *(improvement)*: Added safer, more convenient new-tab behavior for links and clickable source-alert links on hit cards ([#301](https://github.com/CybercentreCanada/howler/pull/301)).
- **Dependency and Test Maintenance** *(technical update)*: Updated UI dependencies and expanded utility/component test coverage; package updates are grouped here rather than listed individually.
- **Case Viewer Shell** *(new feature)*: Added the core case workspace shell for opening, browsing, and managing a case from one place, including the viewer, dashboard, details, overview, and supporting panels.
- **Case Navigation and Structure** *(new feature)*: Added the sidebar, folder tree, root drop zone, folder context menu, and item pages so case content can be organized hierarchically instead of as a flat bundle of alerts.
- **Add and Create Flow** *(new feature)*: Added the create case modal, add-to-case modal, and add-record-to-case modal so cases can be created and populated from the UI without bouncing between workflows.
- **Case Item Operations** *(new feature)*: Added moving items between folders, renaming case folders, deleting items, and handling related case links so analysts can reshape a case as it evolves.
- **Evidence and Observable Views** *(new feature)*: Added dedicated observables, alert, related-case, and markdown views so case content can show alerts, supporting evidence, and context-specific rendering.
- **Case Search and Filters** *(improvement)*: Improved case search with fuzzy matching, date/status/assignee filters, and better sidebar-driven filtering so large cases remain navigable.
- **Case Timeline and Tasks** *(new feature)*: Added the case timeline page and task panel to show case progression, task state, and triage activity over time.
- **Case Rules and Resolution** *(new feature)*: Added the case rules page and resolve modal flow, including multistage triage and the ability to change case escalation during case handling.
- **Case UI Consistency** *(improvement)*: Standardized observable terminology and related UI interactions across the case pages so the overall experience behaves like a unified incident-management workspace.

## Howler API `v4.0.0`

- **ODM Inheritance and Plugin Support** *(new feature)*: Added compatibility shims and improved enum/model type handling, `id_field` validation, and caching so plugins can define ODM subclasses ([#331](https://github.com/CybercentreCanada/howler/pull/331)).
- **Action Execution Queue** *(improvement)*: Added a queue and worker for action execution to limit Elasticsearch query pressure and improve action-service reliability ([#385](https://github.com/CybercentreCanada/howler/pull/385)).
- **Action Runner Roles** *(new feature)*: Added granular roles that control which users may execute actions ([#316](https://github.com/CybercentreCanada/howler/pull/316)).
- **Index Lifecycle Management Support** *(new feature)*: Added configuration and datastore support for ILM, including lifecycle settings, improved collection handling, and integration coverage ([#386](https://github.com/CybercentreCanada/howler/pull/386)).
- **Reindexing Improvements** *(improvement)*: Refactored the reindexing process for more reliable index and mapping operations ([#416](https://github.com/CybercentreCanada/howler/pull/416)).
- **Stale Analytics Cleanup** *(new feature)*: Added a scheduled job to remove analytics that no longer have matching hits ([#353](https://github.com/CybercentreCanada/howler/pull/353)).
- **Redis Resiliency and Health Checks** *(improvement)*: Upgraded Redis handling, added connection resiliency, and exposed Redis ping status through the health endpoint ([#428](https://github.com/CybercentreCanada/howler/pull/428), [#427](https://github.com/CybercentreCanada/howler/pull/427)).
- **Domain Validation** *(new feature)*: Added special-use and private top-level domains to domain validation ([#422](https://github.com/CybercentreCanada/howler/pull/422)).
- **OAuth Client Callbacks** *(new feature)*: Added authentication callbacks for alternative client authentication implementations and corrected related client alert-deduplication behavior ([#392](https://github.com/CybercentreCanada/howler/pull/392)).
- **Configurable Eureka Discovery** *(new feature)*: Added configuration to enable or disable Eureka discovery and removed the obsolete discovery flag ([#384](https://github.com/CybercentreCanada/howler/pull/384), [#400](https://github.com/CybercentreCanada/howler/pull/400)).
- **Assessment Assessor Tracking** *(new feature)*: Stores the user who submitted the latest hit assessment and clears the value when the assessment changes ([#406](https://github.com/CybercentreCanada/howler/pull/406)).
- **Long-Value Schema Updates** *(breaking change)*: Changed `process.pid` and `file.size` from integer to long fields, requiring the corresponding Elasticsearch mappings to be reindexed ([#414](https://github.com/CybercentreCanada/howler/pull/414), [#391](https://github.com/CybercentreCanada/howler/pull/391)).
- **Search and Datastore Fixes** *(bugfix)*: Preserved bare `*` field-list searches, ignored empty field-list entries, allowed long fields in numeric stats, handled uninitialized dossier mappings, and improved datastore behavior after Elasticsearch certificate resets ([#404](https://github.com/CybercentreCanada/howler/pull/404)).
- **ODM and Validation Fixes** *(bugfix)*: Allowed nested identifier fields, corrected certificate-reset handling, and fixed dossier mapping initialization and classification edge cases.
- **ECS Host Field** *(new feature)*: Added `host.hostname` to the supported ECS fields.
- **Audit Logging Fallback** *(bugfix)*: Audit events generated outside a request context now use a safe fallback instead of failing.
- **Classification Type Corrections** *(bugfix)*: Corrected classification type handling across configuration, ODM serialization, and classification helpers.
- **Swagger Query Parameter Documentation** *(improvement)*: API documentation now derives query parameter names, requiredness, and Swagger types from endpoint signatures and docstrings, with improved optional-parameter handling ([#485](https://github.com/CybercentreCanada/howler/pull/485)).
- **API Release and Deployment Updates** *(infrastructure update)*: Updated the API to version 4 to reflect reindexing changes and modernized deployment configuration, including Helm chart alignment and removal of obsolete Elasticsearch deployment templates.
- **Dependency and Validation Maintenance** *(technical update)*: Updated dependencies across the API, client, and plugins and expanded regression, integration, type-checking, and coverage validation; package updates are grouped here rather than listed individually.
- **Case Correlation Rules** *(new feature)*: Added backend support for creating and updating case correlation rules, including validation that `expire_after_resolved` is only allowed when a finite timeframe exists.
- **Incident-Compatible Hierarchies** *(new feature)*: Added the case-backed hierarchical item model needed to represent an incident with multiple alerts, folders, and supporting evidence instead of a single flat bundle.
- **Add to Case Automation** *(new feature)*: Added the case automation action that can search for matching alerts and append them into a case with configurable item names, paths, and titles.
- **Bundle Migration Compatibility** *(technical update)*: Reworked the legacy bundle add/remove actions so they resolve through case storage, preserving older automation while the incident model replaces bundles.
- **Case Item Services** *(technical update)*: Added service-layer support for case item creation, removal, parent-folder resolution, reference handling, and duplicate/skipped item behavior.
- **Case API Surface** *(technical update)*: Updated the API blueprint, viewer query endpoints, and websocket/comms plumbing required for the new case workflow and case viewer screens.
- **Case Model and Access Support** *(technical update)*: Added backend model and datastore updates for case-aware operations, including case lookup, item traversal, and related metadata used by the UI.
- **Case Workflow Validation** *(technical update)*: Added service validation and workflow safeguards so rule and automation behavior stays consistent when cases are created, updated, or resolved.

## Howler Client `v2.4.0`

- **Authentication Callbacks** *(new feature)*: Added callbacks for alternative authentication implementations and incorporated general client fixes and updates ([#392](https://github.com/CybercentreCanada/howler/pull/392)).
- **Client Test and Dependency Maintenance** *(technical update)*: Updated client dependencies and corrected unit-test coverage for the new API/client behavior.

## Howler UI `v2.18.0`

- **Action Outcome Messages** *(new feature)*: Actions now display an appropriate success or failure message according to the outcome of the operation.
- **Right-click Menu Action Count** *(improvement)*: Increased the number of actions available in the hit right-click context menu.
- **Plugin Route Registration Fix** *(bugfix)*: Fixed a race condition where plugin routes were not fully registered before the router was created, causing navigation failures for plugin-defined routes.
- **Embedded Related Link Target Fix** *(bugfix)*: Fixed embedded related links inside alert content so they open in a new tab instead of navigating in-place.

## Howler API `v3.3.0`

- **OpenTelemetry Tracing** *(new feature)*: Replaced ElasticAPM with OpenTelemetry for distributed tracing across the API, enabling vendor-neutral observability ([#297](https://github.com/CybercentreCanada/howler/pull/297)).
- **OAuth Group Role Resolution** *(new feature)*: Added role resolution from OAuth provider groups so that group membership is translated into Howler roles at login ([#233](https://github.com/CybercentreCanada/howler/pull/233)).
- **Chainguard Base Image** *(infrastructure update)*: Migrated the API Docker image from `python:3.12-alpine` to a Chainguard hardened image, and updated ownership to the `nonroot` user for improved supply-chain security.
- **Hit Graph Filter Fix** *(bugfix)*: Added a filter so the hit graph query is correctly bounded to the same number of hits as the main search, preventing count mismatches ([#277](https://github.com/CybercentreCanada/howler/pull/277)).

## Howler UI `v2.17.3`

- **Append-Results Null Crash Fix** *(bugfix)*: Fixed a crash (`can't access property "offset", q is null`) that occurred when a load-more (append) search response resolved after the component had remounted with a null response state (e.g., after a page refresh); the updater now falls back to replacing the response instead of merging into null.

## Howler UI `v2.17.2`

- **Table Settings Persistence** *(new feature)*: Added persistence to table settings in grid view so display preferences are retained across sessions.
- **Field Count in Layout Settings** *(new feature)*: Added field count control to layout settings for more granular display configuration.
- **Dossier Save Notifications** *(new feature)*: Added success notifications when a dossier is created or updated in the dossier editor.
- **Template Field Count in Details** *(bugfix)*: Fixed issue where template field count was incorrectly affecting the details view.
- **View Card Navigation** *(bugfix)*: Fixed view card to correctly open the view it is referring to.
- **Dashboard Edit Controls** *(improvement)*: Moved dashboard edit/refresh icons to the App Bar to reclaim some vertical space.

## Howler API `v3.2.1`

- **Dossier Query Visibility** *(bugfix)*: Fixed dossier queries not respecting dossier visibility settings.
- **Lucene AND NOT / Negation Fix** *(bugfix)*: Fixed `AND NOT` and minus-prefix (`-field:value`) negation in `lucene_service` not being respected. A inverted short-circuit condition in `visit_bool_operation` caused prohibited terms to be ignored, so dossier queries like `_exists_:threat.technique.id AND NOT howler.labels.assignments:msfit` would incorrectly match alerts that should have been excluded.

## Howler UI `v2.17.1`

- **Dashboard Refresh Re-render Fix** *(bugfix)*: Fixed full-page re-renders caused by the auto-refresh countdown timer living in the root dashboard component.
- **Pivot Link Security Fix** *(bugfix)*: Added rel="noopener noreferrer" to dossier links to protect references back to Howler.
- **Template field count** *(new feature)*: Added ability to more granularly control how many fields to show from a template.
- **Search Pane Layout Settings** *(new feature)*: Extracted display-type and hit-density controls from `SearchPane` into a dedicated `LayoutSettings` component. The settings chip now shows labelled toggle buttons for both list/grid display type and dense/normal/comfy hit layout, matching the layout controls already available on the Settings page.
- **Shared Local Storage State** *(improvement)*: Enhanced `useLocalStorageItem` so that all components using the same key share a single logical state. Updates in one component are now reflected immediately in all others on the same page, and changes from other browser tabs are picked up via the native `storage` event.
- **useLocalStorageItem Unit Tests** *(technical update)*: Added a comprehensive unit test suite for `useLocalStorageItem` covering initialization, the setter, the reset function, same-tab cross-component synchronization, and cross-tab synchronization via `StorageEvent`.

## Howler UI `v2.17.0`

- **Dashboard Auto Refresh** *(new feature)*: Added automatic refresh functionality to the dashboard for up-to-date data without manual reloading ([#226](https://github.com/CybercentreCanada/howler/pull/226))
- **Pivot Link Improvements** *(new feature)*: Improved pivot link presentation and layout, including uniform height across all pivot links and enhanced rendering
- **Replace Handlebars Helper** *(new feature)*: Added `replace`handlebars template helper for string manipulation in templates
- **Simplified Sidebar Navigation** *(new feature)*: Removed nesting from the sidebar for a cleaner, flatter navigation structure ([#238](https://github.com/CybercentreCanada/howler/pull/238))
- **Include By Function** *(new feature)*: Added "Include By" function to the hit context menu for more flexible hit filtering ([#176](https://github.com/CybercentreCanada/howler/pull/176))
- **Improved Clue Type Support** *(new feature)*: Enhanced clue type support and UI plugin integration ([#137](https://github.com/CybercentreCanada/howler/pull/137))
- **Dossier Card Overflow** *(bugfix)*: Fixed dossier cards overflowing their container bounds
- **Pivot Initialization** *(bugfix)*: Fixed bug causing incorrect pivot initialization on load
- **Empty Pivot Mapping Crash** *(bugfix)*: Fixed crash when an empty pivot mapping was encountered
- **Pivot and Link Presentation** *(bugfix)*: Fixed display issues with pivots and links rendering ([#234](https://github.com/CybercentreCanada/howler/pull/234))
- **Custom Date Searching** *(bugfix)*: Fixed custom date range searching in Howler ([#235](https://github.com/CybercentreCanada/howler/pull/235))
- **Integrations Check** *(bugfix)*: Added guard for when no integrations are enabled to prevent UI errors
- **Dependencies** *(technical update)*: Updated dompurify to v3.3.2, axios to v1.13.5, @fontsource/roboto to v5.2.9, and various other npm packages

## Howler API `v3.2.0`

- **HMAC-SHA256 API Key Caching** *(new feature)*: Implemented HMAC-SHA256 caching of API key validation for improved authentication performance ([#229](https://github.com/CybercentreCanada/howler/pull/229))
- **Pyright Type Checking** *(new feature)*: Enabled pyright static type checker and resolved resulting type errors for improved code correctness ([#190](https://github.com/CybercentreCanada/howler/pull/190))
- **Improved Clue Type Support** *(new feature)*: Enhanced clue type support in the API ([#137](https://github.com/CybercentreCanada/howler/pull/137))
- **Lucene Timespan Query Fix** *(bugfix)*: Fixed incorrect query generation for timespan fields in Lucene search ([#241](https://github.com/CybercentreCanada/howler/pull/241))
- **Lucene Explanation Bug** *(bugfix)*: Fixed a bug with Lucene query explanation introduced in the latest Elasticsearch v8
- **Minor Bug Fixes** *(bugfix)*: Various minor bug fixes across the API ([#220](https://github.com/CybercentreCanada/howler/pull/220))
- **Type Safety Fixes** *(bugfix)*: Resolved mypy type errors throughout the codebase for improved type correctness
- **Helm Chart Update** *(bugfix)*: Updated howler-helm chart to remove the MinIO dependency ([#189](https://github.com/CybercentreCanada/howler/pull/189))
- **dict_utils.flatten Performance** *(backend improvement)*: Significant performance improvements to the `dict_utils.flatten` function ([#183](https://github.com/CybercentreCanada/howler/pull/183))
- **Dependencies** *(technical update)*: Updated flask to v3.1.3, werkzeug to v3.1.6, cryptography, authlib, ruff, and numerous other pip packages across the API and plugins

## Howler UI `v2.16.1`

- **Rationale Modal Filter Query** *(bugfix)*: Fixed malformed Lucene query in rationale modal that had an extra closing parenthesis
- **Translation Updates** *(technical update)*: Added English and French translations for preset rationale type

## Howler UI `v2.16.0`

- **Composable Views** *(new feature)*: Added support for composable views allowing users to combine and layer multiple views for more flexible data exploration
- **Howler Score Sort Field** *(new feature)*: Added howler.score as a valid sort field for improved result ordering
- **Documentation Editing Plugin** *(new feature)*: Added ability for plugins to modify some documentation pages
- **Preset Rationale Configuration** *(new feature)*: Added ability to configure preset rationales for Howler analytics to streamline workflow
- **Action Button Error Reporting** *(bugfix)*: Improved error reporting for Howler action buttons in markdown content
- **Complex Component Rendering** *(bugfix)*: Removed extra newlines from rendering complex components
- **Dependencies** *(technical update)*: Updated various npm packages

## Howler API `v3.1.0`

- **Configuration Folder Support** *(new feature)*: Added support for HWL_CONF_FOLDER environment variable to allow custom configuration locations while maintaining backward compatibility
- **Elasticsearch Certificate Verification** *(new feature)*: Added ability to specify custom certificate and certificate fingerprint for Elasticsearch client connections for enhanced security when communicating in-cluster
- **Preset Rationale Configuration** *(new feature)*: Added backend support for configuring preset rationales for Howler analytics
- **Enhanced Logging** *(backend improvement)*: Added improved logging throughout the API for better debugging and monitoring
- **Demo Docker Compose** *(infrastructure update)*: Added demo docker-compose configuration for easier project setup and testing
- **Dependabot Configuration** *(infrastructure update)*: Added Dependabot configuration for automated dependency management
- **Dependencies** *(infrastructure update)*: Updated various pip packages

## Howler UI `v2.15.0`

- **Dossier Page URL State Persistence** *(new feature)*: Added URL parameter synchronization for dossier editor tabs
    and indices to maintain UI state across page refreshes and navigation
- **Dossier Card Navigation Enhancements** *(UI/UX improvement)*: Enhanced dossier cards with clickable lead and pivot
    chips for direct navigation, and added "Open in Search" button for quick query execution
- **View Link Enhancements** *(new feature)*: Added additional functionality to ViewLink component for improved
    navigation and interaction
- **Previous Rationales Display** *(new feature)*: Added ability to view previous rationales in the rationale modal for
    better context
- **Exclude By Function** *(new feature)*: Added "Exclude By" function to hit context menu for more flexible filtering options
- **Improved Plugin Components** *(UI/UX improvement)*: Enhanced plugin chip component with mapping support for better
    data visualization
- **View Filtering** *(bugfix)*: Fixed bug where null viewIds would trigger search errors
- **User Profile Settings** *(bugfix)*: Fixed issue where user profile would immediately close when editing settings
- **Custom Pivot Types** *(bugfix)*: Fixed adding custom pivot types to ensure proper functionality
- **Dashboard Enhancements** *(UI/UX improvement)*: Optimizations and fixes for improved dashboard performance and stability
- **Markdown Component Injection** *(bugfix)*: Fixed injection of markdown components to prevent security issues
- **Markdown Retention** *(UI/UX improvement)*: Improved markdown retention across navigation and state changes
- **Borealis to Clue Refactor** *(technical update)*: Completed refactoring from borealis to clue for improved maintainability
- **Dependencies** *(technical update)*: Updated glob to v11.1.0, vite to v6.4.1, axios to v1.12.0
- **Build System** *(technical update)*: Improved UI publishing workflow with better pnpm package handling and type checking
- **Translation Updates** *(technical update)*: Added French translations for new features including dossier "Open in
    Search" functionality and starting markdown templates

## Howler API `v3.0.0`

**⚠️ BREAKING CHANGES - This release requires complete data reindexing. See [migration guide](../documentation/docs/migration.md) for details.**

- **Schema Breaking Changes** *(breaking change)*: Introduction of new data types requiring complete Elasticsearch reindexing:
  - New `odm.Long` data type for handling large integer values with proper Elasticsearch long datatype mapping
  - Migrated `source.bytes` and `destination.bytes` fields from `Integer` to `Long` type
  - Migrated analytic and view titles/names to `odm.CaseInsensitiveKeyword` for improved search functionality
  - Migrated hit outline values from `odm.Text` to `odm.Keyword` for better indexing and querying performance
- **Reindexing Script Improvements** *(new feature)*: Enhanced reindexing script with selective index reindexing,
    safety warnings, and improved user feedback
- **Search API Explanation Endpoint** *(new feature)*: Added explanation endpoint to search API for better query
    debugging and optimization
- **Namespace Management** *(new feature)*: Added add_namespace and remove_namespace functions with comprehensive unit
    tests for better index organization
- **Basic Authentication Support** *(new feature)*: Added basic auth alternative for connecting to datastore as an
    option alongside existing authentication methods
- **Index Mapping Output** *(new feature)*: Added index mapping output to reindex_data.py for better visibility into
    schema changes
- **View Dashboard Cleanup** *(new feature)*: Added cron job for cleaning up references to deleted views from dashboards
- **Dossier Validation** *(bugfix)*: Fixed dossier validation to handle edge cases and improve data integrity
- **Lead Format Validation** *(bugfix)*: Removed enum validation from lead format for more flexible configuration
- **Namespace Index Mappings** *(bugfix)*: Fixed add_namespace function as it relates to index mappings for proper
    schema handling
- **Python 3.9 Support Removed** *(infrastructure update)*: Removed support for Python 3.9, now requires Python 3.10 or higher
- **Filestore Configuration Cleanup** *(infrastructure update)*: Removed references to unused filestore configurations
    for cleaner codebase
- **Docker Image Updates** *(infrastructure update)*: Updated image tags from cccsaurora/howler-api to cccs/howler-api,
    added nightly build tags
- **Dockerfile Reorganization** *(infrastructure update)*: Moved Dockerfile from api/docker/Dockerfile to api/Dockerfile
    for simplified structure
- **Poetry Migration** *(infrastructure update)*: Migrated from abatilo/actions-poetry to direct poetry installation for
    more reliable builds
- **CI/CD Improvements** *(infrastructure update)*: Fixed API dependency build issues and improved workflow reliability
    with better git merge base handling
- **Dependency Updates** *(infrastructure update)*: Updated urllib3 to v2.6.0, werkzeug to v3.1.4, authlib to v1.6.5 for
    security and stability
- **Elasticsearch Shards Configuration** *(database & storage)*: Updated default shards configuration for better cluster
    performance

## Howler UI `v2.14.1`

- **Publishing Script Fix** *(bugfix)*: Fixed publishing script to correctly handle NPM package releases

## Howler UI `v2.14.0`

- **Application Menu Plugin Injection** *(new feature)*: Added support for plugins to inject items into the application
    menu for enhanced extensibility
- **Pinned View Sorting** *(new feature)*: Added ability to sort pinned views for better organization
- **Dashboard Panel Management** *(bugfix)*: Fixed bug preventing users from adding duplicate panels to dashboard
- **Analytic Dashboard Loading** *(bugfix)*: Fixed issue with eagerly fetching all analytics for dashboard to improve performance
- **Tab Rendering** *(bugfix)*: Fixed tab rendering bug that caused display issues in the UI
- **Analytic Hit Comments** *(bugfix)*: Fixed bug affecting analytic hit comments functionality
- **View Deletion** *(bugfix)*: Fixed 404 error when deleting favourited view on Views page
- **Hit Details Pane** *(bugfix)*: Removed redundant metadata from hit details pane for cleaner interface
- **Dossier Creation Validation** *(bugfix)*: Fixed dossier creation validation flow to ensure proper data integrity
- **Plugin Documentation** *(technical update)*: Added comprehensive documentation for UI plugin development with examples
- **Build System** *(technical update)*: Split pnpm packaging and Docker build into separate jobs for better CI/CD workflow
- **Dependency Updates** *(technical update)*: Various dependency updates for improved security and performance

## Howler API `v2.12.0`

- **Reindexing Enhancements** *(backend improvement)*: Various fixes and improvements to the reindexing process for
    better reliability
- **Documentation Updates** *(infrastructure update)*: Migrated documentation to new location, expanded plugin
    development documentation with codebase overview
- **Markdown Documentation** *(infrastructure update)*: Added comprehensive CONTRIBUTING.md and plugin documentation
    for developers
- **README Updates** *(infrastructure update)*: Updated documentation links from howler-docs to howler for consistency
- **Pre-commit Hooks** *(infrastructure update)*: Added UI import validation to pre-commit checks for better code quality

## Howler UI `v2.13.2`

- **Fixed View Panel Configuration** *(bugfix)*: Fixed bug that stopped users from configuring new view panels on the dashboard.
- **Fixed Dossier Presentation Error** *(bugfix)*: Fixed bug that crashed the hit viewer if a dossier with no led was configured.
- **Fixed View Selection Error** *(bugfix)*: Fixed bug that caused views to not use the correct query when first
    navigating to the search page.

## Howler API `v2.11.2`

- **Fixed Compare Metadata Functionality** *(bugfix)*: Added check to not run matching when no hits are provided

## Howler API `v2.11.1`

- **Fixed Compare Metadata Functionality** *(bugfix)*: Added case for when type of an overview/template is `None`.

## Howler UI `v2.13.1`

- **Fixed Chart.js Adapter** *(bugfix)*: Updated to use the correct dayjs adapter for the chart.js charts.

## Howler UI `v2.13.0`

- **Advanced Search Improvements** *(new feature)*: Enhanced advanced search functionality with improved QueryBuilder
- **Action Buttons in Markdown** *(new feature)*: Added button functionality to trigger Howler actions directly from
    markdown content
- **Borealis Plugin** *(new feature)*: New plugin with comprehensive components including chips, pivot forms, and typography
- **Clear Query Button** *(new feature)*: Added clear button with icon for query input fields
- **Theme Toggle** *(new feature)*: Added theme toggle for overview editor
- **Quick Save Button** *(new feature)*: Added quick save functionality for views
- **Search Documentation** *(new feature)*: Added comprehensive documentation for Text vs Keyword search functionality
- **Hit Banner** *(bugfix)*: Fixed middle click functionality for analytic names
- **View Editing** *(bugfix)*: Fixed view editing to allow changing of view type
- **View Filtering** *(bugfix)*: Fixed filtering functionality in views
- **FZF History** *(bugfix)*: Fixed fuzzy finder history mode in query editor
- **Information Pane** *(bugfix)*: Fixed to properly support overview functionality
- **Clear Button** *(bugfix)*: Fixed clear button functionality in hit queries
- **Analytics Provider** *(bugfix)*: Fixed missing AnalyticsProvider issue
- **Query Editor Height** *(bugfix)*: Fixed height issues for multiline queries
- **Timeout Issues** *(bugfix)*: Fixed various timeout-related problems
- **JSON Viewer Search** *(bugfix)*: Fixed JSON search bar not being visible on scroll
- **Related Links** *(UI/UX improvement)*: Refactored PivotLink and RelatedLink components with optional parameters
- **Analytic Context** *(UI/UX improvement)*: Refactored and optimized analytic context for better performance
- **Hit Metadata** *(UI/UX improvement)*: Enhanced hit metadata functionality and network optimization
- **View Optimizations** *(UI/UX improvement)*: Performance improvements for view-related operations
- **Facet Search** *(UI/UX improvement)*: Optimized facet searching functionality
- **Dependencies** *(technical update)*: Updated mermaid to v11.10.0, axios to v1.11.0
- **Docker** *(technical update)*: Converted UI Docker images to Alpine Linux
- **Build System** *(technical update)*: Various build system improvements and test enhancements
- **Configuration** *(technical update)*: Added Howler fields mapping to Borealis plugin
- **Translation Updates** *(technical update)*: Added French translations for new features and updated translation files
    for clear button, theme toggle, and documentation

## Howler API `v2.11.0`

- **Hit Metadata Functionality** *(new feature)*: Enhanced hit metadata with ETag support for improved caching and
    network optimization
- **Search API Optimization** *(new feature)*: Optimized facet searching with improved performance for large datasets
- **View API Enhancement** *(new feature)*: Enhanced view editing capabilities to support changing view types
- **Lucene Query Parser** *(bugfix)*: Fixed query parsing issues in Lucene service
- **Authentication Endpoints** *(bugfix)*: Fixed various authentication-related issues
- **Dossier Service** *(bugfix)*: Improved dossier service reliability and error handling
- **Datastore Optimization** *(backend improvement)*: Handling deprecation warnings and removing unused code for better performance
- **ETag Module** *(backend improvement)*: Added comprehensive ETag support for better caching mechanisms
- **Service Layer** *(backend improvement)*: Refactored analytic and hit services for improved efficiency
- **Test Coverage** *(backend improvement)*: Enhanced unit and integration test coverage across multiple services
- **Docker** *(infrastructure update)*: Converted API Docker images to Alpine Linux for reduced image size
- **Dependencies** *(infrastructure update)*: Removed netifaces dependency, updated various backend dependencies
- **Documentation** *(infrastructure update)*: Added comprehensive API documentation and datastore README
- **Collection Management** *(database & storage)*: Improved collection handling with better shard management
- **Reindexing** *(database & storage)*: Added robust reindexing functionality with better error handling
- **Data Models** *(database & storage)*: Enhanced Link model with optional parameters for better flexibility
