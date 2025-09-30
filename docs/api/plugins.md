# Howler Plugin Development Guide

This guide explains how to create custom plugins for Howler to extend its functionality with additional routes, actions, ODM modifications, and integrations.

## Plugin Structure

A Howler plugin follows a standardized directory structure similar to the main Howler application:

```text
plugin_name/
├── plugin_name/
│   ├── __init__.py
│   ├── config.py          # Plugin configuration
│   ├── manifest.yml       # Plugin manifest file
│   ├── actions/           # Custom actions (optional)
│   │   └── *.py
│   ├── routes/            # API routes (optional)
│   │   └── *.py
│   └── odm/               # ODM modifications (optional)
│       └── *.py
├── pyproject.toml         # Python package configuration
├── poetry.lock           # Dependency lock file
├── README.md
└── test/                 # Unit tests
    └── *.py
```

## Core Components

### 1. Plugin Configuration (`config.py`)

Every plugin must have a configuration class that inherits from `BasePluginConfig`:

```python
import os
from pathlib import Path
from howler.plugins.config import BasePluginConfig
from pydantic_settings import SettingsConfigDict

APP_NAME = os.environ.get("APP_NAME", "howler")
PLUGIN_NAME = "your_plugin_name"

root_path = Path("/etc") / APP_NAME.replace("-dev", "").replace("-stg", "")

config_locations = [
    Path(__file__).parent / "manifest.yml",
    root_path / "conf" / f"{PLUGIN_NAME}.yml",
    Path(os.environ.get("HWL_CONF_FOLDER", root_path)) / f"{PLUGIN_NAME}.yml",
]

class YourPluginConfig(BasePluginConfig):
    "Your Plugin Configuration Model"

    # Add custom configuration fields here
    # example_setting: str = "default_value"

    model_config = SettingsConfigDict(
        yaml_file=config_locations,
        yaml_file_encoding="utf-8",
        strict=True,
        env_nested_delimiter="__",
        env_prefix=f"{PLUGIN_NAME.upper()}_",
    )

config = YourPluginConfig()
```

### 2. Plugin Manifest (`manifest.yml`)

The manifest file defines what modules your plugin provides:

```yaml
name: your_plugin_name
features:
  feature_flag_1: true
  feature_flag_2: false
modules:
  routes:
    - route_name:api_blueprint_name  # Custom API routes
  operations:
    - action_name                    # Custom actions
  token_functions:
    application_name: true           # Custom token functions
  odm:
    modify_odm:
      hit: true                      # Modify existing ODM models
      user: true
    generation:
      hit: true                      # Custom data generation
```

## Plugin Module Types

### 1. Actions (`actions/`)

Actions are bulk operations that can be performed on hits. Each action file should contain an `execute` function:

```python
from typing import Any
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.odm.models.hit import Hit

logger = get_logger(__file__)

OPERATION_ID = "your_action_name"

def execute(query: str, **kwargs) -> list[dict[str, Any]]:
    """Execute your custom action.

    Args:
        query (str): The query on which to apply this automation.
        **kwargs: Additional parameters

    Returns:
        list[dict[str, Any]]: Report of the action results
    """
    report = []
    ds = datastore()

    hits: list[Hit] = ds.hit.search(query, as_obj=True)["items"]

    for hit in hits:
        try:
            # Perform your action logic here
            result = perform_action_on_hit(hit)

            report.append({
                "hit_id": hit.howler.id,
                "status": "success",
                "result": result
            })
        except Exception as e:
            logger.error(f"Failed to process hit {hit.howler.id}: {e}")
            report.append({
                "hit_id": hit.howler.id,
                "status": "error",
                "error": str(e)
            })

    return report

def perform_action_on_hit(hit: Hit):
    """Your custom logic here"""
    pass
```

### 2. API Routes (`routes/`)

Create custom API endpoints by defining Flask blueprints:

```python
from flask import request
from howler.api import make_subapi_blueprint, ok, bad_request, created
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs

SUB_API = "your_api_name"
your_api = make_subapi_blueprint(SUB_API, api_version=1)
your_api._doc = "Your custom API endpoints"

logger = get_logger(__file__)

@generate_swagger_docs()
@your_api.route("/endpoint", methods=["POST"])
def your_endpoint(**kwargs):
    """Your custom endpoint.

    Variables:
        None

    Arguments:
        None

    Data Block:
        {
            "field": "value"
        }

    Result example:
        {
            "api_response": {
                "result": "success"
            }
        }
    """
    try:
        data = request.get_json()

        # Your endpoint logic here
        result = process_request(data)

        return ok(result)
    except Exception as e:
        logger.error(f"Error in endpoint: {e}")
        return bad_request(f"Error: {str(e)}")

def process_request(data):
    """Your processing logic here"""
    return {"processed": True}
```

### 3. ODM Modifications (`odm/`)

Extend existing ODM models or provide custom data generation:

```python
from typing import TYPE_CHECKING
import howler.odm as odm
from howler.common.logging import get_logger

if TYPE_CHECKING:
    from howler.odm.models.hit import Hit

logger = get_logger(__file__)

def modify_odm(target):
    """Add additional fields to existing ODM models."""
    from your_plugin.odm.models.custom_model import CustomModel

    target.add_namespace(
        "your_namespace",
        odm.Optional(odm.Compound(CustomModel, description="Your custom metadata")),
    )

def generate(hit: "Hit") -> "Hit":
    """Add plugin-specific data during hit generation."""
    from your_plugin.odm.models.custom_model import CustomModel

    # Add your custom data
    hit.your_namespace = CustomModel({
        "custom_field": "example_value"
    })

    return ["your_namespace"], hit
```

