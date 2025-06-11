# mypy: ignore-errors
from datetime import datetime
from typing import Optional

from howler import odm
from howler.common import loader
from howler.config import CLASSIFICATION

ACL = {"R", "W", "E", "I"}

DASHBOARD_TYPES = {"view", "analytic"}


@odm.model(index=False, store=False, description="Model for API keys")
class ApiKey(odm.Model):
    acl: list[str] = odm.List(odm.Enum(values=ACL), description="Access Control List for the API key")
    agents: list[str] = odm.List(
        odm.Keyword(),
        default=[],
        description="List of user ids permitted to use this api key for impersonation",
    )
    password: str = odm.Keyword(description="BCrypt hash of the password for the apikey")
    expiry_date: Optional[datetime] = odm.Optional(odm.Date(description="Expiry date for the apikey"))


@odm.model(index=False, store=False, description="Model for user dashboard settings")
class DashboardEntry(odm.Model):
    entry_id: str = odm.Keyword(description="A unique id for this entry")
    type: str = odm.Enum(DASHBOARD_TYPES, description="The type of dashboard entry to render.")
    config: str = odm.Keyword(description="A stringified JSON object containing additional configuration data")


@odm.model(index=True, store=True, description="Model of User")
class User(odm.Model):
    api_quota = odm.Integer(
        default=25,
        store=False,
        description="Maximum number of concurrent API requests",
    )
    apikeys: dict[str, ApiKey] = odm.Mapping(
        odm.Compound(ApiKey),
        default={},
        index=False,
        store=False,
        description="Mapping of API keys",
    )
    classification = odm.Classification(
        is_user_classification=True,
        copyto="__text__",
        default=CLASSIFICATION.UNRESTRICTED,
        description="Maximum classification for the user",
    )
    email = odm.Optional(odm.Email(copyto="__text__"), description="User's email address")
    groups = odm.List(
        odm.Keyword(),
        copyto="__text__",
        default=["USERS"],
        description="List of groups the user submits to",
    )
    is_active = odm.Boolean(default=True, description="Is the user active?")
    name = odm.Keyword(copyto="__text__", description="Full name of the user")
    password = odm.Keyword(index=False, store=False, description="BCrypt hash of the user's password")
    type = odm.List(
        odm.Enum(values=loader.USER_TYPES),
        default=["user", "automation_basic"],
        description="Type of user",
    )
    uname = odm.Keyword(copyto="__text__", description="Username")
    favourite_views = odm.List(
        odm.Keyword(),
        default=[],
        description="List of favourite views of the user",
    )
    favourite_analytics = odm.List(
        odm.Keyword(),
        default=[],
        description="List of favourite analytics of the user",
    )
    dashboard: list[DashboardEntry] = odm.List(
        odm.Compound(DashboardEntry),
        default=[],
        description="A list of dashboard entries to render on the UI.",
    )
