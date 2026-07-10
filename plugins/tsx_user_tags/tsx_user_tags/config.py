import os
from pathlib import Path
from typing import Literal

from howler.plugins.config import BasePluginConfig
from pydantic import BaseModel
from pydantic_settings import SettingsConfigDict

from tsx_user_tags.providers.analytics import (
    AnalyticsPortfolioProvider,
    AnalyticsProductProvider,
)
from tsx_user_tags.providers.base import (
    DisciplineProvider,
    PortfolioProvider,
    ProductProvider,
)
from tsx_user_tags.providers.static import (
    StaticDisciplineProvider,
    StaticPortfolioProvider,
    StaticProductProvider,
)
from tsx_user_tags.services import TagService

APP_NAME = os.environ.get("APP_NAME", "howler")
PLUGIN_NAME = "tsx_user_tags"

root_path = Path("/etc") / APP_NAME.replace("-dev", "").replace("-stg", "")

config_locations = [
    Path(__file__).parent / "manifest.yml",
    root_path / "conf" / f"{PLUGIN_NAME}.yml",
    Path(os.environ.get("HWL_CONF_FOLDER", root_path)) / f"{PLUGIN_NAME}.yml",
]


class PortfolioConfig(BaseModel):
    """Configuration for the portfolio tag provider."""

    provider: Literal["static", "analytics"] = "analytics"
    items: dict[str, str] = {}


class ProductConfig(BaseModel):
    """Configuration for the product tag provider."""

    provider: Literal["static", "analytics"] = "static"
    items: dict[str, str] = {}


class DisciplineConfig(BaseModel):
    """Configuration for the discipline tag provider."""

    provider: Literal["static"] = "static"
    items: dict[str, str] = {}


class TSXUserTagsPluginConfig(BasePluginConfig):
    """tsx_user_tags Plugin Configuration Model."""

    portfolio: PortfolioConfig = PortfolioConfig()
    products: ProductConfig = ProductConfig()
    primary_disciplines: DisciplineConfig = DisciplineConfig()

    model_config = SettingsConfigDict(
        yaml_file=config_locations,
        yaml_file_encoding="utf-8",
        strict=True,
        env_nested_delimiter="__",
        env_prefix=f"PLUGIN_{PLUGIN_NAME.upper()}_",
    )


def _build_portfolio_provider(cfg: PortfolioConfig) -> PortfolioProvider:
    """Build the portfolio provider based on config.

    Args:
        cfg: Portfolio configuration.

    Returns:
        Concrete PortfolioProvider instance.
    """
    if cfg.provider == "analytics":
        return AnalyticsPortfolioProvider()
    return StaticPortfolioProvider(cfg.items)


def _build_product_provider(cfg: ProductConfig) -> ProductProvider:
    """Build the product provider based on config.

    Args:
        cfg: Product configuration.

    Returns:
        Concrete ProductProvider instance.
    """
    if cfg.provider == "analytics":
        return AnalyticsProductProvider()
    return StaticProductProvider(cfg.items)


def _build_discipline_provider(cfg: DisciplineConfig) -> DisciplineProvider:
    """Build the discipline provider based on config.

    Args:
        cfg: Discipline configuration.

    Returns:
        Concrete DisciplineProvider instance.
    """
    return StaticDisciplineProvider(cfg.items)


config = TSXUserTagsPluginConfig()

# Build providers from config and initialize the tag service
tag_service = TagService(
    portfolio_provider=_build_portfolio_provider(config.portfolio),
    product_provider=_build_product_provider(config.products),
    discipline_provider=_build_discipline_provider(config.primary_disciplines),
)

# Allow users to modify their own tags via the generic user PUT endpoint
from howler.services import user_service  # noqa: E402

if "tags" not in user_service.ACCOUNT_USER_MODIFIABLE:
    user_service.ACCOUNT_USER_MODIFIABLE.append("tags")
