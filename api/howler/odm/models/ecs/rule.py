from howler import odm


@odm.model(
    index=True,
    store=True,
    description="Rule fields are used to capture the specifics of any observer or agent "
    "rules that generate alerts or other notable events.",
)
class Rule(odm.Model):
    author = odm.Optional(
        odm.Keyword(
            description="Name, organization, or pseudonym of the author or authors who "
            "created the rule used to generate this event."
        )
    )
    category = odm.Optional(
        odm.Keyword(
            description="A categorization value keyword used by the entity using the "
            "rule for detection of this event."
        )
    )
    description = odm.Optional(odm.Keyword(description="The description of the rule generating the event."))
    id = odm.Optional(
        odm.Keyword(
            description="A rule ID that is unique within the scope of an agent, observer, "
            "or other entity using the rule for detection of this event."
        )
    )
    license = odm.Optional(
        odm.Keyword(
            description="Name of the license under which the rule used to generate this event is made available."
        )
    )
    name = odm.Optional(odm.Keyword(description="The name of the rule or signature generating the event."))
    reference = odm.Optional(
        odm.Keyword(description="Reference URL to additional information about the rule used to generate this event.")
    )
    ruleset = odm.Optional(
        odm.Keyword(
            description="Name of the ruleset, policy, group, or parent category in which the "
            "rule used to generate this event is a member."
        )
    )
    uuid = odm.Optional(
        odm.Keyword(
            description="A rule ID that is unique within the scope of a set or group of agents, observers, "
            "or other entities using the rule for detection of this event."
        )
    )
    version = odm.Optional(odm.Keyword(description="The version / revision of the rule being used for analysis."))
