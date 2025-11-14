# Howler API Codebase Structure

This document outlines the overall structure of the Howler API codebase. The first section denotes development infrastructure - the scripts and files used to test, validate and build the Howler API, before examining the codebase itself.

## Development Infrastructure

- `build_scripts` - scripts used during the development and build phases
  - `check_poetry.sh` - helper script to ensure poetry lockfile and dependency list match
  - `classification.yml` - basic classification file for Howler
  - `coverage_reports.py` - used for printing the code coverage across the codebase during pull requests
  - `generate_classes.py` and `generate_md_docs.py` - used to create generated code and documentation based on the API endpoints and ODMs
  - `keycloak_health.py` - utility script to poll for keycloak in a healthy state during build process
  - `run_tests.py` and `run_wrapped.py` - utility scripts to run tests and other scripts, wrapping the result in a markdown output for the build process
  - `set_version.py` - set the version dynamically for development builds (Why dev builds have an extra tag on them)
  - `type_check.py` - run static type checking on the codebase
- `dev` - contains development docker images
  - `elasticsearch` - used as the backing database for Howler
  - `redis` - used as a temporary cache for Howler
  - `keycloak` - used to test OAuth authentication in Howler
- `test` - all of the unit and integration tests for the Howler API codebase

## Top-Level Files

- **`__init__.py`** - Package initialization
- **`app.py`** - Main Flask application setup and configuration
- **`config.py`** - Application configuration management
- **`error.py`** - Error handling utilities
- **`gunicorn_config.py`** - Gunicorn WSGI server configuration
- **`healthz.py`** - Health check endpoints
- **`patched.py`** - Monkey patching for external libraries via gevent

## Core Folders

- `actions` - contains action plugins for bulk operations on hits:
  - **`add_label.py`**, **`remove_label.py`** - Label management
  - **`add_to_bundle.py`**, **`remove_from_bundle.py`** - Bundle operations
  - **`promote.py`**, **`demote.py`** - Hit promotion/demotion
  - **`change_field.py`**, **`transition.py`** - Field modifications and state transitions
  - **`prioritization.py`** - Priority management
  - **`example_plugin.py`** - Template for custom actions

- `api` - REST API implementation:
  - **`base.py`** - Base API utilities and response functions
  - **`socket.py`** - WebSocket API implementation
  - **`v1`** - Version 1 API endpoints:
    - **`action.py`** - Action management and execution
    - **`analytic.py`** - Analytics management and configuration
    - **`auth.py`** - Authentication and authorization endpoints
    - **`borealis.py`** - Borealis integration endpoints
    - **`configs.py`** - Configuration management
    - **`dossier.py`** - Dossier (case) management
    - **`help.py`** - Help and documentation endpoints
    - **`hit.py`** - Hit management and operations
    - **`notebook.py`** - Notebook management
    - **`overview.py`** - Overview and dashboard data
    - **`search.py`** - Search functionality
    - **`template.py`** - Template management
    - **`tool.py`** - Alternative Hit Ingestion (tool-based endpoint)
    - **`user.py`** - User management
    - **`view.py`** - View management and customization
    - **`utils`** - API utilities:
      - **`etag.py`** - ETag handling for caching

- `common` - shared utilities and helper functions:
  - **`classification.py`** - Security classification handling
  - **`loader.py`** - Configuration and lookup data loading
  - **`net.py`**, **`net_static.py`** - Network utilities
  - **`hexdump.py`**, **`iprange.py`** - Data formatting and IP utilities
  - **`swagger.py`** - API documentation generation
  - **`logging`** - Logging infrastructure

- `datastore` - database abstraction layer:
  - **`howler_store.py`** - Main datastore implementation
  - **`collection.py`** - Database collection management
  - **`operations.py`** - Database operations
  - **`bulk.py`** - Bulk data operations
  - **`migrations/`**, **`support/`** - Database migrations and support utilities

- `external` - external data integration tools:
  - **`generate_mitre.py`** - MITRE ATT&CK framework data generation
  - **`generate_sigma_rules.py`** - Sigma rule processing
  - **`generate_tlds.py`** - Top-level domain data
  - **`reindex_data.py`**, **`wipe_databases.py`** - Database maintenance

- `helper/` - business logic helpers:
  - **`hit.py`** - Hit processing logic
  - **`search.py`** - Search functionality
  - **`oauth.py`**, **`azure.py`** - Authentication helpers
  - **`workflow.py`** - Workflow management
  - **`ws.py`** - WebSocket helpers

- `odm` - object document mapping and data models:
  - **`base.py`** - Base ODM functionality
  - **`helper.py`** - ODM utilities and test data generation
  - **`random_data.py`**, **`randomizer.py`** - Test data generation
  - **`models/`** - Data models including `hit.py` and `howler_data.py`
  - **`sigma/`** - Sigma rule data models

- `services` - business service layer:
  - **`hit_service.py`** - Hit management services
  - **`auth_service.py`**, **`user_service.py`** - Authentication and user management
  - **`analytic_service.py`** - Analytics management
  - **`template_service.py`**, **`overview_service.py`** - UI customization services
  - **`event_service.py`**, **`action_service.py`** - Event and action processing

- `utils` - low-level utilities:
  - **`str_utils.py`** - String manipulation utilities (including `dotdump`)
  - **`path.py`** - Path manipulation utilities
  - **`lucene.py`** - Lucene query processing
  - **`isotime.py`**, **`uid.py`** - Time and ID utilities
  - **`socket_utils.py`** - Socket communication utilities

## Overall Architecture Summary

This is a **layered architecture** for a security alert triage system:

1. **API Layer** (`api/`) - REST and WebSocket endpoints
2. **Service Layer** (`services/`) - Business logic and orchestration
3. **Helper Layer** (`helper/`) - Domain-specific logic
4. **Data Layer** (`odm/`, `datastore/`) - Data models and persistence
5. **Utility Layer** (`utils/`, `common/`) - Cross-cutting concerns

### Other Folders

- **`cronjobs`** - Scheduled tasks (retention, rules processing)
- **`plugins`** - Plugin system configuration
- **`remote`** - Remote system integrations
- **`security`** - Security and authentication utilities
