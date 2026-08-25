"""ECS threat field set."""

from __future__ import annotations

from howler.models import (
    HowlerEmbeddedModel,
    compound,
    date,
    integer,
    ip,
    keyword,
    list_field,
    optional,
    register_model,
    text,
)
from howler.models.ecs.file import File


@register_model(
    index=True, store=True, description="Information about the subtechnique used by this threat.", embedded=True
)
class Email(HowlerEmbeddedModel):
    """Email indicator information."""

    address: optional(
        keyword(), description="Identifies a threat indicator as an email address (irrespective of direction)."
    )


@register_model(
    index=True, store=True, description="Information about the subtechnique used by this threat.", embedded=True
)
class SubTechnique(HowlerEmbeddedModel):
    """Information about the subtechnique used by this threat."""

    id: optional(keyword(), description="The id of subtechnique used by this threat.")
    name: optional(keyword(), description="Name of the type of subtechnique used by this threat.")
    reference: optional(keyword(), description="The reference url of subtechnique used by this threat.")


@register_model(
    index=True, store=True, description="Information about the technique used by this threat.", embedded=True
)
class Technique(HowlerEmbeddedModel):
    """Information about the technique used by this threat."""

    id: optional(keyword(), description="The id of technique  used by this threat.")
    name: optional(keyword(), description="Name of the type of technique used by this threat.")
    reference: optional(keyword(), description="The reference url of technique used by this threat.")
    subtechnique: optional(
        compound(SubTechnique), description="Information about the subtechnique used by this threat."
    )


@register_model(index=True, store=True, description="Information about the tactic used by this threat.", embedded=True)
class Tactic(HowlerEmbeddedModel):
    """Information about the tactic used by this threat."""

    id: optional(keyword(), description="The id of tactic used by this threat.")
    name: optional(keyword(), description="Name of the type of tactic used by this threat.")
    reference: optional(keyword(), description="The reference url of tactic used by this threat.")


@register_model(
    index=True, store=True, description="Information about the software used by this threat.", embedded=True
)
class Software(HowlerEmbeddedModel):
    """Information about the software used by this threat."""

    alias: optional(
        list_field(keyword()),
        description="The alias(es) of the software for a set of related intrusion activity that are "
        "tracked by a common name in the security community.",
    )
    id: optional(
        keyword(),
        description="The id of the software used by this threat to conduct behavior commonly modeled "
        "using MITRE ATT&CK®.",
    )
    name: optional(
        keyword(),
        description="The name of the software used by this threat to conduct behavior commonly modeled "
        "using MITRE ATT&CK®.",
    )
    platform: optional(
        list_field(keyword()),
        description="The platforms of the software used by this threat to conduct behavior commonly "
        "modeled using MITRE ATT&CK®.",
    )
    reference: optional(
        keyword(),
        description="The reference URL of the software used by this threat to conduct behavior commonly "
        "modeled using MITRE ATT&CK®.",
    )
    type: optional(
        keyword(),
        description="The type of software used by this threat to conduct behavior commonly modeled "
        "using MITRE ATT&CK®.",
    )


@register_model(
    index=True, store=True, description="Information about the group related to this threat.", embedded=True
)
class Group(HowlerEmbeddedModel):
    """Information about the group related to this threat."""

    alias: optional(
        list_field(keyword()),
        description="The alias(es) of the group for a set of related intrusion activity that are tracked by "
        "a common name in the security community.",
    )
    id: optional(
        keyword(),
        description="The id of the group for a set of related intrusion activity that are tracked by a common "
        "name in the security community.",
    )
    name: optional(
        keyword(),
        description="The name of the group for a set of related intrusion activity that are tracked by a common "
        "name in the security community.",
    )
    reference: optional(
        keyword(),
        description="The reference URL of the group for a set of related intrusion activity that are tracked "
        "by a common name in the security community.",
    )


@register_model(index=True, store=True, description="Threat feed information.", embedded=True)
class Feed(HowlerEmbeddedModel):
    """Threat feed information."""

    dashboard_id: optional(
        keyword(),
        description="The saved object ID of the dashboard belonging to the threat feed for "
        "displaying dashboard links to threat feeds in Kibana.",
    )
    description: optional(keyword(), description="Description of the threat feed in a UI friendly format.")
    name: optional(keyword(), description="The name of the threat feed in UI friendly format.")
    reference: optional(keyword(), description="Reference information for the threat feed in a UI friendly format.")


@register_model(
    index=True,
    store=True,
    description="Object containing associated indicators enriching the event.",
    embedded=True,
)
class Indicator(HowlerEmbeddedModel):
    """Object containing associated indicators enriching the event."""

    confidence: optional(
        keyword(),
        description="Identifies the vendor-neutral confidence rating using the None/Low/Medium/High scale defined "
        "in Appendix A of the STIX 2.1 framework. Vendor-specific confidence scales may be added as custom fields.",
    )
    description: optional(text(), description="Describes the type of action conducted by the threat.")
    email: optional(compound(Email))
    file: optional(compound(File))
    provider: optional(keyword(), description="The name of the indicator's provider.")
    reference: optional(keyword(), description="Reference URL linking to additional information about this indicator.")
    scanner_stats: optional(
        integer(), description="Count of AV/EDR vendors that successfully detected malicious file or URL."
    )
    sightings: optional(
        integer(), description="Number of times this indicator was observed conducting threat activity."
    )
    ip: optional(ip(), description="Identifies a threat indicator as an IP address (irrespective of direction).")
    type: optional(keyword(), description="Type of indicator as represented by Cyber Observable in STIX 2.0.")
    first_seen: optional(
        date(), description="The date and time when intelligence source first reported sighting this indicator."
    )
    last_seen: optional(
        date(), description="The date and time when intelligence source last reported sighting this indicator."
    )
    port: optional(integer(), description="Identifies a threat indicator as a port number")


@register_model(index=True, store=True, embedded=True)
class Matched(HowlerEmbeddedModel):
    """Threat matched-indicator information."""

    atomic: optional(
        keyword(),
        description="Identifies the atomic indicator value that matched a extended local envirnment "
        "endpoint or network event",
    )


@register_model(index=True, store=True, description="List of enrichments", embedded=True)
class Enrichments(HowlerEmbeddedModel):
    """List of enrichments marked threats from indicator."""

    indicator: optional(compound(Indicator))
    matched: optional(compound(Matched))


@register_model(
    index=True,
    store=True,
    description="Fields to classify events and alerts according to a threat "
    "taxonomy such as the MITRE ATT&CK® framework.",
    embedded=True,
)
class Threat(HowlerEmbeddedModel):
    """Fields to classify events and alerts according to a threat taxonomy."""

    enrichments: optional(
        list_field(compound(Enrichments)),
        description="List of enrichments marked threats from indicator.",
    )
    feed: optional(compound(Feed), description="Threat feed information.")
    framework: optional(
        keyword(),
        description="Name of the threat framework used to further categorize and classify the tactic and "
        "technique of the reported threat.",
    )
    group: optional(compound(Group), description="Information about the group related to this threat.")
    indicator: optional(compound(Indicator), description="Object containing associated indicators enriching the event.")
    software: optional(compound(Software), description="Information about the software used by this threat.")
    tactic: optional(compound(Tactic), description="Information about the tactic used by this threat.")
    technique: optional(compound(Tactic), description="Information about the technique used by this threat.")
