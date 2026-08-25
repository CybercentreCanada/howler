"""User model."""

from __future__ import annotations

from howler.common import loader
from howler.config import CLASSIFICATION
from howler.models import (
    HowlerEmbeddedModel,
    HowlerESModel,
    boolean,
    classification,
    compound,
    date,
    email,
    enum,
    integer,
    keyword,
    list_field,
    mapping,
    optional,
    register_model,
)

ACL = {"R", "W", "E", "I"}
DASHBOARD_TYPES = {"view", "analytic"}


@register_model(index=False, store=False, description="Model for API keys", embedded=True)
class ApiKey(HowlerEmbeddedModel):
    """Model for API keys."""

    acl: list_field(enum(values=ACL), description="Access Control List for the API key")
    agents: list_field(
        keyword(), default=[], description="List of user ids permitted to use this api key for impersonation"
    )
    password: keyword(description="BCrypt hash of the password for the apikey")
    expiry_date: optional(date(), description="Expiry date for the apikey")


@register_model(index=False, store=False, description="Model for user dashboard settings", embedded=True)
class DashboardEntry(HowlerEmbeddedModel):
    """Model for user dashboard settings."""

    entry_id: keyword(description="A unique id for this entry")
    type: enum(values=DASHBOARD_TYPES, description="The type of dashboard entry to render.")
    config: keyword(description="A stringified JSON object containing additional configuration data")


@register_model(index=True, store=True, description="Model of User")
class User(HowlerESModel):
    """Model of User."""

    api_quota: integer(default=25, store=False, description="Maximum number of concurrent API requests")
    apikeys: mapping(compound(ApiKey), default={}, index=False, store=False, description="Mapping of API keys")
    classification: classification(
        is_user_classification=True,
        copyto="__text__",
        default=CLASSIFICATION.UNRESTRICTED,
        description="Maximum classification for the user",
    )
    email: optional(email(copyto="__text__"), description="User's email address")
    groups: list_field(
        keyword(), copyto="__text__", default=["USERS"], description="List of groups the user submits to"
    )
    is_active: boolean(default=True, description="Is the user active?")
    name: keyword(copyto="__text__", description="Full name of the user")
    password: keyword(index=False, store=False, description="BCrypt hash of the user's password")
    access_control: optional(keyword(index=False, store=False), description="Access control filter")
    type: list_field(enum(values=loader.USER_TYPES), default=["user", "actionrunner_basic"], description="Type of user")
    uname: keyword(copyto="__text__", description="Username")
    favourite_views: list_field(keyword(), default=[], description="List of favourite views of the user")
    favourite_analytics: list_field(keyword(), default=[], description="List of favourite analytics of the user")
    dashboard: list_field(
        compound(DashboardEntry), default=[], description="A list of dashboard entries to render on the UI."
    )
    refresh_rate: integer(default=15, description="The refresh rate in seconds for the dashboard.")
