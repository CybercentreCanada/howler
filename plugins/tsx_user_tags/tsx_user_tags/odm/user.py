"""ODM modification for User model to add tags field."""

import howler.odm as odm
from howler.common.logging import get_logger

from tsx_user_tags.odm.models.user_tags import UserTags

logger = get_logger(__file__)


def modify_odm(target: odm.Model) -> None:
    """Add the tags field to the User ODM model.

    Args:
        target: The User ODM model class to modify.
    """
    logger.info("Adding 'tags' field to User ODM model")

    target.add_namespace(
        "tags",
        odm.Optional(
            odm.Compound(UserTags),
            description="User expertise tags for alert assignment scoring",
        ),
    )
