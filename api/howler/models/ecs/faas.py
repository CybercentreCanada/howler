"""ECS function-as-a-service (FaaS) field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, boolean, enum, keyword, register_model

TRIGGER_TYPES = ["http", "pubsub", "datasource", "timer", "other"]


@register_model(index=True, store=True, description="Details about the function trigger.", embedded=True)
class Trigger(HowlerEmbeddedModel):
    """Details about the function trigger."""

    request_id: keyword(optional=True)
    """The ID of the trigger request , message, event, etc."""
    type: enum(values=TRIGGER_TYPES, optional=True)
    """The trigger for the function execution."""


@register_model(
    index=True,
    store=True,
    description="The user fields describe information about the function as a "
    "service (FaaS) that is relevant to the event.",
    embedded=True,
)
class FAAS(HowlerEmbeddedModel):
    """Function-as-a-service (FaaS) fields."""

    coldstart: boolean(optional=True)
    """Boolean value indicating a cold start of a function."""
    execution: keyword(optional=True)
    """The execution ID of the current function execution."""
    id: keyword(optional=True)
    """The unique identifier of a serverless function."""
    name: keyword(optional=True)
    """The name of a serverless function."""
    trigger: Trigger | None = None
    """Details about the function trigger."""
    version: keyword(optional=True)
    """The version of a serverless function."""