### 4. Custom ODM Models (`odm/models/`)

Define custom data models for your plugin:

```python
import howler.odm as odm

@odm.model(index=False, store=False)
class CustomModel(odm.Model):
    """Custom data model for your plugin."""

    custom_field = odm.Optional(odm.Keyword(description="A custom field"))
    another_field = odm.Optional(odm.Integer(description="Another custom field"))

    # Add validation and other model methods as needed
```

## Plugin Registration

### 1. Install Plugin Dependencies

Ensure your plugin's dependencies are compatible with Howler's requirements:

```toml
# pyproject.toml
[tool.poetry.dependencies]
python = "^3.9"
howler-api = {path = "../../api", develop = true}
# Add other dependencies
```

### 2. Configure Howler to Load Your Plugin

Add your plugin to Howler's configuration:

```yaml
# In Howler's main configuration
core:
  plugins:
    - your_plugin_name
```

### 3. Install the Plugin

```bash
# Install in development mode
pip install -e /path/to/your/plugin

# Or install from package
pip install your-plugin-package
```


## Configuring the Plugin

Plugin-specific configuration is handled through separate YAML files in the `/etc/howler/conf/` directory. Each plugin has its own configuration file named `{plugin_name}.yml`.

### Configuration File Location

When deploying howler, plugin configuration is defined in a config file as `/etc/howler/conf/your_plugin_name.yml` in the container:

```yaml
# In /etc/howler/conf/your_plugin_name.yml
setting1: value1
setting2: value2
nested_config:
    option_a: true
    option_b: "example"
```

This configuration gets loaded when the plugin is initialized by howler.

### Example Plugin Configuration

```yaml
# /etc/howler/conf/cccs.yml
scopes:
  scope1: example_scope1
  scope2: example_scope2
  scope3: example_scope3
urls:
  url1: https://example.com
```

### Plugin Configuration Class

Your plugin's `config.py` should define the configuration structure that matches your YAML file:

```python
from howler.plugins.config import BasePluginConfig
from pydantic import BaseModel
from pydantic_settings import SettingsConfigDict

class URLConfig(BaseModel):
    """URL configuration for external services."""
    url1: str

class ScopeConfig(BaseModel):
    """OAuth scope configuration."""
    scope1: str
    scope2: str
    scope3: str

class YourPluginConfig(BasePluginConfig):
    """Your plugin configuration model."""

    urls: URLConfig = URLConfig(
        spellbook="http://localhost:8080/api",
        vault="https://localhost"
    )

    scopes: ScopeConfig = ScopeConfig(
        borealis="default",
        notebook="default",
        spellbook="default"
    )

    model_config = SettingsConfigDict(
        yaml_file=config_locations,
        yaml_file_encoding="utf-8",
        strict=True,
        env_nested_delimiter="__",
        env_prefix=f"{PLUGIN_NAME.upper()}_",
    )
```

### Configuration Priority

Plugin configuration is loaded in the following order (highest to lowest priority):

1. Environment variables (prefixed with `{PLUGIN_NAME}_`)
2. Plugin-specific YAML file (`/etc/howler/conf/{plugin_name}.yml`)
3. Plugin manifest file (`manifest.yml`)
4. Default values in the configuration class

### Environment Variable Override

You can override any configuration value using environment variables:

```bash
# Override the spellbook URL
export YOUR_PLUGIN_NAME_URLS__SPELLBOOK="http://different-server:8080/api"

# Override a scope
export YOUR_PLUGIN_NAME_SCOPES__BOREALIS="custom-scope-id"
```

Note the double underscore (`__`) used to separate nested configuration levels.

## Best Practices

### Error Handling

- Always use try-catch blocks in actions and routes
- Log errors appropriately using Howler's logging system
- Return meaningful error messages to users

### Configuration

- Use environment variables for sensitive data
- Provide sensible defaults in your configuration
- Document all configuration options

### Testing

- Write unit tests for your plugin components
- Test integration with Howler's core functionality
- Use Howler's test utilities and fixtures

### Documentation

- Document your plugin's purpose and functionality
- Provide clear installation and configuration instructions
- Include examples of usage

### Security

- Validate all input data
- Use Howler's authentication and authorization mechanisms
- Follow secure coding practices

## Example Plugins

### Simple Evidence Plugin

The `evidence` plugin demonstrates a minimal plugin that only extends the hit ODM:

```yaml
# evidence/manifest.yml
name: evidence
modules:
  odm:
    modify_odm:
      hit: true
```

### Complex Sentinel Plugin

The `sentinel` plugin demonstrates a full-featured plugin with:

- Custom actions for sending data to Microsoft Sentinel
- API routes for ingesting Sentinel incidents
- ODM modifications for Sentinel metadata
- Custom authentication and token handling

```yaml
# sentinel/manifest.yml
name: sentinel
modules:
  odm:
    modify_odm:
      hit: true
    generation:
      hit: true
  operations:
    - azure_emit_hash
    - send_to_sentinel
    - update_defender_xdr_alert
  routes:
    - ingest:sentinel_api
```

## Troubleshooting

### Plugin Not Loading

- Check that the plugin name in `manifest.yml` matches the directory name
- Verify the plugin is in Python's module path
- Check Howler's logs for import errors

### Configuration Issues

- Ensure configuration files are in the correct locations
- Verify YAML syntax is correct
- Check environment variable naming (use plugin prefix)

### Action/Route Not Available

- Verify the module is listed correctly in `manifest.yml`
- Check for naming conflicts with existing operations/routes
- Ensure the function signatures match expected patterns

For more examples and detailed implementation, refer to the existing plugins in the `plugins/` directory.
