"""Shared ownership fields for user-manageable objects."""

from __future__ import annotations

from howler.models import Keyword


class Ownership:
    """Mixin for documents with an owner and delegated permissions."""

    owner: Keyword
    """The person owning the object."""
    admins: list[Keyword] = []
    """The group administrator for this object."""
    members: list[Keyword] = []
    """The group who can modify the object."""
