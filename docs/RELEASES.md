# Howler Releases

## Howler API `v2.11.2`

## Howler API `v2.11.1`

- **Fixed Compare Metadata Functionality** *(bugfix)*: Added case for when type of an overview/template is `None`.

## Howler UI `v2.13.1`

- **Fixed Chart.js Adapter** *(bugfix)*: Updated to use the correct dayjs adapter for the chart.js charts.

## Howler UI `v2.13.0`

- **Advanced Search Improvements** *(new feature)*: Enhanced advanced search functionality with improved QueryBuilder
- **Action Buttons in Markdown** *(new feature)*: Added button functionality to trigger Howler actions directly from markdown content
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
- **Translation Updates** *(technical update)*: Added French translations for new features and updated translation files for clear button, theme toggle, and documentation

## Howler API `v2.11.0`

- **Hit Metadata Functionality** *(new feature)*: Enhanced hit metadata with ETag support for improved caching and network optimization
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
