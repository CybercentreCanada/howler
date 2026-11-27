"""ECS threat field set."""

from __future__ import annotations

from howler.models import IP, Date, HowlerEmbeddedModel, Integer, Keyword, Text, register_model
from howler.models.ecs.file import File


@register_model(
    index=True, store=True, description="Information about the subtechnique used by this threat.", embedded=True
)
class Email(HowlerEmbeddedModel):
    """Email indicator information."""

    address: Keyword | None = None
    """Identifies a threat indicator as an email address (irrespective of direction)."""


@register_model(
    index=True, store=True, description="Information about the subtechnique used by this threat.", embedded=True
)
class SubTechnique(HowlerEmbeddedModel):
    """Information about the subtechnique used by this threat."""

    id: Keyword | None = None
    """The id of subtechnique used by this threat."""
    name: Keyword | None = None
    """Name of the type of subtechnique used by this threat."""
    reference: Keyword | None = None
    """The reference url of subtechnique used by this threat."""


@register_model(
    index=True, store=True, description="Information about the technique used by this threat.", embedded=True
)
class Technique(HowlerEmbeddedModel):
    """Information about the technique used by this threat."""

    id: Keyword | None = None
    """The id of technique  used by this threat."""
    name: Keyword | None = None
    """Name of the type of technique used by this threat."""
    reference: Keyword | None = None
    """The reference url of technique used by this threat."""
    subtechnique: SubTechnique | None = None
    """Information about the subtechnique used by this threat."""


@register_model(index=True, store=True, description="Information about the tactic used by this threat.", embedded=True)
class Tactic(HowlerEmbeddedModel):
    """Information about the tactic used by this threat."""

    id: Keyword | None = None
    """The id of tactic used by this threat."""
    name: Keyword | None = None
    """Name of the type of tactic used by this threat."""
    reference: Keyword | None = None
    """The reference url of tactic used by this threat."""


@register_model(
    index=True, store=True, description="Information about the software used by this threat.", embedded=True
)
class Software(HowlerEmbeddedModel):
    """Information about the software used by this threat."""

    alias: list[Keyword] | None = None
    (
        "The alias(es) of the software for a set of related intrusion activity that are tracked by a common name in "
        "the security community."
    )
    id: Keyword | None = None
    """The id of the software used by this threat to conduct behavior commonly modeled using MITRE ATT&CK®."""
    name: Keyword | None = None
    """The name of the software used by this threat to conduct behavior commonly modeled using MITRE ATT&CK®."""
    platform: list[Keyword] | None = None
    """The platforms of the software used by this threat to conduct behavior commonly modeled using MITRE ATT&CK®."""
    reference: Keyword | None = None
    (
        "The reference URL of the software used by this threat to conduct behavior commonly modeled using MITRE "
        "ATT&CK\u00ae."
    )
    type: Keyword | None = None
    """The type of software used by this threat to conduct behavior commonly modeled using MITRE ATT&CK®."""


@register_model(
    index=True, store=True, description="Information about the group related to this threat.", embedded=True
)
class Group(HowlerEmbeddedModel):
    """Information about the group related to this threat."""

    alias: list[Keyword] | None = None
    (
        "The alias(es) of the group for a set of related intrusion activity that are tracked by a common name in the "
        "security community."
    )
    id: Keyword | None = None
    (
        "The id of the group for a set of related intrusion activity that are tracked by a common name in the security "
        "community."
    )
    name: Keyword | None = None
    (
        "The name of the group for a set of related intrusion activity that are tracked by a common name in the "
        "security community."
    )
    reference: Keyword | None = None
    (
        "The reference URL of the group for a set of related intrusion activity that are tracked by a common name in "
        "the security community."
    )


@register_model(index=True, store=True, description="Threat feed information.", embedded=True)
class Feed(HowlerEmbeddedModel):
    """Threat feed information."""

    dashboard_id: Keyword | None = None
    (
        "The saved object ID of the dashboard belonging to the threat feed for displaying dashboard links to threat "
        "feeds in Kibana."
    )
    description: Keyword | None = None
    """Description of the threat feed in a UI friendly format."""
    name: Keyword | None = None
    """The name of the threat feed in UI friendly format."""
    reference: Keyword | None = None
    """Reference information for the threat feed in a UI friendly format."""


@register_model(
    index=True,
    store=True,
    description="Object containing associated indicators enriching the event.",
    embedded=True,
)
class Indicator(HowlerEmbeddedModel):
    """Object containing associated indicators enriching the event."""

    confidence: Keyword | None = None
    (
        "Identifies the vendor-neutral confidence rating using the None/Low/Medium/High scale defined in Appendix A of "
        "the STIX 2.1 framework. Vendor-specific confidence scales may be added as custom fields."
    )
    description: Text | None = None
    """Describes the type of action conducted by the threat."""
    email: Email | None = None
    file: File | None = None
    provider: Keyword | None = None
    """The name of the indicator's provider."""
    reference: Keyword | None = None
    """Reference URL linking to additional information about this indicator."""
    scanner_stats: Integer | None = None
    """Count of AV/EDR vendors that successfully detected malicious file or URL."""
    sightings: Integer | None = None
    """Number of times this indicator was observed conducting threat activity."""
    ip: IP | None = None
    """Identifies a threat indicator as an IP address (irrespective of direction)."""
    type: Keyword | None = None
    """Type of indicator as represented by Cyber Observable in STIX 2.0."""
    first_seen: Date | None = None
    """The date and time when intelligence source first reported sighting this indicator."""
    last_seen: Date | None = None
    """The date and time when intelligence source last reported sighting this indicator."""
    port: Integer | None = None
    """Identifies a threat indicator as a port number"""


@register_model(index=True, store=True, embedded=True)
class Matched(HowlerEmbeddedModel):
    """Threat matched-indicator information."""

    atomic: Keyword | None = None
    """Identifies the atomic indicator value that matched a extended local envirnment endpoint or network event"""


@register_model(index=True, store=True, description="List of enrichments", embedded=True)
class Enrichments(HowlerEmbeddedModel):
    """List of enrichments marked threats from indicator."""

    indicator: Indicator | None = None
    matched: Matched | None = None


@register_model(
    index=True,
    store=True,
    description="Fields to classify events and alerts according to a threat "
    "taxonomy such as the MITRE ATT&CK® framework.",
    embedded=True,
)
class Threat(HowlerEmbeddedModel):
    """Fields to classify events and alerts according to a threat taxonomy."""

    enrichments: list[Enrichments] | None = None
    """List of enrichments marked threats from indicator."""
    feed: Feed | None = None
    """Threat feed information."""
    framework: Keyword | None = None
    (
        "Name of the threat framework used to further categorize and classify the tactic and technique of the reported "
        "threat."
    )
    group: Group | None = None
    """Information about the group related to this threat."""
    indicator: Indicator | None = None
    """Object containing associated indicators enriching the event."""
    software: Software | None = None
    """Information about the software used by this threat."""
    tactic: Tactic | None = None
    """Information about the tactic used by this threat."""
    technique: Tactic | None = None
    """Information about the technique used by this threat."""
