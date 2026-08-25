"""ECS rule field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, optional, register_model


@register_model(
    index=True,
    store=True,
    description="Rule fields are used to capture the specifics of any observer or agent "
    "rules that generate alerts or other notable events.",
    embedded=True,
)
class Rule(HowlerEmbeddedModel):
    """Rule fields are used to capture the specifics of any observer or agent rules."""

    author: optional(
        keyword(),
        description="Name, organization, or pseudonym of the author or authors who "
        "created the rule used to generate this event.",
    )
    category: optional(
        keyword(),
        description="A categorization value keyword used by the entity using the rule for detection of this event.",
    )
    description: optional(keyword(), description="The description of the rule generating the event.")
    id: optional(
        keyword(),
        description="A rule ID that is unique within the scope of an agent, observer, "
        "or other entity using the rule for detection of this event.",
    )
    license: optional(
        keyword(),
        description="Name of the license under which the rule used to generate this event is made available.",
    )
    name: optional(keyword(), description="The name of the rule or signature generating the event.")
    reference: optional(
        keyword(), description="Reference URL to additional information about the rule used to generate this event."
    )
    ruleset: optional(
        keyword(),
        description="Name of the ruleset, policy, group, or parent category in which the "
        "rule used to generate this event is a member.",
    )
    uuid: optional(
        keyword(),
        description="A rule ID that is unique within the scope of a set or group of agents, observers, "
        "or other entities using the rule for detection of this event.",
    )
    version: optional(keyword(), description="The version / revision of the rule being used for analysis.")
