# Howler Releases

## Howler UI `v2.13.0`

### New Features

- **Advanced Search Improvements**: Enhanced advanced search functionality with improved QueryBuilder
- **Action Buttons in Markdown**: Added button functionality to trigger Howler actions directly from markdown content
- **Borealis Plugin**: New plugin with comprehensive components including chips, pivot forms, and typography
- **Clear Query Button**: Added clear button with icon for query input fields
- **Theme Toggle**: Added theme toggle for overview editor
- **Quick Save Button**: Added quick save functionality for views
- **Search Documentation**: Added comprehensive documentation for Text vs Keyword search functionality

### Bug Fixes

- **Hit Banner**: Fixed middle click functionality for analytic names
- **View Editing**: Fixed view editing to allow changing of view type
- **View Filtering**: Fixed filtering functionality in views
- **FZF History**: Fixed fuzzy finder history mode in query editor
- **Information Pane**: Fixed to properly support overview functionality
- **Clear Button**: Fixed clear button functionality in hit queries
- **Analytics Provider**: Fixed missing AnalyticsProvider issue
- **Query Editor Height**: Fixed height issues for multiline queries
- **Timeout Issues**: Fixed various timeout-related problems

### UI/UX Improvements

- **Related Links**: Refactored PivotLink and RelatedLink components with optional parameters
- **Analytic Context**: Refactored and optimized analytic context for better performance
- **Hit Metadata**: Enhanced hit metadata functionality and network optimization
- **View Optimizations**: Performance improvements for view-related operations
- **Facet Search**: Optimized facet searching functionality

### Technical Updates

- **Dependencies**: Updated mermaid to v11.10.0, axios to v1.11.0
- **Docker**: Converted UI Docker images to Alpine Linux
- **Build System**: Various build system improvements and test enhancements
- **Configuration**: Added Howler fields mapping to Borealis plugin

### Translation Updates

- Added French translations for new features
- Updated translation files for clear button, theme toggle, and documentation

## Howler API `v2.11.0`

### API New Features

- **Hit Metadata Functionality**: Enhanced hit metadata with ETag support for improved caching and network optimization
- **Search API Optimization**: Optimized facet searching with improved performance for large datasets
- **View API Enhancement**: Enhanced view editing capabilities to support changing view types

### API Bug Fixes

- **Lucene Query Parser**: Fixed query parsing issues in Lucene service
- **Authentication Endpoints**: Fixed various authentication-related issues
- **Dossier Service**: Improved dossier service reliability and error handling

### Backend Improvements

- **Datastore Optimization**: Handling deprecation warnings and removing unused code for better performance
- **ETag Module**: Added comprehensive ETag support for better caching mechanisms
- **Service Layer**: Refactored analytic and hit services for improved efficiency
- **Test Coverage**: Enhanced unit and integration test coverage across multiple services

### Infrastructure Updates

- **Docker**: Converted API Docker images to Alpine Linux for reduced image size
- **Dependencies**: Removed netifaces dependency, updated various backend dependencies
- **Documentation**: Added comprehensive API documentation and datastore README

### Database & Storage

- **Collection Management**: Improved collection handling with better shard management
- **Reindexing**: Added robust reindexing functionality with better error handling
- **Data Models**: Enhanced Link model with optional parameters for better flexibility
