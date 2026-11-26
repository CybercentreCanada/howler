"""Shared ownership fields for user-manageable objects."""

from __future__ import annotations

from howler.models import keyword


class Ownership:
    """Mixin for documents with an owner and delegated permissions."""

    owner: keyword()
    """The person owning the object."""
    admins: list[keyword()] = []
    """The group administrator for this object."""
    members: list[keyword()] = []
    """The group who can modify the object."""
