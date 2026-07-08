# tsx_user_tags

Allow analysts to manage personal tags (portfolio, products, primary_disciplines) for alert assignment.

---

**Module**: tsx-user-tags

**Author**: ts-veerreddys

## Features

- Configurable tag providers per type (static config or analytics datastore)
- `GET /api/v1/tags/all` — Fetch all available tag options
- Extends the User ODM model with a `tags` field via `modify_odm` hook
- Provider-based architecture: `PortfolioProvider`, `ProductProvider`, `DisciplineProvider` ABCs

## Prerequisites

- Howler API with plugin support enabled
- For `analytics` portfolio provider: analytics data populated in the datastore

[API Plugin Docs](https://github.com/CybercentreCanada/howler/blob/develop/docs/api/plugins.md)

---

## Install Plugin

### Configure Howler to load your plugin

`/workspaces/howler/development/devcontainer/config/config.yml`

```yaml
core:
  plugins:
    - tsx_user_tags
```

### Install plugin

```shell
cd /workspaces/howler/api
poetry add --editable ../plugins/tsx_user_tags
```

---

## Plugin Configuration

`/workspaces/howler/development/devcontainer/config/tsx_user_tags.yml`

```yaml
# Provider-based tag configuration

portfolio:
  provider: analytics # or "static" for fixed list
  # items:             # only needed for static provider
  #   group_a: "Group A"

products:
  provider: static
  items:
    crowdstrike: "CrowdStrike"
    elastic: "Elastic"

primary_disciplines:
  provider: static
  items:
    identity: "Identity"
    malware: "Malware"
    network: "Network"
    pivot: "Pivot"
    soc: "SOC"
```

### Provider Types

| Provider    | Description                                                     |
| ----------- | --------------------------------------------------------------- |
| `static`    | Reads from a fixed `items` dictionary in config                 |
| `analytics` | Fetches customer names dynamically from the analytics datastore |

Each tag type (`portfolio`, `products`, `primary_disciplines`) can use a different provider.

## Routes

| Route                        | Method | Description                                                        |
| ---------------------------- | ------ | ------------------------------------------------------------------ |
| `/api/v1/tags/all`           | GET    | Fetch all available tag options (portfolio, products, disciplines) |
| `/api/v1/tags/healthz/ready` | GET    | Returns 200 OK if all services are online/ready                    |
| `/api/v1/tags/healthz/live`  | GET    | Returns 200 OK if plugin is loaded                                 |

## Architecture

This plugin uses an **Abstract Factory** pattern to decouple tag data sources from the
service layer. Each tag type has a dedicated abstract base class (ABC) that defines the
contract, and concrete implementations are selected at startup based on YAML configuration.

### Provider ABCs

Each tag type (`portfolio`, `products`, `primary_disciplines`) has its own ABC in
`providers/base.py`:

```python
class PortfolioProvider(ABC):
    def fetch(self) -> list[dict[str, str]]: ...
    def get_valid_values(self) -> set[str]: ...

class ProductProvider(ABC):
    def fetch(self) -> list[dict[str, str]]: ...
    def get_valid_values(self) -> set[str]: ...

class DisciplineProvider(ABC):
    def fetch(self) -> list[dict[str, str]]: ...
    def get_valid_values(self) -> set[str]: ...
```

Separate ABCs per tag type ensure:

- **Type safety** — You cannot accidentally wire a `ProductProvider` into the portfolio slot.
- **Domain-specific extensions** — Each provider can evolve independently (e.g., caching for analytics, hierarchy for disciplines).
- **Explicit contracts** — Clear interface for new implementations.

### Factory Wiring (config.py)

The `config.py` module acts as the factory, reading the `provider` field from each tag
type's configuration and instantiating the appropriate concrete class:

```python
def _build_portfolio_provider(cfg: PortfolioConfig) -> PortfolioProvider:
    if cfg.provider == "analytics":
        return AnalyticsPortfolioProvider()
    return StaticPortfolioProvider(cfg.items)
```

The `TagService` receives its providers via constructor injection — it has no knowledge
of how providers are built or where data comes from.

### Adding a New Provider

To add a custom data source (e.g., an external API):

1. Create a new file in `providers/` (e.g., `providers/api.py`)
2. Implement the relevant ABC:
   ```python
   class ApiPortfolioProvider(PortfolioProvider):
       def fetch(self) -> list[dict[str, str]]:
           # Call external API
           ...
       def get_valid_values(self) -> set[str]:
           return {item["value"] for item in self.fetch()}
   ```
3. Add the new provider type to `PortfolioConfig.provider` Literal
4. Wire it in `_build_portfolio_provider()` in `config.py`
5. Set `provider: api` in your deployment's `tsx_user_tags.yml`

No changes needed to `TagService`, routes, or ODM.

### File Structure

```
tsx_user_tags/
├── providers/
│   ├── base.py          # ABCs: PortfolioProvider, ProductProvider, DisciplineProvider
│   ├── analytics.py     # AnalyticsPortfolioProvider (from datastore)
│   └── static.py        # Static providers (from config dict)
├── odm/
│   ├── models/
│   │   └── user_tags.py # UserTags model (portfolio, products, primary_disciplines)
│   └── user.py          # modify_odm hook to extend User model
├── routes/
│   ├── tags.py          # GET /all
│   └── healthz.py       # Health check endpoints
├── services.py          # TagService (orchestrates providers)
├── config.py            # Config loading + provider factory wiring
└── manifest.yml         # Plugin manifest
```
