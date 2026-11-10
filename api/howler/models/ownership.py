"""Shared ownership fields for user-manageable objects."""

from __future__ import annotations

from howler.models import keyword, list_field


class Ownership:
    """Mixin for documents with an owner and delegated permissions."""

    owner: keyword(description="The person owning the object.")
    admins: list_field(keyword(), default=[], description="The group administrator for this object.")
    members: list_field(keyword(), default=[], description="The group who can modify the object.")
