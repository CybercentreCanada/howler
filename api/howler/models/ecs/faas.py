"""ECS function-as-a-service (FaaS) field set."""

from __future__ import annotations

from howler.models import Boolean, HowlerEmbeddedModel, Keyword, enum, register_model

TRIGGER_TYPES = ["http", "pubsub", "datasource", "timer", "other"]


@register_model(index=True, store=True, description="Details about the function trigger.", embedded=True)
class Trigger(HowlerEmbeddedModel):
    """Details about the function trigger."""

    request_id: Keyword | None = None
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

    coldstart: Boolean | None = None
    """Boolean value indicating a cold start of a function."""
    execution: Keyword | None = None
    """The execution ID of the current function execution."""
    id: Keyword | None = None
    """The unique identifier of a serverless function."""
    name: Keyword | None = None
    """The name of a serverless function."""
    trigger: Trigger | None = None
    """Details about the function trigger."""
    version: Keyword | None = None
    """The version of a serverless function."""
