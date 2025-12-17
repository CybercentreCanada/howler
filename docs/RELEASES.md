# Howler Releases

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
