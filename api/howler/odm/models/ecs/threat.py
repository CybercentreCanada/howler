from typing import Optional

from howler import odm
from howler.odm.models.ecs.file import File


@odm.model(
    index=True,
    store=True,
    description="Information about the subtechnique used by this threat.",
)
class Email(odm.Model):
    address: Optional[str] = odm.Optional(
        odm.Keyword(),
        description="Identifies a threat indicator as an email address (irrespective of direction).",
    )


@odm.model(
    index=True,
    store=True,
    description="Information about the subtechnique used by this threat.",
)
class SubTechnique(odm.Model):
    id = odm.Optional(odm.Keyword(description="The id of subtechnique used by this threat."))
    name = odm.Optional(odm.Keyword(description="Name of the type of subtechnique used by this threat."))
    reference = odm.Optional(odm.Keyword(description="The reference url of subtechnique used by this threat."))


@odm.model(
    index=True,
    store=True,
    description="Information about the technique used by this threat.",
)
class Technique(odm.Model):
    id = odm.Optional(odm.Keyword(description="The id of technique  used by this threat."))
    name = odm.Optional(odm.Keyword(description="Name of the type of technique used by this threat."))
    reference = odm.Optional(odm.Keyword(description="The reference url of technique used by this threat."))
    subtechnique = odm.Optional(
        odm.Compound(
            SubTechnique,
            description="Information about the subtechnique used by this threat.",
        )
    )


@odm.model(
    index=True,
    store=True,
    description="Information about the tactic used by this threat.",
)
class Tactic(odm.Model):
    id = odm.Optional(odm.Keyword(description="The id of tactic used by this threat."))
    name = odm.Optional(odm.Keyword(description="Name of the type of tactic used by this threat."))
    reference = odm.Optional(odm.Keyword(description="The reference url of tactic used by this threat."))


@odm.model(
    index=True,
    store=True,
    description="Information about the software used by this threat.",
)
class Software(odm.Model):
    alias = odm.Optional(
        odm.List(
            odm.Keyword(),
            description="The alias(es) of the software for a set of related intrusion activity that are "
            "tracked by a common name in the security community.",
        )
    )
    id = odm.Optional(
        odm.Keyword(
            description="The id of the software used by this threat to conduct behavior commonly modeled "
            "using MITRE ATT&CK®."
        )
    )
    name = odm.Optional(
        odm.Keyword(
            description="The name of the software used by this threat to conduct behavior commonly modeled "
            "using MITRE ATT&CK®."
        )
    )
    platform = odm.Optional(
        odm.List(
            odm.Keyword(),
            description="The platforms of the software used by this threat to conduct behavior commonly "
            "modeled using MITRE ATT&CK®.",
        )
    )
    reference = odm.Optional(
        odm.Keyword(
            description="The reference URL of the software used by this threat to conduct behavior commonly "
            "modeled using MITRE ATT&CK®."
        )
    )
    type = odm.Optional(
        odm.Keyword(
            description="The type of software used by this threat to conduct behavior commonly modeled "
            "using MITRE ATT&CK®."
        )
    )


@odm.model(
    index=True,
    store=True,
    description="Information about the group related to this threat.",
)
class Group(odm.Model):
    alias = odm.Optional(
        odm.List(
            odm.Keyword(),
            description="The alias(es) of the group for a set of related intrusion activity that are tracked by "
            "a common name in the security community.",
        )
    )
    id = odm.Optional(
        odm.Keyword(
            description="The id of the group for a set of related intrusion activity that are tracked by a common "
            "name in the security community."
        )
    )
    name = odm.Optional(
        odm.Keyword(
            description="The name of the group for a set of related intrusion activity that are tracked by a common "
            "name in the security community."
        )
    )
    reference = odm.Optional(
        odm.Keyword(
            description="The reference URL of the group for a set of related intrusion activity that are tracked "
            "by a common name in the security community."
        )
    )


