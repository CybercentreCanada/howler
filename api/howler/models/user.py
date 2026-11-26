"""User model."""

from __future__ import annotations

from typing import Annotated

from howler.common import loader
from howler.config import CLASSIFICATION
from howler.models import (
    Boolean,
    Date,
    Email,
    HowlerEmbeddedModel,
    HowlerESModel,
    Integer,
    Keyword,
    UserClassification,
    enum,
    mapping,
    metadata,
    register_model,
)

ACL = {"R", "W", "E", "I"}
DASHBOARD_TYPES = {"view", "analytic", "case", "tasks"}


@register_model(index=False, store=False, description="Model for API keys", embedded=True)
class ApiKey(HowlerEmbeddedModel):
    """Model for API keys."""

    acl: list[enum(values=ACL)]
    """Access Control List for the API key"""
    agents: list[Keyword] = []
    """List of user ids permitted to use this api key for impersonation"""
    password: Keyword
    """BCrypt hash of the password for the apikey"""
    expiry_date: Date | None = None
    """Expiry date for the apikey"""


@register_model(index=False, store=False, description="Model for user dashboard settings", embedded=True)
class DashboardEntry(HowlerEmbeddedModel):
    """Model for user dashboard settings."""

    entry_id: Keyword
    """A unique id for this entry"""
    type: enum(values=DASHBOARD_TYPES)
    """The type of dashboard entry to render."""
    config: Keyword
    """A stringified JSON object containing additional configuration data"""


@register_model(index=True, store=True, description="Model of User")
class User(HowlerESModel):
    """Model of User."""

    api_quota: Annotated[Integer, metadata(store=False)] = 25
    """Maximum number of concurrent API requests"""
    apikeys: mapping(ApiKey, default={}, index=False, store=False)
    """Mapping of API keys"""
    classification: Annotated[UserClassification, metadata(copyto="__text__", default=CLASSIFICATION.UNRESTRICTED)]
    """Maximum classification for the user"""
    email: Annotated[Email | None, metadata(copyto="__text__")] = None
    """User's email address"""
    groups: Annotated[list[Keyword], metadata(copyto="__text__")] = ["USERS"]
    """List of groups the user submits to"""
    is_active: Boolean = True
    """Is the user active?"""
    name: Annotated[Keyword, metadata(copyto="__text__")]
    """Full name of the user"""
    password: Annotated[Keyword, metadata(index=False, store=False)]
    """BCrypt hash of the user's password"""
    access_control: Annotated[Keyword | None, metadata(index=False, store=False)] = None
    """Access control filter"""
    type: list[enum(values=loader.USER_TYPES)] = ["user", "actionrunner_basic"]
    """Type of user"""
    uname: Annotated[Keyword, metadata(copyto="__text__")]
    """Username"""
    favourite_views: list[Keyword] = []
    """List of favourite views of the user"""
    favourite_analytics: list[Keyword] = []
    """List of favourite analytics of the user"""
    dashboard: list[DashboardEntry] = []
    """A list of dashboard entries to render on the UI."""
    refresh_rate: Integer = 15
    """The refresh rate in seconds for the dashboard."""
