from typing import Any, Optional, Union

from howler.common.exceptions import InvalidDataException
from howler.common.logging import get_logger
from howler.datastore.operations import OdmHelper, OdmUpdateOperation
from howler.helper.workflow import Transition
from howler.odm.models.hit import Hit
from howler.odm.models.howler_data import (
    Assessment,
    AssessmentEscalationMap,
    Escalation,
    HitStatus,
    HitStatusTransition,
    Vote,
)
from howler.odm.models.user import User

odm_helper = OdmHelper(Hit)

logger = get_logger(__name__)


def assess_hit(
    assessment: Optional[str] = None,
    rationale: Optional[str] = None,
    hit: Optional[Union[dict[str, Any], Hit]] = None,
    **kwargs,
) -> list[OdmUpdateOperation]:
    """Update the assessment and esclation of a hit

    Args:
        assessment (Optional[str], optional): The assessment to set the hit to. Defaults to None.
        hit (Optional[dict[str, Any]], optional): The hit to update. Defaults to None.

    Raises:
        InvalidDataException: An invalid assessment was provided

    Returns:
        list[OdmUpdateOperation]: A list of the opperations to run on the hit
    """
    escalation: Optional[str] = None
    if not assessment:
        # In case the assessment is set to empty string
        assessment = None
    else:
        if assessment not in Assessment:
            assessment_list = ", ".join(Assessment)
            raise InvalidDataException(f"Must set assessment to one of {assessment_list}.")

        escalation = AssessmentEscalationMap[assessment]

    if assessment is None and rationale:
        rationale = None

    logger.debug(
        "Updating assessment of %s to %s",
        hit["howler"]["id"] if hit else "unknown",
        assessment,
    )
    logger.debug(
        "Updating escalation of %s to %s",
        hit["howler"]["id"] if hit else "unknown",
        escalation,
    )

    return [
        odm_helper.update("howler.assessment", assessment),
        odm_helper.update("howler.escalation", escalation),
        odm_helper.update("howler.rationale", rationale, silent=True),
    ]


def unassign_hit(
    hit: dict[str, Any],
    user: Optional[User] = None,
    **kwargs,
) -> list[OdmUpdateOperation]:
    """Remove the assignment of a hit

    Args:
        user (Optional[User], optional): The user unassigning the hit. Defaults to None.
        hit (Optional[dict[str, Any]], optional): The hit to unassign the user from. Defaults to None.

    Raises:
        InvalidDataException: The user unassigning the hit doesn't have the hit assigned to them

    Returns:
        list[OdmUpdateOperation]: A list of the operations necessary to update the hit
    """
    if user and hit["howler"]["assignment"] == user.get("uname", user.get("username", None)):
        return [odm_helper.update("howler.assignment", "unassigned")]

    raise InvalidDataException("Cannot release hit that isn't assigned to you.")


def assign_hit(
    transition: Transition,
    user: Optional[User] = None,
    assignee: Optional[str] = None,
    hit: Optional[dict[str, Any]] = None,
    **kwargs,
) -> list[OdmUpdateOperation]:
    """Assign a hit to a user

    Args:
        transition (Transition): The type of transition being used to assign the hit
        user (Optional[User], optional): The user assigning the hit. Defaults to None.
        assignee (Optional[str], optional): The user to assign the hit to. Defaults to None.
        hit (Optional[dict[str, Any]], optional): The hit we are assigning. Defaults to None.

    Raises:
        InvalidDataException: Incorrect parameters were provided

    Returns:
        list[OdmUpdateOperation]: A list of operations to update the hit assignment
    """
    if transition["transition"] == HitStatusTransition.ASSIGN_TO_OTHER:
        if not assignee:
            raise InvalidDataException("Must specify an assignee when assigning to another user.")

        if hit and hit["howler"]["assignment"] == assignee:
            raise InvalidDataException("Must specify an assignee that is different from the current assigned user.")

    if not user and not assignee:
        raise InvalidDataException("Could not assign Hit to user a no 'user_id' was provided")

    return [
        odm_helper.update(
            "howler.assignment",
            assignee or user.get("uname", user.get("username", None)) if user else None,
        )
    ]


def check_ownership(
    hit: dict[str, Any],
    user: Optional[dict[str, Any]] = None,
    **kwargs,
) -> list[OdmUpdateOperation]:
    """Check the ownership of a hit, and throw an exception if it doesnt match

    Args:
        hit (dict[str, Any]): The hit to check
        user (Optional[dict[str, Any]], optional): The user to check for ownership of. Defaults to None.

    Raises:
        InvalidDataException: Raised when the hit assignee doesn't match the user

    Returns:
        list[OdmUpdateOperation]: An empty list
    """
    if user and hit["howler"]["assignment"] != user.get("uname", user.get("username", None)):
        raise InvalidDataException("Cannot use this transition when the hit is not assigned to you.")

    return []


def promote_hit(**kwargs) -> list[OdmUpdateOperation]:
    """Promote a hit to an alert

    Returns:
        list[OdmUpdateOperation]: The update to run to promote
    """
    return [odm_helper.update("howler.escalation", kwargs.get("escalation", Escalation.ALERT))]


def demote_hit(**kwargs) -> list[OdmUpdateOperation]:
    """Demote an alert to a hit

    Returns:
        list[OdmUpdateOperation]: The update to run to demote
    """
    return [odm_helper.update("howler.escalation", kwargs.get("escalation", Escalation.HIT))]


def vote_hit(
    hit: dict[str, Any],
    vote: str,
    email: str,
    user: Optional[dict[str, Any]] = None,
    **kwargs,
) -> list[OdmUpdateOperation]:
    """Add a vote to the given hit

    Args:
        hit (dict[str, Any]): The hit to add the vote to
        vote (str): The type of vote to add
        email (str): The email of the user voting
        user (Optional[dict[str, Any]], optional): The user voting. Defaults to None.

    Raises:
        InvalidDataException: Invalid data was provided

    Returns:
        list[OdmUpdateOperation]: A list of operations to update the hit depending on the vote
    """
    if not email:
        raise InvalidDataException("Could not vote on Hit as no email was provided")

    if vote not in Vote or vote == "" or vote is None:
        raise InvalidDataException(f"vote is not optional. Provide a value from: {', '.join(Vote)}")

    actions = []

    # Check to see if there is an existing vote from this user
    old_vote = (
        "benign"
        if email in hit["howler"]["votes"]["benign"]
        else (
            "obscure"
            if email in hit["howler"]["votes"]["obscure"]
            else "malicious"
            if email in hit["howler"]["votes"]["malicious"]
            else None
        )
    )

    if old_vote:
        logger.debug("removing old vote of %s from %s", old_vote, id)
        actions.append(odm_helper.list_remove(f"howler.votes.{old_vote}", email))

    if not old_vote or old_vote != vote:
        logger.debug("Adding vote of %s to %s", vote, id)
        actions.append(odm_helper.list_add(f"howler.votes.{vote}", email, if_missing=True))

    if user and hit["howler"]["assignment"] == user.get("uname", user.get("username", None)):
        if hit["howler"]["status"] in [
            HitStatus.IN_PROGRESS,
            HitStatus.OPEN,
        ]:
            actions.append(odm_helper.update("howler.assignment", "unassigned"))
            actions.append(odm_helper.update("howler.status", HitStatus.OPEN))
        else:
            raise InvalidDataException("Cannot vote on hit you are assigned to.")

    return actions