@odm.model(index=True, store=True, description="Threat feed information.")
class Feed(odm.Model):
    dashboard_id = odm.Optional(
        odm.Keyword(
            description="The saved object ID of the dashboard belonging to the threat feed for "
            "displaying dashboard links to threat feeds in Kibana."
        )
    )
    description = odm.Optional(odm.Keyword(description="Description of the threat feed in a UI friendly format."))
    name = odm.Optional(odm.Keyword(description="The name of the threat feed in UI friendly format."))
    reference = odm.Optional(
        odm.Keyword(description="Reference information for the threat feed in a UI friendly format.")
    )


@odm.model(
    index=True,
    store=True,
    description="Object containing associated indicators enriching the event.",
)
class Indicator(odm.Model):
    confidence = odm.Optional(
        odm.Keyword(
            description="Identifies the vendor-neutral confidence rating using the None/Low/Medium/High scale defined "
            "in Appendix A of the STIX 2.1 framework. Vendor-specific confidence scales may be added as custom fields."
        )
    )
    description = odm.Optional(odm.Text(description="Describes the type of action conducted by the threat."))
    email: Email = odm.Optional(odm.Compound(Email))
    file: File = odm.Optional(odm.Compound(File))
    provider = odm.Optional(odm.Keyword(description="The name of the indicator’s provider."))
    reference = odm.Optional(
        odm.Keyword(description="Reference URL linking to additional information about this indicator.")
    )
    scanner_stats = odm.Integer(
        description="Count of AV/EDR vendors that successfully detected malicious file or URL.", optional=True
    )

    sightings = odm.Integer(
        description="Number of times this indicator was observed conducting threat activity.", optional=True
    )

    ip: Optional[str] = odm.Optional(
        odm.IP(description="Identifies a threat indicator as an IP address (irrespective of direction).")
    )
    type: Optional[str] = odm.Optional(
        odm.Keyword(description="Type of indicator as represented by Cyber Observable in STIX 2.0.")
    )
    first_seen: Optional[str] = odm.Optional(
        odm.Date(description="The date and time when intelligence source first reported sighting this indicator.")
    )
    last_seen: Optional[str] = odm.Optional(
        odm.Date(description="The date and time when intelligence source last reported sighting this indicator.")
    )
    port: Optional[int] = odm.Integer(description="Identifies a threat indicator as a port number", optional=True)


@odm.model(
    index=True,
    store=True,
)
class Matched(odm.Model):
    atomic: Optional[str] = odm.Optional(
        odm.Keyword(
            description="Identifies the atomic indicator value that matched a extended local envirnment endpoint or network event"  # noqa: E501
        )
    )


@odm.model(
    index=True,
    store=True,
    description="List of enrichments",
)
class Enrichments(odm.Model):
    indicator = odm.Optional(odm.Compound(Indicator))
    matched = odm.Optional(odm.Compound(Matched))


@odm.model(
    index=True,
    store=True,
    description="Fields to classify events and alerts according to a threat "
    "taxonomy such as the MITRE ATT&CK® framework.",
)
class Threat(odm.Model):
    enrichments = odm.Optional(
        odm.List(odm.Compound(Enrichments, description="List of enrichments marked threats from indicator."))
    )
    feed = odm.Optional(odm.Compound(Feed, description="Threat feed information."))
    framework = odm.Optional(
        odm.Keyword(
            description="Name of the threat framework used to further categorize and classify the tactic and "
            "technique of the reported threat."
        )
    )
    group = odm.Optional(odm.Compound(Group, description="Information about the group related to this threat."))
    indicator = odm.Optional(
        odm.Compound(
            Indicator,
            description="Object containing associated indicators enriching the event.",
        )
    )
    software = odm.Optional(odm.Compound(Software, description="Information about the software used by this threat."))
    tactic: Tactic = odm.Optional(odm.Compound(Tactic, description="Information about the tactic used by this threat."))
    technique: Tactic = odm.Optional(
        odm.Compound(
            Tactic,
            description="Information about the technique used by this threat.",
        )
    )
