"""User Tags ODM model for storing user expertise tags."""

import howler.odm as odm


@odm.model(index=False, store=False, description="User expertise tags for alert assignment")
class UserTags(odm.Model):
    """Model for user expertise tags.

    Stores portfolio (customer assignments), products (expertise areas),
    and primary disciplines (professional skills) for each user.

    All values are stored as keys that match those returned by
    GET /api/v1/tags/all. The frontend sends these keys when updating
    user tags.
    """

    portfolio: list[str] = odm.List(
        odm.Keyword(),
        default=[],
        description="Customer/organization assignments",
    )
    products: list[str] = odm.List(
        odm.Keyword(),
        default=[],
        description="Products/platforms the user is skilled with",
    )
    primary_disciplines: list[str] = odm.List(
        odm.Keyword(),
        default=[],
        description="Professional disciplines the user specializes in",
    )
